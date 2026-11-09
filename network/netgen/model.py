"""Fabric data model: load, validate, and allocate addressing deterministically."""
from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from pathlib import Path

import yaml

SUPPORTED_PLATFORMS = {"eos", "junos"}


class FabricError(ValueError):
    """Raised when the fabric definition is invalid."""


@dataclass
class Link:
    spine: str
    spine_port: str
    spine_ip: ipaddress.IPv4Interface
    leaf: str
    leaf_port: str
    leaf_ip: ipaddress.IPv4Interface
    spine_asn: int
    leaf_asn: int


@dataclass
class Device:
    name: str
    platform: str
    role: str
    asn: int
    loopback: ipaddress.IPv4Interface
    links: list[Link] = field(default_factory=list)
    rdma: bool = False
    server_vlan: dict | None = None

    @property
    def neighbors(self) -> list[dict]:
        """BGP neighbors from this device's point of view."""
        out = []
        for link in self.links:
            if self.role == "spine":
                out.append({"ip": str(link.leaf_ip.ip), "peer": link.leaf, "asn": link.leaf_asn,
                            "port": link.spine_port, "local_ip": link.spine_ip})
            else:
                out.append({"ip": str(link.spine_ip.ip), "peer": link.spine, "asn": link.spine_asn,
                            "port": link.leaf_port, "local_ip": link.leaf_ip})
        return out

    @property
    def server_gateway(self) -> str | None:
        """First host of the server subnet as the anycast-style default gateway, e.g. 10.110.1.1/24."""
        if not self.server_vlan:
            return None
        net = ipaddress.ip_network(self.server_vlan["subnet"])
        return f"{next(net.hosts())}/{net.prefixlen}"


@dataclass
class Fabric:
    name: str
    mtu: int
    spine_asn: int
    devices: dict[str, Device]

    def leaves(self) -> list[Device]:
        return [d for d in self.devices.values() if d.role != "spine"]

    def spines(self) -> list[Device]:
        return [d for d in self.devices.values() if d.role == "spine"]


def load(path: str | Path) -> Fabric:
    return build(yaml.safe_load(Path(path).read_text()))


def build(data: dict) -> Fabric:
    f = data["fabric"]
    spines, leaves = data.get("spines", []), data.get("leaves", [])
    _validate(f, spines, leaves, data.get("cabling", {}))

    p2p = ipaddress.ip_network(f["underlay_p2p_pool"])
    loopbacks = list(ipaddress.ip_network(f["loopback_pool"]).hosts())
    p2p_subnets = list(p2p.subnets(new_prefix=31))
    # Each spine owns an equal, contiguous block of /31s; leaf id N uses the N-th /31 of every block.
    # Adding a leaf never renumbers existing links.
    stride = len(p2p_subnets) // len(spines)
    if max(leaf["id"] for leaf in leaves) > stride:
        raise FabricError(f"underlay_p2p_pool too small: {len(spines)} spines x leaf id up to "
                          f"{max(leaf['id'] for leaf in leaves)} needs a bigger pool (stride {stride})")
    if len(spines) + len(leaves) > len(loopbacks):
        raise FabricError("loopback_pool too small")

    devices: dict[str, Device] = {}
    for i, s in enumerate(spines):
        devices[s["name"]] = Device(s["name"], s["platform"], "spine", f["spine_asn"],
                                    ipaddress.ip_interface(f"{loopbacks[i]}/32"))
    for leaf in leaves:
        devices[leaf["name"]] = Device(
            leaf["name"], leaf["platform"], leaf.get("role", "compute"), f["leaf_asn_base"] + leaf["id"],
            ipaddress.ip_interface(f"{loopbacks[len(spines) + leaf['id'] - 1]}/32"),
            rdma=leaf.get("rdma", False), server_vlan=leaf.get("server_vlan"),
        )

    cabling = data["cabling"]
    # Deterministic: the /31 index depends only on (spine index, leaf id), never on file order.
    for s_idx, s in enumerate(spines):
        spine_port = cabling["spine_port_template"][s["platform"]]
        for leaf in leaves:
            net = p2p_subnets[s_idx * stride + (leaf["id"] - 1)]
            spine_ip, leaf_ip = (ipaddress.ip_interface(f"{h}/31") for h in (net[0], net[1]))
            link = Link(
                spine=s["name"], spine_port=spine_port.format(n=leaf["id"]), spine_ip=spine_ip,
                leaf=leaf["name"], leaf_port=cabling["leaf_uplink_ports"][leaf["platform"]][s_idx], leaf_ip=leaf_ip,
                spine_asn=f["spine_asn"], leaf_asn=f["leaf_asn_base"] + leaf["id"],
            )
            devices[s["name"]].links.append(link)
            devices[leaf["name"]].links.append(link)

    return Fabric(f["name"], f.get("mtu", 9214), f["spine_asn"], devices)


def _validate(f: dict, spines: list, leaves: list, cabling: dict) -> None:
    names = [d["name"] for d in spines + leaves]
    if dupes := {n for n in names if names.count(n) > 1}:
        raise FabricError(f"duplicate device names: {sorted(dupes)}")
    ids = [leaf["id"] for leaf in leaves]
    if len(ids) != len(set(ids)):
        raise FabricError("duplicate leaf ids (leaf ASN and addressing derive from the id)")
    if any(i < 1 or i > 64 for i in ids):
        raise FabricError("leaf id must be between 1 and 64")
    if not 1 <= len(spines) <= 4:
        raise FabricError("supported spine count is 1-4")
    for d in spines + leaves:
        if d["platform"] not in SUPPORTED_PLATFORMS:
            raise FabricError(f"{d['name']}: unsupported platform {d['platform']!r}")
    for leaf in leaves:
        if len(cabling.get("leaf_uplink_ports", {}).get(leaf["platform"], [])) < len(spines):
            raise FabricError(f"{leaf['name']}: needs {len(spines)} uplink ports for {leaf['platform']}")
        if leaf.get("rdma") and leaf.get("role") != "gpu":
            raise FabricError(f"{leaf['name']}: rdma is only valid on role: gpu leaves")
    leaf_asns = {f["leaf_asn_base"] + i for i in ids}
    if f["spine_asn"] in leaf_asns:
        raise FabricError("spine_asn collides with a leaf ASN")
    if not 1280 <= f.get("mtu", 9214) <= 9216:
        raise FabricError("mtu must be between 1280 and 9216")
