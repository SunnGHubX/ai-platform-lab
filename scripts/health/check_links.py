#!/usr/bin/env python3
"""Fail on broken relative links in Markdown (files and directories), so docs, runbooks and
exercises never point at something that was renamed or deleted. External URLs are not fetched."""
from __future__ import annotations

import re
import sys
from pathlib import Path

LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
FENCE = re.compile(r"```.*?```", re.DOTALL)
SKIP_DIRS = {".git", "node_modules", ".terraform", ".venv", "build"}


def broken_links(root: Path) -> list[str]:
    problems = []
    for md in sorted(root.rglob("*.md")):
        if SKIP_DIRS & set(md.relative_to(root).parts):
            continue
        text = FENCE.sub("", md.read_text(encoding="utf-8", errors="ignore"))
        for target in LINK.findall(text):
            if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith("#"):  # http:, mailto:, anchors
                continue
            path = target.split("#", 1)[0]
            if not path:
                continue
            resolved = (md.parent / path) if not path.startswith("/") else (root / path.lstrip("/"))
            if not resolved.exists():
                problems.append(f"{md.relative_to(root)}: broken link -> {target}")
    return problems


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    problems = broken_links(root)
    for p in problems:
        print(p)
    print(f"{len(problems)} broken link(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
