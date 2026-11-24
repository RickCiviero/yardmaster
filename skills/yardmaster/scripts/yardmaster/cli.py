"""Command line. Prints ids, counts and paths only; chat text appears solely in `preview`."""

import argparse
import json
import os
import shutil
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from . import __version__, paths
from .batch import make_batches, write_batches
from .collectors import COLLECTORS, CollectorContext, in_project
from .detect import detect_harness
from .doctor import doctor, render_doctor
from .export_md import export_md
from .ledger import ledger, render_ledger
from .pricing import Pricing, default_pricing
from .route import RouteError, apply, dry_run, undo
from .safe_io import load_json, make_private_dir, read_text
from .schema import ValidationError, load_manifest_ids, validate_plan, validate_verdicts
from .settings import load_settings
from .timeutil import resolve_range, to_utc_bounds
from .writers import WRITERS

GATE = 0.10  # refuse to analyse if the analysis would cost more than 10% of the period's spend
VERDICT_TOKENS, OVERHEAD_TOKENS = 150, 1500  # per chat output / per batch protocol prompt


def _common() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(add_help=False)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--current", action="store_true", help="1st of this month .. today")
    g.add_argument("--last", action="store_true", help="the whole previous month")
    g.add_argument("--from", dest="date_from", metavar="YYYY-MM-DD", help="start date, inclusive")
    p.add_argument("--to", dest="date_to", metavar="YYYY-MM-DD", help="end date, inclusive (default: today)")
    p.add_argument("--harness", help="comma-separated harness ids (default: all)")
    p.add_argument("--path", action="append", default=[], metavar="HARNESS=DIR", help="override a harness's history root")
    p.add_argument("--project", nargs="?", const=os.getcwd(), metavar="DIR", help="only chats of this project (default: cwd)")
    p.add_argument("--exclude-workspace", action="append", default=[], metavar="DIR")
    p.add_argument("--redact-pii", action="store_true", help="also redact emails, IPs and home paths")
    return p


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="yardmaster", description="Right job. Right track. Lowest fare.")
    ap.add_argument("--version", action="version", version=f"yardmaster {__version__}")
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("survey", parents=[_common()], help="collect, redact and batch chats for analysis")
    s.add_argument("--yes-expensive", action="store_true")
    s.add_argument("--out", help="directory for the batches (default: a private temp dir)")
    s.add_argument("--batch-tokens", type=int, default=60_000)
    s.add_argument("--analysis-model", metavar="[HARNESS:]MODEL", help="model used to price the analysis")
    pv = sub.add_parser("preview", help="print batch N exactly as it would be sent")
    pv.add_argument("n", type=int)
    sub.add_parser("clean", help="delete the survey directory")
    sub.add_parser("ledger", parents=[_common()], help="spend per harness and model (no model call)")
    sub.add_parser("doctor", help="what Yardmaster can read and write here, and what is unverified")
    x = sub.add_parser("export-md", parents=[_common()], help="write a redacted Markdown archive of the range")
    x.add_argument("--out", default=".", help="folder for the .md file (default: cwd)")
    x.add_argument("--overwrite", action="store_true")
    x.add_argument("--force", action="store_true", help="allow writing inside a git repository")
    r = sub.add_parser("route", help="preview (--dry-run) or write (--apply RUN_ID) the routing config")
    r.add_argument("--target", help="harness id(s), comma-separated, or: all | auto")
    r.add_argument("--plan", help="the validated plan.json")
    r.add_argument("--global", dest="global_", action="store_true", help="write the harness's user-level config")
    r.add_argument("--root", default=os.getcwd(), help="project root (default: cwd)")
    mode = r.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", metavar="RUN_ID")
    r.add_argument("--code", help="the approval code printed with the diff")
    u = sub.add_parser("undo", help="restore the files changed by the last (or given) applied run")
    u.add_argument("run_id", nargs="?")
    v = sub.add_parser("validate", help="schema-check the model's verdicts.json or plan.json")
    v.add_argument("kind", choices=["verdicts", "plan"])
    v.add_argument("file")
    v.add_argument("--manifest", help="manifest.json of the survey (default: the current survey)")
    return ap


# ------------------------------------------------------------------ shared steps
def _pricing() -> Pricing:
    return default_pricing(os.environ, sys.platform)


def _harnesses(args, settings) -> list[str]:
    want = [h.strip() for h in args.harness.split(",")] if args.harness else list(COLLECTORS)
    unknown = [h for h in want if h not in COLLECTORS]
    if unknown:
        raise ValueError(f"unknown harness {', '.join(unknown)}; known: {', '.join(COLLECTORS)}")
    return [h for h in want if settings.harnesses is None or h in settings.harnesses]


def _roots(args) -> dict[str, Path]:
    out = {}
    for item in args.path:
        h, sep, d = item.partition("=")
        if not sep or h not in COLLECTORS or not d:
            raise ValueError(f"--path expects HARNESS=DIR with a known harness, got {item!r}")
        out[h] = Path(d)
    return out


