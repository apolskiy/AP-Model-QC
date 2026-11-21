# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Doubles for observing a case once the judge has stopped or the job has ended.

Created: 2026-11-21
Last updated: 2026-11-21

This file contains ``stopped_channel``, which replaces the run's judge channel
with one that has stopped on a code and carries the provider's account of it;
``refuse_dispatch``, which makes any candidate dispatch fail loudly; and
``skip_reason_of``, which observes a case and returns the reason it skipped,
failing the calling case where it was dispatched or not skipped.

**Used by** ``tests/cases/mqc_uni_stopped_judge.py``, whose cases check what a
stopped judge and an ended job do to the cases after them. Kept out of the case
module because collection reads only cases there.

Specified by ``docs/design/consumer_ci.md`` section 6.4.5.
"""

from types import SimpleNamespace
from typing import Any

import pytest

from tests.cases import graded_support


def stopped_channel(monkeypatch: pytest.MonkeyPatch, code: str, detail: str) -> None:
    """Replace the judge channel with a stopped one, and the observation records with nothing.

    Args:
        monkeypatch (pytest.MonkeyPatch): pytest's patcher.
        code (str): The code the channel stopped on.
        detail (str): The failure's detail, as the channel states it.

    Returns:
        None
    """
    monkeypatch.setattr(
        graded_support, "_channel",
        lambda *args, **kwargs: SimpleNamespace(
            stopped=code, stopped_detail=detail, engine="claude", invoke=None,
            args=(args, kwargs), take_wire_attempts=tuple),
    )
    monkeypatch.setattr(graded_support, "record_observation", lambda *args: None)
    monkeypatch.setattr(graded_support, "record_observation_step", lambda *args: None)


def refuse_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make any candidate dispatch raise, so a case that dispatches cannot pass.

    Args:
        monkeypatch (pytest.MonkeyPatch): pytest's patcher.

    Returns:
        None
    """

    def dispatched(*args: Any, **kwargs: Any) -> Any:
        """Refuse a dispatch.

        Args:
            *args (Any): Unused.
            **kwargs (Any): Unused.

        Returns:
            Any: Never returns.

        Raises:
            LookupError: Always, naming the dispatch.
        """
        raise LookupError(f"dispatched with {len(args) + len(kwargs)} arguments")

    monkeypatch.setattr(graded_support, "dispatch_case", dispatched)


def skip_reason_of(config: Any, task_id: str, rule_id: str) -> str:
    """Observe one case and return why it skipped.

    Args:
        config (Any): The simulated pytest configuration.
        task_id (str): The task.
        rule_id (str): The rule set.

    Returns:
        str: The skip's message.

    Raises:
        pytest.fail.Exception: Where the case was dispatched, or ran without
            skipping.
    """
    reason = ""
    try:
        graded_support.observe(config, task_id, rule_id)
    except LookupError as error:
        pytest.fail(f"the case was dispatched: {error}")
    except pytest.skip.Exception as skipped:
        reason = str(skipped)
    if not reason:
        pytest.fail("the case ran without skipping")
    return reason
