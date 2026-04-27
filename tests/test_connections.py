"""Tests for the connections module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from pop_quiz.connections import (
    broadcast_all,
    broadcast_to_hosts,
    broadcast_to_participants,
    get_host_state_with_connections,
    host_connections,
    participant_connections,
)
from pop_quiz.models import Question, Quiz
from pop_quiz.state import GameState


def make_quiz() -> Quiz:
    """Create a simple quiz for testing."""
    return Quiz(
        title="Test Quiz",
        questions=[
            Question(text="Q?", choices=["A", "B"], correct_index=0),
        ],
    )


def make_mock_websocket() -> MagicMock:
    """Create a mock WebSocket."""
    ws = MagicMock()
    ws.send_json = AsyncMock()
    return ws


@pytest.fixture(autouse=True)
def clear_connections():
    """Clear connection lists before each test."""
    host_connections.clear()
    participant_connections.clear()
    yield
    host_connections.clear()
    participant_connections.clear()


class TestGetHostStateWithConnections:
    """Tests for get_host_state_with_connections."""

    def test_returns_empty_for_none_state(self) -> None:
        """Should return empty dict when game_state is None."""
        result = get_host_state_with_connections(None)
        assert result == {}

    def test_includes_connection_status(self) -> None:
        """Should include connection status for each participant."""
        state = GameState.create(make_quiz())
        connected_p = state.add_participant()
        disconnected_p = state.add_participant()

        # Mark one as connected
        participant_connections[connected_p.id] = make_mock_websocket()

        result = get_host_state_with_connections(state)

        participants = result["participants"]
        connected = next(p for p in participants if p["id"] == connected_p.id)
        disconnected = next(
            p for p in participants if p["id"] == disconnected_p.id
        )

        assert connected["connected"] is True
        assert disconnected["connected"] is False


@pytest.mark.asyncio
class TestBroadcastToHosts:
    """Tests for broadcast_to_hosts."""

    async def test_broadcasts_to_all_hosts(self) -> None:
        """Should send to all connected hosts."""
        ws1 = make_mock_websocket()
        ws2 = make_mock_websocket()
        host_connections.extend([ws1, ws2])

        state = GameState.create(make_quiz())
        await broadcast_to_hosts(state)

        ws1.send_json.assert_called_once()
        ws2.send_json.assert_called_once()

    async def test_broadcasts_custom_data(self) -> None:
        """Should broadcast custom data if provided."""
        ws = make_mock_websocket()
        host_connections.append(ws)

        custom_data = {"custom": "data"}
        await broadcast_to_hosts(None, data=custom_data)

        ws.send_json.assert_called_with(custom_data)

    async def test_removes_failed_connections(self) -> None:
        """Should remove hosts that fail to receive."""
        good_ws = make_mock_websocket()
        bad_ws = make_mock_websocket()
        bad_ws.send_json = AsyncMock(side_effect=Exception("Connection lost"))

        host_connections.extend([good_ws, bad_ws])

        state = GameState.create(make_quiz())
        await broadcast_to_hosts(state)

        assert good_ws in host_connections
        assert bad_ws not in host_connections

    async def test_handles_no_hosts(self) -> None:
        """Should handle case with no connected hosts."""
        state = GameState.create(make_quiz())
        # Should not raise
        await broadcast_to_hosts(state)


@pytest.mark.asyncio
class TestBroadcastToParticipants:
    """Tests for broadcast_to_participants."""

    async def test_broadcasts_to_all_participants(self) -> None:
        """Should send personalized state to each participant."""
        state = GameState.create(make_quiz())
        p1 = state.add_participant()
        p2 = state.add_participant()

        ws1 = make_mock_websocket()
        ws2 = make_mock_websocket()
        participant_connections[p1.id] = ws1
        participant_connections[p2.id] = ws2

        await broadcast_to_participants(state)

        ws1.send_json.assert_called_once()
        ws2.send_json.assert_called_once()

    async def test_sends_personalized_state(self) -> None:
        """Should send different state to each participant."""
        state = GameState.create(make_quiz())
        p1 = state.add_participant()
        p2 = state.add_participant()
        p1.display_name = "Player One"
        p2.display_name = "Player Two"

        ws1 = make_mock_websocket()
        ws2 = make_mock_websocket()
        participant_connections[p1.id] = ws1
        participant_connections[p2.id] = ws2

        await broadcast_to_participants(state)

        call1 = ws1.send_json.call_args[0][0]
        call2 = ws2.send_json.call_args[0][0]
        assert call1["display_name"] == "Player One"
        assert call2["display_name"] == "Player Two"

    async def test_removes_failed_connections(self) -> None:
        """Should remove participants that fail to receive."""
        state = GameState.create(make_quiz())
        good_p = state.add_participant()
        bad_p = state.add_participant()

        good_ws = make_mock_websocket()
        bad_ws = make_mock_websocket()
        bad_ws.send_json = AsyncMock(side_effect=Exception("Connection lost"))

        participant_connections[good_p.id] = good_ws
        participant_connections[bad_p.id] = bad_ws

        await broadcast_to_participants(state)

        assert good_p.id in participant_connections
        assert bad_p.id not in participant_connections

    async def test_handles_none_state(self) -> None:
        """Should handle None game state."""
        ws = make_mock_websocket()
        participant_connections["p1"] = ws

        await broadcast_to_participants(None)

        ws.send_json.assert_not_called()


@pytest.mark.asyncio
class TestBroadcastAll:
    """Tests for broadcast_all."""

    async def test_broadcasts_to_hosts_and_participants(self) -> None:
        """Should broadcast to both hosts and participants."""
        state = GameState.create(make_quiz())
        p = state.add_participant()

        host_ws = make_mock_websocket()
        participant_ws = make_mock_websocket()
        host_connections.append(host_ws)
        participant_connections[p.id] = participant_ws

        await broadcast_all(state)

        host_ws.send_json.assert_called_once()
        participant_ws.send_json.assert_called_once()

    async def test_handles_none_state(self) -> None:
        """Should handle None game state."""
        host_ws = make_mock_websocket()
        host_connections.append(host_ws)

        await broadcast_all(None)

        host_ws.send_json.assert_not_called()
