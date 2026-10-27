#!/usr/bin/env bash
# Demo: shows how ClearText keeps a slow ML model behind a fast API.
# Safe to re-run: every run uses fresh comment text, so nothing is cached yet.
set -e

export API=http://localhost:8000
export RUN=$(date +%s)   # makes each run's comments unique, so nothing starts out cached
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# --- output helpers ----------------------------------------------------------
title()  { printf '\n\033[1;36m%s\033[0m\n' "$1"; }
watch()  { printf '   \033[2mWatch for:\033[0m %s\n\n' "$1"; }
result() { printf '   \033[1;32m-> %s\033[0m\n' "$1"; }
line()   { printf '   %s\n' "$1"; }

# Print JSON on one line, leaving out empty (null) fields.
show() {
  python3 -c 'import json,sys; d=json.load(sys.stdin); print("   " + json.dumps({k:v for k,v in d.items() if v is not None}))'
}
task_id() { echo "$1" | python3 -c 'import json,sys; print(json.load(sys.stdin)["task_id"])'; }

# POST one comment; sets BODY (the JSON reply) and TIME (how long the API took, in ms).
submit() {
  local out
  out=$(curl -s -w '\n%{time_total}' -X POST $API/predict \
    -H "Content-Type: application/json" -d "{\"text\": \"$1\"}")
  BODY=$(echo "$out" | head -n 1)
  TIME=$(awk "BEGIN { printf \"%.0f\", $(echo "$out" | tail -n 1) * 1000 }")
}

# Keep checking /result until the worker has finished the job.
wait_for() {
  until curl -sf $API/result/$1 | grep -q '"completed"'; do sleep 0.5; done
}

batcher_log() { docker-compose logs --no-log-prefix worker 2>/dev/null | grep "Batcher:"; }

# --- start the stack ---------------------------------------------------------
printf '\033[1mClearText: a slow ML model behind a fast API\033[0m\n'
line "Running BERT takes time, and a web server that waits for it stops answering everyone."
line "ClearText answers instantly with a ticket and does the slow work in a separate worker."
line "The next five steps show how that holds up."
echo
line "Starting API, worker, Postgres and Redis (the first run builds images, which takes a few minutes)..."
# --build picks up code changes; unchanged layers come from Docker's cache.
docker-compose up -d --build --remove-orphans > $TMP/docker.log 2>&1 || { cat $TMP/docker.log; exit 1; }
until curl -sf $API/docs > /dev/null 2>&1; do sleep 1; done
line "Warming up the model so the timings below are normal..."
submit "warm-up #$RUN"
wait_for "$(task_id "$BODY")"

TEXT="I hate you so much #$RUN"

# --- 1 -----------------------------------------------------------------------
title "1. The API hands back a ticket instead of making you wait"
watch "the reply is instant. The model has not run yet."
line "POST /predict  {\"text\": \"I hate you so much\"}"
submit "$TEXT"
echo "$BODY" | show
result "Ticket in ${TIME} ms."
TASK=$(task_id "$BODY")

# --- 2 -----------------------------------------------------------------------
title "2. A separate worker process runs the model"
watch "the answer is ready under the same ticket. The worker timed itself."
line "GET /result/<task_id>"
wait_for $TASK
RESULT=$(curl -s $API/result/$TASK)
echo "$RESULT" | show
MODEL_MS=$(echo "$RESULT" | python3 -c 'import json,sys; print(round(json.load(sys.stdin)["processing_time_ms"]))')
result "The model itself took ${MODEL_MS} ms, and the API was never blocked by it."

# --- 3 -----------------------------------------------------------------------
title "3. Asking again is answered from the cache"
watch "cached is true and there is no task_id. The queue and worker are skipped."
line "POST /predict  (same comment)"
submit "$TEXT"
echo "$BODY" | show
result "Answered in ${TIME} ms. The cache key includes the model version, so a new model never reuses old answers."

