# 11 · EVPN-VXLAN overlay ★★★★

**Scenario:** tenants need L2 stretch between the two GPU leaves (some RDMA tooling expects one subnet) plus L3 VRF isolation per tenant.

## Tasks

1. Extend the model: `tenants: [{name, vrf, l3vni, vlans: [{id, vni, subnet}]}]`, VTEP loopback (`Loopback1`) allocation.
2. Templates: EOS `router bgp` EVPN address-family over loopback iBGP/eBGP multihop, `interface Vxlan1`, symmetric IRB with anycast gateway (`ip address virtual`). Junos equivalent with `switch-options` / `protocols evpn`.
3. Validation: VNIs unique, VLAN↔VNI 1:1 per leaf, L3VNI ≠ any L2VNI.
4. Golden tests for one EOS and one Junos leaf.

## Acceptance

- [ ] ≥ 6 new tests (allocation + validation + rendering)
- [ ] Optional: boot the configs in containerlab (cEOS + vJunos) and show `show bgp evpn summary`

**Interview angle:** why AI back-end networks usually stay **pure L3 + RoCE** (no VXLAN on the GPU rail) while front-end/storage networks use EVPN. Be ready to defend it.
