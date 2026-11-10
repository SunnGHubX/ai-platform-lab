#!/usr/bin/env bash
# One command to a running local platform, idempotent:  prereqs -> kind -> Argo CD -> app-of-apps -> healthy.
#   make up                   # core platform (Prometheus/Grafana, KEDA, OTel, MLflow, SLO rules)
#   INFERENCE=1 make up       # + vLLM/Triton/gateway (vLLM needs a GPU node)
#   make down                 # delete the cluster
# Re-running `make up` repairs whatever drifted (missing cluster, Argo CD, root app).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"; cd "$ROOT"
CLUSTER="${CLUSTER:-sunn-platform-lab}"
TIMEOUT="${UP_TIMEOUT:-900}"
export PATH="$ROOT/.bin:$PATH"

step() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

step "prerequisites"
python3 scripts/bootstrap/prereqs.py --profile lab ${UP_INSTALL:+--install}

step "kind cluster '$CLUSTER'"
if kind get clusters 2>/dev/null | grep -qx "$CLUSTER"; then
  echo "exists, reusing"
else
  sed "s/^name: .*/name: $CLUSTER/" bootstrap/kind-config.yaml | kind create cluster --config - --wait 120s
fi
kubectl config use-context "kind-$CLUSTER" >/dev/null

step "Argo CD + app-of-apps (syncs from GitHub)"
./bootstrap/install-argocd.sh >/dev/null
if [ -n "${INFERENCE:-}" ]; then kubectl apply -f gitops/root-inference.yaml; fi

step "waiting for Argo CD applications to be Synced + Healthy (timeout ${TIMEOUT}s)"
deadline=$((SECONDS + TIMEOUT))
while :; do
  if out=$(kubectl -n argocd get applications -o json | python3 scripts/bootstrap/argo_status.py --min 5); then
    echo "$out"; break
  fi
  if [ $SECONDS -ge $deadline ]; then
    echo "timed out; not ready: $out"
    echo "debug: make triage   |   kubectl -n argocd get applications"
    exit 1
  fi
  echo "  waiting: ${out:-applications not created yet}"; sleep 15
done

step "ready"
cat <<MSG
  Argo CD   make argocd-ui  -> https://localhost:8080   user admin / pw: $(make -s argocd-password 2>/dev/null)
  Grafana   make grafana-ui -> http://localhost:3000    admin / prom-operator
  MLflow    make mlflow-ui  -> http://localhost:5000
  Debug     make triage     |  tear down: make down
MSG
