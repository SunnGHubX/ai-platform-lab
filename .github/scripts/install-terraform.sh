#!/usr/bin/env bash
# Install Terraform from releases.hashicorp.com with checksum verification (no third-party Action).
set -euo pipefail
# Version comes from mise.toml (single source of truth), overridable for experiments.
v="${TERRAFORM_VERSION:-$(python3 -c 'import tomllib;print(tomllib.load(open("mise.toml","rb"))["tools"]["terraform"])')}"
tmp="$(mktemp -d)"; cd "$tmp"
curl -fsSLO "https://releases.hashicorp.com/terraform/${v}/terraform_${v}_linux_amd64.zip"
curl -fsSLO "https://releases.hashicorp.com/terraform/${v}/terraform_${v}_SHA256SUMS"
grep "terraform_${v}_linux_amd64.zip" "terraform_${v}_SHA256SUMS" | sha256sum --check --strict
unzip -q "terraform_${v}_linux_amd64.zip"
sudo install -m 0755 terraform /usr/local/bin/terraform
terraform version
