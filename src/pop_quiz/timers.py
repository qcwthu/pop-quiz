"""Async timers for quiz game flow."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from pop_quiz.connections import broadcast_all
from pop_quiz.models import QuizPhase

if TYPE_CHECKING:
    from pop_quiz.state import GameState

logger = logging.getLogger(__name__)

COUNTDOWN_DURATION_SECONDS = 3
REVEAL_DURATION_SECONDS = 5

_question_timer_task: asyncio.Task | None = None
_timer_lock = asyncio.Lock()


async def _advance_after_reveal(game_state: GameState) -> None:
    """Common logic to advance game after reveal phase."""
    await asyncio.sleep(REVEAL_DURATION_SECONDS)

    async with game_state._lock:
        if game_state.phase == QuizPhase.REVEAL:
            game_state.next_question()
            should_start_countdown = game_state.phase == QuizPhase.COUNTDOWN
        else:
            should_start_countdown = False

    await broadcast_all(game_state)
    if should_start_countdown:
        asyncio.create_task(_safe_run_countdown(game_state))


async def _safe_run_countdown(game_state: GameState | None) -> None:
    """Wrapper for run_countdown with exception handling."""
    try:
        await run_countdown(game_state)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Error in countdown timer")


async def run_countdown(game_state: GameState | None) -> None:
    """Wait for countdown phase, then transition to question phase."""
    if not game_state or game_state.phase != QuizPhase.COUNTDOWN:
        return

    await asyncio.sleep(COUNTDOWN_DURATION_SECONDS)

    async with game_state._lock:
        if game_state.phase == QuizPhase.COUNTDOWN:
            game_state.start_question()
            should_schedule_timer = True
        else:
            should_schedule_timer = False

    if should_schedule_timer:
        await broadcast_all(game_state)
        await schedule_question_timer(game_state)


async def _run_question_timer(game_state: GameState | None) -> None:
    """Wait for question time limit, then auto-reveal and advance."""
    try:
        if not game_state or game_state.phase != QuizPhase.QUESTION:
            return

        question = game_state.get_current_question()
        if not question:
            return

        await asyncio.sleep(question.time_limit_seconds)

        async with game_state._lock:
            if game_state.phase == QuizPhase.QUESTION:
                game_state.reveal_answer()
                should_advance = True
            else:
                should_advance = False

        if should_advance:
            await broadcast_all(game_state)
            await _advance_after_reveal(game_state)

    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Error in question timer")


async def schedule_question_timer(game_state: GameState | None) -> None:
    """Cancel any existing timer and schedule a new question timer."""
    global _question_timer_task
    async with _timer_lock:
        if _question_timer_task:
            _question_timer_task.cancel()
            # Wait for cancellation to complete to avoid orphaned tasks
            try:
                await _question_timer_task
            except asyncio.CancelledError:
                pass
        _question_timer_task = asyncio.create_task(
            _run_question_timer(game_state)
        )


async def check_all_answered(game_state: GameState | None) -> None:
    """If all participants answered, skip to reveal phase early."""
    global _question_timer_task

    if not game_state or game_state.phase != QuizPhase.QUESTION:
        return

    async with game_state._lock:
        # Guard against empty participants - all() returns True for empty iterator
        if not game_state.participants:
            return

        all_answered = all(
            game_state.current_question in p.answers
            for p in game_state.participants.values()
        )

        if all_answered:
            game_state.reveal_answer()
            should_advance = True
        else:
            should_advance = False

    if should_advance:
        async with _timer_lock:
            if _question_timer_task:
                _question_timer_task.cancel()
                try:
                    await _question_timer_task
                except asyncio.CancelledError:
                    pass

        await broadcast_all(game_state)
        await _advance_after_reveal(game_state)
