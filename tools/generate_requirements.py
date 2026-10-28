# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Writes ``requirements.txt`` and ``requirements-dev.txt`` from ``pyproject.toml``.

Created: 2026-10-28
Last updated: 2026-10-28

This file contains ``main``, which writes this repository's two derived
requirements files. The reading, rendering and comparison live in the harness,
in ``cmn.dependency_declaration``, so this generator, the harness's own and the
cases on both sides run one implementation.

**A contributor runs it after changing a dependency**, and
``MQC_CAS_UNI_115785`` regenerates the contents and fails the run when the
committed files no longer match the declaration.

**This repository had no requirements files until 2026-10-28**, and the gap
hid a defect rather than being a cosmetic difference: ``pyproject.toml``
declared the harness without its ``dev`` extra while the gate workflows
hand-wrote ``ap-harness-qc[dev]``, so ``pip install --editable ".[dev]"`` in a
fresh clone installed no pytest and the suite could not be collected.

Specified by ``docs/design/consumer_ci.md`` section 5.5.

Run it with ``python tools/generate_requirements.py`` after changing a
dependency. The check tells you when you have forgotten.
"""

import sys
from pathlib import Path
from typing import Final

from cmn.dependency_declaration import generated_files

_ENCODING: Final[str] = "utf-8"


def main() -> int:
    """Write this repository's generated requirements files.

    Returns:
        int: Zero on success.
    """
    root = Path(__file__).resolve().parents[1]
    for path, contents in generated_files(root).items():
        path.write_text(contents, encoding=_ENCODING, newline="\n")
        print(f"wrote {path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
