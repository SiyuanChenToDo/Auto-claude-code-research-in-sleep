#!/usr/bin/env python3
"""Audit ARIS Codex skill invocation without modifying runtime policies.

Issue #433: disabling implicit invocation may also interrupt parent-to-child
skills. This tool reports candidates; it cannot establish Codex runtime safety.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

SKILL_INVOKE = re.compile(r"(?<![\w/])(?:/|\$)([a-z][a-z0-9-]*)\b")
SKILL_LINK = re.compile(r"\.\./([a-z][a-z0-9-]*)/SKILL\.md\b")
POLICY_BLOCK = re.compile(r"(?m)^policy:\s*\n((?:[ \t]+[^\n]*\n|\s*\n)*)")
POLICY_VALUE = re.compile(r"(?m)^[ \t]+allow_implicit_invocation:[ \t]*(true|false)[ \t]*(?:#.*)?$")


def parse_policy(path: Path) -> tuple[bool | None, str | None]:
    """Return the policy value or an error; missing sidecars use Codex defaults."""
    if not path.exists():
        return None, None
    raw = path.read_text(encoding="utf-8")
    # Metadata-only sidecars are valid: absent policy means Codex defaults.
    if re.search(r"(?m)^policy\s*:", raw) is None:
        return None, None
    blocks = list(POLICY_BLOCK.finditer(raw))
    if len(blocks) != 1:
        return None, f"{path}: expected exactly one top-level policy mapping"
    values = POLICY_VALUE.findall(blocks[0].group(1))
    if len(values) != 1:
        return None, f"{path}: expected one YAML boolean allow_implicit_invocation"
    return values[0] == "true", None


def audit(root: Path) -> dict:
    """Inventory actual mirror skills, policy sidecars, and references."""
    if not root.is_dir():
        raise ValueError(f"Missing Codex skills directory: {root}")
    files = {p.parent.name: p for p in sorted(root.glob("*/SKILL.md"))}
    if not files:
        raise ValueError(f"No */SKILL.md files found under {root}")
    inbound: dict[str, set[str]] = {name: set() for name in files}
    for parent, file in files.items():
        text = file.read_text(encoding="utf-8")
        targets = set(SKILL_LINK.findall(text)) | set(SKILL_INVOKE.findall(text))
        for child in targets & files.keys():
            if child != parent:
                inbound[child].add(parent)
    result = []
    invalid = []
    for name, file in files.items():
        policy_file = file.parent / "agents" / "openai.yaml"
        implicit, error = parse_policy(policy_file)
        if error:
            invalid.append(error)
        result.append(
            {
                "skill": name,
                "invocation": (
                    "explicit-only" if implicit is False
                    else "implicit-default" if implicit is None
                    else "implicit-allowed"
                ),
                "referenced_by": sorted(inbound[name]),
                "policy_file": str(policy_file.relative_to(root)),
                "policy_valid": error is None,
            }
        )
    return {
        "skill_count": len(files),
        "explicit_only_count": sum(row["invocation"] == "explicit-only" for row in result),
        "referenced_explicit_only": [
            row["skill"] for row in result
            if row["invocation"] == "explicit-only" and row["referenced_by"]
        ],
        "invalid_policies": invalid,
        "skills": result,
        "runtime_verified": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path,
        default=Path(__file__).resolve().parents[1] / "skills" / "skills-codex",
    )
    parser.add_argument(
        "--fail-on-referenced-explicit", action="store_true",
        help="Conservative guard before Codex parent/child runtime compatibility is proven",
    )
    args = parser.parse_args(argv)
    try:
        report = audit(args.root)
    except (ValueError, UnicodeError, OSError) as error:
        parser.error(str(error))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int(bool(report["invalid_policies"] or (
        args.fail_on_referenced_explicit and report["referenced_explicit_only"]
    )))


if __name__ == "__main__":
    raise SystemExit(main())
