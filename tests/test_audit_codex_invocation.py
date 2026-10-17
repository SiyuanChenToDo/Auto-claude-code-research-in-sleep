"""Offline regression tests for Codex invocation policy audit (ARIS #433)."""
from pathlib import Path

import pytest

from tools.audit_codex_invocation import audit, main, parse_policy


def skill(root: Path, name: str, body: str) -> Path:
    path = root / name / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\nname: {name}\ndescription: test\n---\n{body}\n", encoding="utf-8")
    return path


def policy(root: Path, name: str, value: str) -> None:
    path = root / name / "agents" / "openai.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def test_absent_policy_preserves_default(tmp_path: Path) -> None:
    skill(tmp_path, "idea-discovery", "A workflow")
    report = audit(tmp_path)
    assert report["skills"][0]["invocation"] == "implicit-default"
    assert report["runtime_verified"] is False


def test_explicit_only_child_is_flagged(tmp_path: Path) -> None:
    skill(tmp_path, "research-pipeline", "Run /idea-discovery and [child](../idea-discovery/SKILL.md)")
    skill(tmp_path, "idea-discovery", "Workflow")
    policy(tmp_path, "idea-discovery", "policy:\n  allow_implicit_invocation: false\n")
    report = audit(tmp_path)
    assert report["explicit_only_count"] == 1
    assert report["referenced_explicit_only"] == ["idea-discovery"]
    assert next(row for row in report["skills"] if row["skill"] == "idea-discovery")["referenced_by"] == ["research-pipeline"]
    assert main(["--root", str(tmp_path), "--fail-on-referenced-explicit"]) == 1


def test_unreferenced_explicit_only_is_not_blocked(tmp_path: Path) -> None:
    skill(tmp_path, "interview-cheatsheet", "Interview preparation")
    policy(tmp_path, "interview-cheatsheet", 'interface:\n  display_name: "Interview"\npolicy:\n  allow_implicit_invocation: false\n')
    report = audit(tmp_path)
    assert report["referenced_explicit_only"] == []
    assert main(["--root", str(tmp_path), "--fail-on-referenced-explicit"]) == 0
    assert report["runtime_verified"] is False


@pytest.mark.parametrize("payload", [
    "policy:\n  allow_implicit_invocation: no\n",
    "policy:\n  allow_implicit_invocation: false\n  allow_implicit_invocation: true\n",
    "policy:\n  something_else: false\n",
    "policy:\n  allow_implicit_invocation: false\npolicy:\n  allow_implicit_invocation: true\n",
])
def test_invalid_policy_is_reported(tmp_path: Path, payload: str) -> None:
    skill(tmp_path, "sample", "Test")
    policy(tmp_path, "sample", payload)
    assert len(audit(tmp_path)["invalid_policies"]) == 1
    assert main(["--root", str(tmp_path)]) == 1


def test_yaml_boolean_with_comment(tmp_path: Path) -> None:
    path = tmp_path / "openai.yaml"
    path.write_text("policy:\n  allow_implicit_invocation: true # intentional\n", encoding="utf-8")
    assert parse_policy(path) == (True, None)


def test_missing_and_empty_roots(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        audit(tmp_path)
    with pytest.raises(ValueError):
        audit(tmp_path / "missing")


def test_real_codex_mirror_inventory() -> None:
    """Check the actual checked-out ARIS mirror, not only synthetic fixtures."""
    root = Path(__file__).resolve().parents[1] / "skills" / "skills-codex"
    report = audit(root)
    assert report["skill_count"] >= 80
    assert len(report["skills"]) == report["skill_count"]
    assert not report["invalid_policies"]
