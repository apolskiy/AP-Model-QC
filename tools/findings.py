# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""The findings recorder, which keeps each engine's register of model defects up to date.

Created: 2026-10-04
Last updated: 2026-11-06

This file contains ``load_register``, which reads what is already recorded,
``RunContext``, which carries what one run was, ``merge``, which folds the run
into the existing register and reports what changed, ``remove_passed`` and
``resolve_upstream``, which decide what happens to a finding whose case the run
measured passing, ``render``, which is the file as a reader sees it, and
``main``, the command line around them.

**What a run measured is read by ``tools/findings_run.py``**, which is the
other half of this recorder: that module runs the suite and parses its JUnit
XML, and this one decides what the register does with the result.

It is run by hand, one engine at a time, and runs the graded suite itself in
replay or live mode. What it writes, through ``tools.register_files``, is the
engine's bug file under ``config/findings/``. ``tools.ticket_report`` builds
the vendor tickets from the bug file, so an entry recorded here is what gets
filed.

Specified by ``docs/design/consumer_ci.md`` section 9, and section 9.4.11 for
what a passing case does to its finding.

**Nothing here files anything.** The register exists for the interval between
observing a finding and filing it: a finding fixed upstream in that interval
would otherwise arrive as a gate quietly turning green, which reads exactly
like a case that stopped testing anything.

**Generated rather than authored.** Twenty reproductions written by hand drift
from the first re-run, on the same principle that makes the matrix families
column derived.

**Only a live run can credit a vendor.** Replay replays our own recorded
responses, so it cannot show a model changed. ``--resolve-from-live`` is
refused unless the run was live; on every other run a finding whose case was
measured passing is removed, and no record of it is kept.
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
    parse_warnings,
)
from tools.register_files import (
    refuse_empty_run,
    register_path,
    write_register,
)
from tools.ticket_report import reproduce_command

_RESOLVED: Final[str] = "resolved_upstream"
_WARNING: Final[str] = "warning"


