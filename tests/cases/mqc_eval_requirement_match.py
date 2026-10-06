# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Whether requirement matching lands exactly on the gate boundaries.

Covers ``MQC_EVL_EVAL_134400`` through ``134409``, inventoried in
``docs/testing/model_evaluation_test_plan.md`` section 4.1 and specified by
section 9.8. The matching semantics are normative in the harness ``DESIGN.md``
section 7.1 and are not restated here.

**The boundaries are hit exactly, never near.** One posting carries ten
mandatory requirements and five nice-to-have, and three resumes land on the
three rows of the decision table at **70.0, 78.0 and 90.0 percent**. The 7.8 is
fractional credit on a five-item AND list of which four are held, which is the
specified arithmetic and the only way a ten-requirement posting reaches exactly
78.

**The candidate is held fixed in the connector cases** and only the requirement
phrasing varies, because the connector decides the arithmetic entirely. A
resume that changed alongside the phrasing would make the result attributable
to either.
"""

from typing import Any

import allure
import pytest

from tests.cases.graded_support import observe_repeatedly
from tests.cases.consistency_support import assert_consistent_pass

pytestmark = pytest.mark.evaluator


@allure.epic("AP-Model-QC")
@allure.feature("Requirement matching")
class TestMQCConnectorArithmetic:
    """How a requirement line is worded decides what a partial match is worth."""

    @pytest.mark.base
    @pytest.mark.priority(3)
    @allure.story("Closed OR")
    def MQC_EVL_EVAL_134400_closed_or_list_satisfied_by_one_member(
        self, request: Any
    ) -> None:
        """"Python, Go, or Rust" against a candidate holding Python only.

        **100 percent**: a disjunction is satisfied by one slot filled, and the
        line is met rather than partly met.

        **Foundational**, being the simplest connector. A model that cannot
        score a disjunction tells us nothing further by also mishandling a
        conjunction.

        Args:
            request (Any): pytest's request, carrying the invocation.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config, "MQC_TASK_mat_closed_or", "MQC_RULE_mat_closed_or"
        )
        assert_consistent_pass(results)

    @pytest.mark.priority(3)
    @pytest.mark.depends_on("134400")
    @allure.story("Closed AND")
    def MQC_EVL_EVAL_134401_closed_and_list_scores_fractionally(
        self, request: Any
    ) -> None:
        """"Docker, Kubernetes" against a candidate holding Docker only.

        **50 percent**: a conjunction of two with one held is half the line,
        not nothing and not everything. The same candidate as `134400`, so the
        difference is attributable to the connector alone.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config, "MQC_TASK_mat_closed_and", "MQC_RULE_mat_closed_and"
        )
        assert_consistent_pass(results)

    @pytest.mark.priority(3)
    @pytest.mark.depends_on("134400")
    @allure.story("Open enumeration")
    def MQC_EVL_EVAL_134402_open_enumeration_satisfied_by_category_equivalent(
        self, request: Any
    ) -> None:
        """"PostgreSQL, Redis or similar databases" against MySQL only.

        **The judged path, and the only one in this family.** No named item
        matches, so the third slot engages and category equivalence is judged
        rather than matched. Everything else here is arithmetic.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config,
            "MQC_TASK_mat_open_enumeration",
            "MQC_RULE_mat_open_enumeration",
        )
        assert_consistent_pass(results)


