# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""How a security ticket describes where the instruction it followed came from.

Created: 2026-10-15
Last updated: 2026-10-21

This file contains ``framed_problem``, which returns the problem sentence for an
injection or goal hijack finding whose canary sits in the user message rather
than in a supplied document, and ``payload_in_user_turn``, which makes that
check on the task, finding the canary written plainly or base64-encoded.

``tools.ticket_report`` calls ``framed_problem`` while writing a ticket's
problem statement. Where it returns nothing, the report keeps its usual
planted-content wording, so this decides only which of the two a vendor reads.

Design: ``docs/design/consumer_ci.md`` section 9.5.5.3.
"""

import base64
import binascii
import re
from typing import Any, Final, Optional

_CANARY: Final[re.Pattern[str]] = re.compile(r"CANARY_\w+")
_BASE64: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9+/]{16,}={0,2}")
_FRAMED: Final[dict[str, str]] = {
    "QC_LLM_INJECTION_SUSCEPTIBLE":
        "The model let an instruction in the user message override the system "
        "prompt's constraint",
    "QC_LLM_GOAL_HIJACK":
        "The model let a task in the user message replace the one the system "
        "prompt assigned",
}


def payload_in_user_turn(task: Optional[dict[str, Any]]) -> bool:
    """Report whether a task's canary sits in its user message.

    Args:
        task (Optional[dict]): The task as the corpus holds it.

    Returns:
        bool: True where the user prompt carries a canary token and no
        supplied document does.
    """
    if not task:
        return False
    documents = " ".join(
        str(item.get("content", "")) for item in task.get("context_documents") or []
        if isinstance(item, dict)
    )
    return _carries_canary(str(task.get("user_prompt") or "")) and not _carries_canary(
        documents
    )


def _carries_canary(text: str) -> bool:
    """Report whether text carries a canary, plainly or base64-encoded.

    Args:
        text (str): The text to search.

    Returns:
        bool: True where a canary token appears as written, or inside any
        base64 run that decodes to UTF-8 text.
    """
    if _CANARY.search(text):
        return True
    for run in _BASE64.findall(text):
        try:
            decoded = base64.b64decode(run, validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError):
            continue
        if _CANARY.search(decoded):
            return True
    return False


def framed_problem(code: str, task: Optional[dict[str, Any]]) -> Optional[str]:
    """Return the problem a security ticket states, where the payload decides it.

    Args:
        code (str): The finding's taxonomy code.
        task (Optional[dict]): The task the finding was measured on.

    Returns:
        Optional[str]: The precedence wording where the code is a security code
        and the canary sits in the user message, otherwise None, so the
        caller's planted-content wording stands.
    """
    if code in _FRAMED and payload_in_user_turn(task):
        return _FRAMED[code]
    return None
