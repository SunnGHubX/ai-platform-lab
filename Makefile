SHELL := /usr/bin/env bash
# Tools installed by `make prereqs-install` live in ./.bin and win over system versions.
export PATH := $(CURDIR)/.bin:$(PATH)
PROFILE ?= lab
CLUSTER ?= sunn-platform-lab



.PHONY: prereqs prereqs-install up down aws-bootstrap aws-teardown drill triage doctor health exercise exercises e2e test-exercises test test-terraform test-policy test-slo test-network test-gateway help set-repo cluster bootstrap inference argocd-password argocd-ui grafana-ui mlflow-ui vllm-api lint teardown

help: ## Show targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n",$$1,$$2}'

set-repo: ## Point all Argo CD Applications at your fork: make set-repo REPO=https://github.com/<you>/sunn-platform-lab.git
	@test -n "$(REPO)" || (echo "usage: make set-repo REPO=https://github.com/<you>/sunn-platform-lab.git" && exit 1)
	@grep -rl 'https://github.com/REPLACE_ME/sunn-platform-lab.git' gitops | xargs sed -i.bak 's#https://github.com/REPLACE_ME/sunn-platform-lab.git#$(REPO)#g'
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

test: test-terraform test-policy test-slo test-network test-gateway test-exercises test-tooling ## Run every test suite (needs terraform + docker)

test-terraform: ## terraform test with mocked AWS
	$(MAKE) -C terraform test

test-policy: ## Rego unit tests
	docker run --rm -v "$(CURDIR):/p" -w /p openpolicyagent/conftest:latest verify --policy policy/kubernetes

test-slo: ## promtool alert unit tests (every file)
	for f in sre/slo/tests/*.test.yaml; do docker run --rm -v "$(CURDIR):/w" -w /w/sre/slo/tests --entrypoint promtool prom/prometheus:latest test rules $$(basename $$f) || exit 1; done

test-network: ## netgen unit + golden tests
	cd network && pytest -q

test-tooling: ## triage, drills, ci-doctor, health unit tests
	for d in scripts/triage tests/drills .github/scripts scripts/health; do (cd $$d && pytest -q -p no:cacheprovider) || exit 1; done

test-exercises: ## exercise checker unit tests
	cd study/checks && pytest -q -p no:cacheprovider

test-gateway: ## inference-gateway unit tests
	cd services/inference-gateway && pytest

exercises: ## Status board: which study exercises pass their acceptance checks
	@python3 study/checks/check.py --all --quick

exercise: ## Check one exercise: make exercise EX=06
	@test -n "$(EX)" || (echo "usage: make exercise EX=06" && exit 1)
	python3 study/checks/check.py $(EX)

e2e: ## Full end-to-end test in a local kind cluster (needs docker, kind, kubectl, helm)
	./tests/e2e/run.sh

drill: ## Break-fix drill on kind: make drill SCENARIO=oom [PRACTICE=1]
	@test -n "$(SCENARIO)" || (echo "usage: make drill SCENARIO=<$$(python3 -c 'import yaml;print("|".join(yaml.safe_load(open("tests/drills/scenarios.yaml"))))')>" && exit 1)
	./tests/drills/run_drill.sh $(SCENARIO) $(if $(PRACTICE),--no-reveal,)

triage: ## Debug bundle + root-cause findings for the CURRENT kube context: make triage [PROM=http://localhost:9090]
	python3 scripts/triage/triage.py --out triage-bundle-$$(date +%Y%m%d-%H%M%S) $(if $(PROM),--prom-url $(PROM),)

doctor: ## Explain a failed CI run: make doctor RUN=<run id>
	python3 .github/scripts/ci_doctor.py --repo SunnGHubX/sunn-platform-lab --run-id $(RUN)

health: ## Doc links + version drift report
	python3 scripts/health/check_links.py . && python3 scripts/health/version_drift.py

# ---------------------------------------------------------------- bootstrap
prereqs: ## Check tools/Docker/ports for a profile: make prereqs [PROFILE=lab|iac|aws|all]
	python3 scripts/bootstrap/prereqs.py --profile $(PROFILE)

prereqs-install: ## Install missing tools (pinned in mise.toml, checksum-verified) into ./.bin
	python3 scripts/bootstrap/prereqs.py --profile $(PROFILE) --install

up: ## Local platform from zero, idempotent: prereqs -> kind -> Argo CD -> healthy  [INFERENCE=1] [UP_INSTALL=1]
	./scripts/bootstrap/up.sh

down: ## Delete the local kind cluster
	kind delete cluster --name $(CLUSTER)

aws-bootstrap: ## Bootstrap an AWS env: make aws-bootstrap ENV=dev ACCOUNT_ID=123456789012 [REGION=us-west-2] [APPLY=1] [DRY_RUN=1]
	@test -n "$(ENV)" -a -n "$(ACCOUNT_ID)" || (echo "usage: make aws-bootstrap ENV=dev ACCOUNT_ID=123456789012 [REGION=us-west-2] [APPLY=1] [DRY_RUN=1]" && exit 1)
	python3 scripts/bootstrap/aws_bootstrap.py --env $(ENV) --account-id $(ACCOUNT_ID) $(if $(REGION),--region $(REGION),) $(if $(APPLY),--apply,) $(if $(DRY_RUN),--dry-run,)

aws-teardown: ## Destroy an env's stacks in reverse order (services -> eks -> network); never prod, keeps the state bucket
	@test -n "$(ENV)" || (echo "usage: make aws-teardown ENV=dev" && exit 1)
	@test "$(ENV)" != "prod" || (echo "refusing to tear down prod from a laptop" && exit 1)
	for s in services eks network; do $(MAKE) -C terraform destroy ENV=$(ENV) STACK=$$s || exit 1; done
	@echo "Stacks destroyed. The state bucket + CI roles (envs/_global/bootstrap) are kept on purpose."
