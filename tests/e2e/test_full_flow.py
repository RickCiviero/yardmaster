import json
import re
import tomllib

import pytest
import yaml
from secrets_corpus import SECRETS
from synthetic import copilot_home, iso, jsonl, ms, vscode_user
from synthetic_claude import claude_home
from synthetic_codex import codex_home
from yardmaster.catalog import default_catalog
from yardmaster.cli import main

RANGE = ["--from", "2026-09-04", "--to", "2026-09-22"]
ALL_SECRETS = list(SECRETS.values())


@pytest.fixture
def world(tmp_path, home, monkeypatch):
    for k in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "TERM_PROGRAM", "ANTHROPIC_MODEL", "CODEX_HOME", "COPILOT_HOME", "CLAUDE_CONFIG_DIR"):
        monkeypatch.delenv(k, raising=False)
    src = tmp_path / "src"  # the "user's" history: legitimately contains the planted secrets
    trees = {
        "vscode-copilot": vscode_user(src / "vs"),
        "copilot-cli": copilot_home(src / "cli"),
        "claude-code": claude_home(src / "cc"),
        "codex": codex_home(src / "cx"),
    }
    leak = " ".join(ALL_SECRETS)
    jsonl(src / "cc" / ".claude" / "projects" / "C--ws-app" / "sessLeaky.jsonl", [
        {"type": "user", "timestamp": iso(2026, 9, 12), "sessionId": "sessLeaky", "cwd": "C:\\ws\\app", "isSidechain": False,
         "message": {"role": "user", "content": f"here are my credentials {leak}"}},
        {"type": "assistant", "timestamp": iso(2026, 9, 12, 10, 1), "sessionId": "sessLeaky", "isSidechain": False,
         "message": {"id": "m1", "model": "claude-opus-5-5", "role": "assistant", "content": [{"type": "text", "text": f"I will not repeat {leak}"}],
                     "usage": {"input_tokens": 5, "output_tokens": 5}}},
    ])
    vs_sess = next((trees["vscode-copilot"] / "workspaceStorage" / "hash1" / "chatSessions").glob("sessB.json"))
    doc = json.loads(vs_sess.read_text(encoding="utf-8"))
    doc["requests"][0]["message"]["text"] += f" my token is {SECRETS['github-pat']}"
    vs_sess.write_text(json.dumps(doc), encoding="utf-8")
    proj = tmp_path / "proj"
    proj.mkdir()
    return type("W", (), {"tmp": tmp_path, "home": home, "proj": proj, "trees": trees, "out": tmp_path / "out", "src": src})()


def _survey(w, capsys):
    args = ["survey", *RANGE, "--yes-expensive", "--out", str(w.out)]
    for h, p in w.trees.items():
        args += ["--path", f"{h}={p}"]
    assert main(args) == 0
    return capsys.readouterr().out


def _fake_model(w, tmp_path):
    """A deterministic stand-in for the invoking model: valid verdicts and a valid plan from the manifest."""
    catalog = default_catalog()
    ids = json.loads((w.out / "manifest.json").read_text(encoding="utf-8"))["chat_ids"]
    verdicts = []
    for i, cid in enumerate(ids):
        harness = cid.partition(":")[0]
        tier = "heavy" if i % 2 else "light"
        verdicts.append({
            "chat_id": cid, "task_group": "build-and-fix" if tier == "heavy" else "quick-questions",
            "task_summary": "Did some work", "model_used": "opus", "outcome": "ok", "sufficient_tier": tier,
            "weakest_sufficient_model": catalog.choose(harness, tier, frozenset()).id, "confidence": 0.9, "reason": "Fine",
        })
    (w.out / "verdicts.json").write_text(json.dumps(verdicts), encoding="utf-8")
    plan = {"version": 1, "description": "Heavy work to a strong model, the rest to a light one.", "groups": [
        {"name": "build-and-fix", "tier": "heavy", "when": "Building or changing code over many steps.", "examples": ["a feature"],
         "chats": 5, "prefer": {}},
        {"name": "quick-questions", "tier": "light", "when": "Quick answers and small chores.", "examples": ["a lookup"], "chats": 9,
         "prefer": {}}]}
    (w.out / "plan.json").write_text(json.dumps(plan), encoding="utf-8")


