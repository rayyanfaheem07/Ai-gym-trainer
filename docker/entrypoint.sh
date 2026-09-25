#!/bin/sh
set -e

# Wait for database connection if DATABASE_URL contains postgres
if [ -n "$DATABASE_URL" ] && echo "$DATABASE_URL" | grep -q "postgres"; then
    echo "[entrypoint] Waiting for PostgreSQL database to be reachable..."
    RETRIES=30
    until python -c "
import asyncio, os, sys
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

db_url = os.environ.get('DATABASE_URL')
async def check():
    engine = create_async_engine(db_url)
    async with engine.connect() as conn:
        await conn.execute(text('SELECT 1'))
    await engine.dispose()

try:
    asyncio.run(check())
    sys.exit(0)
except Exception:
    sys.exit(1)
" > /dev/null 2>&1 || [ $RETRIES -eq 0 ]; do
        echo "[entrypoint] PostgreSQL is not ready yet - sleeping 1s ($RETRIES retries left)..."
        RETRIES=$((RETRIES - 1))
        sleep 1
    done

    if [ $RETRIES -eq 0 ]; then
        echo "[entrypoint] WARNING: Could not connect to PostgreSQL within timeout."
    else
        echo "[entrypoint] PostgreSQL is ready and accepting connections."
    fi
fi

# Automatically apply Alembic migrations if enabled
if [ "${RUN_MIGRATIONS:-true}" = "true" ] && [ -f "alembic.ini" ]; then
    echo "[entrypoint] Applying database migrations (alembic upgrade head)..."
    alembic upgrade head
    echo "[entrypoint] Database migrations applied successfully."
fi

# Execute the primary container command
exec "$@"

