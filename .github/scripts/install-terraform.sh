#!/usr/bin/env bash
# Install Terraform from releases.hashicorp.com with checksum verification (no third-party Action).
set -euo pipefail
v="${TERRAFORM_VERSION:-$(curl -fsSL https://checkpoint-api.hashicorp.com/v1/check/terraform | python3 -c 'import json,sys;print(json.load(sys.stdin)["current_version"])')}"
tmp="$(mktemp -d)"; cd "$tmp"
curl -fsSLO "https://releases.hashicorp.com/terraform/${v}/terraform_${v}_linux_amd64.zip"
curl -fsSLO "https://releases.hashicorp.com/terraform/${v}/terraform_${v}_SHA256SUMS"
grep "terraform_${v}_linux_amd64.zip" "terraform_${v}_SHA256SUMS" | sha256sum --check --strict
unzip -q "terraform_${v}_linux_amd64.zip"
sudo install -m 0755 terraform /usr/local/bin/terraform
terraform version
