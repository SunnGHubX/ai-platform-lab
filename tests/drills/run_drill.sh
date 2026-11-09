#!/usr/bin/env bash
# Stand up the e2e platform on kind, run one break-fix drill, tear down.
#   ./tests/drills/run_drill.sh oom
#   KEEP_CLUSTER=true ./tests/drills/run_drill.sh netpol-dns --no-reveal    # practise, then poke around
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
SCENARIO="${1:?usage: run_drill.sh <scenario> [--no-reveal]}"; shift || true
EXTRA=("$@")
export CLUSTER="${CLUSTER:-sunn-drill}"
BUNDLE="${BUNDLE_DIR:-/tmp/drill-bundle-$SCENARIO}"
PIDS=()

cleanup() {
  rc=$?
  for pid in "${PIDS[@]:-}"; do
    if [ -n "$pid" ]; then pkill -P "$pid" 2>/dev/null || true; kill "$pid" 2>/dev/null || true; fi
  done
  [ "${KEEP_CLUSTER:-false}" = "true" ] || kind delete cluster --name "$CLUSTER" >/dev/null 2>&1 || true
  exit $rc
}
trap cleanup EXIT

# Platform up, smoke tests skipped, cluster kept for the drill.
E2E_SKIP_TESTS=true KEEP_CLUSTER=true ./tests/e2e/run.sh

port_forward() { # <ns> <svc> <local:remote>, reconnecting
  ( while true; do kubectl -n "$1" port-forward --address 127.0.0.1 "svc/$2" "$3" >/dev/null 2>&1; sleep 1; done ) &
  PIDS+=($!)
}
port_forward inference inference-gateway 18080:80
port_forward monitoring kps-prometheus 19090:9090
for p in 18080 19090; do for _ in $(seq 1 30); do (echo > "/dev/tcp/127.0.0.1/$p") 2>/dev/null && break; sleep 2; done; done

python3 tests/drills/drill.py "$SCENARIO" --bundle "$BUNDLE" "${EXTRA[@]}"
