"""Render per-device configs with Jinja2."""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .model import Device, Fabric

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"


def environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATES),
        undefined=StrictUndefined,  # a typo in a template fails loudly instead of rendering ""
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        autoescape=False,  # noqa: S701 - network configs, not HTML
    )


def template_for(device: Device) -> str:
    role = "spine" if device.role == "spine" else "leaf"
    return f"{device.platform}_{role}.j2"


def render_device(fabric: Fabric, device: Device, env: Environment | None = None) -> str:
    env = env or environment()
    return env.get_template(template_for(device)).render(fabric=fabric, d=device)


def render_all(fabric: Fabric, out_dir: str | Path) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    env = environment()
    written = []
    for device in fabric.devices.values():
        path = out / f"{device.name}.cfg"
        path.write_text(render_device(fabric, device, env))
        written.append(path)
    return written
