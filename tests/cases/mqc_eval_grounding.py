# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Whether the answer stays inside what the source actually says.

Covers ``MQC_EVL_EVAL_134200`` through ``134205``, inventoried in
``docs/testing/model_evaluation_test_plan.md`` section 4.1 and specified by
section 9.7.

**Grounding is measured against a source**, which is what separates this family
from instruction following: that one can be judged from the answer alone and
this one cannot. Every task here supplies a document and every rule checks the
answer against it.

**The source carries exact figures on purpose.** A figure is checkable by
string match, which turns "did the model alter a stated value" from a judgement
into an assertion. Prose claims would need a judge to adjudicate, and a judge
is itself a model.

**Three foundations, because grounding fails in three unrelated ways.**
Asserting something absent (`134200`), altering something present (`134201`) and
contradicting something derivable (`134203`) are different defects, and the code
family formulates all three again in a second domain.
"""

from typing import Any

import allure
import pytest

from tests.cases.graded_support import assert_consistent_pass, observe_repeatedly

pytestmark = pytest.mark.evaluator


@allure.epic("AP-Model-QC")
@allure.feature("Grounding")
class TestMQCFabricationAndAlteration:
    """The two foundational failures: adding, and changing."""

    @pytest.mark.base
    @pytest.mark.priority(1)
    @allure.story("Fabrication")
    def MQC_EVL_EVAL_134200_asserts_nothing_absent_from_source(
        self, request: Any
    ) -> None:
        """A fabrication target is designed into the source.

        The quarterly report names four regions and says nothing about a
        fifth, so a model mentioning one has asserted something absent and the
        check is **exact rather than interpretive**.

        **Foundational**, and formulated again in the code domain by `134100`
        through `134102`: a grounding requirement is domain-independent, and the
        point of a second formulation is that the behaviour survives the change
        of domain.

        Args:
            request (Any): pytest's request, carrying the invocation.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config,
            "MQC_TASK_gnd_no_fabrication",
            "MQC_RULE_gnd_no_fabrication",
        )
        assert_consistent_pass(results)

    @pytest.mark.base
    @pytest.mark.priority(1)
    @allure.story("Alteration")
    def MQC_EVL_EVAL_134201_does_not_alter_explicitly_stated_value(
        self, request: Any
    ) -> None:
        """Every figure in the source is checked for alteration.

        **A different defect from fabrication.** A model that invents nothing
        and quietly rounds a stated figure has produced an answer that reads as
        sourced and is not, which is the harder of the two to notice.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config, "MQC_TASK_gnd_exact_values", "MQC_RULE_gnd_exact_values"
        )
        assert_consistent_pass(results)


@allure.epic("AP-Model-QC")
@allure.feature("Grounding")
class TestMQCContextAndTruth:
    """Using what was supplied, and not contradicting it."""

    @pytest.mark.priority(2)
    @pytest.mark.depends_on("134200")
    @allure.story("Context use")
    def MQC_EVL_EVAL_134202_does_not_ignore_supplied_context(
        self, request: Any
    ) -> None:
        """The context contradicts common assumption, deliberately.

        The internal code name and its meaning exist **nowhere but this
        document**, so a model answering from prior knowledge rather than from
        what it was handed becomes visible. A source agreeing with the world
        could not make that distinction.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config, "MQC_TASK_gnd_uses_context", "MQC_RULE_gnd_uses_context"
        )
        assert_consistent_pass(results)

    @pytest.mark.base
    @pytest.mark.priority(2)
    @pytest.mark.depends_on("134200")
    @allure.story("Falsehood")
    def MQC_EVL_EVAL_134203_does_not_state_verifiable_falsehood(
        self, request: Any
    ) -> None:
        """The source states an arithmetic relation the answer must not deny.

        **A falsehood is checkable only where the ground truth is fixed**,
        which is why the claim under test is arithmetic rather than a matter of
        interpretation.

        **Both a foundation and a dependent.** It presupposes `134200`, and
        `134106` through `134108` presuppose it, formulating the same requirement
        over code.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config, "MQC_TASK_gnd_no_falsehood", "MQC_RULE_gnd_no_falsehood"
        )
        assert_consistent_pass(results)


@allure.epic("AP-Model-QC")
@allure.feature("Grounding")
class TestMQCDirectionalFigures:
    """An asymmetric pair, and the asymmetry is the requirement."""

    @pytest.mark.base
    @pytest.mark.priority(1)
    @allure.story("Overstating")
    def MQC_EVL_EVAL_134205_overstating_a_sourced_figure_is_rejected(
        self, request: Any
    ) -> None:
        """Claiming more than the source supports.

        **Foundational, and the strict half of the pair.** A model that
        overstates is unsafe in a way that one which understates is not, so
        this is the case that has to hold before the permitted direction means
        anything.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config,
            "MQC_TASK_gnd_overstate_rejected",
            "MQC_RULE_gnd_overstate_rejected",
        )
        assert_consistent_pass(results)

    @pytest.mark.priority(2)
    @pytest.mark.depends_on("134205")
    @allure.story("Understating")
    def MQC_EVL_EVAL_134204_understating_a_sourced_figure_is_permitted(
        self, request: Any
    ) -> None:
        """A boundary case, and the boundary is direction rather than size.

        Understating a sourced figure is **permitted** where the instruction
        asks for a conservative floor. Two tasks rather than one, because a
        single task cannot ask for both directions at once.

        **This is why a numeric check must be directional.** A symmetric
        "does the figure match" rule would fail this case and pass nothing
        useful.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config,
            "MQC_TASK_gnd_understate_permitted",
            "MQC_RULE_gnd_understate_permitted",
        )
        assert_consistent_pass(results)
