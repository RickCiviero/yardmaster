"""Property-based fuzzing. 200 examples per test by default (a PR check); set FUZZ_EXAMPLES=20000 for the nightly job.

The properties: nothing raises except the documented error types, no file is written outside the temp dir, and a secret
embedded in arbitrary text never survives redaction."""

import os
import shutil
import tempfile
import tomllib
from pathlib import Path

import pytest
import yaml
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from secrets_corpus import SECRETS
from synthetic import SINCE, UNTIL, copilot_home, vscode_user
from synthetic_claude import claude_home
from synthetic_codex import codex_home
from yardmaster.blocks import BlockError, markers, replace_block
from yardmaster.collectors import COLLECTORS, CollectorContext
from yardmaster.emit import toml_str, yaml_str
from yardmaster.pricing import default_pricing
from yardmaster.redact import redact
from yardmaster.resolve import resolve_plan
from yardmaster.schema import VERDICT_KEYS, ValidationError, validate_plan, validate_verdicts
from yardmaster.writers import WRITERS

pytestmark = pytest.mark.fuzz
FUZZ = settings(max_examples=int(os.environ.get("FUZZ_EXAMPLES", "200")), deadline=None, suppress_health_check=list(HealthCheck))
PRICING = default_pricing({"HOME": "/nonexistent"}, "linux")

scalars = st.none() | st.booleans() | st.integers() | st.floats(allow_nan=True, allow_infinity=True) | st.text(max_size=80)
json_st = st.recursive(scalars, lambda c: st.lists(c, max_size=4) | st.dictionaries(st.text(max_size=12), c, max_size=6), max_leaves=30)


# --------------------------------------------------------------------------------------- validators
@FUZZ
@given(json_st)
def test_validators_only_ever_raise_validation_error(obj):
    for fn in (lambda: validate_verdicts(obj, manifest_ids={"claude-code:c1"}, pricing=PRICING), lambda: validate_plan(obj, pricing=PRICING)):
        try:
            fn()
        except ValidationError:
            pass


_GOOD = {"chat_id": "claude-code:c1", "task_group": "build-and-fix", "task_summary": "Built a parser", "model_used": "opus",
         "outcome": "ok", "sufficient_tier": "standard", "cheapest_sufficient_model": "sonnet", "confidence": 0.9, "reason": "Routine"}


@FUZZ
@given(st.fixed_dictionaries({k: st.just(_GOOD[k]) | json_st for k in VERDICT_KEYS}))
def test_near_valid_verdicts_are_accepted_only_if_truly_valid(v):
    try:
        out = validate_verdicts([v], manifest_ids={"claude-code:c1"}, pricing=PRICING)
    except ValidationError:
        return
    (verdict,) = out  # accepted: then every field has its exact validated shape
    assert 0 <= verdict.confidence <= 1 and verdict.sufficient_tier in ("light", "standard", "heavy", "frontier")
    assert verdict.outcome in ("ok", "struggled", "failed") and verdict.chat_id == "claude-code:c1"
    assert all("\n" not in x and "`" not in x and "://" not in x for x in (verdict.task_summary, verdict.reason, verdict.model_used))


# --------------------------------------------------------------------------------------- emitters and writers
@FUZZ
@given(st.text(max_size=400))
def test_emitted_scalars_always_round_trip(s):
    assert yaml.safe_load(f"k: {yaml_str(s)}\n") == {"k": s}
    assert tomllib.loads(f"k = {toml_str(s)}")["k"] == s


