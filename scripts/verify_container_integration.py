"""
Verification script for Phase 17 containerized integration.
Tests:
1. Backend root health endpoint (/health)
2. Frontend availability (http://localhost:3000)
3. Athlete registration and authentication against PostgreSQL
4. Athlete profile fetch and personalization initialization
5. Real-time WebSocket streaming with pose telemetry
6. AI Coach deterministic fallback when Ollama is unavailable
"""
import asyncio
import json
import logging
import sys
import uuid

import httpx
import websockets

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("container_verify")

BACKEND_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:3000"
WS_URL = "ws://localhost:8000/api/v1/ws/stream"


async def verify_backend_health():
    logger.info("1. Verifying backend /health endpoint...")
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{BACKEND_URL}/health")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        logger.info(f"Health response: {data}")
        assert data["status"] == "ok", f"Expected status 'ok', got {data['status']}"
        assert data["database_connected"] is True, "Database should be connected"
        assert data["environment"] == "production", "Expected production environment"
        logger.info("Backend health check PASSED.")


async def verify_frontend():
    logger.info("2. Verifying frontend HTTP availability...")
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(FRONTEND_URL)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        assert "html" in resp.headers.get("content-type", "").lower()
        logger.info("Frontend availability check PASSED.")


async def verify_auth_and_profile():
    logger.info("3. Verifying athlete registration, login, and profile...")
    unique_id = str(uuid.uuid4())[:8]
    email = f"athlete_{unique_id}@example.com"
    password = "SecurePassword123!"

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Register
        reg_resp = await client.post(
            f"{BACKEND_URL}/api/v1/auth/register",
            json={"email": email, "password": password, "full_name": f"Athlete {unique_id}"},
        )
        assert reg_resp.status_code == 201, f"Registration failed: {reg_resp.text}"
        user_data = reg_resp.json()
        logger.info(f"Registered user: {user_data['email']} (ID: {user_data['id']})")

        # Login
        login_resp = await client.post(
            f"{BACKEND_URL}/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        auth_data = login_resp.json()
        token = auth_data["access_token"]
        assert token, "Missing access token"
        logger.info("Authentication succeeded, token obtained.")

        # Profile
        profile_resp = await client.get(
            f"{BACKEND_URL}/api/v1/profile",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert profile_resp.status_code == 200, f"Profile fetch failed: {profile_resp.text}"
        profile = profile_resp.json()
        logger.info(f"User profile: {profile['fitness_goal']} | {profile['experience_level']}")

    return token, user_data["id"]


async def verify_websocket_stream(token: str):
    logger.info("4. Verifying real-time WebSocket connection and streaming...")
    uri = f"{WS_URL}?token={token}"

    # Sample standard 33 landmark points
    landmarks = [
        {"x": 0.5, "y": 0.5, "z": 0.0, "visibility": 0.99} for _ in range(33)
    ]

    async with websockets.connect(uri) as ws:
        # 0. Initial greeting packet
        init_resp = json.loads(await ws.recv())
        assert init_resp["type"] == "connected", f"Unexpected greeting: {init_resp}"
        logger.info(f"WebSocket initial connection confirmed: {init_resp['status']}")

        # 1. Start Session
        start_msg = {
            "type": "start_session",
            "exercise": "squat",
            "camera_metadata": {"fps": 30, "resolution": "1280x720"},
        }
        await ws.send(json.dumps(start_msg))
        resp = json.loads(await ws.recv())
        assert resp["type"] == "session_started", f"Unexpected start response: {resp}"
        session_id = resp["session_id"]
        logger.info(f"WebSocket session initiated: {session_id}")

        # 2. Stream several pose frames
        for i in range(5):
            frame_msg = {
                "type": "pose_frame",
                "timestamp": float(i) * 0.033,
                "landmarks": landmarks,
            }
            await ws.send(json.dumps(frame_msg))
            resp = json.loads(await ws.recv())
            assert resp["type"] == "analysis_result", f"Unexpected frame response: {resp}"
            await asyncio.sleep(0.02)

        # 3. Stop Session
        stop_msg = {"type": "stop_session"}
        await ws.send(json.dumps(stop_msg))
        resp = json.loads(await ws.recv())
        assert resp["type"] == "session_stopped", f"Unexpected stop response: {resp}"
        logger.info(f"WebSocket session stopped successfully. Summary: {resp['summary']}")
        return session_id


async def verify_coach_fallback(token: str):
    logger.info("5. Verifying AI Coach fallback behavior...")
    async with httpx.AsyncClient(timeout=15.0) as client:
        # 1. Create a workout session
        w_resp = await client.post(
            f"{BACKEND_URL}/api/v1/workouts/start",
            headers={"Authorization": f"Bearer {token}"},
            json={"notes": "Verification workout session for AI coach"},
        )
        assert w_resp.status_code == 201, f"Workout creation failed: {w_resp.text}"
        workout_id = w_resp.json()["id"]
        logger.info(f"Created workout for coach evaluation: {workout_id}")

        # 2. Trigger coach feedback on the workout
        resp = await client.post(
            f"{BACKEND_URL}/api/v1/coach/session/{workout_id}?target_focus=form_improvement",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, f"Coach request failed: {resp.text}"
        coach_data = resp.json()
        logger.info(f"Coach response: {coach_data['summary']}")
        assert "summary" in coach_data
        assert "strengths" in coach_data
        assert "areas_to_improve" in coach_data
        assert len(coach_data["strengths"]) > 0
        logger.info("AI Coach deterministic fallback PASSED.")


async def main():
    try:
        await verify_backend_health()
        await verify_frontend()
        token, _ = await verify_auth_and_profile()
        await verify_websocket_stream(token)
        await verify_coach_fallback(token)
        logger.info("ALL CONTAINER INTEGRATION CHECKS PASSED SUCCESSFULLY!")
    except Exception as e:
        logger.error(f"VERIFICATION FAILED: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
