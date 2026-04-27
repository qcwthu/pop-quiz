"""FastAPI server for the quiz application."""

import asyncio
import ipaddress
import logging
import re
from pathlib import Path
from typing import Annotated

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pop_quiz.connections import (
    _connections_lock,
    broadcast_all,
    broadcast_to_hosts,
    get_host_state_with_connections,
    host_connections,
    participant_connections,
)
from pop_quiz.handlers import ParticipantSession, handle_answer, handle_join
from pop_quiz.state import GameState
from pop_quiz.timers import run_countdown

logger = logging.getLogger(__name__)

# Pattern for validating Host header format (hostname:port or hostname)
_HOST_HEADER_PATTERN = re.compile(
    r"^[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)*"
    r"(:\d{1,5})?$"
)
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Pop Quiz")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(STATIC_DIR))


def get_game_state(request: Request) -> GameState:
    """Dependency to get the game state from the app state."""
    if (
        not hasattr(request.app.state, "game")
        or request.app.state.game is None
    ):
        raise HTTPException(503, "Game not initialized")
    return request.app.state.game


def _is_localhost(request: Request) -> bool:
    """Check if request is from localhost using proper IP address parsing."""
    if not request.client:
        return False
    host = request.client.host
    if host == "localhost":
        return True
    try:
        addr = ipaddress.ip_address(host)
        return addr.is_loopback
    except ValueError:
        return False


def _validate_host_header(host_header: str) -> str:
    """Validate and sanitize Host header to prevent injection attacks.

    Returns a safe default if the header is invalid.
    """
    if not host_header or not _HOST_HEADER_PATTERN.match(host_header):
        return "localhost:8000"
    return host_header


@app.get("/", response_class=HTMLResponse)
async def host_dashboard(
    request: Request,
    game_state: Annotated[GameState, Depends(get_game_state)],
) -> HTMLResponse:
    """Host dashboard - only accessible from localhost."""
    if not _is_localhost(request):
        raise HTTPException(
            403, "Host dashboard only accessible from localhost"
        )

    host_header = _validate_host_header(request.headers.get("host", ""))

    return templates.TemplateResponse(
        request,
        "host.html",
        {
            "quiz_title": game_state.quiz.title,
            "quiz_description": game_state.quiz.description,
            "join_url": game_state.get_join_url(host_header),
            "qr_code": game_state.get_qr_code(host_header),
            "pin": game_state.pin,
        },
    )


@app.get("/health")
async def health_check() -> JSONResponse:
    """Health check endpoint for monitoring."""
    return JSONResponse({"status": "ok"})


@app.get("/quiz", response_class=HTMLResponse)
async def participant_view(
    request: Request,
    game_state: Annotated[GameState, Depends(get_game_state)],
    pin: Annotated[str | None, Query()] = None,
) -> HTMLResponse:
    """Participant quiz view."""

    if pin != game_state.pin:
        return templates.TemplateResponse(
            request,
            "join.html",
            {"error": "Invalid PIN" if pin else None},
        )

    return templates.TemplateResponse(
        request,
        "participant.html",
        {
            "quiz_title": game_state.quiz.title,
            "quiz_description": game_state.quiz.description,
        },
    )


def _is_localhost_websocket(websocket: WebSocket) -> bool:
    """Check if WebSocket connection is from localhost."""
    if not websocket.client:
        return False
    host = websocket.client.host
    if host == "localhost":
        return True
    try:
        addr = ipaddress.ip_address(host)
        return addr.is_loopback
    except ValueError:
        return False


@app.websocket("/ws/host")
async def host_websocket(websocket: WebSocket) -> None:
    """WebSocket endpoint for host dashboard."""
    if not _is_localhost_websocket(websocket):
        await websocket.close(code=4003)
        return

    await websocket.accept()
    game_state: GameState | None = None

    try:
        if (
            not hasattr(websocket.app.state, "game")
            or websocket.app.state.game is None
        ):
            await websocket.close(code=4000, reason="Game not initialized")
            return

        game_state = websocket.app.state.game
        async with _connections_lock:
            host_connections.append(websocket)

        await websocket.send_json(get_host_state_with_connections(game_state))

        while True:
            match await websocket.receive_json():
                case {"action": "start"}:
                    async with game_state._lock:
                        started = game_state.start_quiz()
                    if started:
                        await broadcast_all(game_state)
                        asyncio.create_task(run_countdown(game_state))

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("Error in host WebSocket handler")
    finally:
        async with _connections_lock:
            if websocket in host_connections:
                host_connections.remove(websocket)


@app.websocket("/ws/participant")
async def participant_websocket(websocket: WebSocket) -> None:
    """WebSocket endpoint for participants."""
    await websocket.accept()
    session = ParticipantSession(websocket)
    game_state: GameState | None = None

    try:
        if (
            not hasattr(websocket.app.state, "game")
            or websocket.app.state.game is None
        ):
            await websocket.close(code=4000, reason="Game not initialized")
            return

        game_state = websocket.app.state.game

        while True:
            data = await websocket.receive_json()
            match data:
                case {"action": "join", "pin": pin, **rest}:
                    await handle_join(
                        session, game_state, pin, rest.get("participant_id")
                    )

                case {"action": "answer", **rest} if session.participant_id:
                    question_index = rest.get("question_index")
                    choice = rest.get("choice")
                    # Validate required fields are present and are integers
                    if not isinstance(question_index, int) or not isinstance(
                        choice, int
                    ):
                        await websocket.send_json(
                            {"error": "Invalid answer format"}
                        )
                        continue
                    await handle_answer(
                        session,
                        game_state,
                        question_index,
                        choice,
                    )

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("Error in participant WebSocket handler")
    finally:
        if session.participant_id and game_state:
            async with _connections_lock:
                if session.participant_id in participant_connections:
                    del participant_connections[session.participant_id]
            await broadcast_to_hosts(game_state)
