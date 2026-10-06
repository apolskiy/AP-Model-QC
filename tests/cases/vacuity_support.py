# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Whether each assertion can fail at all, which is the opposite question.

Specified by ``docs/design/consumer_ci.md`` section 9.4.3.

**Everything else asks whether a failure is real. This asks whether a pass
is.** An assertion that cannot fail reports nothing and looks exactly like
coverage, and nothing in this project detected that class until 2026-10-05.

**Three probes, tried in order, because no single one reaches every
assertion.**

| Probe | Reaches |
|---|---|
| Constructed | Presence, substring, length and schema assertions, where
  a violating input follows from the kind |
| Synthesised | Absence assertions whose pattern carries literal alternatives |
| Observed | Absence assertions some real recorded response happens to match |

**A synthesis is verified before it is trusted.** A candidate that does not
match is discarded rather than counted, so this never claims more than it
establishes.

**The declared probes are the honest remainder.** Five absence patterns defeat
the synthesiser, and each carries a hand-written violating input here rather
than in the corpus: a probe is test apparatus and the corpus is the request a
model receives. The check verifies every declared probe actually makes its
assertion fire, so a wrong one fails rather than quietly excusing the
assertion.
"""

import json
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Final, Optional

import yaml

from evaluation.assertions import run_assertion

# Text carrying nothing a presence pattern is likely to want.
_EMPTY_ISH: Final[str] = "zzz."

# HAND-WRITTEN AND VERIFIED, for the absence patterns the synthesiser cannot
# reach. Each was confirmed to make its assertion fire before being recorded,
# and the check confirms it again on every run: a probe that stops working is
# a failure here rather than an assertion quietly going unchecked.
DECLARED_PROBES: Final[dict[str, str]] = {
    "A_AMB_NO_SILENT_ASSUMPTION": "I will set the retry_threshold to 5.",
    "A_COD_NO_INVENTED_CALLS": "It calls response.raise_for_status() here.",
    "A_INS_COMPLETE_SENTENCE": "Summary:\n- an unterminated bullet\n",
    "A_MAT_OR_NOT_READ_AS_AND": "The candidate meets 33.3% of the requirement",
    "A_MAT_OPEN_CLAIMS_NO_NAMED_MATCH": "postgres is listed as a match",
}


def shipped_assertions(root: Path) -> list[tuple[str, str, dict[str, Any]]]:
    """Return every assertion the corpus declares.

    Args:
        root (Path): The repository root.

    Returns:
        list[tuple]: Family filename, rule identifier and the assertion.
    """
    found: list[tuple[str, str, dict[str, Any]]] = []
    for source in sorted((root / "data" / "rules").glob("*.yaml")):
        payload = yaml.safe_load(source.read_text(encoding="utf-8")) or []
        entries = payload if isinstance(payload, list) else payload.get(
            "rule_sets", payload.get("rules", [])
        )
        for rule in entries:
            if not isinstance(rule, dict) or not rule.get("rule_id"):
                continue
            for assertion in rule.get("assertions") or []:
                if isinstance(assertion, dict) and assertion.get("assertion_id"):
                    found.append((source.name, rule["rule_id"], assertion))
    return found


def recorded_responses(root: Path) -> list[str]:
    """Return every recorded candidate response, for use as a probe.

    Args:
        root (Path): The repository root.

    Returns:
        list[str]: The response text of each recording.
    """
    bodies: list[str] = []
    replay = root / "tests" / "fixtures" / "replay"
    for engine in sorted(replay.glob("*")):
        if not engine.is_dir() or engine.name == "judgements":
            continue
        for recorded in engine.rglob("*.json"):
            payload = json.loads(recorded.read_text(encoding="utf-8"))
            bodies.append(str((payload.get("response") or {}).get("text", "")))
    return bodies


# WHAT VIOLATES EACH KIND, as a table rather than a branch per kind. Seven
# returns in one function is one past the limit, and the limit is right here:
# this is a lookup wearing the shape of a decision.
_FILLER: Final[dict[str, str]] = {
    "characters": "x",
    "words": "word ",
    "lines": "line\n",
    "bullets": "- item\n",
}


def constructed_probe(assertion: dict[str, Any]) -> Optional[str]:
    """Return a violating input that follows from the assertion's kind.

    Args:
        assertion (dict): The assertion.

    Returns:
        Optional[str]: The probe, or ``None`` where the kind does not yield one
        mechanically, which is reported rather than treated as sound.
    """
    kind = str(assertion.get("kind", ""))
    parameters = assertion.get("parameters", {}) or {}

    if kind == "json_schema":
        return "not json at all"
    if kind == "contains" or (kind == "regex" and parameters.get("present") is True):
        return _EMPTY_ISH
    if kind == "not_contains":
        value = str(parameters.get("value", parameters.get("substring", "")))
        return f"prefix {value} suffix" if value else None
    if kind == "length":
        return _length_probe(parameters)
    return None


def _length_probe(parameters: dict[str, Any]) -> Optional[str]:
    """Return text breaching whichever bound a length assertion declares.

    Args:
        parameters (dict): The assertion's parameters.

    Returns:
        Optional[str]: Empty text for a minimum, overlong text for a maximum,
        or ``None`` where neither bound is declared.
    """
    if parameters.get("minimum") is not None:
        return ""
    maximum = parameters.get("maximum")
    if maximum is None:
        return None
    unit = str(parameters.get("unit", "characters"))
    return _FILLER.get(unit, "x") * (int(maximum) + 2)


def synthesised_matches(pattern: str) -> list[str]:
    """Return candidate strings built from a pattern's literal fragments.

    **Candidates, not matches.** The caller verifies each against the pattern
    and discards what does not match, so a weak synthesiser understates rather
    than lies.

    Args:
        pattern (str): The regular expression.

    Returns:
        list[str]: Candidate strings, longest first.
    """
    candidates: list[str] = []
    for group in re.findall(r"\(([^()?][^()]*)\)", pattern):
        for option in group.split("|"):
            literal = re.sub(r"\\[a-zA-Z]|\\.|[\[\]{}+*?^$]", "", option)
            literal = literal.replace("\\s", " ").strip()
            if len(literal) >= 3:
                candidates.append(literal)
    bare = re.sub(r"\(\?i\)|\\b|\\w\*|\\s\+|\\s\*|[\\()\[\]{}|+*?^$]", " ", pattern)
    bare = " ".join(bare.split())
    if len(bare) >= 3:
        candidates.append(bare)
    return sorted(set(candidates), key=len, reverse=True)


def _fires(assertion: dict[str, Any], probe: str) -> bool:
    """Report whether this assertion fails on the given input.

    Args:
        assertion (dict): The assertion.
        probe (str): The candidate violating input.

    Returns:
        bool: True when the assertion reports a failure.
    """
    node = SimpleNamespace(
        assertion_id=assertion["assertion_id"],
        kind=assertion["kind"],
        parameters=assertion.get("parameters", {}) or {},
        severity=assertion.get("severity", "violation"),
        taxonomy_code=assertion.get("taxonomy_code", ""),
    )
    return not run_assertion(node, probe).passed


def unfailable_assertions(root: Path) -> tuple[list[str], dict[str, int]]:
    """Report every assertion no probe can make fail, and how each was reached.

    Args:
        root (Path): The repository root.

    Returns:
        tuple: One message per unfailable assertion, and a tally naming which
        probe reached the rest.
    """
    corpus = recorded_responses(root)
    tally = {"constructed": 0, "synthesised": 0, "observed": 0, "declared": 0}
    unfailable: list[str] = []

    for family, rule_id, assertion in shipped_assertions(root):
        name = str(assertion["assertion_id"])
        label = f"{family}:{rule_id}:{name}"

        probe = constructed_probe(assertion)
        if probe is not None and _fires(assertion, probe):
            tally["constructed"] += 1
            continue

        declared = DECLARED_PROBES.get(name)
        if declared is not None:
            if _fires(assertion, declared):
                tally["declared"] += 1
            else:
                unfailable.append(
                    f"{label} has a declared probe that no longer makes it "
                    f"fire, so the assertion is excused by a stale probe"
                )
            continue

        parameters = assertion.get("parameters", {}) or {}
        pattern = str(parameters.get("pattern", ""))
        if pattern and any(
            _fires(assertion, candidate)
            for candidate in synthesised_matches(pattern)
        ):
            tally["synthesised"] += 1
            continue

        if any(_fires(assertion, body) for body in corpus):
            tally["observed"] += 1
            continue

        unfailable.append(
            f"{label} ({assertion.get('kind')}) cannot be made to fail by a "
            f"constructed, synthesised or observed probe, so nothing "
            f"establishes it tests anything. Add a verified probe to "
            f"DECLARED_PROBES or correct the assertion"
        )
    return unfailable, tally
