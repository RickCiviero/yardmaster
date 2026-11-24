#!/bin/bash -eu
# Runs in the builder, in the repository root. The runtime is copied next to the target so the target imports what ships.
cp -r skills/yardmaster "$OUT/skill"
compile_python_fuzzer .clusterfuzzlite/fuzz_verdicts.py
