#!/usr/bin/env bash
set -euo pipefail

# ==============================
# Config (override via env vars)
# ==============================
: "${WORKER_URL:=http://localhost:8087/pubsub/push}"    # e.g., https://ingest-worker-xyz-uc.a.run.app/pubsub/push
: "${BUCKET:=shoki-ai-audio}"
: "${OBJECT:=recording.wav}"
: "${SESSION_ID:=sess-030}"
: "${USER_ID:=user-152}"
: "${USE_ID_TOKEN:=false}"   # set true when hitting Cloud Run with auth
: "${AUDIENCE:=}"            # optional audience for identity token; default WORKER_URL if empty

MODE="${1:-happy}"           # happy | retryable | permanent | duplicate

now_nanos() { date +%s%N; }

b64() {
  # Portable base64 without newlines
  if command -v base64 >/dev/null 2>&1; then
    base64 | tr -d '\n'
  else
    python - <<'PY'
import sys, base64
sys.stdout.write(base64.b64encode(sys.stdin.buffer.read()).decode('ascii'))
PY
  fi
}

auth_header() {
  if [[ "${USE_ID_TOKEN}" == "true" ]]; then
    local aud="${AUDIENCE:-$WORKER_URL}"
    if ! command -v gcloud >/dev/null 2>&1; then
      echo "ERROR: gcloud is required for ID token but not found." >&2
      exit 1
    fi
    local tok
    tok="$(gcloud auth print-identity-token --audiences="${aud}")"
    echo "Authorization: Bearer ${tok}"
  fi
}

make_event_json() {
  local gen="$1" sim="$2" sess="$3"
  if [[ -n "${sim}" ]]; then
    cat <<EOF
{"bucket":"${BUCKET}","name":"${OBJECT}","generation":"${gen}","metadata":{"session_id":"${sess}","user_id":"${USER_ID}","simulate_failure":"${sim}"}}
EOF
  else
    cat <<EOF
{"bucket":"${BUCKET}","name":"${OBJECT}","generation":"${gen}","metadata":{"session_id":"${sess}","user_id":"${USER_ID}"}}
EOF
  fi
}

send_pubsub_push() {
  local msg_id="$1" event_json="$2"
  local data_b64
  data_b64="$(printf '%s' "${event_json}" | b64)"
  local envelope
  envelope=$(printf '{"message":{"messageId":"%s","data":"%s"}}' "${msg_id}" "${data_b64}")

  echo ">>> POST ${WORKER_URL}"
  echo ">>> messageId=${msg_id}"
  echo ">>> event: ${event_json}"
  echo

  local auth
  auth="$(auth_header || true)"

  # shellcheck disable=SC2086
  curl -i -sS -X POST "${WORKER_URL}" \
    -H "Content-Type: application/json" \
    ${auth:+-H "$auth"} \
    -d "${envelope}"

  echo -e "\n"
}

case "${MODE}" in
  happy)
    GEN="$(now_nanos)"
    MSG_ID="m-happy-${GEN}"
    EVENT_JSON="$(make_event_json "${GEN}" "" "${SESSION_ID}")"
    send_pubsub_push "${MSG_ID}" "${EVENT_JSON}"
    ;;

  retryable)
    GEN="$(now_nanos)"
    MSG_ID="m-retry-${GEN}"
    EVENT_JSON="$(make_event_json "${GEN}" "retryable" "sess-retry")"
    send_pubsub_push "${MSG_ID}" "${EVENT_JSON}"
    echo "Note: Expect HTTP 500 from worker (retryable). In production, Pub/Sub would retry."
    ;;

  permanent)
    GEN="$(now_nanos)"
    MSG_ID="m-perm-${GEN}"
    EVENT_JSON="$(make_event_json "${GEN}" "permanent" "sess-perm")"
    send_pubsub_push "${MSG_ID}" "${EVENT_JSON}"
    echo "Note: Expect HTTP 204 but worker marks FAILED_PERMANENT (no retry)."
    ;;

  duplicate)
    # Same generation + session_id sent twice
    GEN="$(now_nanos)"
    SESS="sess-dup-${GEN}"
    MSG_ID1="m-dup-1-${GEN}"
    MSG_ID2="m-dup-2-${GEN}"
    EVENT_JSON="$(make_event_json "${GEN}" "" "${SESS}")"
    echo "First delivery (PROCESSING/DONE path expected):"
    send_pubsub_push "${MSG_ID1}" "${EVENT_JSON}"
    echo "Second delivery (duplicate_skip expected):"
    send_pubsub_push "${MSG_ID2}" "${EVENT_JSON}"
    ;;

  *)
    echo "Usage: $0 [happy|retryable|permanent|duplicate]" >&2
    exit 1
    ;;
esac