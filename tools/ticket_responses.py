# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""The responses part of a ticket, and the appendix holding what the judge was given.

Created: 2026-11-05
Last updated: 2026-11-06

This file contains ``responses_block``, which quotes every recorded response
whole, each labelled by its checks and, where the judge decided the finding,
by the judge's score and rationale; and returns the appendix holding every
judge prompt and, where the checks decided the finding, the judge's scores.

``tools.ticket_report`` places the responses after the request as sent and
the appendix at the end of the ticket. The judge's prompt is this instrument
rather than the vendor's model, so it is never in the body.

Specified by ``docs/design/consumer_ci.md`` sections 9.5.5.8 and 9.5.5.13.
"""

from typing import Optional

from tools.ticket_reproduction import fenced


def responses_block(
    engine: str,
    responses: list[str],
    outcomes: list[tuple[int, bool, str]],
    judged: Optional[list[Optional[tuple[bool, float, str]]]] = None,
    prompts: Optional[list[str]] = None,
) -> tuple[list[str], list[str]]:
    """Return every response, each labelled, and the appendix the judge's material goes to.

    Args:
        engine (str): The engine under test.
        responses (list): Each recorded response's text, in order.
        outcomes (list): Each response's check outcome: its index, whether its
            checks passed, and what failed if not.
        judged (Optional[list]): Each response's judged outcome, whether it
            passed, its score and the rationale, None where it was not judged.
        prompts (Optional[list]): Each response's judge prompt, empty where the
            judge never saw it.

    Returns:
        tuple: The body's lines and the appendix's lines. **The judge decided
        the finding** where a response passed its checks and failed the judge,
        and then each score and rationale stands under its response; otherwise
        they go to the appendix. Every judge prompt goes to the appendix. The
        appendix is empty where nothing was judged.
    """
    if not any(text.strip() for text in responses):
        return ([
            "**Responses**", "",
            f"_No recording at `tests/fixtures/replay/{engine}/`, so this "
            f"finding cannot show what was returned._", "",
        ], [])
    checks = {index: (passed, detail) for index, passed, detail in outcomes}
    judgements = list(judged or [])
    total = len(responses)
    judgements.extend([None] * (total - len(judgements)))
    shown = list(prompts or [])
    shown.extend([""] * (total - len(shown)))
    decided = any(
        checks.get(index, (True, ""))[0] and judgement is not None and not judgement[0]
        for index, judgement in enumerate(judgements)
    )
    body = [f"**Responses.** The problem appeared on "
            f"{failing_count(total, outcomes, judgements)} of {total} attempts. "
            f"Every response is quoted whole.", ""]
    appendix: list[str] = []
    for index, text in enumerate(responses):
        body.extend([
            f"*Response {index + 1} of {total}.* "
            f"{_label(checks.get(index, (True, '')), judgements[index], decided)}", "",
            *fenced(text or "[no text and no tool call]"), "",
        ])
        judgement = judgements[index]
        if judgement is not None and not decided:
            appendix.extend([
                f"*The judge on response {index + 1} of {total}.* "
                f"{'Passed' if judgement[0] else 'Failed'}, scoring {judgement[1]:g}. "
                f"{judgement[2]}".rstrip(), "",
            ])
        if shown[index]:
            appendix.extend([
                "<details>",
                f"<summary>Judge prompt, response {index + 1} of {total}</summary>", "",
                *fenced(shown[index]), "", "</details>", "",
            ])
    if appendix:
        appendix = ["**Appendix: what the judge was given and returned**", "", *appendix]
    return body, appendix


def failing_count(
    total: int,
    outcomes: list[tuple[int, bool, str]],
    judged: Optional[list[Optional[tuple[bool, float, str]]]] = None,
) -> int:
    """Return how many responses failed their checks or the judge.

    Args:
        total (int): How many responses were recorded.
        outcomes (list): Each response's check outcome.
        judged (Optional[list]): Each response's judged outcome, None where unjudged.

    Returns:
        int: The count.
    """
    checks = {index: passed for index, passed, _ in outcomes}
    judgements = list(judged or [])
    return sum(
        1 for index in range(total)
        if not checks.get(index, True)
        or (index < len(judgements) and judgements[index] is not None
            and not judgements[index][0])
    )


def _label(
    checks: tuple[bool, str], judgement: Optional[tuple[bool, float, str]], decided: bool
) -> str:
    """Return one response's label: its checks, then the judge where the judge decided.

    Args:
        checks (tuple): Whether its checks passed, and what failed if not.
        judgement (Optional[tuple]): Its judged outcome, None when unjudged.
        decided (bool): Whether the judge decided the finding.

    Returns:
        str: The label.
    """
    passed, detail = checks
    if not passed:
        if judgement is None:
            return f"Failed its checks, so the judge was not called: {detail}"
        scored = (f"the judge scored it {judgement[1]:g}. {judgement[2]}".rstrip()
                  if decided else "the judge's score is in the appendix.")
        return f"Failed its checks: {detail}; {scored}"
    if judgement is None:
        return "Passed its checks."
    if not decided:
        return "Passed its checks. The judge's score is in the appendix."
    if not judgement[0]:
        return f"Failed: the judge scored it {judgement[1]:g}. {judgement[2]}".rstrip()
    return f"Passed its checks and the judge, scoring {judgement[1]:g}. {judgement[2]}".rstrip()
