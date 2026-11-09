import copy
import ipaddress
import os
from pathlib import Path

import pytest
import yaml
from netgen.model import FabricError, build, load
from netgen.render import render_all, render_device

HERE = Path(__file__).parent
FABRIC_FILE = HERE.parent / "fabric" / "fabric.yaml"
GOLDEN = HERE / "golden"


@pytest.fixture
def data() -> dict:
    return yaml.safe_load(FABRIC_FILE.read_text())


@pytest.fixture
def fabric(data):
    return build(data)


# ---------------------------------------------------------------- addressing
def test_every_link_is_a_matching_31(fabric):
    for spine in fabric.spines():
        for link in spine.links:
            assert link.spine_ip.network.prefixlen == 31
            assert link.spine_ip.network == link.leaf_ip.network, f"{link.spine}<->{link.leaf} not on same /31"
            assert link.spine_ip.ip != link.leaf_ip.ip


def test_no_ip_is_used_twice(fabric):
    ips = [str(d.loopback.ip) for d in fabric.devices.values()]
    ips += [str(link.spine_ip.ip) for s in fabric.spines() for link in s.links]
    ips += [str(link.leaf_ip.ip) for s in fabric.spines() for link in s.links]
    assert len(ips) == len(set(ips))


def test_full_mesh_spine_to_leaf(fabric):
    for leaf in fabric.leaves():
        assert sorted(link.spine for link in leaf.links) == ["spine1", "spine2"]


def test_addressing_is_stable_when_leaves_are_reordered(data):
    reordered = copy.deepcopy(data)
    reordered["leaves"].reverse()
    a, b = build(data), build(reordered)
    for name in a.devices:
        assert [str(n["local_ip"]) for n in a.devices[name].neighbors] == \
            sorted([str(n["local_ip"]) for n in b.devices[name].neighbors], key=lambda ip: ipaddress.ip_interface(ip))


def test_adding_a_leaf_does_not_renumber_existing_links(data, fabric):
    grown = copy.deepcopy(data)
    grown["leaves"].append({"name": "leaf9", "id": 9, "platform": "eos", "role": "compute"})
    bigger = build(grown)
    for name, dev in fabric.devices.items():
        if dev.role != "spine":
            assert [str(n["local_ip"]) for n in dev.neighbors] == \
                [str(n["local_ip"]) for n in bigger.devices[name].neighbors]


# ---------------------------------------------------------------- BGP design rules
def test_leaf_asns_unique_and_spines_shared(fabric):
    leaf_asns = [d.asn for d in fabric.leaves()]
    assert len(leaf_asns) == len(set(leaf_asns))
    assert {d.asn for d in fabric.spines()} == {fabric.spine_asn}


def test_spine_peers_with_each_leaf_asn(fabric):
    spine = fabric.devices["spine1"]
    assert {n["asn"] for n in spine.neighbors} == {d.asn for d in fabric.leaves()}


# ---------------------------------------------------------------- validation
@pytest.mark.parametrize(
    ("mutate", "error"),
    [
        (lambda d: d["leaves"].append(dict(d["leaves"][0])), "duplicate device names"),
        (lambda d: d["leaves"][1].update(id=1), "duplicate leaf ids"),
        (lambda d: d["leaves"][0].update(platform="nxos"), "unsupported platform"),
        (lambda d: d["leaves"][0].update(rdma=True), "rdma is only valid"),
        (lambda d: d["fabric"].update(spine_asn=65101), "collides"),
        (lambda d: d["fabric"].update(mtu=10000), "mtu"),
        (lambda d: d["fabric"].update(underlay_p2p_pool="10.255.0.0/29"), "too small"),
        (lambda d: d["leaves"][0].update(id=0), "between 1 and 64"),
    ],
)
def test_rejects_invalid_fabrics(data, mutate, error):
    mutate(data)
    with pytest.raises(FabricError, match=error):
        build(data)


# ---------------------------------------------------------------- rendering
def test_eos_leaf_renders_bgp_and_gateway(fabric):
    cfg = render_device(fabric, fabric.devices["leaf1"])
    assert "router bgp 65101" in cfg
    assert "neighbor SPINES remote-as 65000" in cfg
    assert "ip address 10.110.1.1/24" in cfg
    assert "priority-flow-control" not in cfg  # compute leaves are not lossless


def test_gpu_leaf_gets_lossless_rdma_profile(fabric):
    cfg = render_device(fabric, fabric.devices["gpu-leaf1"])
    assert "priority-flow-control priority 3 no-drop" in cfg
    assert "random-detect ecn" in cfg
    assert cfg.count("priority-flow-control on") == 2  # every uplink


def test_junos_leaf_renders_set_commands(fabric):
    cfg = render_device(fabric, fabric.devices["leaf2"])
    assert "set routing-options autonomous-system 65102" in cfg
    assert "set protocols bgp group underlay peer-as 65000" in cfg
    assert all(line.startswith(("set ", "/*")) for line in cfg.strip().splitlines())


def test_mtu_applied_to_every_fabric_link(fabric):
    for dev in fabric.devices.values():
        cfg = render_device(fabric, dev)
        assert cfg.count(str(fabric.mtu)) >= len(dev.links)


def test_render_all_writes_one_file_per_device(fabric, tmp_path):
    paths = render_all(fabric, tmp_path)
    assert {p.stem for p in paths} == set(fabric.devices)


@pytest.mark.parametrize("device", ["spine1", "gpu-leaf1", "leaf2"])
def test_golden_configs(device):
    """Snapshot tests: any template change shows up as a reviewable diff.
    Regenerate intentionally with:  UPDATE_GOLDEN=1 pytest network/tests"""
    fabric = load(FABRIC_FILE)
    rendered = render_device(fabric, fabric.devices[device])
    golden = GOLDEN / f"{device}.cfg"
    if os.getenv("UPDATE_GOLDEN") == "1":
        golden.write_text(rendered)
    assert rendered == golden.read_text()
