#!/usr/bin/env bash
# Installs Argo CD with Helm, then hands control to the app-of-apps.
set -euo pipefail

ARGOCD_CHART_VERSION="${ARGOCD_CHART_VERSION:-10.17.0}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if grep -q "REPLACE_ME" "${ROOT_DIR}/gitops/root-app.yaml"; then
  echo "ERROR: run 'make set-repo REPO=https://github.com/<you>/sunn-platform-lab.git' first." >&2
  exit 1
fi

helm repo add argo https://argoproj.github.io/argo-helm >/dev/null
helm repo update argo >/dev/null

helm upgrade --install argocd argo/argo-cd \
  --namespace argocd --create-namespace \
  --version "${ARGOCD_CHART_VERSION}" \
  --set configs.params."server\.insecure"=true \
  --wait

kubectl apply -f "${ROOT_DIR}/gitops/root-app.yaml"

echo
echo "Argo CD installed. Initial admin password:"
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d; echo
