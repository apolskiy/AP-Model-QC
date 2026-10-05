# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""The apparatus the corpus cases assert against.

Specified by the harness ``test_taxonomy.md`` section 13.

**Extracted 2026-10-05**, when the case module stood at 969 lines against the
thousand-line ceiling. The screening walk in particular is a procedure rather
than a claim: it reads every shipped payload and reports what it found, and the
case that calls it is the claim.

**Public names, deliberately.** A support module is an interface, and a leading
underscore on something another module imports says the opposite of what is
true.

**`_repository_root` is gone rather than moved**, being one of four
byte-identical copies of ``graded_support.repository_root``.
"""

import ast
import re
from pathlib import Path
from typing import Any, Final

from cmn.vectors import match_vectors


def normalised(text: str) -> str:
    """Return text with line endings and trailing blank lines removed.

    Args:
        text (str): Either copy of an excerpt.

    Returns:
        str: A form comparable across platforms.
    """
    return text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")


def named_pairs(source: Path) -> list[tuple[int, str, str]]:
    """Return every task and rule pair a graded module names literally.

    Args:
        source (Path): The module to read.

    Returns:
        list: Line number, task id and rule id for each pair found.
    """
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    found: list[tuple[int, str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
        if name not in {"observe", "observe_repeatedly", "case_for"}:
            continue
        pair = [
            argument.value
            for argument in node.args
            if isinstance(argument, ast.Constant)
            and isinstance(argument.value, str)
            and argument.value.startswith("MQC_")
        ]
        if len(pair) >= 2:
            found.append((node.lineno, pair[0], pair[1]))
    return found


def demoted_or_mislabelled(rows: list[dict[str, str]]) -> list[str]:
    """Return a problem for every row whose derived family is not primary.

    **Primary and not merely present.** The relation is many to many, so a row
    may carry further families after the derived one; what it may not do is
    omit it, replace it, or demote it behind a secondary. Design
    ``model_evaluation_test_plan.md`` section 8.5.1.

    Args:
        rows (list[dict]): Matrix rows, each with ``families`` and ``test_ids``.

    Returns:
        list[str]: One description per offending row, empty when every row
        whose layer maps to a family carries that family first.
    """
    problems: list[str] = []
    for row in rows:
        layers = {
            found.group(1)
            for case in (row.get("test_ids") or "").split(";")
            if (found := CASE_LAYER.match(case.strip())) is not None
        }
        derived = {FAMILY_BY_LAYER[name] for name in layers if name in FAMILY_BY_LAYER}
        if not derived:
            continue
        if len(derived) > 1:
            problems.append(
                f"{row.get('requirement_id')} names cases in two mapped layers "
                f"{sorted(derived)}, so no single family is primary"
            )
            continue
        expected = next(iter(derived))
        declared = [
            value.strip() for value in (row.get("families") or "").split(";")
            if value.strip()
        ]
        if not declared:
            problems.append(f"{row.get('requirement_id')} carries no family, expected {expected}")
        elif declared[0] != expected:
            problems.append(
                f"{row.get('requirement_id')} carries {declared!r}, expected "
                f"{expected} first"
            )
    return problems


def assert_every_payload_is_screened(tasks: Any) -> None:
    """Refuse a payload that lost the two-screen cross-check by accident.

    **Lifted out of the case that grew past the local-variable ceiling**, which
    is the right reason to extract: the check reads as one claim and the test
    body now says so in one line.

    Args:
        tasks (Any): Every shipped task.

    Returns:
        None

    Raises:
        AssertionError: When an untagged payload matches no vector, when a
            tagged one matches after all, or when too few match for
            ``MQC_EVL_UNI_114608`` to have material to compare.
    """
    recognised = 0
    exempt: list[str] = []
    payloads = 0
    for task in tasks:
        if not task.contains_adversarial_content:
            continue
        payloads += 1
        payload = (task.user_prompt or "") + " ".join(
            document.content for document in task.context_documents
        )
        hits = match_vectors(payload)
        evasive = "screen_evasion" in task.tags

        if hits:
            recognised += 1
            # A TAG THAT STOPPED BEING TRUE WOULD HIDE A REGRESSION, so the
            # exemption is checked in both directions and cannot rot into an
            # excuse for a real gap (harness tier1_ingestion.md section 7.3.4).
            assert not evasive, (
                f"{task.task_id} declares screen_evasion and matches "
                f"{sorted({entry.vector for entry in hits})}, so the tag is "
                f"stale and is now silencing a check it no longer needs"
            )
            continue

        assert evasive, (
            f"{task.task_id} matches no registered vector and does not declare "
            f"screen_evasion, so it has lost the two-screen cross-check by "
            f"accident rather than by design"
        )
        exempt.append(task.task_id)

    # A SHARE, NOT A NUMBER. The exemption has to stay scarce or it becomes the
    # path of least resistance for a genuine pattern gap, which is how the two
    # gaps found on 2026-09-26 survived: `154103` and `154107` matched
    # incidentally and looked covered. A proportion scales with the corpus where
    # a fixed count would either throttle a growing family or stop biting
    # (harness tier1_ingestion.md section 7.3.5).
    #
    # THE RULE ABOVE STOPS A STALE TAG AND THIS ONE STOPS A LAZY ONE. They are
    # different failures: one is a tag that outlived its truth, the other a tag
    # reached for instead of asking whether the pattern is wrong.
    allowed = int(payloads * EVASION_SHARE)
    assert len(exempt) <= allowed, (
        f"{len(exempt)} of {payloads} payloads declare screen_evasion, above "
        f"the {EVASION_SHARE:.0%} share that leaves {allowed}. Before tagging "
        f"another, ask whether the vector pattern is what is wrong: "
        f"{sorted(exempt)}"
    )
    assert recognised >= payloads - allowed, (
        f"only {recognised} of {payloads} payloads match a vector, so the "
        f"two-screen comparison has too little to compare"
    )

# THE LAYERS THAT MAP TO EXACTLY ONE EVALUATION FAMILY. Data and not a pair of
# conditionals: `test_taxonomy.md` section 11.6 records that the registry is
# open and a sixth family is expected, so a further one-to-one family is a row
# here. EVAL is deliberately absent, since that layer spans three families and
# nothing declares which applies (section 11.5.1).
FAMILY_BY_LAYER: Final[dict[str, str]] = {
    "SEC": "injection_resistance",
    "TOOL": "tool_compliance",
}


# A CASE IDENTIFIER'S MODULE AND LAYER TOKENS, as `MQC_EVL_SEC_154100_...`.
CASE_LAYER = re.compile(r"MQC_[A-Z]+_([A-Z]+)_\d+")


# The share of declared payloads that may decline the vector screen.
# Fifteen percent of twenty payloads is three, against two in use.
EVASION_SHARE: Final[float] = 0.15
