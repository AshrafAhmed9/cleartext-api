#!/usr/bin/env bash
# One-command demo: start everything (reusing what's already running/built), open the frontend.
# Pass --rebuild to force a clean rebuild if something's actually broken.
set -e

if [ "$1" = "--rebuild" ]; then
  docker-compose down --remove-orphans
  docker-compose up --build -d
elif curl -sf http://localhost:8000/health > /dev/null 2>&1; then
  echo "Backend already running — skipping rebuild/restart."
else
  # No --build: reuses existing images so the worker doesn't reload the
  # BERT model from a cold container every single demo run.
  docker-compose up -d
fi

echo "Waiting for the API to come up..."
until curl -sf http://localhost:8000/health > /dev/null 2>&1; do
  sleep 1
done

echo "API ready."
echo "Swagger:   http://localhost:8000/docs"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/frontend"

if [ ! -d node_modules ]; then
  echo "Installing frontend dependencies (first run only)..."
  npm install
fi

echo "Starting frontend..."
npm run dev &
FRONTEND_PID=$!

cleanup() {
  kill "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT

sleep 2
echo "Frontend:  http://localhost:5173"
open http://localhost:5173 2>/dev/null || true

cd "$SCRIPT_DIR"
docker-compose logs -f
