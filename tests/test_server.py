"""Tests for the server module."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from pop_quiz.connections import host_connections, participant_connections
from pop_quiz.models import Question, Quiz
from pop_quiz.server import (
    _is_localhost,
    _is_localhost_websocket,
    _validate_host_header,
    app,
)
from pop_quiz.state import GameState


def make_quiz() -> Quiz:
    """Create a simple quiz for testing."""
    return Quiz(
        title="Test Quiz",
        questions=[
            Question(
                text="What is 1+1?",
                choices=["1", "2", "3", "4"],
                correct_index=1,
                time_limit_seconds=30,
            ),
            Question(
                text="What is 2+2?",
                choices=["2", "3", "4", "5"],
                correct_index=2,
            ),
        ],
    )


@pytest.fixture
def game_state():
    """Create a game state for testing."""
    return GameState.create(make_quiz())


@pytest.fixture
def client(game_state):
    """Create a test client with game state."""
    app.state.game = game_state
    yield TestClient(app)
    # Clean up
    host_connections.clear()
    participant_connections.clear()


class TestValidateHostHeader:
    """Tests for Host header validation."""

    def test_valid_hostname(self) -> None:
        """Should accept valid hostnames."""
        assert _validate_host_header("localhost:8000") == "localhost:8000"
        assert _validate_host_header("example.com") == "example.com"
        assert (
            _validate_host_header("quiz.example.com:3000")
            == "quiz.example.com:3000"
        )

    def test_empty_header(self) -> None:
        """Should return default for empty header."""
        assert _validate_host_header("") == "localhost:8000"

    def test_invalid_header(self) -> None:
        """Should return default for invalid header."""
        assert _validate_host_header("invalid<>header") == "localhost:8000"
        assert _validate_host_header("host/with/slashes") == "localhost:8000"


class TestIsLocalhost:
    """Tests for localhost detection."""

    def test_localhost_string(self) -> None:
        """Should detect 'localhost'."""
        request = MagicMock()
        request.client = MagicMock()
        request.client.host = "localhost"
        assert _is_localhost(request) is True

    def test_ipv4_loopback(self) -> None:
        """Should detect IPv4 loopback."""
        request = MagicMock()
        request.client = MagicMock()
        request.client.host = "127.0.0.1"
        assert _is_localhost(request) is True

    def test_ipv6_loopback(self) -> None:
        """Should detect IPv6 loopback."""
        request = MagicMock()
        request.client = MagicMock()
        request.client.host = "::1"
        assert _is_localhost(request) is True

    def test_external_ip(self) -> None:
        """Should reject external IPs."""
        request = MagicMock()
        request.client = MagicMock()
        request.client.host = "192.168.1.1"
        assert _is_localhost(request) is False

    def test_no_client(self) -> None:
        """Should return False when client is None."""
        request = MagicMock()
        request.client = None
        assert _is_localhost(request) is False


class TestIsLocalhostWebSocket:
    """Tests for WebSocket localhost detection."""

    def test_localhost(self) -> None:
        """Should detect localhost for WebSocket."""
        websocket = MagicMock()
        websocket.client = MagicMock()
        websocket.client.host = "127.0.0.1"
        assert _is_localhost_websocket(websocket) is True

    def test_external(self) -> None:
        """Should reject external for WebSocket."""
        websocket = MagicMock()
        websocket.client = MagicMock()
        websocket.client.host = "10.0.0.1"
        assert _is_localhost_websocket(websocket) is False


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_check(self, client) -> None:
        """Should return OK status."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestHostDashboard:
    """Tests for host dashboard endpoint."""

    def test_requires_localhost(self, client) -> None:
        """Should reject non-localhost requests."""
        # TestClient defaults to 'testclient' as host which is not localhost
        with patch("pop_quiz.server._is_localhost", return_value=False):
            response = client.get("/")
            assert response.status_code == 403

    def test_allows_localhost(self, client) -> None:
        """Should allow localhost requests."""
        with patch("pop_quiz.server._is_localhost", return_value=True):
            response = client.get("/")
            assert response.status_code == 200
            assert "text/html" in response.headers["content-type"]