def load_register(engine: str) -> dict[str, dict[str, Any]]:
    """Return the findings already recorded for an engine, keyed by case.

    Args:
        engine (str): The engine.

    Returns:
        dict: Case identifier to its entry. **Absent means empty**, as it does
        for quarantine: a register that must exist to be read would make the
        file a prerequisite for a clean repository.
    """
    path = register_path(engine)
    if not path.is_file():
        return {}
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {
        str(entry["case"]): dict(entry)
        for entry in loaded.get("findings", ()) or ()
    }


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
        resolve (bool): Whether a finding whose case passed is recorded as the
            vendor's fix rather than removed, which only a live run may ask for.
        passed (frozenset): The cases the run measured as passing. Only one of
            these can have stopped reproducing (section 9.4.7.1).
    """

    engine: str
    mode: str
    models: dict[str, str]
    expected: dict[str, str]
    today: date
    resolve: bool
    passed: frozenset[str] = frozenset()


def remove_passed(
    merged: dict[str, dict[str, Any]],
    observed: dict[str, dict[str, Any]],
    run: RunContext,
) -> list[str]:
    """Remove every finding whose case this run measured as passing.

    A finding resolved upstream is kept, and so is one whose case the run did
    not measure: a skip is not a pass (section 9.4.7.1). Nothing records a
    removed finding, because the fix that removed it replaced the recordings
    it was observed on (section 9.4.11).

    Args:
        merged (dict): The register, modified in place.
        observed (dict): What this run reported, by case.
        run (RunContext): What the run was, for the date and what passed.

    Returns:
        list[str]: One ``REMOVED`` line per removal, naming the date.
    """
    removed = sorted(
        case for case, entry in merged.items()
        if case not in observed and case in run.passed
        and entry.get("status") != _RESOLVED
    )
    for case in removed:
        del merged[case]
    return [f"REMOVED {case}, it passed on {run.today.isoformat()}" for case in removed]


def resolve_upstream(
    merged: dict[str, dict[str, Any]],
    observed: dict[str, dict[str, Any]],
    run: RunContext,
) -> list[str]:
    """Retire every finding a live run no longer reproduces, as the vendor's.

    Only a live run may ask for this, because replay replays our own recording
    and cannot bear on the current model (section 9.4). A finding whose case
    the run did not measure is kept: it may have skipped behind a failed
    foundation, and a run that measured nothing has nothing to credit
    (section 9.4.9).

    Args:
        merged (dict): The register, modified in place.
        observed (dict): What this run reported, by case.
        run (RunContext): What the run was.

    Returns:
        list[str]: One line per retirement.
    """
    changed: list[str] = []
    for case, entry in sorted(merged.items()):
        if case in observed or entry.get("status") == _RESOLVED:
            continue
        # A SKIP IS NOT A PASS. A case the run did not measure keeps its
        # finding, and the next run that measures it decides (section 9.4.9).
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

    A finding the run reproduced is recorded or updated. A finding whose case
    the run measured passing is resolved upstream where the run asks to
    resolve, and removed otherwise; one whose case the run did not measure is
    kept unchanged. An entry whose severity the run measured differently is
    replaced by a fresh entry (section 9.4.11).

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
            merged[case] = _fresh_entry(case, measured, run)
            changes.append(f"RECORDED {case} ({measured['taxonomy_code']})"
                           + (", passed with a warning" if measured.get("severity") else ""))
            continue

        # A CHANGE OF SEVERITY IS A NEW FINDING. A warning and a failure are
        # different claims, so nothing of the one carries over (9.4.11).
        if measured.get("severity") != entry.get("severity"):
            merged[case] = _fresh_entry(case, measured, run)
            changes.append(
                f"REPLACED {case}, {entry.get('severity') or 'failure'} is now "
                f"{measured.get('severity') or 'failure'}, recorded afresh"
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

    retire = resolve_upstream if run.resolve else remove_passed
    changes.extend(retire(merged, observed, run))

    return merged, changes


def _fresh_entry(
    case: str, measured: dict[str, Any], run: RunContext
) -> dict[str, Any]:
    """Return a new open entry for a finding the run reproduced.

    Args:
        case (str): The case.
        measured (dict): What the run said about the case.
        run (RunContext): What the run was, for the date, model and requirement.

    Returns:
        dict: The entry, dated today, with an empty ``ticket``. A warning
        carries ``severity: warning`` and a failure carries no ``severity``
        field (``consumer_ci.md`` section 6.4.6).
    """
    return {
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
        # --with-prerequisites: without it a case resting on a foundation is
        # refused (consumer_ci.md section 9.5.5).
        "reproduce": reproduce_command(run.engine, case),
        "ticket": "",
        **({"severity": _WARNING} if measured.get("severity") == _WARNING else {}),
    }


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


def render(engine: str, findings: dict[str, dict[str, Any]]) -> str:
    """Return the register as the file holds it.

    Args:
        engine (str): The engine.
        findings (dict): The entries.

    Returns:
        str: YAML, with the generated-file warning a reader needs.
    """
    ordered = [findings[case] for case in sorted(findings)]
    open_count = sum(1 for entry in ordered if entry.get("status") != _RESOLVED)
    header = (
        "# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy\n"
        "# SPDX-License-Identifier: MIT\n"
        f"# Findings observed against {engine}.\n"
        "# THE BUG FILE. Every open entry reproduced on the latest run that\n"
        "# measured its case, whatever its failure rate. A finding whose case\n"
        "# a run measured passing is removed, unless a live run resolved it\n"
        "# upstream (consumer_ci.md section 9.4.11).\n"
        "#\n"
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
        f"{len(ordered) - open_count} resolved upstream.\n\n"
    )
    return header + yaml.safe_dump(
        {"engine": engine, "findings": ordered},
        sort_keys=False, allow_unicode=True, width=100,
    )


def _retired_count(
    existing: dict[str, dict[str, Any]], merged: dict[str, dict[str, Any]]
) -> int:
    """Return how many entries a merge removed or newly resolved upstream.

    Args:
        existing (dict): The register before the merge.
        merged (dict): The register after it.

    Returns:
        int: The entries absent from ``merged``, and those resolved upstream in
        ``merged`` that were not resolved in ``existing``.
    """
    return sum(
        1 for case, entry in existing.items()
        if case not in merged or (
            merged[case].get("status") == _RESOLVED
            and entry.get("status") != _RESOLVED
        )
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
            "Record a finding whose case this run measured passing as resolved "
            "upstream instead of removing it. Live only: replay replays our "
            "own recording and cannot bear on the current model"
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
    # A CASE THAT PASSED WITH A WARNING is a finding too, filed apart
    # (section 6.4.6). A failure on the same case wins, though JUnit never
    # carries both.
    observed = {**parse_warnings(report), **parse_failures(report)}

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

    existing = load_register(arguments.engine)
    merged, changes = merge(
        existing,
        observed,
        RunContext(
            engine=arguments.engine,
            mode=arguments.mode,
            models=models_by_case(results),
            expected=expected_by_case(Path("docs/testing/rtm_model.csv")),
            today=today,
            resolve=arguments.resolve_from_live,
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
    refusal = refuse_empty_run(report, observed, _retired_count(existing, merged))
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
