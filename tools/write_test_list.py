# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Write a dispatch input to the file the harness selection reads.

Specified by ``docs/design/consumer_ci.md`` section 6.

**This replaced a step that validated the entries itself and built a ``-k``
expression.** The harness does both now, by identifier rather than by substring
and inside collection, so this is reduced to the one thing a workflow has to
do: turn a text input into a file with one entry per line.

**It does not validate.** An entry naming no collected test is reported by the
run as a skip carrying ``QC_HARNESS_SELECTION_UNRESOLVED``, which is the whole
point of the file form: one typo costs that entry and not the run. Validating
here would restore the behaviour the harness design removed.
"""

import argparse
import os
import re
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    """Write the requested entries, one per line.

    Args:
        argv (list[str]): Command line arguments.

    Returns:
        int: ``0`` when a file was written, ``1`` when the input named nothing.
        **An empty input is refused here** rather than reaching the harness,
        because a dispatch with no tests named is a mistake at the form and a
        clearer message is available at this end.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args(argv)

    requested = [
        entry.strip()
        for entry in re.split(r"[,\n]", os.environ.get("REQUESTED", ""))
        if entry.strip()
    ]
    if not requested:
        print("::error::no test identifiers were supplied")
        return 1

    arguments.out.parent.mkdir(parents=True, exist_ok=True)
    arguments.out.write_text("\n".join(requested) + "\n", encoding="utf-8")
    print(f"count={len(requested)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
