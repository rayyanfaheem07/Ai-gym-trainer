"""
Real-Time AI Gym Trainer — WebSocket Example Client

Demonstrates connecting to the real-time WebSocket streaming endpoint:
1. Registers/Logs in via REST API to obtain a valid JWT access token.
2. Connects to `ws://localhost:8000/api/v1/ws/stream?token=<JWT>`.
3. Sends `start_session`.
4. Streams pose frames in real time and prints analysis results.
5. Sends `ping` and handles `pong`.
6. Sends `stop_session` and retrieves summary metrics.
"""

import asyncio
import json
import logging
import sys
import time

try:
    import httpx
    import websockets
except ImportError:
    print("Please install httpx and websockets: pip install httpx websockets")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/api/v1/ws/stream"


async def get_auth_token(email: str = "athlete@gymtrainer.com", password: str = "StrongPassword123!") -> str:
    """Authenticates or registers a user and returns the JWT access token."""
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        # Try login first
        login_res = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
        if login_res.status_code == 200:
            token = login_res.json()["access_token"]
            logger.info(f"Logged in successfully. User token: {token[:15]}...")
            return token

        # If not found, register
        reg_res = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "full_name": "Demo Athlete"},
        )
        if reg_res.status_code == 201:
            login_res = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
            token = login_res.json()["access_token"]
            logger.info(f"Registered and logged in. User token: {token[:15]}...")
            return token

        raise RuntimeError(f"Authentication failed: {login_res.text}")


def generate_mock_landmarks(knee_angle_deg: float = 175.0) -> list[dict[str, float]]:
    """Generates 33 MediaPipe pose landmarks with knee angle variation."""
    landmarks = []
    for i in range(33):
        landmarks.append({
            "x": 0.5 + 0.01 * (i % 5),
            "y": 0.5 + 0.01 * (i // 5),
            "z": 0.0,
            "visibility": 0.95,
        })
    return landmarks


async def run_client():
    try:
        token = await get_auth_token()
    except Exception as e:
        logger.error(f"Failed to obtain token: {e}")
        return

    uri = f"{WS_URL}?token={token}"
    logger.info(f"Connecting to WebSocket at {WS_URL}...")

    async with websockets.connect(uri) as ws:
        # 1. Receive Connected acknowledgement
        conn_ack = await ws.recv()
        logger.info(f"[Server -> Client] Connected: {conn_ack}")

        # 2. Send Heartbeat Ping
        logger.info("[Client -> Server] Sending ping...")
        await ws.send(json.dumps({"type": "ping"}))
        pong_res = await ws.recv()
        logger.info(f"[Server -> Client] Pong: {pong_res}")

        # 3. Start Exercise Session
        logger.info("[Client -> Server] Starting squat session...")
        await ws.send(json.dumps({"type": "start_session", "exercise": "squat"}))
        start_res = await ws.recv()
        logger.info(f"[Server -> Client] Session started: {start_res}")

        # 4. Stream Pose Frames
        logger.info("Streaming simulated pose frames...")
        for angle in [175.0, 140.0, 90.0, 140.0, 175.0]:
            frame_msg = {
                "type": "pose_frame",
                "timestamp_ms": time.time() * 1000.0,
                "exercise": "squat",
                "landmarks": generate_mock_landmarks(knee_angle_deg=angle),
            }
            await ws.send(json.dumps(frame_msg))
            analysis_res = await ws.recv()
            analysis_data = json.loads(analysis_res)
            logger.info(
                f"[Analysis] Exercise={analysis_data.get('exercise')} | "
                f"Stage={analysis_data.get('stage')} | "
                f"Reps={analysis_data.get('rep_count')} | "
                f"Score={analysis_data.get('form_score')}"
            )
            await asyncio.sleep(0.05)

        # 5. Stop Exercise Session
        logger.info("[Client -> Server] Stopping session...")
        await ws.send(json.dumps({"type": "stop_session", "save_to_db": False}))
        stop_res = await ws.recv()
        logger.info(f"[Server -> Client] Session summary: {stop_res}")


if __name__ == "__main__":
    asyncio.run(run_client())
