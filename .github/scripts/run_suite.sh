#!/usr/bin/env bash
# Run one test suite with an optional filter and debug verbosity. Used by the run-tests workflow,
# and handy locally:   SUITE=gateway FILTER=rate_limit DEBUG=true ./.github/scripts/run_suite.sh
# Inputs come from env (never interpolated into the shell by the workflow → no script injection).
set -euo pipefail
SUITE="${SUITE:?}"; FILTER="${FILTER:-}"; DEBUG="${DEBUG:-false}"
ARTIFACTS="${ARTIFACTS:-/tmp/test-artifacts}"; mkdir -p "$ARTIFACTS"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"; cd "$ROOT"
dbg() { [ "$DEBUG" = "true" ]; }

pytest_suite() { # <dir>
  local args=(-p no:cacheprovider --junitxml="$ARTIFACTS/$SUITE-junit.xml")
  [ -n "$FILTER" ] && args+=(-k "$FILTER")
  dbg && args+=(-vv -s --log-cli-level=DEBUG --showlocals) || args+=(-q)
  (cd "$1" && python3 -m pytest "${args[@]}")
}

case "$SUITE" in
  terraform)
    dbg && export TF_LOG=DEBUG TF_LOG_PATH="$ARTIFACTS/terraform-debug.log"
    for d in $(find terraform/modules terraform/stacks -type d -name tests -exec dirname {} \; | sort); do
      [ -n "$FILTER" ] && [[ "$d" != *"$FILTER"* ]] && continue
      echo "== $d"
      terraform -chdir="$d" init -backend=false -input=false >/dev/null
      if dbg; then terraform -chdir="$d" test -verbose; else terraform -chdir="$d" test; fi
    done ;;
  policy)
    args=(test /p/policy/kubernetes)
    [ -n "$FILTER" ] && args+=(--run "$FILTER")
    dbg && args+=(-v --explain=full)
    docker run --rm -v "$PWD:/p" openpolicyagent/opa:latest "${args[@]}" ;;
  slo)
    for f in sre/slo/tests/*.test.yaml; do
      [ -n "$FILTER" ] && [[ "$f" != *"$FILTER"* ]] && continue
      docker run --rm -v "$PWD:/w" -w /w/sre/slo/tests --entrypoint promtool prom/prometheus:latest test rules "$(basename "$f")"
    done ;;
  gateway)            pytest_suite services/inference-gateway ;;
  network)            pytest_suite network ;;
  triage)             pytest_suite scripts/triage ;;
  drills-static)      pytest_suite tests/drills ;;
  ci-doctor)          pytest_suite .github/scripts ;;
  exercise-checker)   pytest_suite study/checks ;;
  repo-health)        pytest_suite scripts/health ;;
  ansible)
    cd ansible && ansible-galaxy collection install -r requirements.yml >/dev/null
    if dbg; then ansible-lint -vv; else ansible-lint; fi ;;
  e2e)
    BUNDLE_DIR="$ARTIFACTS/triage-bundle" JUNIT_XML="$ARTIFACTS/e2e-junit.xml" ./tests/e2e/run.sh ;;
  *) echo "unknown suite: $SUITE"; exit 2 ;;
esac
