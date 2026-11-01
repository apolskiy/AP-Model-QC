# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""The findings recorder, which keeps each engine's register of model defects up to date.

Created: 2026-10-04
Last updated: 2026-11-01

This file contains ``load_register``, which reads what is already recorded,
``RunContext``, which carries what one run was, ``merge``, which folds the run
into the existing register and reports what changed, ``hold_unreproduced`` and
``resolve_upstream``, which decide what happens to an open finding the run did
not reproduce, ``clear_stale_reproductions``, which drops the reproduction mark
of a withdrawn finding the run passed, ``render``, which is the file as a
reader sees it, and ``main``, the command line around them.

**What a run measured is read by ``tools/findings_run.py``**, which is the
other half of this recorder: that module runs the suite and parses its JUnit
XML, and this one decides what the register does with the result.

It is run by hand, one engine at a time, and runs the graded suite itself in
replay or live mode. What it writes, through ``tools.register_files``, is the
engine's bug file under ``config/findings/`` and its holding list under
``config/findings/unconfirmed/``. ``tools.ticket_report`` builds the vendor
tickets from the bug file, so an entry recorded here is what gets filed.

Specified by ``docs/design/consumer_ci.md`` section 9.

**Nothing here files anything.** The register exists for the interval between
observing a finding and filing it: a finding fixed upstream in that interval
would otherwise arrive as a gate quietly turning green, which reads exactly
like a case that stopped testing anything.

**Generated rather than authored.** Twenty reproductions written by hand drift
from the first re-run, on the same principle that makes the matrix families
column derived.

