#!/usr/bin/env bash
# One-command demo: start the stack, send one comment, and wait for the result.
# Pass --rebuild to force a clean rebuild if something's actually broken.
set -e

API=http://localhost:8000

if [ "$1" = "--rebuild" ]; then
  docker-compose down --remove-orphans
  docker-compose up --build -d
elif curl -sf $API/docs > /dev/null 2>&1; then
  echo "Backend already running — skipping rebuild/restart."
else
  # No --build: reuses existing images so the worker doesn't reload the
  # BERT model from a cold container every single demo run.
  docker-compose up -d
fi

echo "Waiting for the API to come up..."
until curl -sf $API/docs > /dev/null 2>&1; do
  sleep 1
done
echo "API ready. Swagger: $API/docs"

# Submit a comment. The API answers immediately with a task ID.
echo "Submitting a comment..."
RESPONSE=$(curl -s -X POST $API/predict \
  -H "Content-Type: application/json" \
  -d '{"text": "I hate you so much"}')
echo "$RESPONSE"

TASK_ID=$(echo "$RESPONSE" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("task_id", ""))')

# A cached answer has no task ID, so there is nothing to wait for.
if [ -n "$TASK_ID" ]; then
  # The worker may still be loading the model, so keep checking until it's done.
  echo "Waiting for the worker to finish $TASK_ID..."
  until curl -sf $API/result/$TASK_ID | grep -q '"completed"'; do
    sleep 1
  done
  curl -s $API/result/$TASK_ID
  echo
fi

docker-compose logs -f
