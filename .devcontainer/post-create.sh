#!/usr/bin/env bash
# Runs once when the devcontainer / Codespace is created: same pinned tools as CI and laptops.
set -euo pipefail
python3 scripts/bootstrap/prereqs.py --profile all --install --skip-docker
pip install --quiet --disable-pip-version-check pyyaml jinja2 pytest pre-commit \
  -r services/inference-gateway/requirements-dev.txt
pre-commit install --install-hooks >/dev/null 2>&1 || echo "pre-commit hooks will install on first commit"
cat <<'MSG'

  sunn-platform-lab devcontainer ready.
    make prereqs      # verify (Docker-in-Docker starts with the container)
    make up           # local platform on kind
    make test         # every unit test suite
    make exercises    # study progress
MSG