@FUZZ
@given(st.text(max_size=300), st.text(max_size=120), st.text(max_size=80))
def test_any_text_that_passes_validation_cannot_change_a_written_files_structure(when, desc, example):
    plan_doc = {"version": 1, "description": desc, "groups": [
        {"name": "build-and-fix", "tier": "heavy", "when": when, "examples": [example], "chats": 1, "prefer": {}},
        {"name": "quick-questions", "tier": "light", "when": "Quick answers.", "examples": [], "chats": 1, "prefer": {}}]}
    try:
        plan = validate_plan(plan_doc, pricing=PRICING)
    except ValidationError:
        return
    with tempfile.TemporaryDirectory() as td:
        root, env = Path(td) / "proj", {"HOME": str(Path(td) / "home"), "USERPROFILE": str(Path(td) / "home")}
        for harness, write in WRITERS.items():
            for c in write(plan, resolve_plan(plan, harness, PRICING, frozenset()), root, False, env):
                c.path.resolve().relative_to(c.root.resolve())  # contained
                if c.path.name.endswith(".model-router.yml"):
                    doc = yaml.safe_load(c.new)
                    assert doc["description"] == desc and doc["routes"][0]["when"] == when and len(doc["routes"]) == 2
                elif c.new.startswith("---\n"):
                    assert set(yaml.safe_load(c.new.split("---\n")[1])) == {"name", "description", "model"}
                elif c.path.name == "config.toml":
                    assert set(tomllib.loads(c.new)["profiles"]) == {"ym-build-and-fix", "ym-quick-questions"}
                else:
                    ls = [ln.strip() for ln in c.new.splitlines()]
                    assert sum(ln.startswith("<!-- yardmaster:begin") for ln in ls) == sum(ln.startswith("<!-- yardmaster:end") for ln in ls) == 1


# --------------------------------------------------------------------------------------- block editor
@FUZZ
@given(st.lists(st.sampled_from([markers("md")[0], markers("md")[1], "x", "", "inline <!-- yardmaster:begin v1 --> mention", "  " + markers("md")[0]]),
                max_size=8), st.sampled_from(["\n", "\r\n"]), st.lists(st.text(max_size=20), max_size=3))
def test_replace_block_never_corrupts_a_file(lines, eol, body_lines):
    text, body = eol.join(lines), "\n".join(body_lines)
    try:
        out = replace_block(text, body, style="md")
    except BlockError:
        return
    ls = [ln.strip() for ln in out.splitlines()]
    assert ls.count(markers("md")[0]) == 1 and ls.count(markers("md")[1]) == 1 and ls.index(markers("md")[0]) < ls.index(markers("md")[1])
    assert replace_block(out, body, style="md") == out  # idempotent
    if not any(markers("md")[0] in ln or markers("md")[1] in ln for ln in lines):
        assert out.startswith(text)  # an untouched file only ever gains a block at the end


# --------------------------------------------------------------------------------------- redactor
@FUZZ
@given(st.text(max_size=3000))
def test_redact_never_raises_and_always_returns_encodable_text(s):
    out, counts = redact(s, pii=True)
    out.encode("utf-8")
    assert all(v > 0 for v in counts.values())


@FUZZ
@given(st.text(max_size=400), st.sampled_from(sorted(SECRETS)), st.text(max_size=400))
def test_a_secret_embedded_in_arbitrary_text_never_survives(prefix, key, suffix):
    secret = SECRETS[key]
    out, _ = redact(f"{prefix} {secret} {suffix}")
    assert secret not in out


# --------------------------------------------------------------------------------------- collectors
@pytest.fixture(scope="module")
def base_trees(tmp_path_factory):
    root = tmp_path_factory.mktemp("fuzzbase")
    return {"vscode-copilot": vscode_user(root / "vs"), "copilot-cli": copilot_home(root / "cli"),
            "claude-code": claude_home(root / "cc"), "codex": codex_home(root / "cx")}, root


@FUZZ
@given(st.integers(min_value=0, max_value=10**6), st.integers(min_value=0, max_value=10**6), st.integers(0, 3),
       st.binary(max_size=64), st.sampled_from(["flip", "truncate", "insert", "wipe"]))
def test_collectors_survive_byte_level_corruption(base_trees, pick, offset, which_tree, junk, op):
    trees, base = base_trees
    harness = list(trees)[which_tree]
    with tempfile.TemporaryDirectory() as td:
        work = Path(td) / "t"
        shutil.copytree(base, work)
        rel = trees[harness].relative_to(base)
        files = sorted(p for p in (work / rel).rglob("*") if p.is_file())
        if files:
            f = files[pick % len(files)]
            data = bytearray(f.read_bytes())
            at = offset % (len(data) + 1)
            if op == "flip" and data:
                data[at % len(data)] ^= 0xFF
            elif op == "truncate":
                del data[at:]
            elif op == "insert":
                data[at:at] = junk
            else:
                data[:] = junk
            f.write_bytes(bytes(data))
        ctx = CollectorContext(since=SINCE, until=UNTIL, env={}, platform="linux", roots=[work / rel])
        chats = COLLECTORS[harness](ctx)  # must never raise
        assert isinstance(chats, list) and all(c.first <= c.last for c in chats)
