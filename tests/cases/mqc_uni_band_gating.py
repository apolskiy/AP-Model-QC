# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""How a band's result is gated and how it is reported.

Covers ``MQC_CAS_UNI_115709`` and ``115712``, inventoried in
``docs/design/consumer_ci.md`` section 4 and designed in sections 3.12.2 and
3.12.3.

**Split from ``mqc_uni_workflows.py`` on 2026-10-07**, which the blocking floor
took to 945 lines against the nine-hundred-line runway ceiling. The subject is
narrower than that module's: not whether a workflow is shaped correctly, but
what a band is allowed to conclude from what it ran.

**Both cases here answer the same question in different directions.** One says a
band must publish its result even when the run was red; the other says it may
not call that result a pass when a third of the band never ran. A band reporting
green at seven of eleven was the defect that produced the second.

A failure here is our defect, so the module carries no priority marker, per the
harness ``framework-rules.md`` section 3.3.
"""

from typing import Any

import allure
import pytest

from tools.band_floor import assess_blocking

from tests.cases.workflow_support import (
    jobs as _jobs,
    load as _load,
    needs as _needs,
    run_lines as _run_lines,
)

pytestmark = pytest.mark.unit


class TestMQCBandGating:
    """The gate's own summary, and the condition it has to run under."""

    @allure.story("The band table survives the run that needed it")
    def MQC_CAS_UNI_115709_a_gate_reporting_only_on_green_is_reported(self) -> None:
        """The reporting job needs every band and runs whatever they did.

        **A red run is the one worth reading.** The per-band table exists to
        answer a release question, and the release question is only ever asked
        when something failed, so a job that skipped itself on a band failure
        would produce its summary exactly when nobody needed it.

        Design: ``consumer_ci.md`` section 3.12.3.

        Returns:
            None
        """
        gate = _jobs(_load("gate-target.yml"))
        assert "report" in gate, (
            f"the gate publishes no band table, so a reader has to open three "
            f"jobs to answer one question: {sorted(gate)}"
        )
        reporting = gate["report"]

        # IT NEEDS EVERY BAND, so no band's result can be missing from the table
        # because the job ran before that band finished.
        required = set(_needs(reporting))
        missing = {"graded-p0", "graded-p1", "graded-lower"} - required
        assert not missing, (
            f"the reporting job does not wait for {sorted(missing)}, so the "
            f"table it publishes can omit a band that was still running"
        )

        # AND IT RUNS ON A RED RUN. `success()` here would be the defect.
        condition = str(reporting.get("if", "")).lower()
        assert "always()" in condition, (
            f"the reporting job is conditional on {condition!r} rather than "
            f"always(), so the summary is absent from the runs that need it"
        )

        # THE BANDS ARE NAMED RATHER THAN INFERRED, so renaming an artifact
        # cannot relabel a band's result in the published table.
        rendered = "\n".join(_run_lines(reporting))
        assert "--overall" in rendered, (
            "the reporting job does not request the per-band table, so it "
            "publishes a single figure that decides nothing"
        )
        for band in ("--priority 0", "--priority 1", "--priority 2,3,4"):
            assert band in rendered, (
                f"the reporting job states no {band!r}, so a row would be "
                f"attributed by filename rather than by what produced it: "
                f"{rendered}"
            )

        # AND IT JUDGES NOTHING. Each band still gates on its own status.
        assert not any("band_floor" in line for line in _run_lines(reporting)), (
            "the reporting job applies a floor, so a reader became a judge and "
            "a band's verdict is now computed in two places"
        )


    @allure.story("A blocking band answers for every case it selected")
    def MQC_CAS_UNI_115712_a_blocking_band_passing_on_unmeasured_cases_is_reported(
        self, tmp_path: Any
    ) -> None:
        """Seven of eleven is not a hundred percent of anything.

        **The band this guards reported success.** claude band P1 selected
        eleven, executed seven, passed every one it executed, and called itself
        a pass while four release blocking cases skipped behind failed
        foundations: execution pass 100 percent, total pass 63.6.

        **A skip is not a pass and not a failure; it is an absence**, and a band
        that exists to block a release cannot report green on an absence. The
        replaced claim was that pytest's exit status enforces V1 because "any
        observation not passing" and "this band had a failure" say the same
        thing. A skipped case is an observation not passing and an exit status
        cannot see one.

        Design: ``consumer_ci.md`` section 3.12.2.

        Args:
            tmp_path (Any): pytest's temporary directory.

        Returns:
            None
        """
        report = tmp_path / "band.xml"

        # THE SHAPE THAT REPORTED GREEN: everything executed passed, and a
        # third of the band never ran.
        report.write_text(
            '<testsuite>'
            + '<testcase name="MQC_EVL_SEC_154000_alpha"/>' * 7
            + '<testcase name="MQC_EVL_SEC_154001_beta">'
              '<skipped message="QC_HARNESS_DEPENDENCY_UNMET"/></testcase>' * 4
            + "</testsuite>",
            encoding="utf-8",
        )
        code, message = assess_blocking(report)
        assert code != 0, (
            f"a blocking band passed with four of eleven cases unmeasured, "
            f"which is a selective passing rate and not a passing rate: "
            f"{message}"
        )
        assert "11 selected, 7 executed" in message, (
            f"the message does not state the selected denominator beside what "
            f"ran, so a reader sees a rate without knowing what it is over: "
            f"{message}"
        )
        # SKIPPED IS A STATE AND IT CARRIES ITS CAUSE. "Not measured" names no
        # outcome, and the remedy differs by cause: a dependency skip clears
        # when the band above it is fixed and one of ours is ours. The project
        # owner's correction, 2026-10-07.
        assert "4 skipped behind a higher band failure" in message, (
            f"the skipped cases are not named as skipped, or their cause is "
            f"absent, so a reader cannot tell whose defect this is: {message}"
        )
        assert "not measured" not in message, (
            f"the message still reports a non-state: {message}"
        )

        # AND A BAND THAT MEASURED EVERYTHING PASSES, or the floor blocks every
        # release rather than the ones that earned it.
        report.write_text(
            '<testsuite>'
            + '<testcase name="MQC_EVL_SEC_154000_alpha"/>' * 11
            + "</testsuite>",
            encoding="utf-8",
        )
        code, message = assess_blocking(report)
        assert code == 0, (
            f"a band that measured and passed all eleven was refused: {message}"
        )

        # A QUARANTINED CASE LEAVES THE DENOMINATOR, because somebody wrote
        # down why, with an expiry and a finding behind it. That is what
        # separates an exclusion from whatever the run happened to skip.
        report.write_text(
            '<testsuite>'
            + '<testcase name="MQC_EVL_SEC_154000_alpha"/>' * 10
            + '<testcase name="MQC_EVL_SEC_154099_declared">'
              '<skipped message="quarantined"/></testcase>'
            + "</testsuite>",
            encoding="utf-8",
        )
        code, message = assess_blocking(report)
        assert code != 0, (
            "an undeclared skip was excused, so any skip can leave the "
            "denominator without anybody deciding to"
        )
        code, message = assess_blocking(report, frozenset({"154099"}))
        assert code == 0, (
            f"a declared quarantine did not leave the denominator, so the one "
            f"recorded exclusion cannot be used: {message}"
        )
        assert "1 quarantined" in message, (
            f"the message hides the exclusion, which is the thing a reader has "
            f"to be able to audit: {message}"
        )

        # A FAILURE STILL FAILS, so this is a floor added rather than one moved.
        report.write_text(
            '<testsuite><testcase name="MQC_EVL_SEC_154000_alpha"/>'
            '<testcase name="MQC_EVL_SEC_154001_beta">'
            '<failure message="QC_LLM_INJECTION_SUSCEPTIBLE"/></testcase>'
            "</testsuite>",
            encoding="utf-8",
        )
        assert assess_blocking(report)[0] != 0, (
            "a blocking band with a failure passed"
        )

        # AN ERROR IS OURS AND IS REFUSED RATHER THAN FAILED, which keeps the
        # distinction the taxonomy rests on.
        report.write_text(
            '<testsuite><testcase name="MQC_EVL_SEC_154000_alpha">'
            '<error message="QC_HARNESS_PARSER_ERROR"/></testcase></testsuite>',
            encoding="utf-8",
        )
        code, message = assess_blocking(report)
        assert code == 4, (
            f"an error was reported as a model finding rather than refused: "
            f"{code}, {message}"
        )