**Only a live run can retire a finding.** Replay replays our own recorded
responses, so a recorded finding reproduces from replay whatever the vendor
does. ``record`` reads a run of either mode; ``--resolve-from-live`` is refused
unless the run was live, because the alternative is retiring a finding on
evidence that could not bear on it.
"""

import argparse
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Final, Optional

import yaml

from tools.findings_run import (
    expected_by_case,
    models_by_case,
    observe,
    parse_failures,
    parse_passed,
)
from tools.register_files import (
    holding_path,
    refuse_empty_run,
    register_path,
    write_register,
)
from tools.ticket_report import reproduce_command

_RESOLVED: Final[str] = "resolved_upstream"

# WITHDRAWN IS OURS, RESOLVED IS THEIRS. A finding withdrawn because our own
# assertion was wrong must not read as a vendor fix: crediting a vendor with a
# correction they did not make is wrong in the direction that most damages a
# published report. Section 9.4.1.
_WITHDRAWN: Final[str] = "withdrawn"

# A FLIP IS NOT A RETRACTION. A finding that stopped reproducing says nothing
# about the model until it is seen again, and nothing about our assertion
# either: it is an absence of a measurement rather than a correction of one.
# So it takes its own status and waits in the holding list, where a later run
# can promote it back with the intermittent marker (section 9.4.8).
_UNREPRODUCED: Final[str] = "not_reproduced"


def load_register(engine: str) -> dict[str, dict[str, Any]]:
    """Return the findings already recorded for an engine, keyed by case.

    Args:
        engine (str): The engine.

    Returns:
        dict: Case identifier to its entry. **Absent means empty**, as it does
        for quarantine: a register that must exist to be read would make the
        file a prerequisite for a clean repository.
    """
    found: dict[str, dict[str, Any]] = {}
    # BOTH FILES, because the holding list is where a flipped finding waits and
    # a run that could not see it would record the same finding again as new
    # (section 9.4.8).
    for path in (register_path(engine), holding_path(engine)):
        if not path.is_file():
            continue
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for entry in loaded.get("findings", ()) or ():
            found[str(entry["case"])] = dict(entry)
    return found


@dataclass(frozen=True)
class RunContext:
    """What one measuring run was, for the entries it produces.

    Attributes:
        engine (str): Which engine was measured.
        mode (str): ``replay`` or ``live``.
        models (dict): Case name to the model that served it.
        expected (dict): Case name to the requirement it traces to.
        today (date): The date to stamp, injected rather than read, so a
            register is reproducible from the same inputs.
        resolve (bool): Whether an absent finding may be retired as the
            vendor's fix, which only a live run may ask for.
        hold_unreproduced (bool): Whether an absent finding may be
            withdrawn as ours. **Replay may ask for this**, because it is a
            question about our own record rather than about the model
            (section 9.4.7).
        passed (frozenset): The cases the run measured as passing. Only one of
            these can have stopped reproducing (section 9.4.7.1).
    """

    engine: str
    mode: str
    models: dict[str, str]
    expected: dict[str, str]
    today: date
    resolve: bool
    hold_unreproduced: bool = False
    passed: frozenset[str] = frozenset()


def hold_unreproduced(
    merged: dict[str, dict[str, Any]],
    observed: dict[str, dict[str, Any]],
    run: RunContext,
) -> list[str]:
    """Hold every open finding this run did not reproduce.

    **Neither ours nor theirs, which is why it has its own status.** A finding
    that stops reproducing is not a retraction of our assertion and not a
    vendor's fix: it is an absence of a measurement. Crediting a vendor with a
    correction they did not make is the error that most damages a published
    report (section 9.4.1), and calling it our defect would be the mirror of
    that error.

    **Intermittent is a run-to-run property, not a failure rate.** A case
    failing one observation in five has been measured, and that measurement is
    the finding; a case that failed and now passes has flipped, and this is the
    only situation the holding list is for (section 9.4.8).

    **Replay may ask for this**, unlike resolution. It asks whether our own
    record still shows what we said it showed, which is exactly what replay
    answers (section 9.4.7).

    **Named rather than inline so a case can call it**, which is the lesson the
    cascade marker taught when it was set and read by nothing.

    Args:
        merged (dict): The register, modified in place.
        observed (dict): What this run reported, by case.
        run (RunContext): What the run was, for the date and the intent.

    Returns:
        list[str]: One line per withdrawal, naming the population it was drawn
        from, because a one-in-five finding is a claim about variance and a
        five-in-five finding is a claim about behaviour.
    """
    changed: list[str] = []
    for case, entry in sorted(merged.items()):
        if case in observed or entry.get("status") in (_RESOLVED, _WITHDRAWN):
            continue
        # HELD ONCE. An entry already held keeps the day it was first held and
        # its reason, which may have been written by hand (section 9.4.8).
        if entry.get("status") == _UNREPRODUCED:
            continue
        # A SKIP IS NOT A PASS. A case the run did not measure keeps its
        # finding, and the next run that measures it decides (9.4.7.1).
        if case not in run.passed:
            continue
        population = entry.get("observations") or "population not recorded"
        entry["status"] = _UNREPRODUCED
        entry["held_on"] = run.today.isoformat()
        entry["held_reason"] = (
            f"Did not reproduce on a fresh run of {run.today.isoformat()}. "
            f"Recorded from {population}, so it was a claim drawn from that "
            f"population and the sample did not hold. Nothing had asked "
            f"whether an open finding still reproduced: the inventory checks "
            f"compare the register to the suite and the trace checks to the "
            f"matrix, and none compared it to a result (consumer_ci.md "
            f"section 9.4.7)"
        )
        changed.append(f"HELD {case}, it no longer reproduces ({population})")
    return changed


def clear_stale_reproductions(
    merged: dict[str, dict[str, Any]],
    observed: dict[str, dict[str, Any]],
    run: RunContext,
) -> list[str]:
    """Drop the reproduction mark of a withdrawn finding this run passed.

    ``reproduced_on`` is the evidence a review ticket is written from, so an
    entry carries it only while the run that wrote it is the latest word on
    that case. The condition is the one :func:`hold_unreproduced` uses: a case
    the run measured as passing has stopped reproducing, and a case it skipped
    decides nothing.

    **It runs whatever the flags say**, unlike holding and resolving. Those
    change a finding's status, which is a judgement the caller asks for; this
    withdraws a fact the register no longer has.

    Design: ``consumer_ci.md`` section 9.5.5.12.

    Args:
        merged (dict): The register, modified in place.
        observed (dict): What this run reported, by case.
        run (RunContext): What the run was, for the date and what passed.

    Returns:
        list[str]: One line per entry whose mark was dropped, naming the date
        it carried, because that date is what a reader was acting on.
    """
    changed: list[str] = []
    for case, entry in sorted(merged.items()):
        if case in observed or entry.get("status") != _WITHDRAWN:
            continue
        if not entry.get("reproduced_on") or case not in run.passed:
            continue
        changed.append(
            f"NO LONGER RETURNED {case}, it passed on "
            f"{run.today.isoformat()} and its reproduction of "
            f"{entry['reproduced_on']} is no longer the latest word"
        )
        entry.pop("reproduced_on", None)
    return changed


def resolve_upstream(
    merged: dict[str, dict[str, Any]],
    observed: dict[str, dict[str, Any]],
    run: RunContext,
) -> list[str]:
    """Retire every finding a live run no longer reproduces, as the vendor's.

    **Theirs, not ours**, which is the mirror of
    :func:`hold_unreproduced` and the reason the two are separate
    functions. Only a live run may ask for this, because replay replays our own
    recording and cannot bear on the current model (section 9.4).

    **Absent is not passing, and both guards here are that one sentence.** A
    case missing from a run's failures may have skipped behind a failed
    foundation, so the run measured nothing and has nothing to credit; and a
    withdrawn finding is a conclusion about our own record, so resolving it
    would claim a vendor corrected something we had already said was never
    theirs. A **held** finding stays resolvable: it is an absence of a
    measurement rather than a conclusion, and a live pass is the measurement it
    was waiting for, so its ``held_on`` and ``held_reason`` are kept as the
    record of how it got here (section 9.4.9).

    Args:
        merged (dict): The register, modified in place.
        observed (dict): What this run reported, by case.
        run (RunContext): What the run was.

    Returns:
        list[str]: One line per retirement.
    """
    changed: list[str] = []
    for case, entry in sorted(merged.items()):
        if case in observed or entry.get("status") in (_RESOLVED, _WITHDRAWN):
            continue
        # A SKIP IS NOT A PASS, as it is not for a hold. A case the run did not
        # measure keeps its finding, and the next run that measures it decides
        # (section 9.4.9).
        if case not in run.passed:
            continue
        entry["status"] = _RESOLVED
        entry["resolved_on"] = run.today.isoformat()
        # THE MODEL THIS RUN USED, from any case it did serve: a resolved
        # finding has no result of its own to read, having not failed.
        entry["resolved_model"] = next(iter(sorted(set(run.models.values()))), "")
        changed.append(f"RESOLVED UPSTREAM {case}, it no longer reproduces live")
    return changed


def merge(
    existing: dict[str, dict[str, Any]],
    observed: dict[str, dict[str, Any]],
    run: RunContext,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Return the register after a run, and what changed.

    **A finding that stops reproducing is kept**, and which state it takes
    depends on what stopped. ``resolved_upstream`` needs a live run, because
    only that bears on the current model. ``withdrawn`` is the answer where the
    run shows our own record no longer holds, which replay answers perfectly
    well: it asks whether we still see what we said we saw
    (section 9.4.7).

    Args:
        existing (dict): What was already recorded.
        observed (dict): What this run reported.
        run (RunContext): What the run was.

    Returns:
        tuple: The merged register, and one line per change.
    """
    merged = {case: dict(entry) for case, entry in existing.items()}
    changes: list[str] = []

    for case, measured in sorted(observed.items()):
        entry = merged.get(case)
        if entry is None:
            merged[case] = {
                "case": case,
                "taxonomy_code": measured["taxonomy_code"],
                "observations": measured.get("observations", "1 of 1 passed"),
                "observed_model": run.models.get(case, ""),
                "first_observed": run.today.isoformat(),
                "last_observed": run.today.isoformat(),
                "status": "open",
                "expected": run.expected.get(case, ""),
                "actual": measured.get("actual", ""),
                # ONE COMMAND, SHARED WITH THE TICKET, which carries
                # --with-prerequisites: without it a case resting on a
                # foundation is refused (consumer_ci.md section 9.5.5).
                "reproduce": reproduce_command(run.engine, case),
                "ticket": "",
            }
            changes.append(f"RECORDED {case} ({measured['taxonomy_code']})")
            continue

        # A WITHDRAWN ENTRY IS LEFT ALONE. It records a claim we made and
        # retracted, so stamping it with today's run would make it look live
        # again, and reopening it would resurrect a judgement about an
        # assertion that no longer exists. Section 9.4.1.
        if entry.get("status") == _UNREPRODUCED:
            # IT CAME BACK, SO IT IS FILEABLE AND IT IS MARKED. A claim that
            # has flipped is a different claim from one that has held, and a
            # vendor is told plainly that the behaviour is not every run
            # (section 9.4.8).
            entry["status"] = "open"
            entry["intermittent"] = True
            entry["last_observed"] = run.today.isoformat()
            entry.pop("held_on", None)
            entry.pop("held_reason", None)
            changes.append(
                f"PROMOTED {case} reproduced again and is filed as intermittent"
            )
            continue

        if entry.get("status") == _WITHDRAWN:
            # REPORTED, NOT REOPENED. The status is a judgement we made about
            # our own assertion and this run cannot revisit it, but a retracted
            # claim that is failing again is the one thing a reader of the
            # register must not learn by accident (section 9.4.7).
            #
            # RECORDED, NOT ONLY ANNOUNCED. The line below is read once, by
            # whoever ran the merge. The date goes on the entry so a reader of
            # the register a week later can tell, and so the ticket generator
            # can give the finding the evidence a ruling needs without being
            # told which cases failed (section 9.5.5.12).
            entry["reproduced_on"] = run.today.isoformat()
            changes.append(
                f"RETURNED {case} is withdrawn and reproduces again "
                f"({measured['taxonomy_code']}). Read it against its recording: "
                f"either the assertion was repaired and now fires correctly, or "
                f"the same false positive has come back"
            )
            continue

        entry["last_observed"] = run.today.isoformat()
        serving = run.models.get(case, "")
        if serving and serving != entry.get("observed_model"):
            if entry.get("observed_model"):
                changes.append(
                    f"MODEL MOVED {case}: {entry['observed_model']} to {serving}, "
                    f"and it still reproduces"
                )
            entry["observed_model"] = serving
        if entry.get("status") == _RESOLVED:
            entry["status"] = "open"
            entry.pop("resolved_on", None)
            entry.pop("resolved_model", None)
            changes.append(f"REOPENED {case}, it reproduces again")
        if measured["taxonomy_code"] != entry.get("taxonomy_code"):
            changes.append(
                f"CODE CHANGED {case}: {entry.get('taxonomy_code')} to "
                f"{measured['taxonomy_code']}"
            )
            entry["taxonomy_code"] = measured["taxonomy_code"]
        if measured.get("actual") and measured["actual"] != entry.get("actual"):
            changes.append(f"MESSAGE CHANGED {case}, the failure reads differently")
            entry["actual"] = measured["actual"]
        changes.extend(_update_population(case, entry, measured))

    # UNCONDITIONAL, because it withdraws a fact rather than deciding a status
    # (section 9.5.5.12).
    changes.extend(clear_stale_reproductions(merged, observed, run))

    if run.hold_unreproduced:
        changes.extend(hold_unreproduced(merged, observed, run))

    if run.resolve:
        changes.extend(resolve_upstream(merged, observed, run))

    return merged, changes


