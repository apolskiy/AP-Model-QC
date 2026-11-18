# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""The carried-outcome artifacts a changed engine leaves behind, picked from a listing.

Created: 2026-11-17
Last updated: 2026-11-18

This file contains ``stale_carriers``, which picks out of an artifact listing
the identifiers of one engine's carried outcomes from the gate and the
regression run, and ``main``, the command line the version probe's dispatch job
runs for each changed engine before it deletes each identifier printed and
dispatches the engine's regression run.

The listing holds one artifact a line, its identifier and its name separated by
a space. A carried outcome is ``carry-after-<band>-<engine>-<os>`` from the
gate or ``carry-live-live-after-<band>-<engine>`` from the regression run;
every other artifact, another engine's included, is kept. A line that is not
an identifier and a name refuses the whole listing with
``QC_HARNESS_PARSER_ERROR`` and exit ``4``, printing nothing.

Specified by ``docs/design/consumer_ci.md`` section 4.23.3.
"""

import argparse
import logging
import re
from pathlib import Path
from typing import Final, Optional

logger = logging.getLogger(__name__)

_EXIT_PRINTED: Final[int] = 0
_EXIT_REFUSED: Final[int] = 4

_PARSER: Final[str] = "QC_HARNESS_PARSER_ERROR"

# ONE ARTIFACT A LINE: a numeric identifier, one space, a name without spaces.
_LINE: Final[re.Pattern[str]] = re.compile(r"(\d+) (\S+)")


def _carried_outcome(engine: str) -> re.Pattern[str]:
    """Return the pattern one engine's carried-outcome artifact names match.

    Args:
        engine (str): The engine whose model changed.

    Returns:
        re.Pattern: Matching the gate's ``carry-after-<band>-<engine>-<os>`` and
        the regression run's ``carry-live-live-after-<band>-<engine>``.
    """
    named = re.escape(engine)
    return re.compile(rf"carry-after-p\d+-{named}-.+|carry-live-live-after-p\d+-{named}")


def stale_carriers(listing: str, engine: str) -> list[str]:
    """Return the identifiers of one engine's carried outcomes, in listing order.

    Args:
        listing (str): One artifact a line, ``<identifier> <name>``.
        engine (str): The engine whose model changed.

    Returns:
        list[str]: The identifiers to delete.

    Raises:
        ValueError: With ``QC_HARNESS_PARSER_ERROR`` naming the first line that
            is not an identifier and a name.
    """
    pattern = _carried_outcome(engine)
    stale: list[str] = []
    for number, line in enumerate(listing.splitlines(), start=1):
        if not line.strip():
            continue
        parsed = _LINE.fullmatch(line.strip())
        if parsed is None:
            raise ValueError(
                f"{_PARSER}: artifact listing line {number} is not an identifier "
                f"and a name: {line!r}"
            )
        if pattern.fullmatch(parsed.group(2)):
            stale.append(parsed.group(1))
    return stale


def main(argv: Optional[list[str]] = None) -> int:
    """Print the identifiers of one engine's carried outcomes, or refuse.

    Args:
        argv (Optional[list]): Arguments, for calling in-process from a case.

    Returns:
        int: ``0`` printed the identifiers, one a line; ``4`` refused a
        malformed listing and printed none.
    """
    parser = argparse.ArgumentParser(
        prog="stale-carriers",
        description="Print the identifiers of a changed engine's carried-outcome artifacts",
    )
    parser.add_argument("--engine", required=True, help="The engine whose model changed")
    parser.add_argument("--artifacts", type=Path, required=True,
                        help="The listing, one '<identifier> <name>' a line")
    parsed = parser.parse_args(argv)
    try:
        stale = stale_carriers(parsed.artifacts.read_text(encoding="utf-8"), parsed.engine)
    except ValueError as error:
        logger.error("%s", error)
        return _EXIT_REFUSED
    for identifier in stale:
        print(identifier)
    logger.info("%d carried-outcome artifact(s) of %s are stale", len(stale), parsed.engine)
    return _EXIT_PRINTED


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(main())
