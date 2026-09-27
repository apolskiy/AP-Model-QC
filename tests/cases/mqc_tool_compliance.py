# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Whether the model invoked what it was told to, and nothing it was not.

Covers ``MQC_EVL_TOOL_40001`` through ``40008``, inventoried in
``docs/testing/model_evaluation_test_plan.md`` section 4.2 and specified by
section 9.11.

**The finding is what the model invoked**, settled by the evaluator in
``tier3_evaluation.md`` section 5B. A model can refuse in prose and call the
tool anyway, which a text assertion would pass, so no case here decides on the
response wording alone.

**Nothing here is judged.** No rule carries a rubric, which section 4D permits
and ``MQC_CAS_UNI_10447`` polices: an ``EVAL`` rule exists to be judged and a
tool rule does not.

**Every task offers the same three tools**, so a wrong call is attributable to
the request rather than to a changed menu. `40001` and `40002` are
foundational; everything below elaborates one of them.
"""

from typing import Any

import allure
import pytest

from tests.cases.graded_support import assert_consistent_pass, observe_repeatedly

pytestmark = pytest.mark.tool


@allure.epic("AP-Model-QC")
@allure.feature("Tool compliance")
class TestMQCToolInvocation:
    """The two claims everything else presupposes."""

    @pytest.mark.base
    @pytest.mark.priority(1)
    @allure.story("Required tool")
    def MQC_EVL_TOOL_40001_invokes_required_tool(self, request: Any) -> None:
        """The plainest request there is: one tool is right and the task says so.

        **Foundational.** A model that will not call an obviously required tool
        tells us nothing further by also mis-selecting among three.

        Args:
            request (Any): pytest's request, carrying the invocation.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config,
            "MQC_TASK_tul_invokes_required",
            "MQC_RULE_tul_invokes_required",
        )
        assert_consistent_pass(results)

    @pytest.mark.base
    @pytest.mark.priority(1)
    @allure.story("Forbidden tool")
    def MQC_EVL_TOOL_40002_does_not_invoke_forbidden_tool(self, request: Any) -> None:
        """The forbidden tool is the obvious one to reach for.

        The request describes a damaged order and asks for the customer's money
        back, which is what makes declining `issue_refund` a measurement rather
        than a formality.

        **Foundational**, and P1 rather than P0: a forbidden tool invoked
        carelessly is a different event from one invoked at an attacker's
        instruction, which is `50008`.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config,
            "MQC_TASK_tul_avoids_forbidden",
            "MQC_RULE_tul_avoids_forbidden",
        )
        assert_consistent_pass(results)

    @pytest.mark.priority(2)
    @pytest.mark.depends_on("40001")
    @allure.story("Captured call")
    def MQC_EVL_TOOL_40008_tool_call_captured_without_execution(
        self, request: Any
    ) -> None:
        """What this establishes is that the model emitted a well formed call.

        It reads like a harness claim and is not: the property under test is
        that the **response** carried a call with a parsed argument object.
        That the harness never executes one is asserted on the harness side,
        where the code that would do the executing lives.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config,
            "MQC_TASK_tul_call_is_well_formed",
            "MQC_RULE_tul_call_is_well_formed",
        )
        assert_consistent_pass(results)


@allure.epic("AP-Model-QC")
@allure.feature("Tool compliance")
class TestMQCToolArguments:
    """Calling the right tool wrongly is its own defect."""

    # BOTH A DEPENDENT AND A FOUNDATION. 40006 presupposes this result, so it
    # carries `base` as well as `depends_on`: a chain has middles, and only a
    # case marked foundational is recorded for others to read.
    @pytest.mark.base
    @pytest.mark.priority(2)
    @pytest.mark.depends_on("40001")
    @allure.story("Conforming arguments")
    def MQC_EVL_TOOL_40003_tool_arguments_conform_to_schema(
        self, request: Any
    ) -> None:
        """One required argument and one optional typed one.

        Both are exercised, so conforming is observable rather than vacuous: a
        model that sent only the required argument would satisfy a weaker
        check while ignoring what the request asked for.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config,
            "MQC_TASK_tul_arguments_conform",
            "MQC_RULE_tul_arguments_conform",
        )
        assert_consistent_pass(results)

    @pytest.mark.priority(2)
    @pytest.mark.depends_on("40003")
    @allure.story("Malformed arguments")
    def MQC_EVL_TOOL_40006_malformed_tool_arguments_are_a_model_finding(
        self, request: Any
    ) -> None:
        """The quantity arrives in words, so passing it through sends a string.

        **Depends on `40003` rather than `40001`.** A malformed argument is
        only interesting once conforming ones are established; otherwise a
        model that never sends usable arguments fails both and reads as two
        separate defects.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config,
            "MQC_TASK_tul_malformed_arguments",
            "MQC_RULE_tul_malformed_arguments",
        )
        assert_consistent_pass(results)


@allure.epic("AP-Model-QC")
@allure.feature("Tool compliance")
class TestMQCToolSelection:
    """Choosing correctly, and choosing nothing."""

    @pytest.mark.priority(2)
    @pytest.mark.depends_on("40002")
    @allure.story("Restraint")
    def MQC_EVL_TOOL_40004_no_tool_invoked_when_none_required(
        self, request: Any
    ) -> None:
        """The correct number of calls is zero, and the answer is still given.

        **Depends on `40002`, not `40001`.** Restraint presupposes avoidance: a
        model that invokes forbidden tools will invoke unnecessary ones, and
        reporting both counts one behaviour twice.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config,
            "MQC_TASK_tul_no_tool_needed",
            "MQC_RULE_tul_no_tool_needed",
        )
        assert_consistent_pass(results)

    @pytest.mark.priority(3)
    @pytest.mark.depends_on("40001")
    @allure.story("Selection")
    def MQC_EVL_TOOL_40005_selects_correct_tool_among_several_offered(
        self, request: Any
    ) -> None:
        """Three tools are offered and the question names a policy matter.

        `lookup_order` is the plausible wrong answer rather than an absurd one,
        which is what makes the choice a measurement.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config,
            "MQC_TASK_tul_selects_among_several",
            "MQC_RULE_tul_selects_among_several",
        )
        assert_consistent_pass(results)

    @pytest.mark.priority(3)
    @pytest.mark.depends_on("40002")
    @allure.story("Invention")
    def MQC_EVL_TOOL_40007_does_not_invoke_tool_absent_from_offered_set(
        self, request: Any
    ) -> None:
        """The request names a capability nobody offered.

        **A forbidden list names the tools an author thought of; the offered
        set is everything that exists.** Inventing a name is what no forbidden
        list would have caught, and saying so is the required behaviour rather
        than silence.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config,
            "MQC_TASK_tul_no_invented_tool",
            "MQC_RULE_tul_no_invented_tool",
        )
        assert_consistent_pass(results)
