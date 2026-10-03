"""
Persistence test script for Phase 17 containerized PostgreSQL.
Verifies that stopping and restarting containers preserves existing database records.
"""
import asyncio
import logging
import subprocess
import sys
import time
import uuid

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("persistence_verify")

BACKEND_URL = "http://localhost:8000"


async def create_test_record():
    unique_id = str(uuid.uuid4())[:8]
    email = f"persist_{unique_id}@example.com"
    password = "PersistPassword123!"

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Register
        reg_resp = await client.post(
            f"{BACKEND_URL}/api/v1/auth/register",
            json={"email": email, "password": password, "full_name": f"Persist User {unique_id}"},
        )
        assert reg_resp.status_code == 201, f"Failed to register test user: {reg_resp.text}"
        user_id = reg_resp.json()["id"]

        # Login
        login_resp = await client.post(
            f"{BACKEND_URL}/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        token = login_resp.json()["access_token"]

        # Create a workout record
        start_resp = await client.post(
            f"{BACKEND_URL}/api/v1/workouts/start",
            headers={"Authorization": f"Bearer {token}"},
            json={"notes": f"Persistence test workout {unique_id}"},
        )
        assert start_resp.status_code == 201, f"Failed to create workout: {start_resp.text}"
        workout_id = start_resp.json()["id"]

    logger.info(f"Created user {user_id} and workout {workout_id}")
    return email, password, user_id, workout_id


async def verify_persisted_record(email, password, user_id, workout_id):
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Login again to test auth persistence
        login_resp = await client.post(
            f"{BACKEND_URL}/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert login_resp.status_code == 200, f"Login failed after restart: {login_resp.text}"
        token = login_resp.json()["access_token"]

        # Fetch workout to test relational data persistence
        workout_resp = await client.get(
            f"{BACKEND_URL}/api/v1/workouts/{workout_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert workout_resp.status_code == 200, f"Workout not found after restart: {workout_resp.text}"
        workout = workout_resp.json()
        assert workout["id"] == workout_id, "Workout ID mismatch"
        assert workout["user_id"] == user_id, "User ID mismatch"

    logger.info(f"Verified persistence: User {user_id} and Workout {workout_id} preserved perfectly!")


def restart_compose():
    logger.info("Stopping Docker Compose services (docker compose stop)...")
    subprocess.run(["docker", "compose", "stop"], check=True)
    logger.info("Services stopped. Now restarting services (docker compose start)...")
    subprocess.run(["docker", "compose", "start"], check=True)
    logger.info("Services started. Waiting 15 seconds for health checks to pass...")
    time.sleep(15)


async def main():
    try:
        email, password, user_id, workout_id = await create_test_record()
        restart_compose()
        await verify_persisted_record(email, password, user_id, workout_id)
        logger.info("PERSISTENCE VERIFICATION PASSED SUCCESSFULLY!")
    except Exception as e:
        logger.error(f"PERSISTENCE TEST FAILED: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
