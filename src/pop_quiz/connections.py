"""WebSocket connection management and broadcasting."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from fastapi import WebSocket

if TYPE_CHECKING:
    from pop_quiz.state import GameState

logger = logging.getLogger(__name__)

# Timeout for WebSocket send operations to prevent hanging clients from blocking
BROADCAST_TIMEOUT_SECONDS = 5.0

host_connections: list[WebSocket] = []
participant_connections: dict[str, WebSocket] = {}
_connections_lock = asyncio.Lock()


def get_host_state_with_connections(game_state: GameState | None) -> dict:
    """Build host state dict with participant connection status."""
    if not game_state:
        return {}
    state = game_state.get_state_for_host()
    for participant in state.get("participants", []):
        participant["connected"] = participant["id"] in participant_connections
    return state


async def broadcast_to_hosts(
    game_state: GameState | None, data: dict | None = None
) -> None:
    """Send state update to all connected host views."""
    payload = (
        data
        if data is not None
        else get_host_state_with_connections(game_state)
    )
    # Take a snapshot of connections to avoid issues during iteration
    async with _connections_lock:
        connections_snapshot = list(host_connections)

    dead_connections = []
    for websocket in connections_snapshot:
        try:
            await asyncio.wait_for(
                websocket.send_json(payload),
                timeout=BROADCAST_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.warning("Timeout sending to host WebSocket")
            dead_connections.append(websocket)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.debug("Error sending to host WebSocket", exc_info=True)
            dead_connections.append(websocket)

    # Remove dead connections under lock
    if dead_connections:
        async with _connections_lock:
            for ws in dead_connections:
                if ws in host_connections:
                    host_connections.remove(ws)


async def broadcast_to_participants(game_state: GameState | None) -> None:
    """Send personalized state update to all connected participants."""
    if not game_state:
        return

    # Take a snapshot of connections to avoid issues during iteration
    async with _connections_lock:
        connections_snapshot = list(participant_connections.items())

    dead_participants = []
    for participant_id, websocket in connections_snapshot:
        try:
            await asyncio.wait_for(
                websocket.send_json(
                    game_state.get_state_for_participant(participant_id)
                ),
                timeout=BROADCAST_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Timeout sending to participant WebSocket: %s", participant_id
            )
            dead_participants.append(participant_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.debug(
                "Error sending to participant WebSocket: %s",
                participant_id,
                exc_info=True,
            )
            dead_participants.append(participant_id)

    # Remove dead connections under lock
    if dead_participants:
        async with _connections_lock:
            for pid in dead_participants:
                participant_connections.pop(pid, None)


async def broadcast_all(game_state: GameState | None) -> None:
    """Broadcast current state to all host and participant connections."""
    if game_state:
        await broadcast_to_hosts(game_state)
        await broadcast_to_participants(game_state)
