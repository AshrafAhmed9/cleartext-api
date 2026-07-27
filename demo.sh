#!/usr/bin/env bash
# One-command demo: build + start everything, then open the frontend.
set -e

# Tear down any previous run first so stale containers/networks never hold onto ports.
docker-compose down --remove-orphans > /dev/null 2>&1 || true

docker-compose up --build -d

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
