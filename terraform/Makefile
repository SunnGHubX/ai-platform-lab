# Usage:
#   make plan  ENV=dev STACK=network
#   make apply ENV=dev STACK=network
#   make plan-all ENV=staging          # network -> eks -> services, in dependency order
#   make apply ENV=prod STACK=eks CONFIRM=prod
SHELL  := /usr/bin/env bash
STACKS := network eks services
ENV    ?=
STACK  ?=

TF      = terraform -chdir=stacks/$(STACK)
ENV_DIR = ../../envs/$(ENV)
VARS    = -var-file=$(ENV_DIR)/common.tfvars -var-file=$(ENV_DIR)/$(STACK).tfvars
PLAN    = $(ENV)-$(STACK).tfplan

.PHONY: help guard init plan apply destroy plan-all apply-all fmt validate lint

help: ## Show targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-10s\033[0m %s\n",$$1,$$2}'

guard:
	@[[ "$(ENV)" =~ ^(dev|staging|prod)$$ ]] || { echo "ENV must be dev|staging|prod"; exit 1; }
	@[[ " $(STACKS) " == *" $(STACK) "* ]] || { echo "STACK must be one of: $(STACKS)"; exit 1; }

init: guard ## Init a stack against its own state key: <env>/<stack>/terraform.tfstate
	$(TF) init -reconfigure -input=false \
	  -backend-config=$(ENV_DIR)/backend.hcl \
	  -backend-config="key=$(ENV)/$(STACK)/terraform.tfstate"

plan: init ## Plan one stack and save the plan file
	$(TF) plan -input=false $(VARS) -out=$(PLAN)

apply: guard ## Apply the saved plan (prod requires CONFIRM=prod)
	@if [ "$(ENV)" = "prod" ] && [ "$(CONFIRM)" != "prod" ]; then echo "Refusing to apply prod without CONFIRM=prod"; exit 1; fi
	$(TF) apply -input=false $(PLAN)

destroy: init ## Destroy one stack (blocked for prod)
	@if [ "$(ENV)" = "prod" ]; then echo "Destroying prod from a laptop is disabled."; exit 1; fi
	$(TF) destroy $(VARS)

plan-all: ## Plan every stack for ENV in dependency order
	@for s in $(STACKS); do $(MAKE) --no-print-directory plan ENV=$(ENV) STACK=$$s || exit 1; done

apply-all: ## Plan+apply every stack for ENV in order (each stack needs the previous one's SSM outputs)
	@for s in $(STACKS); do $(MAKE) --no-print-directory plan apply ENV=$(ENV) STACK=$$s CONFIRM=$(CONFIRM) || exit 1; done

fmt: ## Format all Terraform
	terraform fmt -recursive

validate: ## terraform validate every module and stack (no backend, no credentials)
	@for d in modules/* stacks/* envs/_global/bootstrap; do \
	  echo "== $$d"; terraform -chdir=$$d init -backend=false -input=false >/dev/null && terraform -chdir=$$d validate || exit 1; \
	done

lint: ## tflint every module and stack
	tflint --init
	@for d in modules/* stacks/* envs/_global/bootstrap; do echo "== $$d"; tflint --chdir=$$d --config=$(CURDIR)/.tflint.hcl || exit 1; done
