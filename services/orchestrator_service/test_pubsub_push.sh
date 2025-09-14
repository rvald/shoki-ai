#!/usr/bin/env bash
set -euo pipefail

# ==============================
# Config (override via env vars)
# ==============================
: "${ORCH_BASE:=https://55adbca5a727.ngrok-free.app}"     # e.g., http://localhost:8080 when running uvicorn main:app --reload
: "${RUNS_URL:=${ORCH_BASE}/runs}"
: "${PUBSUB_URL:=${ORCH_BASE}/events/pubsub}"

: "${AUDIO_BUCKET:=shoki-ai-audio}"
: "${PRIVACY_BUCKET:=shoki-ai-privacy-service}"
: "${TRANSCRIBE_BUCKET:=shoki-ai-transcribe-service}"
: "${OBJECT:=recording.wav}"
: "${SESSION_ID:=sess-local-001}"
: "${USER_ID:=user-local-001}"
: "${GENERATION:=}"                         # default: auto-generate
: "${CORRELATION_ID:=local-$(date +%s)}"

MODE="${1:-start}"  # start | transcribe-completed | react-completed

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
  curl -i -sS -X POST "${url}" \
    -H "Content-Type: application/json" \
    -d "${body}"
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

make_transcribe_completed_event() {
  local run_id="$1" bucket="$2" name="$3" gen="$4" sess="$5"
  cat <<EOF
{
  "version":"1",
  "event_type":"transcribe.completed",
  "run_id":"89d421044d0230fe65262d789345f897d98048af5a975811d741ee5a6cda027e",
  "step":"transcribe",
  "input":{"bucket":"${bucket}","name":"${name}","generation":"${gen}","metadata":{"session_id":"${sess}","user_id":"${USER_ID}"}},
  "artifacts":{"transcript_uri":"gs://${bucket}/${name}.${gen}/transcript.json"},
  "ts":"$(rfc3339_now)"
}
EOF
}

make_redact_completed_event() {
  local run_id="$1" bucket="$2" name="$3" gen="$4" sess="$5"
  cat <<EOF
{
  "version":"1",
  "event_type":"redact.completed",
  "run_id":"76ad6af4817e8a2a38f1fe9fa843dc6657d9b0c9c83ec255a71b32f1075cafde",
  "step":"redact",
  "input":{"bucket":"${bucket}","name":"${name}","generation":"${gen}","metadata":{"session_id":"${sess}","user_id":"${USER_ID}"}},
  "artifacts":{"redact_uri":"gs://${bucket}/${name}.${gen}/redacted.json"},
  "ts":"$(rfc3339_now)"
}
EOF
}

main() {
  local gen="${GENERATION:-$(now_nanos)}"
  case "${MODE}" in
    start)
      # Start a new run (or return existing if duplicate)
      local body
      body="$(make_runs_body "${AUDIO_BUCKET}" "${OBJECT}" "${gen}" "${CORRELATION_ID}" "${SESSION_ID}")"
      post_json "${RUNS_URL}" "${body}"
      echo "Tip: to progress the workflow locally, run:"
      echo "  $0 transcribe-completed"
      echo "  $0 react-completed"
      ;;

    transcribe-completed)
      # Compute run_id exactly as orchestrator does, then simulate Pub/Sub push for transcribe.completed
      local run_id
      run_id="$(compute_run_id "${TRANSCRIBE_BUCKET}" "${OBJECT}" "${gen}" "${SESSION_ID}")"
      local evt
      evt="$(make_transcribe_completed_event "${run_id}" "${TRANSCRIBE_BUCKET}" "${OBJECT}" "${gen}" "${SESSION_ID}")"
      local env
      env="$(make_pubsub_envelope "m-transcribe-${gen}" "${evt}")"
      post_json "${PUBSUB_URL}" "${env}"
      ;;

    redact-completed)
      # Simulate Pub/Sub push for react.completed
      local run_id
      run_id="$(compute_run_id "${PRIVACY_BUCKET}" "${OBJECT}" "${gen}" "${SESSION_ID}")"
      local evt
      evt="$(make_redact_completed_event "${run_id}" "${PRIVACY_BUCKET}" "${OBJECT}" "${gen}" "${SESSION_ID}")"
      local env
      env="$(make_pubsub_envelope "m-react-${gen}" "${evt}")"
      post_json "${PUBSUB_URL}" "${env}"
      ;;

    *)
      echo "Usage: $0 [start|transcribe-completed|redact-completed]" >&2
      exit 1
      ;;
  esac
}

main "$@" 