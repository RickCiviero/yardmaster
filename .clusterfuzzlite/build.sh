#!/bin/bash -eu
# Runs in the builder, in the repository root. The runtime is copied next to the target so the target imports what ships.
cp -r skills/yardmaster "$OUT/skill"
cp .clusterfuzzlite/fuzz_verdicts.py "$OUT/fuzz_verdicts"
chmod +x "$OUT/fuzz_verdicts"  # a plain script, not a PyInstaller bundle: its __file__ must point beside skill/
