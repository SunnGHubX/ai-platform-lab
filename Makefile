SHELL := /usr/bin/env bash
CLUSTER ?= ai-platform-lab

.PHONY: help set-repo cluster bootstrap inference argocd-password argocd-ui grafana-ui mlflow-ui vllm-api lint teardown

help: ## Show targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n",$$1,$$2}'

set-repo: ## Point all Argo CD Applications at your fork: make set-repo REPO=https://github.com/<you>/ai-platform-lab.git
	@test -n "$(REPO)" || (echo "usage: make set-repo REPO=https://github.com/<you>/ai-platform-lab.git" && exit 1)
	@grep -rl 'https://github.com/REPLACE_ME/ai-platform-lab.git' gitops | xargs sed -i.bak 's#https://github.com/REPLACE_ME/ai-platform-lab.git#$(REPO)#g'
	@find gitops -name '*.bak' -delete
	@echo "repoURL set to $(REPO) — commit and push."

cluster: ## Create a local kind cluster
	kind create cluster --config bootstrap/kind-config.yaml

bootstrap: ## Install Argo CD and apply the core app-of-apps
	./bootstrap/install-argocd.sh

inference: ## Enable vLLM (GPU) + Triton via the inference app-of-apps
	kubectl apply -f gitops/root-inference.yaml

argocd-password: ## Print the initial Argo CD admin password
	@kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d; echo

argocd-ui: ## Port-forward Argo CD to http://localhost:8080
	kubectl -n argocd port-forward svc/argocd-server 8080:80

grafana-ui: ## Port-forward Grafana to http://localhost:3000
	kubectl -n monitoring port-forward svc/grafana 3000:80

mlflow-ui: ## Port-forward MLflow to http://localhost:5000
	kubectl -n mlops port-forward svc/mlflow 5000:5000

vllm-api: ## Port-forward vLLM to http://localhost:8000
	kubectl -n inference port-forward svc/vllm 8000:8000

lint: ## yamllint + kustomize build of every platform dir
	yamllint .
	@for d in platform/*/; do [ -f $$d/kustomization.yaml ] && kubectl kustomize $$d >/dev/null && echo "kustomize OK: $$d"; done; true

teardown: ## Delete the kind cluster
	kind delete cluster --name $(CLUSTER)
