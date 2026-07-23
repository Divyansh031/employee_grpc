#!/bin/bash
# startup.sh - prompts for a DB backend, prepares the environment,
# initializes the DB, and starts the server.
#
# Usage:
#   ./startup.sh

set -e  # exit immediately if any command fails

# --- 0. Ask the user which backend to use ---
echo "Select database backend:"
echo "  1) PostgreSQL"
echo "  2) MongoDB"
read -rp "Enter choice [1-2]: " db_choice

case "$db_choice" in
    1)
        DB_BACKEND="postgres"
        ;;
    2)
        DB_BACKEND="mongo"
        ;;
    *)
        echo "ERROR: Invalid choice '$db_choice'. Please enter 1 or 2."
        exit 1
        ;;
esac
echo "DB_BACKEND: $DB_BACKEND"

# --- 1. Resolve the project root regardless of where this script is called from ---
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"
echo "Project root: $PROJECT_ROOT"

# --- 2. Make sure 'db' (and any other root-level package) is importable ---
export PYTHONPATH="$PROJECT_ROOT"
echo "PYTHONPATH set to: $PYTHONPATH"

# --- 3. Wait for the chosen backend to actually be reachable, and prep it ---
if [ "$DB_BACKEND" = "postgres" ]; then
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

    # Postgres needs an explicit CREATE TABLE step (via SQLAlchemy's create_all)
    echo "Running db.init_db..."
    python3 -m db.init_db

elif [ "$DB_BACKEND" = "mongo" ]; then
    echo "Waiting for MongoDB to accept connections..."
    MAX_ATTEMPTS=15
    attempt=0
    until docker exec employee-mongo mongosh --quiet --eval "db.adminCommand('ping')" > /dev/null 2>&1; do
        attempt=$((attempt + 1))
        if [ "$attempt" -ge "$MAX_ATTEMPTS" ]; then
            echo "ERROR: MongoDB did not become ready after ${MAX_ATTEMPTS} attempts."
            echo "Check 'docker ps' and 'docker compose up -d' output."
            exit 1
        fi
        sleep 1
    done
    echo "MongoDB is ready."
    # No init step needed - MongoDB creates collections automatically on
    # first insert, and our counters collection is created lazily too.
fi

echo "Startup checks complete."

# --- 4. Start the server ---
export DB_BACKEND
echo "Starting server (backend: $DB_BACKEND)..."
exec python3 server/server.py