def _collect(args, harnesses: list[str]):
    r = resolve_range(current=args.current, last=args.last, date_from=args.date_from, date_to=args.date_to,
                      today=date.today())
    since, until = to_utc_bounds(r)
    roots, per, chats, warnings = _roots(args), {}, [], []
    for h in harnesses:
        ctx = CollectorContext(since, until, os.environ, sys.platform, [roots[h]] if h in roots else None,
                               Path(args.project) if args.project else None)
        try:
            found = COLLECTORS[h](ctx)
        except Exception as e:  # one broken store must not sink the others; never echo its content
            warnings.append(f"{h}: collector failed ({type(e).__name__})")
            found = []
        warnings += [f"{h}: {w}" for w in ctx.warnings]
        found = [c for c in found if not any(c.workspace and in_project(c.workspace, Path(x)) for x in args.exclude_workspace)]
        per[h] = found
        chats += found
    return r, per, chats, warnings


# ---------------------------------------------------------------------- commands
def _survey_pointer() -> Path:
    return paths.state_dir(os.environ, sys.platform) / "survey.json"


def _analysis_cost(pricing: Pricing, args, harnesses: list[str], n_batches: int, tokens: int, n_chats: int):
    harness, _, name = (args.analysis_model or "").rpartition(":") if args.analysis_model else ("", "", "")
    harness = harness or detect_harness(os.environ) or (harnesses[0] if harnesses else "claude-code")
    model = pricing.get(harness, name) if name else None
    if model is None:
        heavy = [m for m in pricing.models(harness) if m.tier == "heavy"]
        model = max(heavy, key=lambda m: m.sort_key) if heavy else None
    if model is None:
        return 0.0, f"{harness}:unknown"
    if model.input is not None:
        cost = model.unit_cost(tokens + OVERHEAD_TOKENS * n_batches, VERDICT_TOKENS * n_chats + 600, 0)
    else:
        cost = model.multiplier * (n_batches + 1) * 0.01  # credits per request x requests x $0.01
    return cost, f"{harness}:{model.id}"


def _cmd_survey(args) -> int:
    settings, pricing = load_settings(os.environ, sys.platform), _pricing()
    r, per, chats, warnings = _collect(args, _harnesses(args, settings))
    print(f"Range: {r.start} .. {r.end} (local time, inclusive)")
    for h, found in per.items():
        print(f"  {h:<16} " + (f"{len(found)} chats, {sum(c.requests for c in found)} requests" if found else f"no chats found for {h}"))
    for w in warnings:
        print(f"  warning: {w}")
    if not chats:
        return 0
    print("Workspaces included (edit with --exclude-workspace):")
    for ws, n in Counter(c.workspace or "-" for c in chats).most_common():
        print(f"  {n:>4} chats  {ws}")
    batches, counts = make_batches(chats, pii=settings.redact_pii or args.redact_pii, max_tokens=args.batch_tokens)
    tokens = sum(b.est_tokens for b in batches)
    print(f"Redacted before sending: {sum(counts.values())}" + (f" ({', '.join(f'{k} {v}' for k, v in counts.most_common())})" if counts else ""))
    print(f"Batches: {len(batches)} (~{tokens:,} tokens)")
    spend = ledger(chats, pricing)["total_est_usd"]
    cost, via = _analysis_cost(pricing, args, list(per), len(batches), tokens, len(chats))
    print(f"Spend in range: ${spend:,.2f} (estimated) | analysis: ~${cost:,.4f} via {via} (estimated)")
    if not pricing.verified:
        print("  note: pricing.json is UNVERIFIED (estimated prices); check docs/wiki/Pricing.md")
    if len(batches) > settings.max_batches:
        print(f"Too many batches: {len(batches)} exceed max_batches ({settings.max_batches}). Narrow the range, harnesses or workspaces.")
        return 4
    if spend > 0 and cost > GATE * spend and not args.yes_expensive:
        print(f"The analysis would cost ~${cost:,.4f}, more than {GATE:.0%} of the ${spend:,.2f} spent. Re-run with --yes-expensive to continue.")
        return 3
    _cmd_clean(None)  # a new survey replaces the previous one; never leave old chat data behind
    out = Path(args.out) if args.out else make_private_dir()
    if args.out:
        if out.exists() and any(out.iterdir()):
            print(f"Refusing to write into non-empty {out}")
            return 2
        out.mkdir(parents=True, exist_ok=True)
        if os.name == "posix":
            os.chmod(out, 0o700)
    write_batches(batches, out)
    ptr = _survey_pointer()
    ptr.parent.mkdir(parents=True, exist_ok=True)
    ptr.write_text(json.dumps({"dir": str(out)}), encoding="utf-8")
    print(f"Batches written to: {out}")
    return 0


