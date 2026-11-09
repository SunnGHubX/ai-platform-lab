"""python3 -m netgen <fabric.yaml> [--out build/]"""
import argparse
import sys

from .model import FabricError, load
from .render import render_all


def main() -> int:
    p = argparse.ArgumentParser(prog="netgen")
    p.add_argument("fabric")
    p.add_argument("--out", default="network/build")
    a = p.parse_args()
    try:
        fabric = load(a.fabric)
    except FabricError as e:
        print(f"invalid fabric: {e}", file=sys.stderr)
        return 2
    for path in render_all(fabric, a.out):
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
