# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""The quarantine tool, which re-runs an engine's quarantined cases and rewrites its file.

Created: 2026-10-02
Last updated: 2026-11-16

This file contains ``main``, which loads ``config/quarantine/<engine>.yaml``,
re-observes every case in it, lets the harness decide what each entry becomes
and writes the file back; ``build_parser``, its arguments; ``plan_dependents``,
which adds the dependents of a quarantined foundation only where
``--with-dependents`` names it and lists every other dependent left in; and
``parse_as_of``, which reads the date the run is stamped with. ``--dry-run``
prints the changes and writes nothing.

An operator runs it by hand, normally live with a spend ceiling. The file it
rewrites is the quarantine list collection reads, so an entry it keeps holds
its case out of the next run while the entry is in force, and an entry it
drops no longer does. ``render`` writes each entry with the day its hold began
and whether a model change ends it.

Specified by ``docs/design/consumer_ci.md`` sections 4.14 and 4.14.2, against harness
``cmn_verdict_and_cli.md`` sections 4.6.5 and 4.6.10.

**The decision is the harness's and the running is ours.** Re-observing needs
the cases, which only this repository has, so ``cmn.quarantine.reconcile``
decides what each entry becomes and this tool measures and writes.

**It spends money, deliberately.** "Does this still fail?" is a question about
the current model, so the useful run is live and the tool takes a spend
ceiling like any other spending surface. A replay asks whether the recorded
fixtures still fail, which is a different and cheaper question.

