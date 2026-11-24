"""ClusterFuzzLite target: bytes given to the verdict and plan validators may only ever raise ValidationError.

build.sh copies the runtime to skill/ next to this file, so the target runs the code that ships, not a stub."""

import json
import os
import sys

import atheris

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "skill", "scripts"))

from yardmaster.pricing import default_pricing  # noqa: E402
from yardmaster.schema import ValidationError, validate_plan, validate_verdicts  # noqa: E402

PRICING = default_pricing({"HOME": "/nonexistent"}, "linux")


def TestOneInput(data: bytes) -> None:
    try:
        doc = json.loads(data)
    except (UnicodeDecodeError, ValueError, RecursionError):
        return
    for check in (lambda: validate_verdicts(doc, manifest_ids={"claude-code:c1"}, pricing=PRICING),
                  lambda: validate_plan(doc, pricing=PRICING)):
        try:
            check()
        except ValidationError:
            pass


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
