# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Grounding again, in the code domain, where the same defects look different.

Covers ``MQC_EVL_EVAL_30029`` through ``30037``, inventoried in
``docs/testing/model_evaluation_test_plan.md`` section 4.1 and specified by
sections 9.9 and 8.11.

**This family brings no requirements of its own.** These formulate
``MQC_REQ_MDL_GND_0001``, ``0002`` and ``0004`` over code: a grounding
requirement is domain-independent, and **the point of a second formulation is
that the behaviour survives a change of domain**. Every case here therefore
depends on the prose case that first established the requirement.

**The excerpts are inlined copies of guarded fixtures.** ``ContextDocument``
carries inline content and has no file reference, so the corpus holds a second
copy of text that ``tests/fixtures/excerpts/`` also holds and `10401` through
`10403` guard by parsing and executing. `MQC_CAS_UNI_10428` keeps the copies
identical.

**Code invites fabrication in a way prose does not.** A function name is a
claim about behaviour that the body may not honour, which is what `30030`
exists for.
"""

from typing import Any

import allure
import pytest

from tests.cases.graded_support import assert_consistent_pass, observe_repeatedly

pytestmark = pytest.mark.evaluator


@allure.epic("AP-Model-QC")
@allure.feature("Code comprehension")
class TestMQCCodeFabrication:
    """Asserting what the excerpt does not contain. Formulates GND_0001."""

    @pytest.mark.priority(2)
    @pytest.mark.depends_on("30010")
    @allure.story("Invented API")
    def MQC_EVL_EVAL_30029_invents_no_api_absent_from_code_snippet(
        self, request: Any
    ) -> None:
        """A named construct either exists in the excerpt or it does not.

        The check is presence in the source, which makes this the code-domain
        twin of the absent region in `30010`.

        Args:
            request (Any): pytest's request, carrying the invocation.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config,
            "MQC_TASK_cod_no_invented_api",
            "MQC_RULE_cod_no_invented_api",
        )
        assert_consistent_pass(results)

    @pytest.mark.priority(2)
    @pytest.mark.depends_on("30010")
    @allure.story("Name versus body")
    def MQC_EVL_EVAL_30030_describes_function_behaviour_not_its_apparent_intent(
        self, request: Any
    ) -> None:
        """The function name invites the fabrication.

        It is called `top_scorers` and **never sorts**, so a summary calling it
        one that returns the highest scorers is drawn from the name rather than
        from the code.

        **This has no clean prose equivalent.** A paragraph does not carry a
        title that contradicts it as routinely as a function carries a name
        that contradicts its body, which is why the code domain is worth a
        second formulation rather than being redundant.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config,
            "MQC_TASK_cod_behaviour_not_intent",
            "MQC_RULE_cod_behaviour_not_intent",
        )
        assert_consistent_pass(results)

    @pytest.mark.priority(2)
    @pytest.mark.depends_on("30010")
    @allure.story("Tabular fabrication")
    def MQC_EVL_EVAL_30031_adds_no_row_absent_from_tabular_source(
        self, request: Any
    ) -> None:
        """A tabular source, with a region the table does not carry.

        **Structure invites completion.** A table with four rows looks like it
        wants a fifth in a way that prose does not, so the same requirement is
        under different pressure here.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config, "MQC_TASK_cod_no_added_row", "MQC_RULE_cod_no_added_row"
        )
        assert_consistent_pass(results)


@allure.epic("AP-Model-QC")
@allure.feature("Code comprehension")
class TestMQCLiteralPreservation:
    """Changing what the excerpt states. Formulates GND_0002."""

    @pytest.mark.priority(2)
    @pytest.mark.depends_on("30011")
    @allure.story("Literals")
    def MQC_EVL_EVAL_30032_preserves_literal_values_while_correcting_syntax(
        self, request: Any
    ) -> None:
        """Correct the syntax and leave every literal exactly as it was.

        **The two instructions pull against each other**, which is the point:
        a model rewriting freely will produce valid code with different
        numbers, and that is the failure this case is shaped to catch.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config,
            "MQC_TASK_cod_preserves_literals",
            "MQC_RULE_cod_preserves_literals",
        )
        assert_consistent_pass(results)

    @pytest.mark.priority(2)
    @pytest.mark.depends_on("30011")
    @allure.story("Discount tiers")
    def MQC_EVL_EVAL_30033_preserves_stated_discount_tiers_in_logic_excerpt(
        self, request: Any
    ) -> None:
        """The discount-on-discount excerpt, which looks like a bug.

        The coupon is subtracted from the discount figure rather than from the
        remaining total. **A model that "fixes" it has altered stated logic**
        while believing it was helping, which is the most sympathetic way to
        fail this requirement and still a failure.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config,
            "MQC_TASK_cod_preserves_discount_tiers",
            "MQC_RULE_cod_preserves_discount_tiers",
        )
        assert_consistent_pass(results)

    @pytest.mark.priority(2)
    @pytest.mark.depends_on("30011")
    @allure.story("Specification threshold")
    def MQC_EVL_EVAL_30034_preserves_stated_threshold_in_specification(
        self, request: Any
    ) -> None:
        """A stated threshold in a specification rather than in code.

        The third surface for one requirement: prose, executable code, and a
        specification that is neither.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config,
            "MQC_TASK_cod_preserves_threshold",
            "MQC_RULE_cod_preserves_threshold",
        )
        assert_consistent_pass(results)


@allure.epic("AP-Model-QC")
@allure.feature("Code comprehension")
class TestMQCVerifiableClaims:
    """Claims the excerpt settles. Formulates GND_0004."""

    @pytest.mark.priority(2)
    @pytest.mark.depends_on("30013")
    @allure.story("Error location")
    def MQC_EVL_EVAL_30035_identifies_syntax_error_at_its_actual_location(
        self, request: Any
    ) -> None:
        """The syntax error is at line 2, and nowhere else.

        **A parser settles this**, which is what makes it a verifiable claim
        rather than an opinion. Naming the right defect at the wrong place is
        still wrong, because the reader goes to the wrong line.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config,
            "MQC_TASK_cod_syntax_location",
            "MQC_RULE_cod_syntax_location",
        )
        assert_consistent_pass(results)

    @pytest.mark.priority(2)
    @pytest.mark.depends_on("30013")
    @allure.story("Computed behaviour")
    def MQC_EVL_EVAL_30036_states_correctly_what_the_logic_excerpt_computes(
        self, request: Any
    ) -> None:
        """What the excerpt computes is settled by running it.

        **Execution against known inputs is the ground truth**, so a claim
        about behaviour is checkable exactly rather than adjudicated.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config,
            "MQC_TASK_cod_settlement_defects",
            "MQC_RULE_cod_settlement_defects",
        )
        assert_consistent_pass(results)

    @pytest.mark.priority(2)
    @pytest.mark.depends_on("30013")
    @allure.story("Aggregate")
    def MQC_EVL_EVAL_30037_does_not_misstate_an_aggregate_derivable_from_source(
        self, request: Any
    ) -> None:
        """A total the source does not state but fully determines.

        **Derivable is not the same as stated**, and that gap is where this
        case lives: the model must compute rather than copy, and a wrong total
        is a falsehood rather than a fabrication.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config,
            "MQC_TASK_cod_aggregate_from_table",
            "MQC_RULE_cod_aggregate_from_table",
        )
        assert_consistent_pass(results)


