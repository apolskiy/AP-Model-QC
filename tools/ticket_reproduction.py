# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""The parts of a ticket that state the test case and reproduce it, in and out of this repository.

Created: 2026-11-05
Last updated: 2026-11-05

This file contains ``case_steps``, which states a finding's test case step by
step: what is sent, how many times, what each response is checked for and what
it must do to pass; ``reproduce_outside``, which reproduces the recorded call
without this repository, from a ``request.json`` file posted by ``curl`` for
bash and ``curl.exe`` for PowerShell, or through the provider's SDK; and
``reproduce_through_repository``, which reproduces the case live through this
repository and then replays its committed recordings.

``tools.ticket_report`` places each part in a finding's ticket, and the
harness adapters declare the provider knowledge each one reads: the endpoint,
the headers, the credential variable and the reply field.

Specified by ``docs/design/consumer_ci.md`` section 9.5.5.13.
"""

from typing import Any, Final, Optional

from execution.adapters.registry import (
    adapter_for,
    reproduction_body,
    reproduction_curl,
    reproduction_snippet,
)

from tools.ticket_reasons import rule_lines

# WHERE THIS REPOSITORY AND THE HARNESS IT PINS ARE FETCHED FROM. main pairs
# with the harness's main in config/harness_pin.yaml.
_CLONE: Final[str] = "https://github.com/apolskiy/AP-Model-QC.git"
_HARNESS: Final[str] = (
    '"ap-harness-qc[dev] @ git+https://github.com/apolskiy/AP-Harness-QC@main"'
)


def case_steps(
    task: Optional[dict[str, Any]], rules: Any, request: Optional[dict[str, Any]], total: int
) -> list[str]:
    """Return the test case as numbered steps a reader outside this project can follow.

    Args:
        task (Optional[dict]): The task as the corpus holds it.
        rules (Any): The case's golden rule set, or None where unresolved.
        request (Optional[dict]): The recorded request, for the model requested.
        total (int): How many times the request was sent.

    Returns:
        list[str]: Markdown lines: what one request carries, how many times it
        is sent, what each response is checked for, and what passing takes.
    """
    task = task or {}
    model = str((request or {}).get("model") or "the model under test")
    carried: list[str] = []
    if str(task.get("system_instruction") or "").strip():
        carried.append("   - a system instruction, quoted in full under *Request as sent*")
    for document in task.get("context_documents") or []:
        if isinstance(document, dict):
            carried.append(f"   - the document `{document.get('document_id', '')}`")
    carried.append("   - the prompt")
    tools = [
        f"`{item.get('tool_name', '')}`"
        for item in task.get("available_tools") or [] if isinstance(item, dict)
    ]
    if tools:
        carried.append(f"   - the tools {', '.join(tools)}, offered for the model to call")
    checks = [f"   {line}" for line in (rule_lines(rules, task) if rules is not None else [])]
    return [
        "**The test case, step by step**", "",
        f"1. One request is sent to `{model}`, carrying:", *carried,
        f"2. The same request is sent {total} times, each a separate call with no "
        f"shared history.",
        "3. Each response is held to the rule:", *(checks or ["   - the rule under *Expected*"]),
        "4. The case passes only when every response holds to every part of the rule.",
        "",
    ]


def reproduce_outside(
    engine: str, request: Optional[dict[str, Any]], failing: int, total: int
) -> list[str]:
    """Return how to re-issue the recorded call without this repository.

    Args:
        engine (str): The engine the call was made against.
        request (Optional[dict]): The recorded request, None where none was stored.
        failing (int): How many of the responses showed the problem.
        total (int): How many times the request was sent.

    Returns:
        list[str]: Markdown lines. Where the recording is the wire body: the
        body as ``request.json``, a ``curl`` for bash and a ``curl.exe`` for
        PowerShell reading it, then the SDK call. Otherwise the SDK call alone,
        saying why. Then how many times to send it and which reply field to read.
    """
    out = ["**Reproduce without this repository**", ""]
    if request is None:
        return [*out, "_No request was recorded, so none can be re-issued._", ""]
    adapter = adapter_for(engine)
    body = reproduction_body(engine, request)
    snippet = reproduction_snippet(engine, request)
    if body:
        out.extend([
            "1. Save this body as `request.json`:", "", *fenced(body, "json"), "",
            f"2. Set `{adapter.API_KEY_ENV}` and post the file. In bash:", "",
            *fenced(reproduction_curl(engine, request), "bash"), "",
            "   In PowerShell, which runs `curl.exe` in place of its own `curl` alias:", "",
            *fenced(reproduction_curl(engine, request, shell="powershell"), "powershell"), "",
        ])
        sdk = "The same call through the provider's SDK, if you prefer it:"
    else:
        out.extend([
            "1. This recording carries a field with no REST form, so the call is "
            "re-issued through the provider's SDK, which sends it exactly.", "",
            f"2. Set `{adapter.API_KEY_ENV}` and run:", "",
        ])
        sdk = ""
    if snippet:
        out.extend([*([sdk, ""] if sdk else []), *fenced(snippet, "python"), ""])
    out.extend([
        f"3. Send it {total} times. The problem appeared on {failing} of {total} "
        f"attempts, so a single send may not show it.",
        f"4. In each reply read {adapter.reproduction_reply_fields()}, and compare "
        f"it with the rule under *Expected* and with the responses quoted above.",
        "",
    ])
    return out


def reproduce_through_repository(engine: str, case: str, judge_engine: str) -> list[str]:
    """Return how to reproduce the case live through this repository, then replay it.

    Args:
        engine (str): The engine under test.
        case (str): The full case name.
        judge_engine (str): The engine that judged it, empty where none did.

    Returns:
        list[str]: Markdown lines: clone and install, set the credential
        variables by name for bash and PowerShell, run the case live with its
        prerequisites, where the result lands, and the replay command.
    """
    parts = case.split("_")
    number = parts[3] if len(parts) > 3 else case
    variables = [adapter_for(engine).API_KEY_ENV]
    judged = f" --judge-engine {judge_engine}" if judge_engine else ""
    if judge_engine:
        variables.append(adapter_for(judge_engine).API_KEY_ENV)
    variables = list(dict.fromkeys(variables))
    run = f"python -m pytest --engine {engine} --mode live --tests {number} --with-prerequisites"
    return [
        "**Reproduce with this repository**", "",
        "1. Clone this repository and install the harness it pins "
        "(`config/harness_pin.yaml`):", "",
        *fenced("\n".join([
            f"git clone {_CLONE}", "cd AP-Model-QC",
            f"python -m pip install {_HARNESS}",
            "python -m pip install --no-deps --editable .",
        ]), "bash"), "",
        f"2. Set {' and '.join(f'`{name}`' for name in variables)}. In bash:", "",
        *fenced("\n".join(f'export {name}="<your key>"' for name in variables), "bash"), "",
        "   In PowerShell:", "",
        *fenced("\n".join(f'$env:{name} = "<your key>"' for name in variables), "powershell"),
        "",
        "3. Run the case live. `--with-prerequisites` runs the cases it rests on first"
        + (", and the judge engine scores each response" if judge_engine else "") + ":", "",
        *fenced(run + judged), "",
        f"4. The run's last lines give the case's verdict and its counts. Each response "
        f"is written under `tests/fixtures/replay/{engine}/`"
        + (f", and each judgement under `tests/fixtures/replay/judgements/{engine}/`"
           if judge_engine else "") + ".",
        "5. To see the responses this ticket quotes, replay the committed recordings, "
        "which needs no credential:", "",
        *fenced(f"python -m pytest --engine {engine} --mode replay --tests {number} "
                f"--with-prerequisites"), "",
    ]


def fenced(text: str, info: str = "") -> list[str]:
    """Return text inside a code fence longer than any backtick run it holds.

    Args:
        text (str): What the fence holds.
        info (str): The fence's language tag, if any.

    Returns:
        list[str]: The opening fence, the text, and the closing fence.
    """
    longest = 0
    run = 0
    for character in text:
        run = run + 1 if character == "`" else 0
        longest = max(longest, run)
    fence = "`" * max(3, longest + 1)
    return [f"{fence}{info}", text.rstrip(), fence]
