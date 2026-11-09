# Ansible: on-prem GPU nodes + network fabric

| Playbook | What it does |
|---|---|
| `playbooks/gpu_nodes.yml` | Ubuntu GPU hosts → NVIDIA server driver (held), persistence mode, Container Toolkit wired into containerd, swap off, kernel modules/sysctls. Validates with `nvidia-smi`. One node at a time. |
| `playbooks/network_deploy.yml` | Pushes configs rendered by `network/netgen` to Arista EOS (`eos_config`, then waits for BGP Established) and Junos (`commit confirmed 5` → auto-rollback if the box goes dark). |

```bash
cd ansible
ansible-galaxy collection install -r requirements.yml
ansible-lint                                                  # CI runs this
ansible-playbook playbooks/gpu_nodes.yml --check --diff --limit gpu-node-01
python3 -m netgen ../network/fabric/fabric.yaml --out ../network/build
NET_USER=admin NET_PASSWORD=... ansible-playbook playbooks/network_deploy.yml --check --diff
```

After nodes are ready, install the [NVIDIA GPU Operator](https://github.com/NVIDIA/gpu-operator) with `driver.enabled=false` and `toolkit.enabled=false` (Ansible owns those layers), so the operator only runs the device plugin, DCGM exporter and GPU feature discovery.