**It never commits.** The operator reads the printed actions, reviews the diff
and commits, which is also why this is a tool rather than a step in a gate: a
gate rewriting tracked configuration would race between the platform and band
legs that run in parallel.
"""

import argparse
import logging
from dataclasses import replace
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Final, Mapping, Optional

import yaml

from cmn.pytest_support import case_identifier
from cmn.quarantine_file import load_quarantine_for
from cmn.quarantine import DROPPED, STAMPED, UNDECIDED, QuarantineEntry, reconcile
from ingestion.cases import build_case_id

from tests.cases.graded_support import (
    dispatch_session,
    observe_repeatedly,
    repository_root,
)
from tests.cases.quarantine_support import declared_dependents
from tests.cases.suite_support import case_rules_from_suite

logger = logging.getLogger(__name__)

_ENCODING: Final[str] = "utf-8"

# The separator `ingestion.cases.build_case_id` composes an identifier with.
# Split rather than re-derived, because the entry stores the composed form.
_CASE_ID_SEPARATOR: Final[str] = "::"

# Mirrors the verdict tool's codes, which `cmn_verdict_and_cli.md` section 7.3
# chose to stay clear of argparse's own exit 2.
_EXIT_DONE: Final[int] = 0
_EXIT_UNDECIDED: Final[int] = 1
_EXIT_REFUSED: Final[int] = 4


def _flag_carrier(parsed: argparse.Namespace) -> Any:
    """Return the object ``graded_support`` reads a run's flags from.

    ``observe_repeatedly`` takes pytest's configuration and uses it only as a
    flag carrier, through ``getoption``. Built here rather than by starting a
    pytest session, because this tool selects its cases from the quarantine
    file rather than by collection.

    Args:
        parsed (argparse.Namespace): This tool's arguments.

    Returns:
        Any: An object answering ``getoption`` for the flags the graded helpers
        consult.
    """
    values = {
        "--engine": parsed.engine,
        "--mode": parsed.mode,
        "--judge-mode": "",
        "--judge-engine": "",
        "--observations": 0,
        "--keep-connection": False,
        "--fill-gaps": False,
        "--max-spend": parsed.max_spend,
    }

    def getoption(name: str, default: Any = None) -> Any:
        """Return a flag's value, as pytest's configuration would.

        Args:
            name (str): The flag.
            default (Any): What to return when it is unset.

        Returns:
            Any: The value.
        """
        return values.get(name, default)

    return SimpleNamespace(getoption=getoption, option=SimpleNamespace())


def _observe_entries(
    carrier: Any, entries: list[QuarantineEntry]
) -> tuple[dict[str, list[bool]], str]:
    """Re-observe every quarantined case and report what each produced.

    Each case is observed under the escalation policy rather than once:
    ``observe_repeatedly`` dispatches the configured count and the two further
    observations a single disagreement earns. **Dropping an entry on one green
    observation would un-quarantine a flaky case on its lucky run.**

    Args:
        carrier (Any): The flag carrier the graded helpers read.
        entries (list[QuarantineEntry]): The entries to re-observe.

    Returns:
        tuple: Per case identifier, whether each observation passed, and the one
        model the run served, empty when it served none or several.

        **The model comes from the session, not from a result.** An
        ``EvaluationResult`` carries a score and assertions, never the model
        that produced the response; the session records every model it served
        for exactly this question (harness ``tier2_execution.md`` section
        8.6.5).
    """
    outcomes: dict[str, list[bool]] = {}

    for entry in entries:
        if _CASE_ID_SEPARATOR not in entry.case_id:
            logger.error(
                "Skipping %r: not a composed case identifier, so the task and "
                "rule halves cannot be recovered", entry.case_id,
            )
            continue
        task_id, rule_id = entry.case_id.split(_CASE_ID_SEPARATOR, 1)
        try:
            results = observe_repeatedly(carrier, task_id, rule_id)
        except KeyError:
            # AN ENTRY CAN OUTLIVE ITS CASE. A renamed or deleted case leaves
            # an entry naming a pair the corpus no longer defines, which is
            # unobservable rather than passing: dropping it would decide on no
            # evidence and raising would let one stale entry block every other.
            # It falls through to UNDECIDED. Design section 4.14.
            logger.error(
                "%s names a case the corpus does not define, so it cannot be "
                "re-observed and is left unchanged", entry.case_id,
            )
            continue
        outcomes[entry.case_id] = [bool(result.passed) for result in results]

    served = dispatch_session(carrier).served
    return outcomes, next(iter(served)) if len(served) == 1 else ""


def render(entries: list[QuarantineEntry]) -> str:
    """Render the entries back as the file they came from.

    An absent date or model is written as nothing rather than as a null, so an
    unconfirmed entry round-trips to the same shape it was read in.

    Args:
        entries (list[QuarantineEntry]): The entries that remain.

    Returns:
        str: The YAML document, with a header saying what writes it.
    """
    payload: list[dict[str, Any]] = []
    for entry in entries:
        record: dict[str, Any] = {"case_id": entry.case_id, "reason": entry.reason}
        if entry.quarantined_on is not None:
            record["quarantined_on"] = entry.quarantined_on.isoformat()
        # THE DAY THE HOLD BEGAN, which a re-stamp never moves. Section 3.12.2.
        if entry.originally_quarantined_on is not None:
            record["originally_quarantined_on"] = (
                entry.originally_quarantined_on.isoformat()
            )
        record["ends_on_model_change"] = entry.ends_on_model_change
        if entry.observed_model:
            record["observed_model"] = entry.observed_model
        if entry.ticket:
            record["ticket"] = entry.ticket
        payload.append(record)

    body = yaml.safe_dump(
        {"quarantine": payload}, sort_keys=False, allow_unicode=True, width=100
    )
    return (
        "# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy\n"
        "# SPDX-License-Identifier: MIT\n"
        "# Written by tools/quarantine.py. An entry holds its case out until\n"
        "# its 21-day window lapses, or the model changes where\n"
        "# ends_on_model_change is true; see consumer_ci.md sections 3.12.2\n"
        "# and 4.14 and harness cmn_verdict_and_cli.md section 4.6.15.\n"
        + body
    )


def parse_as_of(value: str) -> date:
    """Parse the injected date, refusing anything that is not an ISO date.

    Args:
        value (str): The argument as given.

    Returns:
        date: The parsed date.

    Raises:
        ValueError: With ``QC_HARNESS_PARSER_ERROR`` when it will not parse.
            **Refused rather than defaulted to today**, because a stamped date
            decides a window and a silent default would make the stamp depend
            on when the tool happened to run.
    """
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(
            f"QC_HARNESS_PARSER_ERROR: {value!r} is not an ISO date, and a "
            f"stamped date decides a window"
        ) from error


def plan_dependents(
    entries: list[QuarantineEntry],
    pairs: Mapping[str, tuple[str, str]],
    dependents: Mapping[str, list[str]],
    requested: frozenset[str],
) -> tuple[list[QuarantineEntry], list[str]]:
    """Return the dependent entries asked for, and a line for each dependent left in.

    A dependent of a quarantined foundation is added only where ``requested``
    names that foundation, carrying its ticket, dates, observed model and
    model-change flag; any other dependent not quarantined is listed as running
    and counting. Design: ``consumer_ci.md`` section 4.14.2.

    Args:
        entries (list[QuarantineEntry]): The entries the file holds.
        pairs (Mapping): Case name to the task and rule it dispatches.
        dependents (Mapping): Foundation case number to the names resting on it.
        requested (frozenset[str]): The foundation case numbers whose
            dependents are to be quarantined.

    Returns:
        tuple: The entries to add, and one line per dependent left in or not
        quarantinable.
    """
    held = {entry.case_id for entry in entries}
    number_of = {
        build_case_id(*pair): case_identifier(name) for name, pair in pairs.items()
    }
    added: list[QuarantineEntry] = []
    listed: list[str] = []
    for entry in entries:
        foundation = number_of.get(entry.case_id)
        if not foundation:
            continue
        for name in dependents.get(foundation, []):
            pair = pairs.get(name)
            if pair is None:
                listed.append(
                    f"{name} rests on quarantined {foundation} and dispatches no "
                    f"corpus case, so it cannot be quarantined"
                )
                continue
            case_id = build_case_id(*pair)
            if case_id in held:
                continue
            if foundation in requested:
                added.append(replace(
                    entry, case_id=case_id, release_accepted_in="",
                    reason=f"its foundation {foundation} is quarantined",
                ))
                held.add(case_id)
            else:
                listed.append(
                    f"{name} rests on quarantined {foundation} and is not "
                    f"quarantined, so it runs and counts"
                )
    return added, listed


def _with_requested_dependents(
    entries: list[QuarantineEntry], requested: list[str]
) -> list[QuarantineEntry]:
    """Return the entries with the requested dependents added, logging each decision.

    Args:
        entries (list[QuarantineEntry]): The entries surviving re-observation.
        requested (list[str]): The foundation case numbers ``--with-dependents`` named.

    Returns:
        list[QuarantineEntry]: The entries, then those added.
    """
    root = repository_root()
    added, listed = plan_dependents(
        entries, case_rules_from_suite(root),
        declared_dependents(root / "tests" / "cases"), frozenset(requested),
    )
    for line in listed:
        logger.info("%s", line)
    for entry in added:
        logger.info("%s: quarantined with its foundation, %s", entry.case_id, entry.reason)
    return [*entries, *added]


def build_parser() -> argparse.ArgumentParser:
    """Return the tool's argument parser.

    Returns:
        argparse.ArgumentParser: The parser ``main`` reads its arguments with.
    """
    parser = argparse.ArgumentParser(
        prog="quarantine",
        description="Re-observe quarantined cases and write back the result",
    )
    parser.add_argument("--engine", required=True, help="Whose quarantine to confirm")
    parser.add_argument(
        "--mode", default="live",
        help="`live` asks whether the case still fails against the current "
             "model, `replay` whether the recorded fixtures still fail",
    )
    parser.add_argument(
        "--max-spend", type=float, default=0.0,
        help="The session ceiling, as the graded suites take it",
    )
    parser.add_argument("--as-of", required=True, help="The date to stamp, ISO")
    parser.add_argument(
        "--config-dir", type=Path, default=None,
        help="Where `quarantine/<engine>.yaml` lives, defaulting to `config/`",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would change and write nothing",
    )
    parser.add_argument(
        "--with-dependents", action="append", default=[], metavar="CASE_NUMBER",
        help="Also quarantine the dependents of this quarantined foundation; "
             "repeatable. Without it no dependent is added",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """Re-observe one engine's quarantined cases and return an exit code.

    Args:
        argv (Optional[list]): Arguments, for calling in-process from a case.

    Returns:
        int: ``0`` when every entry was decided, ``1`` when any was left
        undecided because its case produced no observations, ``4`` when the
        engine's file names nothing to re-observe.
    """
    parsed = build_parser().parse_args(argv)

    config_dir = parsed.config_dir or (repository_root() / "config")
    entries = load_quarantine_for(config_dir, parsed.engine)
    if not entries:
        logger.error(
            "QC_HARNESS_PREFLIGHT_FAILURE: %s names no quarantined case for "
            "%r, so there is nothing to confirm",
            config_dir / "quarantine" / f"{parsed.engine}.yaml", parsed.engine,
        )
        return _EXIT_REFUSED

    carrier = _flag_carrier(parsed)
    outcomes, resolved_model = _observe_entries(carrier, entries)
    remaining, actions = reconcile(
        entries, outcomes, parse_as_of(parsed.as_of), resolved_model
    )

    for case_id in sorted(actions):
        logger.info("%s: %s", case_id, actions[case_id])

    # DEPENDENTS AFTER THE RE-OBSERVATION, and only those asked for by name:
    # quarantining one is an explicit decision (section 4.14.2).
    remaining = _with_requested_dependents(remaining, parsed.with_dependents)
    if not resolved_model:
        logger.warning(
            "The run resolved no single model, so every surviving entry was "
            "stamped with an empty model and its expiry rests on the window "
            "alone. A mixed corpus is the ordinary cause"
        )

    target = config_dir / "quarantine" / f"{parsed.engine}.yaml"
    if parsed.dry_run:
        logger.info("Dry run, %s left unwritten:\n%s", target, render(remaining))
    else:
        target.write_text(render(remaining), encoding=_ENCODING, newline="\n")
        logger.info("Wrote %s, %d entries remain", target, len(remaining))

    undecided = sorted(
        case_id for case_id, action in actions.items() if action == UNDECIDED
    )
    if undecided:
        logger.error(
            "%d entries were not decided because their cases produced no "
            "observations, so they are unchanged: %s",
            len(undecided), ", ".join(undecided),
        )
        return _EXIT_UNDECIDED
    logger.info(
        "Decided every entry: %d dropped, %d re-stamped",
        sum(1 for action in actions.values() if action == DROPPED),
        sum(1 for action in actions.values() if action == STAMPED),
    )
    return _EXIT_DONE


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(main())
