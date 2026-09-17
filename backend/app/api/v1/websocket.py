import logging

from backend.app.core.database import get_db
from backend.app.services.websocket_service import (
    WebSocketConnectionManager,
    WebSocketSessionTracker,
    connection_manager,
    websocket_service,
)
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
router = APIRouter()

# Aliases for backwards compatibility
ConnectionManager = WebSocketConnectionManager
SessionAnalyzerTracker = WebSocketSessionTracker
manager = connection_manager


@router.websocket("/stream")
async def websocket_stream_endpoint(
    websocket: WebSocket,
    token: str | None = Query(None, description="JWT access token for authentication"),
    db: AsyncSession = Depends(get_db),
):
    """
    Real-Time Authenticated WebSocket streaming endpoint for pose telemetry & form coaching.

    Handshake & Authentication:
      - Requires JWT passed via query string: `ws://host/api/v1/ws/stream?token=<JWT>`
      - Unauthenticated, expired, or invalid tokens are rejected with WebSocket close code 1008.
      - User identity is bound strictly to the validated JWT 'sub' claim.

    Message Lifecycle:
      - Client -> Server: pose_frame, start_session, stop_session, ping, set_exercise, reset
      - Server -> Client: connected, analysis_result, session_started, session_stopped, pong, error
    """
    tracker = await connection_manager.authenticate_and_accept(websocket, token, db=db)
    if tracker is None:
        # Rejected and cleanly closed with code 1008
        return

    try:
        while True:
            data_text = await websocket.receive_text()
            await websocket_service.handle_incoming_message(
                websocket=websocket,
                tracker=tracker,
                raw_text=data_text,
                db=db,
            )
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
        logger.info(f"WebSocket client disconnected cleanly: user={tracker.user_id}")
    except Exception as e:
        logger.error(f"WebSocket unexpected session error: {e}", exc_info=True)
        connection_manager.disconnect(websocket)