# --- 4 -----------------------------------------------------------------------
title "4. A burst of 16 comments at once"
watch "all tickets come back almost immediately, and the worker groups the comments."
SEEN=$(batcher_log | wc -l)   # so we only look at log lines from this step
python3 - 16 > $TMP/burst.txt <<'PY'
import json, os, sys, threading, time, urllib.request

API, RUN, N = os.environ["API"], os.environ["RUN"], int(sys.argv[1])

def post(text):
    req = urllib.request.Request(API + "/predict", json.dumps({"text": text}).encode(),
                                 {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req))

ids = [None] * N
def send(i):
    ids[i] = post(f"burst comment {i} #{RUN}")["task_id"]

start = time.time()
threads = [threading.Thread(target=send, args=(i,)) for i in range(N)]
for t in threads: t.start()
for t in threads: t.join()
tickets_ms = round((time.time() - start) * 1000)

for task in ids:
    while json.load(urllib.request.urlopen(f"{API}/result/{task}"))["status"] != "completed":
        time.sleep(0.1)
print(tickets_ms, round(time.time() - start, 1))
PY
read TICKETS_MS ALL_DONE < $TMP/burst.txt
SIZES=$(batcher_log | tail -n +$((SEEN + 1)) | sed 's/.*running \([0-9]*\) .*/\1/' | tr '\n' ' ')
CALLS=$(echo $SIZES | wc -w | tr -d ' ')
line "All 16 tickets issued in ${TICKETS_MS} ms."
line "All 16 answers ready in ${ALL_DONE} s."
line "The worker ran the model ${CALLS} times, not 16. Comments per model call: ${SIZES}"
result "Requests arriving together share one model call, which is much cheaper than one call each."

# --- 5 -----------------------------------------------------------------------
title "5. Overload: the worker stops and the API keeps taking requests"
watch "the queue fills up, then new requests are refused instead of piling up forever."
line "Stopping the worker, then sending 120 comments. The queue limit is 100 waiting jobs."
docker-compose stop worker > /dev/null 2>&1
IDS_FILE=$TMP/ids.txt python3 - 120 > $TMP/flood.txt <<'PY'
import json, os, sys, urllib.error, urllib.request

API, RUN, N = os.environ["API"], os.environ["RUN"], int(sys.argv[1])
accepted, rejected, retry_after, ids = 0, 0, None, []
for i in range(N):
    req = urllib.request.Request(API + "/predict", json.dumps({"text": f"flood comment {i} #{RUN}"}).encode(),
                                 {"Content-Type": "application/json"})
    try:
        ids.append(json.load(urllib.request.urlopen(req))["task_id"])
        accepted += 1
    except urllib.error.HTTPError as e:
        if e.code != 503:
            raise
        rejected += 1
        retry_after = e.headers.get("Retry-After")
print(accepted, rejected, retry_after)
open(os.environ["IDS_FILE"], "w").write("\n".join(ids))
PY
read ACCEPTED REJECTED RETRY < $TMP/flood.txt
line "Accepted and queued: ${ACCEPTED}"
line "Refused with HTTP 503 and Retry-After: ${RETRY}s: ${REJECTED}"
result "The circuit breaker turned new work away once the line was too long."
echo
line "Starting the worker again. The ${ACCEPTED} queued jobs should all still be there."
docker-compose start worker > /dev/null 2>&1
START=$SECONDS
while read -r id; do wait_for "$id"; done < $TMP/ids.txt
result "All ${ACCEPTED} queued jobs completed $(( SECONDS - START ))s after the worker came back. Nothing was lost."

# --- wrap-up -----------------------------------------------------------------
title "Summary"
line "Ticket first, work later     the API replied in milliseconds while BERT ran elsewhere"
line "Cache                        repeat comments skip the model entirely"
line "Batching                     requests arriving together share one model call"
line "Circuit breaker              a full queue gets a 503 and Retry-After instead of growing"
line "Dead-letter queue            a job that fails 3 retries is saved for replay (GET /dlq, POST /dlq/<id>/replay)"
echo
line "Explore it yourself: $API/docs"
