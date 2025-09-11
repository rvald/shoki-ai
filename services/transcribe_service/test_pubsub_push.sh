#!/usr/bin/env bash
set -euo pipefail

# ==============================
# Config (override via env vars)
# ==============================
# Orchestrator (optional: start a run to register state)
: "${ORCH_BASE:=http://localhost:8088}"
: "${RUNS_URL:=${ORCH_BASE}/runs}"
: "${ORCH_PUBSUB_URL:=${ORCH_BASE}/events/pubsub}"

# Transcribe service (target for Pub/Sub push simulation)
: "${TRANSCRIBE_BASE:=http://localhost:8089}"
: "${TRANSCRIBE_PUBSUB_URL:=${TRANSCRIBE_BASE}/events/pubsub}"
: "${TASKS_URL:=${TRANSCRIBE_BASE}/tasks/transcribe}"   # optional direct task call for dev

# Workload inputs
: "${BUCKET:=shoki-ai-audio}"
: "${OBJECT:=recording.wav}"
: "${SESSION_ID:=sess-local-001}"
: "${USER_ID:=user-local-001}"
: "${GENERATION:=}"                         # default: auto-generate
: "${LANGUAGE_HINT:=}"                      # e.g., "en"
: "${SIMULATE:=}"                           # "", "retryable-once", "retryable-always", "permanent"
: "${CORRELATION_ID:=local-$(date +%s)}"

# Auth to Cloud Run (set true if hitting deployed URL)
: "${USE_ID_TOKEN:=false}"
: "${AUDIENCE:=}"                           # optional; defaults to the target URL

MODE="${1:-start}"  # start | transcribe-requested

now_nanos() { date +%s%N; }
rfc3339_now() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

b64() {
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
  local url="$1"
  if [[ "${USE_ID_TOKEN}" == "true" ]]; then
    local aud="${AUDIENCE:-$url}"
    if ! command -v gcloud >/dev/null 2>&1; then
      echo "ERROR: gcloud is required for ID token but not found." >&2
      exit 1
    fi
    local tok
    tok="$(gcloud auth print-identity-token --audiences="${aud}")"
    echo "Authorization: Bearer ${tok}"
  fi
}

compute_run_id() {
  # Args: bucket name generation session_id
  local bucket="$1" name="$2" gen="$3" sess="$4"
  python - "$bucket" "$name" "$gen" "$sess" <<'PY'
import sys, hashlib
bucket, name, gen, sess = sys.argv[1:]
raw = f"{bucket}/{name}@{gen}|{sess}".encode("utf-8")
print(hashlib.sha256(raw).hexdigest())
PY
}

post_json() {
  local url="$1" body="$2"
  echo ">>> POST ${url}"
  echo ">>> payload: ${body}"
  echo
  local auth; auth="$(auth_header "${url}" || true)"
  # shellcheck disable=SC2086
  curl -i -sS -X POST "${url}" -H "Content-Type: application/json" ${auth:+-H "$auth"} -d "${body}"
  echo -e "\n"
}

make_runs_body() {
  local bucket="$1" name="$2" gen="$3" corr="$4" sess="$5"
  cat <<EOF
{"bucket":"${bucket}","name":"${name}","generation":"${gen}","correlation_id":"${corr}","session_id":"${sess}"}
EOF
}

make_pubsub_envelope() {
  # Wraps raw event JSON into a Pub/Sub push envelope
  local msg_id="$1" event_json="$2"
  local data_b64
  data_b64="$(printf '%s' "${event_json}" | b64)"
  cat <<EOF
{"message":{"messageId":"${msg_id}","publishTime":"$(rfc3339_now)","data":"${data_b64}"}}
EOF
}

make_transcribe_requested_event() {
  # Matches transcribe service handler expectations
  local run_id="$1" bucket="$2" name="$3" gen="$4" sess="$5" corr="$6" simulate="$7" lang="$8"
  # event_type: transcribe.requested; include optional language_hint and simulate_failure
  cat <<EOF
{
  "version":"1",
  "event_type":"transcribe.requested",
  "run_id":"${run_id}",
  "step":"transcribe",
  "input":{
    "bucket":"${bucket}",
    "name":"${name}",
    "generation":"${gen}"${lang:+, "language_hint":"${lang}"}
  },
  "correlation_id":"${corr}"${simulate:+, "simulate_failure":"${simulate}"},
  "ts":"$(rfc3339_now)"
}
EOF
}

main() {
  local gen="${GENERATION:-$(now_nanos)}"

  case "${MODE}" in
    start)
      # Start a new run via orchestrator (optional)
      local body
      body="$(make_runs_body "${BUCKET}" "${OBJECT}" "${gen}" "${CORRELATION_ID}" "${SESSION_ID}")"
      post_json "${RUNS_URL}" "${body}"
      echo "Next: send a transcribe.requested event to the Transcribe service:"
      echo "  $0 transcribe-requested"
      ;;

    transcribe-requested)
      # Compute run_id exactly as orchestrator does, then simulate Pub/Sub push for transcribe.requested to Transcribe service
      local run_id
      run_id="$(compute_run_id "${BUCKET}" "${OBJECT}" "${gen}" "${SESSION_ID}")"
      local evt env
      evt="$(make_transcribe_requested_event "${run_id}" "${BUCKET}" "${OBJECT}" "${gen}" "${SESSION_ID}" "${CORRELATION_ID}" "${SIMULATE}" "${LANGUAGE_HINT}")"
      env="$(make_pubsub_envelope "m-transcribe-req-${gen}" "${evt}")"
      post_json "${TRANSCRIBE_PUBSUB_URL}" "${env}"
      echo "If Cloud Tasks is configured, the service will process and publish transcribe.completed."
      echo "If running locally without Pub/Sub, ensure the Transcribe service has ORCHESTRATOR_PUBSUB_URL set so it can POST the completed event to the orchestrator."
      ;;

    *)
      echo "Usage: $0 [start|transcribe-requested]" >&2
      exit 1
      ;;
  esac
}

main "$@"