def _update_population(
    case: str, entry: dict[str, Any], measured: dict[str, Any]
) -> list[str]:
    """Set an entry's population to what the latest run stated.

    Args:
        case (str): The case, for the change line.
        entry (dict): The register entry, updated in place.
        measured (dict): What the latest run said about the case.

    Returns:
        list[str]: One change line when the population moved, else none. A run
        stating no population failed every observation, so an earlier figure
        is dropped (``consumer_ci.md`` section 9.5.5.1).
    """
    stated = str(measured.get("observations") or "")
    held = str(entry.get("observations") or "")
    if stated == held:
        return []
    entry["observations"] = stated
    return [f"POPULATION CHANGED {case}: {held or 'none stated'} to "
            f"{stated or 'every observation failing'}"]


def render(
    engine: str,
    findings: dict[str, dict[str, Any]],
    *,
    holding: bool = False,
) -> str:
    """Return the register as the file holds it.

    Args:
        engine (str): The engine.
        findings (dict): The entries.

    Returns:
        str: YAML, with the generated-file warning a reader needs.
    """
    ordered = [findings[case] for case in sorted(findings)]
    open_count = sum(
        1 for entry in ordered
        if entry.get("status") not in (_RESOLVED, _WITHDRAWN)
    )
    withdrawn_count = sum(
        1 for entry in ordered if entry.get("status") == _WITHDRAWN
    )
    header = (
        "# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy\n"
        "# SPDX-License-Identifier: MIT\n"
        f"# Findings observed against {engine}.\n"
        + ("# THE HOLDING LIST. Nothing here is filed: each entry either was\n"
           "# retracted as ours or stopped reproducing. A held finding that a\n"
           "# later run reproduces returns to the bug file carrying\n"
           "# `intermittent: true` (consumer_ci.md section 9.4.8).\n"
           if holding else
           "# THE BUG FILE. Every entry reproduced on the latest run, whatever\n"
           "# its failure rate. What did not reproduce waits in unconfirmed/\n"
           "# (consumer_ci.md section 9.4.8).\n")
        + "#\n"
        "# GENERATED BY tools/findings.py. Specified by\n"
        "# docs/design/consumer_ci.md section 9.\n"
        "#\n"
        "# `expected` is the requirement the case traces to and `actual` is\n"
        "# what the run said, both generated. `ticket` is the one field a\n"
        "# person fills in, once a vendor reference exists, and the tool\n"
        "# never overwrites it.\n"
        "#\n"
        "# NOTHING HERE AFFECTS A VERDICT. A record that could turn a gate\n"
        "# green would be a quarantine with a different name, and a P0 or P1\n"
        "# cannot be exempted at all.\n"
        f"#\n# {open_count} open, "
        f"{len(ordered) - open_count - withdrawn_count} resolved upstream, "
        f"{withdrawn_count} withdrawn.\n\n"
    )
    return header + yaml.safe_dump(
        {"engine": engine, "findings": ordered},
        sort_keys=False, allow_unicode=True, width=100,
    )


