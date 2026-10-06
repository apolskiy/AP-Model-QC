# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Whether a result from this suite means what it says.

Covers ``MQC_CAS_UNI_115713``, ``115714`` and ``115716``, inventoried in
``docs/design/consumer_ci.md`` section 4 and designed in sections 9.4.2 and
9.4.3.

**Split from ``mqc_uni_instrument.py`` on 2026-10-05**, which these two
subjects took to 904 lines against the nine-hundred-line runway ceiling
introduced the same day. The rule caught itself on its first run, which is the
outcome it was written for: the next subject belongs in a module of its own.

**One subject in two halves.** A failure that is ours reported as a model's,
and a pass that could never have been a failure. Both are the instrument
describing itself wrongly, and both reached a ticket page before anything
caught them.

A failure here is our defect, so the module carries no priority marker, per the
harness ``framework-rules.md`` section 3.3.
"""

import json
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Final

import allure
import pytest

from cmn.registries import is_registered_harness_code, registered_codes
from evaluation.screening import screen_text

from tests.cases.graded_support import (
    failure_detail,
    repository_root,
    shipped_corpus,
)
from tests.cases.vacuity_support import unfailable_assertions

pytestmark = pytest.mark.unit

_TAXONOMY_CODE: Final[re.Pattern] = re.compile(
    r"\b(QC_(?:LLM|HARNESS|SEC|DATA)_[A-Z_]+)\b"
)


@allure.epic("AP-Model-QC")
@allure.feature("Suite governance")
class TestMQCTheInstrumentDoesNotManufactureFindings:
    """Two ways a defect of ours becomes a finding about somebody's model.

    **Both of these produced a withdrawn finding on 2026-10-05**, and neither
    was caught by anything until a reader checked the arithmetic by hand. A
    false positive in the instrument is the most expensive defect this project
    can produce, because it arrives looking exactly like the output.
    """

    @allure.story("An ordinary case screens clean")
    def MQC_CAS_UNI_115713_a_screening_hit_on_an_ordinary_case_is_reported(
        self,
    ) -> None:
        """No recorded response on an ordinary case matches an attack vector.

        **On an ordinary case a screen hit aborts the observation**, so the
        observation does not evaluate, does not pass, and a single one of five
        makes the case `QC_LLM_INCONSISTENT`. A false positive in a vector is
        therefore a finding against a vendor.

        **The instance: `task_substitution` matched "an unhandled exception
        instead of a business-level answer"**, which is a model correctly
        describing the defect it was asked to find. claude `134109` was reported
        at 4 of 5 and is withdrawn.

        **A declared adversarial case is excluded**, because there a hit is
        evidence feeding the grade rather than an abort: a model quoting the
        payload it caught is expected, and the harness narrows the judge's
        exposure instead.

        Design: harness ``tier3_evaluation.md`` sections 3 and 5.2.

        Returns:
            None
        """
        root = repository_root()
        adversarial = {
            task.task_id for task in shipped_corpus()[0]
            if getattr(task, "contains_adversarial_content", False)
        }
        offenders: list[str] = []
        screened = 0
        for engine in sorted((root / "tests" / "fixtures" / "replay").glob("*")):
            if not engine.is_dir() or engine.name == "judgements":
                continue
            for recorded in sorted(engine.rglob("*.json")):
                task_id = recorded.parent.parent.name
                if task_id in adversarial:
                    continue
                screened += 1
                payload = json.loads(recorded.read_text(encoding="utf-8"))
                body = str((payload.get("response") or {}).get("text", ""))
                for finding in screen_text(task_id, "text", body):
                    offenders.append(
                        f"{engine.name}/{task_id} observation "
                        f"{recorded.stem} matches {finding.vector}: "
                        f"{finding.excerpt.strip()[:70]!r}"
                    )

        assert screened > 300, (
            f"only {screened} ordinary recorded responses were screened, so "
            f"the walk no longer reaches the corpus it is checking"
        )
        assert not offenders, (
            f"{len(offenders)} recorded response(s) on ordinary cases match an "
            f"attack vector, which aborts the observation and reports the "
            f"model for our own pattern: " + "; ".join(offenders)
        )

    @allure.story("Every failure message names its class")
    def MQC_CAS_UNI_115714_a_failure_message_without_a_taxonomy_code_is_reported(
        self,
    ) -> None:
        """Every message ``failure_detail`` can return carries a registered code.

        **A message without a code is recordable by nothing.**
        `tools/findings.py` classifies by the code in the text, so a failure
        carrying none is reported as `UNCLASSIFIED` and never enters the
        register: the finding exists, the gate is red, and the catalogue a
        vendor would be sent from does not have it.

        **The instance: the rubric branch.** `QC_LLM_RUBRIC_FAILURE` was
        registered, documented, and attached to the result, and absent from the
        one place a reader and the register both look. claude `134110` was
        therefore unrecordable until 2026-10-05, and it is a real finding.

        **All three branches, because the third was missing one too**, and an
        anomalous branch is exactly where a code is least likely to be noticed.

        Design: harness ``testing-standards.md`` section 4.

        Returns:
            None
        """
        rubric_only = SimpleNamespace(
            assertion_results=[],
            score=SimpleNamespace(value=1.0),
            judged=True,
            judge_skipped_reason=None,
        )
        assertion_failed = SimpleNamespace(
            assertion_results=[
                SimpleNamespace(
                    assertion_id="A_PROBE",
                    taxonomy_code="QC_LLM_DEFECT_MISSED",
                    detail="pattern absent",
                    passed=False,
                )
            ],
            score=None,
            judged=False,
            judge_skipped_reason=None,
        )
        neither = SimpleNamespace(
            assertion_results=[], score=None, judged=False,
            judge_skipped_reason=None,
        )

        uncoded: list[str] = []
        for name, probe in (
            ("an assertion failure", assertion_failed),
            ("a rubric failure", rubric_only),
            ("neither assertion nor score", neither),
        ):
            message = failure_detail(probe)
            # FOUND BY PATTERN, NOT BY SPLITTING. The assertion branch writes
            # the code parenthesised, `A_PROBE (QC_LLM_DEFECT_MISSED): detail`,
            # so a token scan sees a leading bracket and finds nothing. The
            # first version of this case failed on that and was wrong about
            # the message rather than the message being wrong.
            codes = _TAXONOMY_CODE.findall(message)
            registered = [
                code for code in codes if is_registered_harness_code(code)
                or code in registered_codes()
            ]
            if not registered:
                uncoded.append(f"{name}: {message[:90]!r}")

        assert not uncoded, (
            f"{len(uncoded)} failure message(s) carry no registered taxonomy "
            f"code, so the failure is UNCLASSIFIED and enters no register: "
            + "; ".join(uncoded)
        )


@allure.epic("AP-Model-QC")
@allure.feature("Suite governance")
class TestMQCAssertionsCanFail:
    """Whether a passing assertion is passing for a reason."""

    @allure.story("Every assertion can be made to fail")
    def MQC_CAS_UNI_115716_an_assertion_that_cannot_fail_is_reported(
        self,
    ) -> None:
        """No assertion in the corpus passes because it cannot fail.

        **This asks the opposite question from everything beside it.** The
        other checks ask whether a failure is real; an assertion that cannot
        fail reports nothing and looks exactly like coverage.

        **Four probes, and the tally is asserted as well as the absence.** A
        check that reached no assertions would report none unfailable, which is
        the vacuity it exists to prevent, one level up.

        **A declared probe is re-verified here on every run**, so a probe that
        stops working fails rather than quietly excusing its assertion.

        Design: ``consumer_ci.md`` section 9.4.3.

        Returns:
            None
        """
        root = Path(__file__).resolve().parents[2]
        unfailable, tally = unfailable_assertions(root)

        assert sum(tally.values()) > 100, (
            f"only {sum(tally.values())} assertion(s) were probed, so the walk "
            f"no longer reaches the corpus and reporting none unfailable "
            f"establishes nothing: {tally}"
        )
        assert not unfailable, (
            f"{len(unfailable)} assertion(s) cannot be made to fail by any "
            f"probe, so nothing establishes they test anything: "
            + "; ".join(unfailable)
        )
