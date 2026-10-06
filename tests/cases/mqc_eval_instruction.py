# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Whether the model does what the instruction said, in the shape it said.

Covers ``MQC_EVL_EVAL_134300`` through ``134308``, inventoried in
``docs/testing/model_evaluation_test_plan.md`` section 4.1 and specified by
section 9.5.

**This family can be judged from the answer alone**, which is what separates it
from grounding: no source has to be consulted to see whether four bullets were
returned when three were asked for. The assertions settle shape and the rubric
grades quality inside it.

**30001 and 30002 are an ablation pair**, differing only in whether the format
instruction is stated at all. A model returning JSON when nothing asked for it
is following a habit rather than an instruction, and the pair exists so that
`134300` cannot take credit for that habit.

**Everything here presupposes `134300`.** A model that will not honour a format
it was handed tells us nothing further by also mishandling a bullet ceiling.
"""

from typing import Any

import allure
import pytest

from tests.cases.graded_support import observe_repeatedly
from tests.cases.consistency_support import assert_consistent_pass

pytestmark = pytest.mark.evaluator


@allure.epic("AP-Model-QC")
@allure.feature("Instruction following")
class TestMQCDeclaredFormat:
    """The stated shape, and the control that keeps it honest."""

    @pytest.mark.base
    @pytest.mark.priority(1)
    @allure.story("Declared format")
    def MQC_EVL_EVAL_134300_obeys_declared_output_format(self, request: Any) -> None:
        """Two named keys and nothing outside the object.

        **Parsing and preamble are checked separately**, because a response
        that parses once a preamble is stripped has still disobeyed "return
        nothing outside the JSON object".

        **Foundational.** Every case below elaborates on a model that honours
        a format it was given.

        Args:
            request (Any): pytest's request, carrying the invocation.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config,
            "MQC_TASK_ins_format_stated",
            "MQC_RULE_ins_format_stated",
        )
        assert_consistent_pass(results)

    @pytest.mark.priority(2)
    @pytest.mark.depends_on("134300")
    @allure.story("Ablation control")
    def MQC_EVL_EVAL_134301_format_violation_is_recorded(self, request: Any) -> None:
        """The same task with the format instruction removed.

        **The control, and it runs the opposite way.** Identical material and
        request, so a model returning JSON here is exhibiting a habit. Without
        this case `134300` would be credited for behaviour no instruction
        produced.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config,
            "MQC_TASK_ins_format_absent",
            "MQC_RULE_ins_format_absent",
        )
        assert_consistent_pass(results)


@allure.epic("AP-Model-QC")
@allure.feature("Instruction following")
class TestMQCQuantitativeCeilings:
    """One task, four ceilings, four separate findings.

    **They share a task deliberately.** A model that returns five bullets of
    thirty words each has broken two ceilings in one response, and splitting
    them across tasks would make that look like two unrelated events.
    """

    @pytest.mark.priority(2)
    @pytest.mark.depends_on("134300")
    @allure.story("Bullet ceiling")
    def MQC_EVL_EVAL_134302_rejects_output_exceeding_bullet_ceiling(
        self, request: Any
    ) -> None:
        """A count, which is the least interpretive check in the family.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config, "MQC_TASK_ins_quantities", "MQC_RULE_ins_quantities"
        )
        assert_consistent_pass(results)

    @pytest.mark.priority(3)
    @pytest.mark.depends_on("134300")
    @allure.story("Word ceiling")
    def MQC_EVL_EVAL_134303_rejects_sentence_exceeding_word_ceiling(
        self, request: Any
    ) -> None:
        """A per-sentence ceiling, which a whole-response count would miss.

        **P3 rather than P2.** Exceeding a word ceiling inside one sentence is
        a drift a reader absorbs; exceeding the bullet count changes the shape
        of the answer.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config, "MQC_TASK_ins_quantities", "MQC_RULE_ins_word_ceiling"
        )
        assert_consistent_pass(results)

    @pytest.mark.priority(2)
    @pytest.mark.depends_on("134300")
    @allure.story("Capitalisation")
    def MQC_EVL_EVAL_134304_sentence_begins_with_capital(self, request: Any) -> None:
        """A positive check, and the family needs one.

        The other three ceilings are all violations to be caught. **A suite of
        only negatives cannot distinguish a compliant model from a broken
        checker**, which is the positive control this case supplies.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config, "MQC_TASK_ins_quantities", "MQC_RULE_ins_capitalised"
        )
        assert_consistent_pass(results)

    @pytest.mark.priority(4)
    @pytest.mark.depends_on("134300")
    @allure.story("Sentence completeness")
    def MQC_EVL_EVAL_134305_sentence_lacking_subject_or_verb_is_flagged(
        self, request: Any
    ) -> None:
        """A fragment under a word ceiling is the predictable way to comply.

        **P4, informational.** Telegraphic prose is a quality signal rather
        than a broken instruction, and pricing it higher would let a stylistic
        judgement gate a run.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config, "MQC_TASK_ins_quantities", "MQC_RULE_ins_complete_sentence"
        )
        assert_consistent_pass(results)


@allure.epic("AP-Model-QC")
@allure.feature("Instruction following")
class TestMQCOrderingAndProhibition:
    """Instructions about arrangement and about what must not appear."""

    @pytest.mark.priority(2)
    @pytest.mark.depends_on("134300")
    @allure.story("Ordering")
    def MQC_EVL_EVAL_134306_measurables_ordered_above_remainder(
        self, request: Any
    ) -> None:
        """An instruction about arrangement rather than about content.

        Everything asked for may be present and the instruction still
        disobeyed, which is what makes ordering its own requirement.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config, "MQC_TASK_ins_ordering", "MQC_RULE_ins_ordering"
        )
        assert_consistent_pass(results)

    @pytest.mark.priority(2)
    @pytest.mark.depends_on("134300")
    @allure.story("Prohibition")
    def MQC_EVL_EVAL_134307_prohibited_glyph_is_recorded(self, request: Any) -> None:
        """A prohibition, which is the inverse of every ceiling above.

        A ceiling says how much; this says never. **The distinction matters
        because a model can satisfy every ceiling and still emit the one
        character it was told not to.**

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config, "MQC_TASK_ins_prohibition", "MQC_RULE_ins_prohibition"
        )
        assert_consistent_pass(results)

    @pytest.mark.priority(2)
    @pytest.mark.depends_on("134300")
    @allure.story("Combined constraints")
    def MQC_EVL_EVAL_134308_combined_constraints_do_not_degrade_each_other(
        self, request: Any
    ) -> None:
        """Every constraint above, in one request.

        **Compliance is not additive**, which is the whole claim. A model that
        honours each constraint alone may drop one when several apply, and no
        single-constraint case can see that.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config, "MQC_TASK_ins_combined", "MQC_RULE_ins_combined"
        )
        assert_consistent_pass(results)
