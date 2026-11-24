# Contributing

1. Fork, branch, and keep the change small.
2. Set up: `python -m pip install -e ".[dev]"`.
3. Run `python -m pytest -q` and `ruff check .`. For security-sensitive changes also run `python -m pytest -m pentest -q` and `python -m pytest tests/fuzz -q`.
4. Write the test first. A new collector follows one pattern: verify the format against the live tool, add an anonymised fixture, then the collector, the writer, pentest cases and the docs row.
5. **Never commit real chat text.** Use `tools/make_fixture.py`, which rewrites ids and drops text.
6. The runtime stays standard library only. A new import, a network call, `subprocess`, `eval` or `pickle` in `skills/yardmaster/` fails CI.
7. If you add a security claim to the docs, cite the test that proves it as `tests/path.py::test_name`; `tests/unit/test_docs_links.py` checks it.

Report vulnerabilities privately, as described in [Security and compliance](Security-and-compliance).