def _survey_dir() -> Path | None:
    try:
        return Path(json.loads(read_text(_survey_pointer()))["dir"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _cmd_preview(args) -> int:
    d = _survey_dir()
    f = d / f"batch-{args.n:03d}.txt" if d else None
    if not f or not f.is_file():
        print("No such batch. Run `survey` first.")
        return 2
    sys.stdout.write(read_text(f))
    return 0


def _cmd_clean(_args) -> int:
    d = _survey_dir()
    if d and d.is_dir() and (d / "manifest.json").is_file():  # only ever delete what survey wrote
        for f in d.iterdir():
            if f.is_file() and (f.name.startswith("batch-") or f.name in {"manifest.json", "verdicts.json", "plan.json"}):
                f.unlink()
        try:
            d.rmdir()
        except OSError:
            pass
    shutil.rmtree(_survey_pointer(), ignore_errors=True) if _survey_pointer().is_dir() else _survey_pointer().unlink(missing_ok=True)
    return 0


def _cmd_ledger(args) -> int:
    settings = load_settings(os.environ, sys.platform)
    _, _, chats, warnings = _collect(args, _harnesses(args, settings))
    for w in warnings:
        print(f"warning: {w}")
    print(render_ledger(ledger(chats, _pricing())), end="")
    return 0


def _cmd_validate(args) -> int:
    doc = load_json(Path(args.file))
    if doc is None:
        print(f"error: cannot read {args.file} as JSON")
        return 2
    pricing = _pricing()
    try:
        if args.kind == "plan":
            plan = validate_plan(doc, pricing=pricing)
            print(f"OK: plan with {len(plan.groups)} groups")
            return 0
        d = _survey_dir()
        manifest = Path(args.manifest) if args.manifest else (d / "manifest.json" if d else None)
        m = load_json(manifest) if manifest else None
        if not isinstance(m, dict):
            print("error: no manifest; run `survey` first or pass --manifest")
            return 2
        verdicts = validate_verdicts(doc, manifest_ids=load_manifest_ids(m), pricing=pricing)
        print(f"OK: {len(verdicts)} verdicts")
        return 0
    except ValidationError as e:  # message holds a JSON pointer and a reason, never the offending value
        print(f"INVALID at {e}")
        return 1


def _cmd_doctor(_args) -> int:
    rows = doctor(os.environ, sys.platform)
    print(render_doctor(rows), end="")
    return 1 if any(status == "fail" for _, status, _ in rows) else 0


def _cmd_export_md(args) -> int:
    settings = load_settings(os.environ, sys.platform)
    r, _, chats, warnings = _collect(args, _harnesses(args, settings))
    for w in warnings:
        print(f"warning: {w}")
    out = export_md(chats, r, Path(args.out), pii=settings.redact_pii or args.redact_pii, overwrite=args.overwrite, force=args.force)
    print(f"Written: {out} ({len(chats)} chats, redacted)")
    return 0


def _targets(spec: str, settings) -> list[str]:
    if spec == "auto":
        found = detect_harness(os.environ)
        if not found:
            raise ValueError("--target auto cannot tell which harness is running; pass --target explicitly")
        return [found]
    if spec == "all":
        return [t for t in WRITERS if settings.harnesses is None or t in settings.harnesses]
    return [t.strip() for t in spec.split(",") if t.strip()]


def _cmd_route(args) -> int:
    if args.apply:
        written = apply(args.apply, args.code, interactive=sys.stdin.isatty(), env=os.environ, platform=sys.platform)
        print(f"Applied: {len(written)} file(s) written. Undo with: yardmaster undo {args.apply}")
        for w in written:
            print(f"  {w}")
        return 0
    if not args.dry_run:
        print("error: give --dry-run (preview) or --apply RUN_ID")
        return 2
    if not args.plan or not args.target:
        print("error: --dry-run needs --plan and --target")
        return 2
    settings = load_settings(os.environ, sys.platform)
    dry_run(Path(args.plan), _targets(args.target, settings), Path(args.root), args.global_, os.environ, sys.platform,
            settings=settings)
    return 0


def _cmd_undo(args) -> int:
    restored = undo(args.run_id, os.environ, sys.platform)
    print(f"Restored {len(restored)} file(s).")
    return 0


COMMANDS = {
    "doctor": _cmd_doctor,
    "export-md": _cmd_export_md,
    "route": _cmd_route,
    "undo": _cmd_undo,
    "survey": _cmd_survey,
    "preview": _cmd_preview,
    "clean": _cmd_clean,
    "ledger": _cmd_ledger,
    "validate": _cmd_validate,
}


def main(argv: list[str] | None = None) -> int:
    ap = _build_parser()
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:  # argparse exits on --version/--help/errors; the CLI returns codes instead
        return e.code if isinstance(e.code, int) else 2
    if not args.cmd:
        ap.print_help()
        return 2
    try:
        return COMMANDS[args.cmd](args)
    except RouteError as e:
        print(f"error: {e}")
        return 1
    except ValidationError as e:  # a JSON pointer and a reason, never the offending value
        print(f"INVALID at {e}")
        return 1
    except (ValueError, OSError) as e:
        print(f"error: {e}")
        return 2
