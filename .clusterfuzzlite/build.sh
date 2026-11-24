#!/bin/bash -eu
# Runs in the builder, in the repository root. PyInstaller must see the runtime and the model catalog as ordinary imports,
# so both go on PYTHONPATH, and the target loads the catalog from a generated module rather than from a file beside __file__.
BUILD=$(mktemp -d)
python3 -c "import json,sys; open(sys.argv[1], 'w').write('DATA = ' + repr(json.load(open('skills/yardmaster/scripts/yardmaster/models.json'))) + '\n')" "$BUILD/catalog_data.py"
export PYTHONPATH="$PWD/skills/yardmaster/scripts:$BUILD"
compile_python_fuzzer .clusterfuzzlite/fuzz_verdicts.py