class TestParticipantView:
    """Tests for participant quiz view."""

    def test_invalid_pin_shows_join(self, client, game_state) -> None:
        """Should show join form with error for invalid PIN."""
        response = client.get("/quiz?pin=000000")
        assert response.status_code == 200
        assert "Invalid PIN" in response.text

    def test_valid_pin_shows_quiz(self, client, game_state) -> None:
        """Should show quiz page with valid PIN."""
        response = client.get(f"/quiz?pin={game_state.pin}")
        assert response.status_code == 200
        assert game_state.quiz.title in response.text

    def test_no_pin_shows_join(self, client) -> None:
        """Should show join form when no PIN provided."""
        response = client.get("/quiz")
        assert response.status_code == 200
        # Should not show error for no PIN
        assert "Invalid PIN" not in response.text


class TestHostWebSocket:
    """Tests for host WebSocket endpoint."""

    def test_rejects_non_localhost(self, client) -> None:
        """Should reject WebSocket from non-localhost."""
        with patch(
            "pop_quiz.server._is_localhost_websocket", return_value=False
        ):
            with pytest.raises(WebSocketDisconnect):
                with client.websocket_connect("/ws/host"):
                    pass

    def test_accepts_localhost(self, client) -> None:
        """Should accept WebSocket from localhost."""
        with patch(
            "pop_quiz.server._is_localhost_websocket", return_value=True
        ):
            with client.websocket_connect("/ws/host") as websocket:
                data = websocket.receive_json()
                assert "phase" in data
                assert "quiz_title" in data


class TestParticipantWebSocket:
    """Tests for participant WebSocket endpoint."""

    def test_join_with_valid_pin(self, client, game_state) -> None:
        """Should allow joining with valid PIN."""
        with client.websocket_connect("/ws/participant") as websocket:
            websocket.send_json(
                {
                    "action": "join",
                    "pin": game_state.pin,
                }
            )
            data = websocket.receive_json()
            assert data["joined"] is True
            assert "participant_id" in data

    def test_join_with_invalid_pin(self, client, game_state) -> None:
        """Should reject joining with invalid PIN."""
        with client.websocket_connect("/ws/participant") as websocket:
            websocket.send_json(
                {
                    "action": "join",
                    "pin": "wrong-pin",
                }
            )
            data = websocket.receive_json()
            assert "error" in data

    def test_submit_answer(self, client, game_state) -> None:
        """Should accept answer submission."""
        # Add participant and start quiz
        p = game_state.add_participant()
        game_state.start_quiz()
        game_state.start_question()

        with client.websocket_connect("/ws/participant") as websocket:
            # Join (reconnect) with existing ID
            websocket.send_json(
                {
                    "action": "join",
                    "pin": game_state.pin,
                    "participant_id": p.id,
                }
            )
            join_data = websocket.receive_json()
            assert join_data["joined"] is True
            assert join_data["reconnected"] is True

            # Submit answer
            websocket.send_json(
                {
                    "action": "answer",
                    "question_index": 0,
                    "choice": 1,
                }
            )
            answer_data = websocket.receive_json()
            assert answer_data["answer_accepted"] is True


class TestGameNotInitialized:
    """Tests for when game is not initialized."""

    def test_host_dashboard_503(self) -> None:
        """Should return 503 when game not initialized."""
        app.state.game = None
        client = TestClient(app)
        with patch("pop_quiz.server._is_localhost", return_value=True):
            response = client.get("/")
            assert response.status_code == 503

    def test_participant_view_503(self) -> None:
        """Should return 503 when game not initialized."""
        app.state.game = None
        client = TestClient(app)
        response = client.get("/quiz?pin=123456")
        assert response.status_code == 503
