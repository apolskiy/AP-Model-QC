# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""The calibration check a regression run makes before any live band spends.

Created: 2026-11-15
Last updated: 2026-11-15

This file contains ``calibration_refusal``, which says why a judge may not
grade a regression run, or nothing when it may, and ``main``, the command line
the regression run's ``calibration`` job runs.

**It checks calibration and never runs it.** Two conditions, both required:
the latest completed ``calibrate-<judge>.yml`` run on the default branch
concluded success, which the job reads through the GitHub API and passes as
``--conclusion``; and the record at the head of the default branch covers the
judge as it serves now, judged by the harness ``record_invalidity`` against the
samples in this checkout. Exit ``0`` passed and ``3`` refused with
``QC_HARNESS_JUDGE_UNCALIBRATED``, an instrument problem rather than a model
finding, before anything is spent.

Specified by ``docs/design/consumer_ci.md`` section 7.9.3.
"""

import argparse
import sys
from pathlib import Path
from typing import Callable, Final, Mapping, Optional

from cmn.calibration_record import CalibrationRecord, read_calibration_record, record_invalidity
from cmn.config import load_engines, packaged_roster_path

from tests.cases.calibration_support import samples_digest

_EXIT_PASSED: Final[int] = 0
_EXIT_REFUSED: Final[int] = 3
_UNCALIBRATED: Final[str] = "QC_HARNESS_JUDGE_UNCALIBRATED"
_SUCCESS: Final[str] = "success"

ServedReader = Callable[[str, str], dict[str, str]]


def calibration_refusal(conclusion: str, record: Optional[CalibrationRecord], judge: str,
                        served: Mapping[str, str], digest: str) -> Optional[str]:
    """Return why the judge may not grade a regression run, or None.

    Args:
        conclusion (str): The latest completed calibration run's conclusion,
            empty where none completed.
        record (Optional[CalibrationRecord]): The record read, None if absent.
        judge (str): The judge engine.
        served (Mapping[str, str]): What the judge serves now.
        digest (str): The digest of the calibration samples in this checkout.

    Returns:
        Optional[str]: The refusal, carrying its code, or None.
    """
    if conclusion != _SUCCESS:
        state = f"concluded {conclusion}" if conclusion else "none completed"
        return f"{_UNCALIBRATED}: the latest calibrate-{judge}.yml run {state}"
    reason = record_invalidity(record, judge, served, digest)
    return f"{_UNCALIBRATED}: {reason}" if reason else None


def _served_facts(engine: str, model: str) -> dict[str, str]:
    """Ask the judge's provider what it serves.

    Args:
        engine (str): The judge engine.
        model (str): The judge model.

    Returns:
        dict[str, str]: ``served_version`` and ``served_digest``, empty on failure.
    """
    from execution.preflight import served_facts  # pylint: disable=import-outside-toplevel
    return served_facts(engine, model)


def main(argv: Optional[list[str]] = None, *,
         served_reader: Optional[ServedReader] = None) -> int:
    """Check the judge's calibration and print the outcome.

    Args:
        argv (Optional[list[str]]): The arguments, ``sys.argv`` where None.
        served_reader (Optional[ServedReader]): Reads what the judge serves,
            the provider by default.

    Returns:
        int: ``0`` where the judge may grade, ``3`` where it may not.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--judge", required=True, help="The judge engine.")
    parser.add_argument("--record", required=True, type=Path,
                        help="The record taken from the head of the default branch.")
    parser.add_argument("--conclusion", default="",
                        help="The latest completed calibration run's conclusion.")
    arguments = parser.parse_args(argv)
    try:
        record = read_calibration_record(arguments.record)
    except ValueError as error:
        print(f"{_UNCALIBRATED}: {error}")
        return _EXIT_REFUSED
    entry = load_engines(packaged_roster_path()).get(arguments.judge)
    served: Mapping[str, str] = {}
    if record is not None and arguments.conclusion == _SUCCESS:
        served = (served_reader or _served_facts)(
            arguments.judge, entry.model if entry is not None else "")
    refusal = calibration_refusal(arguments.conclusion, record, arguments.judge,
                                  served, samples_digest())
    if refusal:
        print(refusal)
        return _EXIT_REFUSED
    print(f"Calibration of {arguments.judge} is green and covers the model it serves now")
    return _EXIT_PASSED


if __name__ == "__main__":
    sys.exit(main())
