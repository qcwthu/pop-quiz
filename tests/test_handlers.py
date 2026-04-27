"""Tests for the handlers module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from pop_quiz.handlers import ParticipantSession, handle_answer, handle_join
from pop_quiz.models import Question, Quiz
from pop_quiz.state import GameState


def make_quiz() -> Quiz:
    """Create a simple quiz for testing."""
    return Quiz(
        title="Test Quiz",
        questions=[
            Question(
                text="Q1?",
                choices=["A", "B", "C", "D"],
                correct_index=0,
                time_limit_seconds=30,
            ),
            Question(
                text="Q2?",
                choices=["X", "Y", "Z"],
                correct_index=1,
            ),
        ],
    )


def make_mock_websocket() -> MagicMock:
    """Create a mock WebSocket."""
    ws = MagicMock()
    ws.send_json = AsyncMock()
    return ws


class TestParticipantSession:
    """Tests for ParticipantSession."""

    def test_session_creation(self) -> None:
        """Should create session with websocket."""
        ws = make_mock_websocket()
        session = ParticipantSession(websocket=ws)
        assert session.websocket is ws
        assert session.participant_id is None

    def test_session_with_participant_id(self) -> None:
        """Should store participant ID."""
        ws = make_mock_websocket()
        session = ParticipantSession(websocket=ws, participant_id="test-id")
        assert session.participant_id == "test-id"


@pytest.mark.asyncio
class TestHandleJoin:
    """Tests for handle_join function."""

    async def test_join_with_valid_pin(self) -> None:
        """Should successfully join with valid PIN."""
        ws = make_mock_websocket()
        session = ParticipantSession(websocket=ws)
        state = GameState.create(make_quiz())

        await handle_join(session, state, state.pin, None)

        assert session.participant_id is not None
        assert session.participant_id in state.participants
        ws.send_json.assert_called()
        call_data = ws.send_json.call_args[0][0]
        assert call_data["joined"] is True
        assert call_data["reconnected"] is False

    async def test_join_with_invalid_pin(self) -> None:
        """Should reject join with invalid PIN."""
        ws = make_mock_websocket()
        session = ParticipantSession(websocket=ws)
        state = GameState.create(make_quiz())

        await handle_join(session, state, "wrong-pin", None)

        assert session.participant_id is None
        ws.send_json.assert_called_with({"error": "Invalid PIN"})

    async def test_join_with_stored_id_new_participant(self) -> None:
        """Should create participant with server-generated ID (stored ID ignored for new)."""
        ws = make_mock_websocket()
        session = ParticipantSession(websocket=ws)
        state = GameState.create(make_quiz())

        await handle_join(session, state, state.pin, "custom-id")

        # ID should be server-generated, not the client-provided one
        assert session.participant_id is not None
        assert session.participant_id != "custom-id"
        assert session.participant_id in state.participants

    async def test_reconnect_existing_participant(self) -> None:
        """Should reconnect existing participant."""
        ws = make_mock_websocket()
        session = ParticipantSession(websocket=ws)
        state = GameState.create(make_quiz())

        # First join - get server-generated ID
        p = state.add_participant()

        # Reconnect with that ID
        await handle_join(session, state, state.pin, p.id)

        assert session.participant_id == p.id
        call_data = ws.send_json.call_args[0][0]
        assert call_data["joined"] is True
        assert call_data["reconnected"] is True

    async def test_join_after_quiz_started(self) -> None:
        """Should reject new participants after quiz started."""
        ws = make_mock_websocket()
        session = ParticipantSession(websocket=ws)
        state = GameState.create(make_quiz())
        state.add_participant("existing")
        state.start_quiz()

        await handle_join(session, state, state.pin, None)

        assert session.participant_id is None
        ws.send_json.assert_called_with({"error": "Quiz already started"})


@pytest.mark.asyncio
class TestHandleAnswer:
    """Tests for handle_answer function."""

    async def test_submit_answer_success(self) -> None:
        """Should accept valid answer."""
        ws = make_mock_websocket()
        state = GameState.create(make_quiz())
        p = state.add_participant()
        session = ParticipantSession(websocket=ws, participant_id=p.id)
        state.start_quiz()
        state.start_question()

        await handle_answer(session, state, 0, 0)

        ws.send_json.assert_called()
        call_data = ws.send_json.call_args[0][0]
        assert call_data["answer_accepted"] is True

    async def test_submit_correct_answer(self) -> None:
        """Should accept correct answer (was_correct not leaked before reveal)."""
        ws = make_mock_websocket()
        state = GameState.create(make_quiz())
        p = state.add_participant()
        session = ParticipantSession(websocket=ws, participant_id=p.id)
        state.start_quiz()
        state.start_question()

        # Get correct index for shuffled question
        _, correct_idx = state.get_shuffled_question(0)

        await handle_answer(session, state, 0, correct_idx)

        call_data = ws.send_json.call_args[0][0]
        assert call_data["answer_accepted"] is True
        # was_correct should NOT be in response (info leak fix)
        assert "was_correct" not in call_data

    async def test_submit_wrong_answer(self) -> None:
        """Should accept wrong answer (was_correct not leaked before reveal)."""
        ws = make_mock_websocket()
        state = GameState.create(make_quiz())
        p = state.add_participant()
        session = ParticipantSession(websocket=ws, participant_id=p.id)
        state.start_quiz()
        state.start_question()

        # Get wrong index
        _, correct_idx = state.get_shuffled_question(0)
        wrong_idx = (correct_idx + 1) % 4

        await handle_answer(session, state, 0, wrong_idx)

        call_data = ws.send_json.call_args[0][0]
        assert call_data["answer_accepted"] is True
        # was_correct should NOT be in response (info leak fix)
        assert "was_correct" not in call_data

    async def test_submit_answer_no_participant_id(self) -> None:
        """Should ignore answer without participant ID."""
        ws = make_mock_websocket()
        session = ParticipantSession(websocket=ws)  # No participant_id
        state = GameState.create(make_quiz())
        state.add_participant()
        state.start_quiz()
        state.start_question()

        await handle_answer(session, state, 0, 0)

        ws.send_json.assert_not_called()

    async def test_submit_answer_wrong_phase(self) -> None:
        """Should reject answer in wrong phase."""
        ws = make_mock_websocket()
        state = GameState.create(make_quiz())
        p = state.add_participant()
        session = ParticipantSession(websocket=ws, participant_id=p.id)
        state.start_quiz()
        # Don't call start_question - still in COUNTDOWN

        await handle_answer(session, state, 0, 0)

        call_data = ws.send_json.call_args[0][0]
        assert call_data["answer_accepted"] is False
