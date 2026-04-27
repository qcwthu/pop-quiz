"""WebSocket message handlers for participant actions."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pop_quiz.connections import (
    _connections_lock,
    broadcast_to_hosts,
    participant_connections,
)
from pop_quiz.models import Answer
from pop_quiz.timers import check_all_answered

if TYPE_CHECKING:
    from fastapi import WebSocket

    from pop_quiz.state import GameState

# Rate limiting for PIN attempts: max attempts per time window
_PIN_RATE_LIMIT_MAX_ATTEMPTS = 5
_PIN_RATE_LIMIT_WINDOW_SECONDS = 60.0
_pin_attempts: dict[str, list[float]] = defaultdict(list)
_pin_attempts_lock = asyncio.Lock()


def _get_client_ip(websocket: "WebSocket") -> str:
    """Extract client IP for rate limiting."""
    if websocket.client:
        return websocket.client.host
    return "unknown"


async def _check_rate_limit(client_ip: str) -> bool:
    """Check if client has exceeded PIN attempt rate limit.

    Returns True if the request should be allowed, False if rate limited.
    """
    current_time = time.time()
    async with _pin_attempts_lock:
        # Clean old attempts
        attempts = _pin_attempts[client_ip]
        cutoff = current_time - _PIN_RATE_LIMIT_WINDOW_SECONDS
        _pin_attempts[client_ip] = [t for t in attempts if t > cutoff]

        if len(_pin_attempts[client_ip]) >= _PIN_RATE_LIMIT_MAX_ATTEMPTS:
            return False

        _pin_attempts[client_ip].append(current_time)
        return True


@dataclass
class ParticipantSession:
    """Tracks a participant's WebSocket session state."""

    websocket: WebSocket
    participant_id: str | None = None


async def handle_join(
    session: ParticipantSession,
    game_state: GameState,
    pin: str,
    stored_id: str | None,
) -> None:
    """Handle a participant join request."""
    client_ip = _get_client_ip(session.websocket)

    # Rate limit PIN attempts
    if not await _check_rate_limit(client_ip):
        await session.websocket.send_json(
            {"error": "Too many attempts. Please wait before trying again."}
        )
        return

    if pin != game_state.pin:
        await session.websocket.send_json({"error": "Invalid PIN"})
        return

    async with game_state._lock:
        # Check if participant already exists before adding
        existing = (
            game_state.participants.get(stored_id) if stored_id else None
        )
        participant = game_state.add_participant(stored_id)
        if participant:
            is_reconnect = existing is not None
            response = {
                "joined": True,
                "reconnected": is_reconnect,
                "participant_id": participant.id,
                **game_state.get_state_for_participant(participant.id),
            }
        else:
            response = {"error": "Quiz already started"}

    if participant:
        session.participant_id = participant.id
        async with _connections_lock:
            participant_connections[participant.id] = session.websocket

    await session.websocket.send_json(response)
    if participant:
        await broadcast_to_hosts(game_state)


async def handle_answer(
    session: ParticipantSession,
    game_state: GameState,
    question_index: int,
    choice_index: int,
) -> None:
    """Handle a participant answer submission."""
    if not session.participant_id:
        return

    # Validate input types
    if not isinstance(question_index, int) or not isinstance(
        choice_index, int
    ):
        await session.websocket.send_json({"error": "Invalid answer format"})
        return

    answer = Answer(
        participant_id=session.participant_id,
        question_index=question_index,
        choice_index=choice_index,
    )

    async with game_state._lock:
        success = game_state.submit_answer(answer)
        # Don't leak was_correct - participant learns this during reveal phase
        response = {
            "answer_accepted": success,
            **game_state.get_state_for_participant(session.participant_id),
        }

    await session.websocket.send_json(response)
    await broadcast_to_hosts(game_state)

    if success:
        asyncio.create_task(check_all_answered(game_state))