def _tree_bytes(*roots):
    for root in roots:
        for p in root.rglob("*"):
            if p.is_file():
                yield p, p.read_bytes()


def _assert_no_secrets(*roots):
    for p, data in _tree_bytes(*roots):
        text = data.decode("utf-8", errors="ignore")
        for s in ALL_SECRETS:
            core = s[8:40] if len(s) > 48 else s[len(s) // 2 : len(s) // 2 + 12]
            assert s not in text and core not in text, f"secret leaked into {p}"


EXPECT = {
    "vscode-copilot": [".agents/model-router/yardmaster.model-router.yml"],
    "copilot-cli": [".github/agents/ym-quick-questions.agent.md", "AGENTS.md"],
    "claude-code": ["CLAUDE.md", ".claude/agents/ym-quick-questions.md"],
    "codex": ["AGENTS.md"],
}


@pytest.mark.parametrize("target", list(EXPECT))
def test_full_flow_each_target(target, world, capsys):
    w = world
    out = _survey(w, capsys)
    assert "[REDACTED" in (w.out / "batch-001.txt").read_text(encoding="utf-8") and "claude-code:sessLeaky" in out + str(
        (w.out / "manifest.json").read_text(encoding="utf-8"))
    _fake_model(w, w.tmp)
    assert main(["validate", "verdicts", str(w.out / "verdicts.json")]) == 0
    assert main(["validate", "plan", str(w.out / "plan.json")]) == 0
    assert main(["preview", "1"]) == 0
    capsys.readouterr()

    assert main(["route", "--target", target, "--plan", str(w.out / "plan.json"), "--root", str(w.proj), "--dry-run"]) == 0
    dry = capsys.readouterr().out
    run_id, code = re.search(r"Run id: (\S+)\nApproval code: (\S+)", dry).groups()
    assert not any(w.proj.iterdir())  # a dry run writes nothing into the project
    assert main(["route", "--apply", run_id, "--code", code]) == 0

    for rel in EXPECT[target]:
        assert (w.proj / rel).is_file(), rel
    if target == "vscode-copilot":
        doc = yaml.safe_load((w.proj / EXPECT[target][0]).read_text(encoding="utf-8"))
        assert doc["version"] == 1 and {r["model"] for r in doc["routes"]} and all(set(r) == {"model", "when"} for r in doc["routes"])
    if target == "codex":
        prof = tomllib.loads(next(w.home.rglob("ym-*.config.toml")).read_text(encoding="utf-8"))
        assert set(prof) == {"model"}
    _assert_no_secrets(w.home, w.proj, w.out)  # state dir, record, report, written configs, batches, verdicts, plan

    assert main(["undo", run_id]) == 0
    assert not any(p.is_file() for p in w.proj.rglob("*"))
    assert not list(w.home.rglob("ym-*.config.toml"))
    assert main(["clean"]) == 0
    assert not w.out.exists()  # the survey folder (redacted chat text) is gone
    assert not [d for d in w.home.rglob("ym-*") if d.is_dir()]
    _assert_no_secrets(w.home, w.proj)
    captured = capsys.readouterr().out
    assert not any(s in captured for s in ALL_SECRETS)


def test_ledger_and_export_never_leak_the_planted_secrets(world, capsys):
    w = world
    base = ["--path", f"claude-code={w.trees['claude-code']}", "--path", f"vscode-copilot={w.trees['vscode-copilot']}", *RANGE]
    assert main(["ledger", *base]) == 0
    assert main(["export-md", *base, "--out", str(w.out)]) == 0
    text = capsys.readouterr().out + next(w.out.glob("*.md")).read_text(encoding="utf-8")
    assert not any(s in text for s in ALL_SECRETS) and "[REDACTED" in text
    assert ms(2026, 9, 1) > 0