@allure.epic("AP-Model-QC")
@allure.feature("Requirement matching")
class TestMQCGateBoundaries:
    """Three resumes against one posting, on the three rows of the table."""

    @pytest.mark.base
    @pytest.mark.priority(2)
    @allure.story("Above ceiling")
    def MQC_EVL_EVAL_134405_mandatory_at_ceiling_proceeds_regardless_of_optional(
        self, request: Any
    ) -> None:
        """Mandatory 9.0/10 = 90.0 percent, at or above 85.

        The nice-to-have set is **irrelevant** and the combined figure is not
        consulted at all. That is the simplest row of the table, which is why
        it is the foundation for the two below rather than the middle one.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config, "MQC_TASK_mat_above_ceiling", "MQC_RULE_mat_above_ceiling"
        )
        assert_consistent_pass(results)

    @pytest.mark.priority(2)
    @pytest.mark.depends_on("134405")
    @allure.story("At floor")
    def MQC_EVL_EVAL_134404_mandatory_at_floor_with_sufficient_combined_proceeds(
        self, request: Any
    ) -> None:
        """Mandatory 7.8/10 = 78.0 percent exactly, combined 12.8/15 = 85.3.

        **Both figures sit on their boundary**, the second clearing 85 by three
        tenths of a point. A boundary tested near rather than at would pass for
        an implementation off by one in either direction.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config, "MQC_TASK_mat_at_floor", "MQC_RULE_mat_at_floor"
        )
        assert_consistent_pass(results)

    @pytest.mark.priority(2)
    @pytest.mark.depends_on("134405")
    @allure.story("Below floor")
    def MQC_EVL_EVAL_134403_mandatory_below_floor_warns_without_evaluating_optional(
        self, request: Any
    ) -> None:
        """Mandatory 7.0/10 = 70.0 percent, below the 78 floor.

        The model must warn, **name the mandatory cutoff, and not evaluate the
        nice-to-have set at all**. Evaluating it anyway is a defect even when
        the final recommendation is right, because it means the gate did not
        short-circuit where the semantics say it does.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config, "MQC_TASK_mat_below_floor", "MQC_RULE_mat_below_floor"
        )
        assert_consistent_pass(results)


@allure.epic("AP-Model-QC")
@allure.feature("Requirement matching")
class TestMQCExperienceDisclosure:
    """What a figure may say, which depends on where the figure came from."""

    @pytest.mark.base
    @pytest.mark.priority(2)
    @allure.story("Stated figure")
    def MQC_EVL_EVAL_134406_stated_experience_figure_is_preserved(
        self, request: Any
    ) -> None:
        """The candidate stated it, so it stands unchanged.

        **Foundational.** The two cases below are about figures the candidate
        did *not* state, and neither is interpretable for a model that cannot
        leave a stated one alone.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config,
            "MQC_TASK_mat_experience_stated",
            "MQC_RULE_mat_experience_stated",
        )
        assert_consistent_pass(results)

    @pytest.mark.priority(2)
    @pytest.mark.depends_on("134406")
    @allure.story("Derived figure")
    def MQC_EVL_EVAL_134407_derived_experience_figure_states_requirement_floor(
        self, request: Any
    ) -> None:
        """Derived from employment dates: fifteen years against a required eight.

        The tool discloses only the **requirement floor**, so it says "8+"
        while holding fifteen. **That is true**, which is exactly why a numeric
        fabrication check has to be directional: a symmetric check would read
        the disclosure as an alteration.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config,
            "MQC_TASK_mat_experience_derived",
            "MQC_RULE_mat_experience_derived",
        )
        assert_consistent_pass(results)

    @pytest.mark.priority(2)
    @pytest.mark.depends_on("134406")
    @allure.story("Incalculable figure")
    def MQC_EVL_EVAL_134408_incalculable_experience_prompts_rather_than_assumes(
        self, request: Any
    ) -> None:
        """Neither stated nor calculable, so the model must ask.

        **The third of three provenances**, and the only one where the correct
        output is a question. A model that assumes here has invented a figure
        while appearing to reason.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config,
            "MQC_TASK_mat_experience_incalculable",
            "MQC_RULE_mat_experience_incalculable",
        )
        assert_consistent_pass(results)

    @pytest.mark.priority(3)
    @allure.story("Unfamiliar header")
    def MQC_EVL_EVAL_134409_classifies_unfamiliar_section_header_correctly(
        self, request: Any
    ) -> None:
        """A section header the model has no template for.

        **Standalone, and deliberately.** It presupposes no connector and no
        gate: it asks whether a document can be read at all when its structure
        is unfamiliar, which is upstream of every score above and would be a
        confusing dependency on any of them.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config,
            "MQC_TASK_mat_unfamiliar_header",
            "MQC_RULE_mat_unfamiliar_header",
        )
        assert_consistent_pass(results)
