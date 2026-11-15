# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Support code running the regression run's calibration check against a written record.

Created: 2026-11-15
Last updated: 2026-11-15

This file contains ``JUDGE``, ``SERVED_VERSION`` and ``SERVED_DIGEST``, the
judge and what it serves in every case; ``write_record``, which writes a
record calibrating that judge over the samples in this checkout; and
``run_check``, which runs ``tools/calibration_ready.py`` as the regression
run's ``calibration`` job does, with what the judge serves injected so no
judge is called.

**Not a test module.** ``pytest.ini`` collects ``mqc_*.py``, so this name sits
outside that pattern deliberately, as ``workflow_support.py`` does.

Specified by ``docs/design/consumer_ci.md`` section 7.9.3.
"""

from pathlib import Path
from typing import Final

from cmn.calibration_record import CalibrationRecord, write_calibration_record

from tests.cases.calibration_support import samples_digest
from tools.calibration_ready import main

JUDGE: Final[str] = "claude"
SERVED_VERSION: Final[str] = "judge-2026-11-01"
SERVED_DIGEST: Final[str] = "a1b2c3d4"


def write_record(directory: Path) -> Path:
    """Write a record calibrating the judge as it serves ``SERVED_VERSION``.

    Args:
        directory (Path): Where the record goes.

    Returns:
        Path: The record written.
    """
    path = directory / "records" / "calibration" / f"{JUDGE}.json"
    write_calibration_record(path, CalibrationRecord(
        judge_engine=JUDGE,
        judge_model="claude-model",
        judge_served_version=SERVED_VERSION,
        judge_served_digest=SERVED_DIGEST,
        samples_digest=samples_digest(),
        code_ref="harness",
        case_ref="cases",
        recorded="2026-11-01",
        families={},
    ))
    return path


def run_check(record: Path, conclusion: str, version: str = SERVED_VERSION,
              digest: str = SERVED_DIGEST) -> int:
    """Run the check as the regression run's calibration job does.

    Args:
        record (Path): The record the job took from the default branch.
        conclusion (str): The latest calibration run's conclusion.
        version (str): What the judge serves now.
        digest (str): The digest of that.

    Returns:
        int: The exit status.
    """
    def served(_engine: str, _model: str) -> dict[str, str]:
        return {"served_version": version, "served_digest": digest}

    return main(
        ["--judge", JUDGE, "--record", str(record), "--conclusion", conclusion],
        served_reader=served,
    )
