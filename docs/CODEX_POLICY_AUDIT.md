# Codex skill invocation audit (Issue #433)

This is a **read-only** audit. It inventories ARIS's actual Codex skill mirror, checks optional `agents/openai.yaml` invocation policies, and identifies possible parent-to-child skill references.

It intentionally does **not** rewrite skill policies. ARIS workflows invoke other skills; disabling implicit invocation must be tested with a pinned Codex CLI version before rollout.

Run from the repository root:

```bash
python3 tools/audit_codex_invocation.py > /tmp/codex-policy-audit.json
python3 tools/audit_codex_invocation.py --fail-on-referenced-explicit
python3 -m pytest -q tests/test_audit_codex_invocation.py
```

The JSON output includes the scanned skill count, explicit-only skills, incoming references, invalid policies, and `runtime_verified: false`. References are conservative text matches, not proof that a parent invokes a child. The stricter flag fails if an explicit-only skill is referenced by another skill.

Before enabling `policy.allow_implicit_invocation: false` on any workflow component, perform two real Codex CLI checks: direct `$skill-name` invocation and parent-workflow invocation of the same child. If either breaks, do not enable the policy.

**Scope:** supports issue #433's audit and regression-test acceptance criteria, but **does not claim** a complete fix for routing overhead or verified runtime invocation behavior.
