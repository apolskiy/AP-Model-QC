# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""A ticket's opening summary: the prompt, the incorrect responses and any judge at odds.

Created: 2026-11-09
Last updated: 2026-11-09

This file contains ``summary_lines``, which returns a ticket's opening summary:
the prompt whole; each incorrect response by the words its check reported, or
every response where the case failed; each judgement whose verdict disagrees
with its response's checks; and ``judge_split``, which names identical
responses the judge scored on opposite sides of the threshold.

``tools.ticket_report`` places the summary under the problem statement, and
``tools.ticket_files`` carries the split onto the filing sheet. The summary
quotes; the evidence stays whole in the body below it.

Specified by ``docs/design/consumer_ci.md`` section 9.5.5.14.
"""

from typing import Final, Optional

_EXCERPT: Final[int] = 200
_STATED: Final[str] = "asserted in '"
_CORRECTED: Final[str] = "', corrected after it in '"

Judged = Optional[tuple[bool, float, str]]


def summary_lines(
    prompt: Optional[str],
    responses: list[str],
    outcomes: list[tuple[int, bool, str]],
    judged: list[Judged],
    warned: bool,
) -> list[str]:
    """Return a ticket's opening summary.

    Args:
        prompt (Optional[str]): The user prompt the case sent, or None where
            the task could not be resolved.
        responses (list): Each recorded response's text, in order.
        outcomes (list): Each response's check outcome: its index, whether its
            checks passed, and what was reported.
        judged (list): Each response's judged outcome, None where unjudged.
        warned (bool): Whether the finding is a warning, a pass that corrected
            itself.

    Returns:
        list[str]: Markdown lines. **A failed case lists every response**, the
        passing ones being the contrast a reader needs; a warning lists only
        the responses that carried it. A judgement is quoted only where its
        verdict disagrees with its response's checks, and identical responses
        judged apart are flagged.
    """
    total = len(responses)
    checks = {index: (passed, detail) for index, passed, detail in outcomes}
    judgements = list(judged) + [None] * (total - len(judged))
    wrong = [index for index in range(total) if _incorrect(checks.get(index), judgements[index])]
    shown = wrong if warned else (list(range(total)) if wrong else [])
    quoted = " ".join(prompt.split()) if prompt else ""
    out = ["**Summary**", "",
           f'*Prompt:* "{quoted}"' if quoted else "*Prompt:* _the task could not be resolved._",
           "", f"*Incorrect, {len(wrong)} of {total}:*", ""]
    out.extend(_response_line(index, total, responses[index], checks.get(index),
                              judgements[index]) for index in shown)
    disagreeing = [
        f"- Response {index + 1}: its checks failed and the judge passed it, scoring "
        f"{judgement[1]:g}. {judgement[2]}".rstrip()
        for index, judgement in enumerate(judgements)
        if judgement is not None and judgement[0] and not checks.get(index, (True, ""))[0]
    ]
    out.extend(["", "*Judgements disagreeing with the outcome:*" if disagreeing
                else "*Judgements:* none disagree with the outcome.", ""])
    if disagreeing:
        out.extend([*disagreeing, ""])
    split = judge_split(responses, judgements)
    if split:
        out.extend([f"**Identical responses judged differently:** {split}", ""])
    return out


def judge_split(responses: list[str], judged: list[Judged]) -> str:
    """Return identical responses the judge scored on opposite sides of the threshold.

    Args:
        responses (list): Each recorded response's text, in order.
        judged (list): Each response's judged outcome, None where unjudged.

    Returns:
        str: A sentence naming each such group, or empty where there is none.
        Identical text with opposite verdicts means the judge, not the model,
        separated them, so the finding is reviewed as possibly ours before it
        is filed.
    """
    groups: dict[str, list[int]] = {}
    for index, text in enumerate(responses):
        normalised = " ".join(text.split())
        if normalised:
            groups.setdefault(normalised, []).append(index)
    named = []
    for members in groups.values():
        verdicts = {judged[index][0] for index in members
                    if index < len(judged) and judged[index] is not None}
        if len(verdicts) == 2:
            named.append(" and ".join(str(index + 1) for index in members))
    if not named:
        return ""
    return (f"responses {'; '.join(named)} have the same text, and the judge passed one "
            f"and failed another, so the judge separated them, not the model. "
            f"Review before filing.")


def _incorrect(checks: Optional[tuple[bool, str]], judgement: Judged) -> bool:
    """Report whether a response showed the problem: failed, warned, or failed the judge.

    Args:
        checks (Optional[tuple]): Whether its checks passed, and what was reported.
        judgement (Judged): Its judged outcome, None where unjudged.

    Returns:
        bool: True where it is incorrect.
    """
    passed, detail = checks or (True, "")
    return not passed or bool(detail) or (judgement is not None and not judgement[0])


def _response_line(
    index: int, total: int, text: str, checks: Optional[tuple[bool, str]], judgement: Judged
) -> str:
    """Return one response's summary line, quoting the words that decided it.

    Args:
        index (int): The response's position, from zero.
        total (int): How many responses were recorded.
        text (str): The response's text.
        checks (Optional[tuple]): Whether its checks passed, and what was reported.
        judgement (Judged): Its judged outcome, None where unjudged.

    Returns:
        str: A list item. A warning quotes what was stated and what corrected
        it; a failed check quotes what it reported; a judged failure quotes the
        judge; each other response quotes its opening.
    """
    passed, detail = checks or (True, "")
    label = f"- Response {index + 1} of {total}:"
    if passed and detail:
        stated, corrected = _warning_words(detail)
        return f'{label} stated "{stated}" Corrected later: "{corrected}"'
    opening = f'Opens: "{_excerpt(text)}"'
    if not passed:
        return f"{label} failed its checks: {detail}. {opening}"
    if judgement is not None and not judgement[0]:
        return (f"{label} the judge failed it, scoring {judgement[1]:g}. "
                f"{judgement[2]} {opening}")
    return f"{label} passed. {opening}"


def _warning_words(detail: str) -> tuple[str, str]:
    """Return the stated words and the correcting words a warning's detail quotes.

    Args:
        detail (str): The check's report, holding ``asserted in '...'`` and
            ``corrected after it in '...'``.

    Returns:
        tuple: The stated words and the correcting words, the whole detail as
        the stated words where it does not carry both.
    """
    head, found, corrected = detail.rpartition(_CORRECTED)
    if not found or _STATED not in head:
        return detail, ""
    return head.split(_STATED, 1)[1], corrected.rstrip("'")


def _excerpt(text: str) -> str:
    """Return a response's opening, on one line.

    Args:
        text (str): The response's text.

    Returns:
        str: Its first 200 characters, whitespace collapsed, with ``...`` where
        it was cut.
    """
    flat = " ".join(text.split()) or "[no text]"
    return flat if len(flat) <= _EXCERPT else flat[:_EXCERPT - 3].rstrip() + "..."