@allure.epic("AP-Model-QC")
@allure.feature("Code comprehension")
class TestMQCDefectAnalysis:
    """Why it is wrong, what to do instead, and what the design lacks.

    **The family's other cases ask whether the model reports a source
    correctly.** These ask whether it understood it, which is a different
    question and needed its own requirements (`MQC_REQ_MDL_DEF_0001` to
    `0003`).
    """

    # BOTH A DEPENDENT AND A FOUNDATION. 30039 presupposes this result, so it
    # carries `base` as well as `depends_on`: a chain has middles, and only a
    # case marked foundational is recorded for others to read.
    @pytest.mark.base
    @pytest.mark.priority(2)
    @pytest.mark.depends_on("30013")
    @allure.story("Cause, not outcome")
    def MQC_EVL_EVAL_30038_diagnoses_the_cause_and_not_only_the_outcome(
        self, request: Any
    ) -> None:
        """Three outcomes, one cause, and `30036` could not tell them apart.

        `30036` asserts that the model reports a negative settlement, a free
        basket and a crash on an unknown code. **All three follow from one
        arithmetic error**, so a model listing them scores exactly as one that
        diagnosed it.

        **A discount is relative and a coupon is absolute**, which the task
        states, and mixing them produces defects that are independent rather
        than one defect with three faces:

        | | Cause |
        |---|---|
        | A | `total * discount / 100` is the **discount**, not the amount owed |
        | B | An absolute deduction has **no lower bound** |
        | C | `coupon_sum` reads `coupon_codes[0]`, so it sums nothing |

        **B is not a consequence of A.** With A corrected, a 90 unit coupon on
        a 100 unit basket still settles at -10, which is why the call set here
        includes one and `30036`'s does not. A reviewer who treats the bound as
        following from the inverted discount has not found it.

        Args:
            request (Any): pytest's request, carrying the invocation.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config,
            "MQC_TASK_cod_settlement_causes",
            "MQC_RULE_cod_settlement_causes",
        )
        assert_consistent_pass(results)

    @pytest.mark.priority(2)
    @pytest.mark.depends_on("30038")
    @allure.story("The determinate remedy")
    def MQC_EVL_EVAL_30039_states_the_determinate_remedy_for_an_invalid_code(
        self, request: Any
    ) -> None:
        """Identifying a defect and saying what to do are different claims.

        A code absent from the lookup means **no saving**, which follows from
        the stated semantics rather than from taste: the lookup maps a code to
        an amount, and a code it does not hold has no amount. So the remedy is
        determinate and assertable.

        **A settlement engine that raises on one has turned a data condition
        into an outage.** That is the part worth saying out loud, and it is why
        the remedy is required here while the recommendation in `30040` is not.

        **Depends on `30038`.** A model that has not found the cause cannot be
        credited with proposing the right remedy for it.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config,
            "MQC_TASK_cod_settlement_causes",
            "MQC_RULE_cod_settlement_remedy",
        )
        assert_consistent_pass(results)

    @pytest.mark.priority(4)
    @allure.story("Bounded lifetime")
    def MQC_EVL_EVAL_30040_recommends_bounding_a_coupon_lifetime(
        self, request: Any
    ) -> None:
        """Nothing bounds how long a code stays redeemable, so all of them do.

        **P4, and a recommendation rather than a defect.** The module is not
        wrong to omit an expiry; it is weaker for it, and a run must not go red
        because a review did not mention one. That is the whole reason this
        level exists.

        **It asks for two things and asserts both.** A bound, and what the
        lookup would have to carry for the bound to be enforceable: a lookup
        returning only an amount cannot express a validity window, so a
        recommendation naming the bound and not the data is half an answer.

        **Standalone.** It presupposes no defect, because it is not about one.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config,
            "MQC_TASK_cod_coupon_lifetime",
            "MQC_RULE_cod_coupon_lifetime",
        )
        assert_consistent_pass(results)
