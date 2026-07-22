#!/bin/bash
# startup.sh - prepares the environment and initializes the DB.
# Safe to run every time before starting the server; init_db.py's
# create_all() is idempotent (it won't recreate tables that already exist).

set -e  # exit immediately if any command fails

# --- 1. Resolve the project root regardless of where this script is called from ---
# $0 is the path this script was invoked with; dirname gets its folder;
# cd + pwd resolves it to an absolute path even if called via a relative path.
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"
echo "Project root: $PROJECT_ROOT"

# --- 2. Make sure 'db' (and any other root-level package) is importable ---
export PYTHONPATH="$PROJECT_ROOT"
echo "PYTHONPATH set to: $PYTHONPATH"

# --- 3. Make sure Postgres is actually reachable before we try to use it ---
# docker ps starting the container isn't the same moment as Postgres being
# ready to accept connections - there's a brief startup window in between.
echo "Waiting for Postgres to accept connections..."
MAX_ATTEMPTS=15
attempt=0
until docker exec employee-postgres pg_isready -U employee_app -d employee_db > /dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge "$MAX_ATTEMPTS" ]; then
        echo "ERROR: Postgres did not become ready after ${MAX_ATTEMPTS} attempts."
        echo "Check 'docker ps' and 'docker compose up -d' output."
        exit 1
    fi
    sleep 1
done
echo "Postgres is ready."

# --- 4. Create tables if they don't exist yet ---
echo "Running db.init_db..."
python3 -m db.init_db

echo "Startup checks complete."

# --- 5. Start the server ---
# exec replaces this shell process with the server process instead of
# spawning a child - so Ctrl+C, signals, and exit codes behave normally,
# as if you'd run this command directly.
echo "Starting server..."
exec python3 server/server.py