def main(argv: Optional[list[str]] = None) -> int:
    """Record or re-verify one engine's findings.

    Returns:
        int: ``0`` when the register was written, ``1`` when the run produced
        no usable measurement. **A red suite is not an error here**: findings
        are what this reads, so a failing run is the normal input.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", required=True)
    parser.add_argument("--mode", default="replay", choices=("replay", "live"))
    parser.add_argument("--as-of", required=True, help="The date to stamp, ISO")
    parser.add_argument(
        "--resolve-from-live",
        action="store_true",
        help=(
            "Retire a finding this run did not reproduce. Live only: replay "
            "replays our own recording and cannot bear on the current model"
        ),
    )
    parser.add_argument(
        "--hold-unreproduced",
        action="store_true",
        help=(
            "Hold an open finding this run did not reproduce. Permitted in "
            "replay: it asks whether our own record still holds, not whether "
            "the model changed"
        ),
    )
    parser.add_argument("--dry-run", action="store_true")
    arguments = parser.parse_args(argv)

    if arguments.resolve_from_live and arguments.mode != "live":
        print(
            "QC_HARNESS_PARSER_ERROR: --resolve-from-live needs --mode live. "
            "Replay replays our own recorded responses, so it cannot show that "
            "a model stopped doing something",
            file=sys.stderr,
        )
        return 1

    today = date.fromisoformat(arguments.as_of)
    report, results = observe(arguments.engine, arguments.mode)
    observed = parse_failures(report)

    # A FAILURE CARRYING NO MODEL CODE IS REPORTED, NEVER DROPPED. It is either
    # an instrument defect, which belongs nowhere near this register, or a
    # reader could not classify, and both are things a person has to see.
    unclassified = sorted(
        case for case, entry in observed.items() if not entry["taxonomy_code"]
    )
    for case in unclassified:
        print(
            f"UNCLASSIFIED {case}: the failure carries no QC_LLM_* or QC_SEC_* "
            f"code, so it is either an instrument defect or a message this "
            f"reader does "
            f"not recognise",
            file=sys.stderr,
        )
        del observed[case]

    merged, changes = merge(
        load_register(arguments.engine),
        observed,
        RunContext(
            engine=arguments.engine,
            mode=arguments.mode,
            models=models_by_case(results),
            expected=expected_by_case(Path("docs/testing/rtm_model.csv")),
            today=today,
            resolve=arguments.resolve_from_live,
            hold_unreproduced=arguments.hold_unreproduced,
            passed=parse_passed(report),
        ),
    )

    for line in changes:
        print(line)
    if not changes:
        print(f"no change: {len(observed)} finding(s) reproduce as recorded")
    if unclassified:
        print(
            f"{len(unclassified)} failure(s) were not recorded, named above",
            file=sys.stderr,
        )

    if arguments.dry_run:
        print("--dry-run, nothing written")
        return 0

    path = register_path(arguments.engine)
    path.parent.mkdir(parents=True, exist_ok=True)
    held_count = sum(
        1 for entry in merged.values()
        if entry.get("status") == _UNREPRODUCED
        and entry.get("held_on") == today.isoformat()
    )
    refusal = refuse_empty_run(report, observed, held_count)
    if refusal is not None:
        print(
            f"QC_HARNESS_REGISTER_REFUSED: refusing to write the register because "
            f"{refusal}.",
            file=sys.stderr,
        )
        return 1

    write_register(arguments.engine, merged, render)
    print(f"wrote {path} with {len(merged)} finding(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
