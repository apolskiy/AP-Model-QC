# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""The fields a graded observation records, measured or skipped.

Created: 2026-11-06
Last updated: 2026-11-06

This file contains ``declared_fields``, the half of an observation the corpus
declares; ``skip_fields``, the observation a skipped case contributes to the
pass rate; and ``measured_fields``, the observation an evaluated case produced,
which turns an unavailable or withheld judgement into a skip carrying the
judge's own code.

**``observe`` in ``graded_support`` calls them** after dispatch and evaluation,
and hands what they return to the harness's ``assemble_observation``. The
record is what the pass rate, the bands and the tickets read, so a wrong field
here is a wrong figure everywhere downstream.

**Not collected**, as the filename carries no ``mqc_`` prefix. Moved out of
``graded_support.py`` on 2026-11-06, which had reached the runway ceiling
(harness ``code-style.md`` section 5.1).

Specified by ``docs/design/consumer_ci.md`` section 6.4.5 and harness
``cmn_verdict_and_cli.md`` section 5.4.1.
"""

from typing import Any, Final

from tests.cases.consistency_support import harness_code

# THE LAYER A RULE BELONGS TO, from its identifier's third token. The layer is
# a property of the test and `observe` has no item, so it is derived from the
# corpus the case comes from: one rule file per layer, which `pytest.ini`'s
# marker registry and the design's one-layer-per-file rule already require.
_LAYER_BY_RULE: Final[dict[str, str]] = {
    "amb": "EVAL", "cod": "EVAL", "gnd": "EVAL", "ins": "EVAL", "mat": "EVAL",
    "sec": "SEC", "tul": "TOOL",
}

# THE REASON A JUDGEMENT WAS NOT AVAILABLE, matched rather than inferred. The
# pipeline sets it where the replay store held no judgement for an observation
# (harness `tier3_evaluation.md` section 6.5).
_JUDGEMENT_UNAVAILABLE: Final[str] = "judgement_unavailable"

# THE REASON AND CODE AN OBSERVATION LEFT UNJUDGED ON REQUEST CARRIES (harness
# `harness_test_taxonomy.md` section 7.4.1.4).
_UNJUDGED: Final[str] = "unjudged"
_WITHHELD_CODE: Final[str] = "QC_HARNESS_JUDGE_WITHHELD"


def declared_fields(case: Any, index: int) -> dict[str, Any]:
    """Return the half of an observation the corpus declares.

    **Shared by a measured case and a skipped one**, because the identity, the
    band and the traced requirements are properties of the case rather than of
    what happened to it. A skipped case that reported a different priority from
    the one it was selected into would leave the band unable to answer for it.

    Args:
        case (Any): The joined task and rule set.
        index (int): Which observation this is.

    Returns:
        dict: Identity and grading metadata.
    """
    rules = case.golden_rules
    return {
        "case_id": case.case_id,
        "layer": _LAYER_BY_RULE.get(str(rules.rule_id).split("_")[2], "EVAL"),
        "observation_index": index,
        "priority": rules.priority,
        "priority_conditions": list(rules.priority_conditions),
        "requirement_ids": list(rules.requirement_ids),
        # DECLARED BY THE RULE SET, not derived from the layer. The layer
        # answers for SEC and TOOL because each maps to one family and could
        # never have answered for EVAL, which spans four. Harness
        # `harness_test_taxonomy.md` section 11.8.3.
        "families": tuple(rules.families),
    }


def skip_fields(
    case: Any, outcome: Any, index: int, *, reason: str, code: str
) -> dict[str, Any]:
    """Return the observation a skipped case contributes to the pass rate.

    **A skip is a non-pass, and the reason decides whether it is a failure**
    (harness `harness_test_taxonomy.md` section 7.4.1). Recording it is what gives the
    rate a skip to count: nothing recorded a skipped case, so a band that
    skipped a third of its cases reported a rate over the rest.

    Args:
        case (Any): The joined task and rule set.
        outcome (Any): The dispatch outcome, or None where nothing dispatched.
        index (int): Which observation this is.
        reason (str): A registered skip reason.
        code (str): The taxonomy code naming what stopped it.

    Returns:
        dict: Fields an :class:`Observation` accepts.
    """
    response = getattr(outcome, "response", None)
    return {
        **declared_fields(case, index),
        "outcome": "skip",
        "skip_reason": reason,
        "taxonomy_code": code,
        "engine": str(getattr(outcome, "engine", "") or ""),
        "mode": str(getattr(outcome, "mode", "") or ""),
        "requested_model": str(getattr(response, "requested_model", "") or ""),
        "resolved_model": str(getattr(response, "resolved_model", "") or ""),
    }


def measured_fields(case: Any, outcome: Any, result: Any, index: int) -> dict[str, Any]:
    """Return the observation this case produced, ready to record.

    **The two halves the harness design names** (`cmn_verdict_and_cli.md`
    section 5.4.1): what dispatch measured, and the grading metadata the rule
    set declares, which since 2026-10-04 includes the evaluation families. The
    layer is still derived from the rule identifier, because ``observe`` holds
    no pytest item and the layer is a property of the test.

    An unavailable judgement records an ``environmental`` skip carrying the
    judge's own harness code, and a withheld one an ``unjudged`` skip
    (``consumer_ci.md`` sections 6.4.2 and 6.4.5). A passing result carrying a
    warning code is recorded ``passw`` with that code (section 6.4.6).

    Args:
        case (Any): The joined task and rule set.
        outcome (Any): The dispatch outcome.
        result (Any): What evaluation produced.
        index (int): Which observation this is.

    Returns:
        dict: Fields an :class:`Observation` accepts.
    """
    response = getattr(outcome, "response", None)
    codes = list(getattr(result, "taxonomy_codes", ()) or ())

    # A JUDGE THAT DID NOT ANSWER IS NOT A MODEL FAILURE. The model produced a
    # response; our judgement of it is missing, so the observation is a skip
    # whose reason leaves the pass rate rather than a fail charged to the
    # model (harness `harness_test_taxonomy.md` section 7.4.1). It carries the
    # judge's own code, not the first of any family: an assertion that failed
    # before the judge was asked leads the list (section 6.4.5).
    if getattr(result, "judge_skipped_reason", "") == _JUDGEMENT_UNAVAILABLE:
        return skip_fields(
            case,
            outcome,
            index,
            reason="environmental",
            code=harness_code(result),
        )

    # A JUDGE WITHHELD ON REQUEST is not a measurement either, and never a pass:
    # the screen and the assertions held and the judged criteria were not
    # checked, so the observation is a skip that leaves the rate.
    if getattr(result, "judge_skipped_reason", "") == _UNJUDGED:
        return skip_fields(case, outcome, index, reason=_UNJUDGED, code=_WITHHELD_CODE)

    # AN ANSWER THAT CORRECTED ITSELF passed, and carries the code of what it
    # corrected so the finding can name it (section 6.4.6).
    warnings = list(getattr(result, "warning_codes", ()) or ()) if result.passed else []
    return {
        **declared_fields(case, index),
        "outcome": ("passw" if warnings else "pass") if result.passed else "fail",
        # THE FIRST CODE, because a record carries one root-cause class and the
        # pipeline reports them in the order it found them. The rest reach the
        # attachment with the assertions that produced them.
        "taxonomy_code": (codes or warnings or [None])[0],
        "engine": str(getattr(outcome, "engine", "") or ""),
        "mode": str(getattr(outcome, "mode", "") or ""),
        "requested_model": str(getattr(response, "requested_model", "") or ""),
        "resolved_model": str(getattr(response, "resolved_model", "") or ""),
        "duration": int(getattr(outcome, "duration_ms", 0) or 0),
        "duration_kind": str(getattr(outcome, "duration_kind", "measured") or "measured"),
        "score": getattr(result, "score", None),
    }
