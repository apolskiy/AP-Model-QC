# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Support code for the preconditions that observe a case with its judge and records replaced.

Created: 2026-11-17
Last updated: 2026-11-20

This file contains ``isolate_observation``, which replaces the judge channel
and the observation records of ``graded_support`` with doubles, collecting what
is recorded; ``observed_result``, one evaluated observation, measured or missing
its judgement; and ``MISSING_JUDGEMENT`` and ``MISSING_RECORDING``, the records
of a judgement and a recording the replay store could not find.

``mqc_uni_partial_recording.py`` and ``mqc_uni_stopped_judge.py`` import it.
Not collected, as the name carries no ``mqc_`` prefix.

Specified by ``docs/design/consumer_ci.md`` sections 6.4.5 and 9.4.5.
"""

from types import SimpleNamespace
from typing import Any, Final, Optional

import pytest

from cmn.missing_artifact import ARTIFACT_MISSING, MissingArtifact

from tests.cases import graded_support

MISSING_JUDGEMENT: Final[MissingArtifact] = MissingArtifact(
    kind="judgement", path="tests/fixtures/replay/judgements/grok/gemini/t/r/1.json",
    detail="is absent: no judgement of t::r observation 1",
)
MISSING_RECORDING: Final[MissingArtifact] = MissingArtifact(
    kind="recording", path="tests/fixtures/replay/grok/t/r/0.json",
    detail="is absent: no recording of t::r on grok observation 0",
)


def isolate_observation(monkeypatch: pytest.MonkeyPatch, recorded: list[Any]) -> None:
    """Replace the judge channel and the observation records with doubles.

    The channel answers and has not stopped; each recorded observation is
    appended to ``recorded``, and the observation steps record nothing.

    Args:
        monkeypatch (pytest.MonkeyPatch): pytest's patcher.
        recorded (list): Receives each recorded observation.

    Returns:
        None
    """
    monkeypatch.setattr(
        graded_support, "_channel",
        lambda *args, **kwargs: SimpleNamespace(
            stopped=None, engine="claude", invoke=None, args=(args, kwargs),
            take_wire_attempts=tuple),
    )
    monkeypatch.setattr(
        graded_support, "record_observation",
        lambda observation, *rest: recorded.append(observation),
    )
    monkeypatch.setattr(
        graded_support, "record_observation_step", lambda *args, **kwargs: None
    )


def observed_result(*, passed: bool, missing: Optional[MissingArtifact] = None) -> Any:
    """Return one evaluated observation, measured or missing its judgement.

    Args:
        passed (bool): Whether a measured one passed.
        missing (Optional[MissingArtifact]): The judgement replay could not use.

    Returns:
        Any: An object answering what the observation loop and the skip read.
    """
    return SimpleNamespace(
        passed=passed and missing is None,
        judge_skipped_reason="judgement_unavailable" if missing else None,
        taxonomy_codes=(ARTIFACT_MISSING,) if missing else (),
        missing_artifact=missing,
    )
