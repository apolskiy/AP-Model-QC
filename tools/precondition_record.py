# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""The declaration a band makes when the precondition record it downloaded is not there.

Created: 2026-11-18
Last updated: 2026-11-18

This file contains ``main``, the command line the band action runs before its
band where no earlier step declared an artifact missing. Given a record path
that is not a file, it writes ``missing=precondition_record=<path>`` to the step
output file, so the band runs with ``--missing-artifact`` and every graded case
skips at setup with ``QC_HARNESS_ARTIFACT_MISSING``; given a file, it writes
nothing. It exits ``0`` either way.

Specified by ``docs/design/consumer_ci.md`` section 3.12.1.3.
"""

import argparse
import logging
from pathlib import Path
from typing import Final, Optional

logger = logging.getLogger(__name__)

_EXIT_WRITTEN: Final[int] = 0

_MISSING: Final[str] = "QC_HARNESS_ARTIFACT_MISSING"
_KIND: Final[str] = "precondition_record"


def main(argv: Optional[list[str]] = None) -> int:
    """Declare the precondition record missing where it is not a file.

    Args:
        argv (Optional[list]): Arguments, for calling in-process from a case.

    Returns:
        int: ``0``, having declared the record or found it present.
    """
    parser = argparse.ArgumentParser(
        prog="precondition-record",
        description="Declare a band's precondition record missing when its download found nothing",
    )
    parser.add_argument("--record", type=Path, required=True,
                        help="Where the band reads the precondition record from")
    parser.add_argument("--output", type=Path, required=True,
                        help="Where to append missing=<KIND=PATH>, the step output file")
    parsed = parser.parse_args(argv)
    if parsed.record.is_file():
        logger.info("The precondition record is at %s", parsed.record)
        return _EXIT_WRITTEN
    # A RUN GIVEN NO RECORD READS AS UNGATED, so the record is declared rather
    # than left absent (harness `cmn_verdict_and_cli.md` section 7.1.4).
    logger.error("%s: %s %s, its download found nothing", _MISSING, _KIND, parsed.record)
    with parsed.output.open("a", encoding="utf-8") as output:
        output.write(f"missing={_KIND}={parsed.record}\n")
    return _EXIT_WRITTEN


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(main())
