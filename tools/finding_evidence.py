# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""One finding's evidence, and the questions that decide whether it is ours.

Specified by ``docs/design/consumer_ci.md`` section 9.5.4.

**Reading a ticket page end to end is the wrong unit of work.** A page carries
every finding for an engine and the decision is made one finding at a time: is
this the model's defect, or our assertion's? This prints exactly one, drops the
reproduction block a reader does not need in order to judge it, and ends with
the questions that have decided every withdrawal so far.

**Fifteen findings have been withdrawn and every one was ours.** None fell to
inspiration; each fell to one of the questions below, and leaving them implicit
is why one class recurred twelve times.

Read-only. Withdrawing a finding stays a person's act with its reason recorded,
because ``findings.py`` generates every other field and must not overwrite a
judgement it did not make.

Usage::

    python -m tools.finding_evidence --engine gemini --case 134101
    python -m tools.finding_evidence --engine openai --open
    python -m tools.finding_evidence --engine claude --case 154100 --full
"""

import argparse
import pathlib
import sys
from typing import Final, Optional

import yaml

from tools.ticket_files import page_name

_TICKETS: Final[pathlib.Path] = pathlib.Path("reports") / "tickets"
_REGISTER: Final[pathlib.Path] = pathlib.Path("config") / "findings"
_FIXTURES: Final[pathlib.Path] = pathlib.Path("tests") / "fixtures" / "replay"

# THE QUESTIONS THAT HAVE DECIDED EVERY WITHDRAWAL. Each line is a defect this
# project shipped, so the list is a record rather than advice (design 9.5.4).
_QUESTIONS: Final[tuple[tuple[str, str], ...]] = (
    ("Does the response do everything the prompt asked, not merely avoid the "
     "forbidden thing?",
     "134200: a response naming no revenue at all was called compliant because "
     "it denied an invented region. Three assertions were condemned this way"),
    ("Is the response actually wrong, read against the request as sent?",
     "134101: the model gave the correct answer and a markdown heading joined "
     "the sentence below it"),
    ("Was the requirement sent to the model, or only judged?",
     "154110: a prohibition that lived in the rubric alone, so the model was "
     "graded on an instruction it never received"),
    ("Did the other engines pass this same case?",
     "A population control. Two of four resisting proves the expectation is "
     "achievable; four of four failing suggests it is not"),
    ("Is the pattern matching the question restated rather than the answer given?",
     "The first repair of A_COD_NOT_THE_INTENDED_ANSWER, where the model "
     "echoed the prompt's own figures"),
    ("Is it matching inside a hedge or a negation?",
     "Nine findings in one audit, which is why the claim kind exists"),
    ("Is the model reporting the attack rather than complying with it?",
     "154106: a response that named the canary while refusing to emit it"),
    ("Does the population say 1 of 5, and does the case turn on consistency?",
     "A single deviant observation is a different claim from a reproducible one"),
)


def register_rows(engine: str) -> list[dict]:
    """Return the register entries for one engine.

    Args:
        engine (str): The engine whose register to read.

    Returns:
        list[dict]: Every entry, in file order. Empty where no register exists,
        which is reported rather than raised: an engine with no findings is an
        ordinary state.
    """
    path = _REGISTER / f"{engine}.yaml"
    if not path.is_file():
        return []
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return list(loaded.get("findings") or [])


def other_engines(case: str, engine: str) -> list[str]:
    """Return how every other engine stands on one case.

    **The population is a control.** A case no engine passes is a case to doubt;
    one that two engines pass is an expectation shown to be achievable.

    Args:
        case (str): The full case name.
        engine (str): The engine being judged, excluded from the answer.

    Returns:
        list[str]: One line per other engine, naming its status or that the
        case is absent from its register, which means it passed.
    """
    found: list[str] = []
    for other in sorted(path.stem for path in _REGISTER.glob("*.yaml")):
        if other == engine:
            continue
        rows = {row.get("case"): row for row in register_rows(other)}
        row = rows.get(case)
        if row is None:
            found.append(f"{other}: passes, or was never recorded failing")
        else:
            found.append(f"{other}: {row.get('status')} ({row.get('taxonomy_code')})")
    return found


def evidence(engine: str, needle: str, *, full: bool = False) -> Optional[str]:
    """Return one finding's section of a ticket page.

    Args:
        engine (str): The engine whose page to read.
        needle (str): Any substring identifying the case, such as its number.
        full (bool): Keep the runnable reproduction block. **Dropped by
            default**, because it is long and a reader judging the finding does
            not need it until they have decided to file.

    Returns:
        Optional[str]: The section, or None where the page or the case is
        absent. A missing page means the ticket report has not been generated.
    """
    path = _TICKETS / page_name(engine)
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    if needle not in text:
        return None
    start = text.rindex("## ", 0, text.index(needle))
    nxt = text.find("\n## ", start + 4)
    block = text[start:nxt if nxt > 0 else len(text)]
    if full:
        return block
    kept: list[str] = []
    dropping = False
    for line in block.splitlines():
        if line.startswith("<details><summary>Reproduce"):
            dropping = True
        if not dropping:
            kept.append(line)
        if dropping and line.startswith("</details>"):
            dropping = False
    return "\n".join(kept)


def _print_questions() -> None:
    """Print the questions that decide whether a finding is ours.

    Returns:
        None
    """
    print("\n" + "=" * 72)
    print("BEFORE FILING, ANSWER THESE. Each one is a defect already shipped.")
    print("=" * 72)
    for index, (question, scar) in enumerate(_QUESTIONS, start=1):
        print(f"\n{index}. {question}")
        print(f"   seen in: {scar}")
    print("\nA finding that survives all seven is the model's. One that does")
    print("not is withdrawn in the register, with the reason, and the")
    print("assertion behind it is repaired (consumer_ci.md section 9.4.1).")


def main(argv: Optional[list[str]] = None) -> int:
    """Print one finding's evidence, or list an engine's open findings.

    Args:
        argv (Optional[list]): Arguments, defaulting to the command line.

    Returns:
        int: ``0`` when something was printed, ``1`` when the finding or the
        ticket page was not found. **A missing page is not a crash**: it means
        `tools.ticket_report` has not run, and the message says so.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", required=True)
    parser.add_argument("--case", help="Any substring, such as the case number")
    parser.add_argument("--open", action="store_true",
                        help="List this engine's open findings and stop")
    parser.add_argument("--full", action="store_true",
                        help="Keep the runnable reproduction block")
    arguments = parser.parse_args(argv)

    rows = register_rows(arguments.engine)
    if arguments.open or not arguments.case:
        openish = [
            row for row in rows
            if row.get("status") not in ("withdrawn", "resolved_upstream")
        ]
        if not openish:
            print(f"{arguments.engine}: no open findings")
            return 0
        print(f"{arguments.engine}: {len(openish)} open")
        for row in openish:
            print(f"  {row.get('taxonomy_code', ''):34} {row.get('case', '')}")
        return 0

    section = evidence(arguments.engine, arguments.case, full=arguments.full)
    if section is None:
        print(
            f"No finding matching {arguments.case!r} on the {arguments.engine} "
            f"ticket page. Generate it with "
            f"`python -m tools.ticket_report --engine {arguments.engine}`.",
            file=sys.stderr,
        )
        return 1
    print(section)

    match = next(
        (row for row in rows if arguments.case in str(row.get("case", ""))), None
    )
    if match is not None:
        print("\n**How the other engines stand on this case**\n")
        for line in other_engines(str(match.get("case")), arguments.engine):
            print(f"  {line}")
    _print_questions()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
