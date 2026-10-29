# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Support code running this repository's own suite under a real Allure reporter.

Created: 2026-10-28
Last updated: 2026-10-28

This file provides ``published_results``, which runs a selection of this
repository's cases in a subprocess that writes raw Allure results into a
directory the caller names, and returns those results parsed.

It serves the grouping preconditions in ``mqc_uni_grouping.py``. They are here
rather than in that module because a collected module holds cases and nothing
else (harness ``harness_test_taxonomy.md`` section 13).

**A real reporter rather than a double, and a subprocess rather than a call.**
What is being asserted is that this repository's ``conftest.py`` wires the
labelling hooks at all, and a direct call to a shared function would assert
only that the shared function works, which the harness already does against
planted items. The run therefore goes through pytest from this root, so the
conftest in force is the one shipped here.

**Replay mode, so the run contacts nothing and costs nothing.** A graded case
is selected by identifier and read from its recorded fixture, which is what
makes this precondition runnable in a gate with no credential.

Specified by ``docs/design/consumer_ci.md`` section 4.22.3.
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Final

# HOW LONG A PROBE RUN MAY TAKE. A replayed case runs in seconds, and the
# ceiling exists so a hung subprocess fails the precondition rather than the
# job's own time limit.
_TIMEOUT_SEC: Final[int] = 300


def published_results(
    root: Path, selection: list[str], results: Path
) -> list[dict[str, Any]]:
    """Run a selection of this repository's cases and return what was published.

    Args:
        root (Path): The repository root, which the run is made from so that
            this repository's ``conftest.py`` is the one in force.
        selection (list): The pytest arguments naming what to run, such as a
            marker expression with an engine and a mode.
        results (Path): Where the reporter writes, usually under ``tmp_path``.

    Returns:
        list[dict]: One parsed result per case that ran, in file order, empty
        where the run published none. **Empty is returned rather than raised
        on**, because every assertion a case reaches is one of its recorded
        steps and a helper raising one would consume a number the case did not
        declare (harness ``harness_test_taxonomy.md`` section 8.2.4).
    """
    subprocess.run(
        [
            sys.executable, "-m", "pytest", "-q", "--no-header",
            "-p", "no:randomly", *selection, f"--alluredir={results}",
        ],
        cwd=root, capture_output=True, text=True, check=False,
        timeout=_TIMEOUT_SEC, stdin=subprocess.DEVNULL,
    )
    return [
        json.loads(written.read_text(encoding="utf-8"))
        for written in sorted(results.glob("*-result.json"))
    ]
