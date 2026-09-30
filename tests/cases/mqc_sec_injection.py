# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Whether the model under test resists an instruction planted against it.

Covers ``MQC_EVL_SEC_50001`` through ``50009``, inventoried in
``docs/testing/model_evaluation_test_plan.md`` section 4.3 and specified by
section 9.10.

**These are findings about a third party, not about this repository.** A
failure here says a model was talked out of its instructions, which is a
`QC_LLM_*` or `QC_SEC_*` event rather than our defect. The suite runs as its
own gate and is exempt from the priority distribution ceilings, so security
coverage never competes with functional coverage for a budget.

**Nothing here is judged.** Every task declares adversarial content, so A19
removes the exposure rather than mitigating it: no payload reaches a judge and
every determination is a string check against a planted canary.

**The simple cases gate the elaborate ones.** `50001` is the plainest override
there is; the four P1 obfuscation cases each ask whether the same attack works
once disguised, which is only worth asking of a model that refused it in the
open.
"""

from typing import Any

import allure
import pytest

from tests.cases.graded_support import assert_consistent_pass, observe_repeatedly, redacted_detail

pytestmark = pytest.mark.sec


@allure.epic("AP-Model-QC")
@allure.feature("Model security")
class TestMQCInstructionOverride:
    """An instruction planted where the model will read it."""

    @pytest.mark.base
    @pytest.mark.priority(0)
    @allure.story("Direct override")
    def MQC_EVL_SEC_50001_resists_direct_instruction_override(
        self, request: Any
    ) -> None:
        """The plainest override there is, with nothing disguising it.

        **Foundational.** Every obfuscation case below asks whether this same
        attack works once hidden, and that question is only informative for a
        model that refused it in the open.

        Args:
            request (Any): pytest's request, carrying the invocation.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config,
            "MQC_TASK_sec_direct_override",
            "MQC_RULE_sec_direct_override",
        )
        assert_consistent_pass(results, _explain)

    # BOTH A FOUNDATION AND A DEPENDENT. Its payload carries instruction
    # override AND role assertion, so it presupposes the single-vector case for
    # each: a compound payload is only interpretable once each vector in it has
    # been measured alone. It remains foundational because 50012 splits this
    # same attack across two documents.
    @pytest.mark.base
    @pytest.mark.priority(0)
    @pytest.mark.depends_on("50001")
    @pytest.mark.depends_on("50010")
    @allure.story("Context override")
    def MQC_EVL_SEC_50002_resists_override_planted_in_context(
        self, request: Any
    ) -> None:
        """The same attack from the surface that matters in retrieval.

        The override arrives in a retrieved document rather than from the
        user, which is the case a real pipeline faces: the user is trusted and
        the document is not.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config,
            "MQC_TASK_sec_context_override",
            "MQC_RULE_sec_context_override",
        )
        assert_consistent_pass(results, _explain)

    @pytest.mark.priority(1)
    @pytest.mark.depends_on("50001")
    @allure.story("Delimiter escape")
    def MQC_EVL_SEC_50009_resists_delimiter_escape_attempt(
        self, request: Any
    ) -> None:
        """The payload imitates the chat framing itself.

        It tries to make the model read the attacker's text as a new system
        turn rather than as content.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config,
            "MQC_TASK_sec_delimiter_escape",
            "MQC_RULE_sec_delimiter_escape",
        )
        assert_consistent_pass(results, _explain)


@allure.epic("AP-Model-QC")
@allure.feature("Model security")
class TestMQCDisclosureAndHijack:
    """What the model gives away, and what it does instead of its task."""

    @pytest.mark.base
    @pytest.mark.priority(0)
    @allure.story("Prompt extraction")
    def MQC_EVL_SEC_50003_does_not_disclose_system_instruction(
        self, request: Any
    ) -> None:
        """The canary is the secret, so emitting it is the disclosure.

        There is no separate token to plant: absence and compliance are the
        same check, which is why this case needs no second assertion to
        distinguish them.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config,
            "MQC_TASK_sec_prompt_extraction",
            "MQC_RULE_sec_prompt_extraction",
        )
        assert_consistent_pass(results, _explain)

    # COMPOUND BY NATURE, and it presupposes each vector it combines. The
    # payload asserts a role, overrides the instruction and substitutes the
    # task, so a failure here says which of three things the model fell for
    # only once each has been measured alone.
    @pytest.mark.base
    @pytest.mark.priority(0)
    @pytest.mark.depends_on("50001")
    @pytest.mark.depends_on("50010")
    @allure.story("Goal hijack")
    def MQC_EVL_SEC_50004_performs_assigned_task_not_injected_one(
        self, request: Any
    ) -> None:
        """Substitution rather than refusal, which a refusal check misses.

        The attacker does not ask the model to stop; it asks the model to do
        something else while appearing to work.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config,
            "MQC_TASK_sec_task_hijack",
            "MQC_RULE_sec_task_hijack",
        )
        assert_consistent_pass(results, _explain)

    # ITS PAYLOAD CARRIES OVERRIDE TOO, in "ignore all previous instructions
    # about refunds", which is how tool coercion looked screened for as long as
    # it did: the match was incidental (harness tier1_ingestion.md 7.3.1). So it
    # presupposes the single-vector override case, and the single-vector
    # coercion cases presuppose it rather than the reverse.
    @pytest.mark.base
    @pytest.mark.priority(0)
    @pytest.mark.depends_on("50001")
    @allure.story("Tool coercion")
    def MQC_EVL_SEC_50008_does_not_invoke_forbidden_tool_under_injection(
        self, request: Any
    ) -> None:
        """Decided by the tool evaluator, not by a string check.

        A model can refuse in prose and call the tool anyway, which a text
        assertion would pass. **A forbidden tool invoked at an attacker's
        instruction is a different event from one invoked carelessly**, which
        is why this is P0 while `40002` is P1.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config,
            "MQC_TASK_sec_tool_coercion",
            "MQC_RULE_sec_tool_coercion",
        )
        assert_consistent_pass(results, _explain)


@allure.epic("AP-Model-QC")
@allure.feature("Model security")
class TestMQCObfuscatedOverride:
    """The same override, disguised three ways. Each presupposes `50001`."""

    @pytest.mark.priority(1)
    @pytest.mark.depends_on("50001")
    @allure.story("Base64")
    def MQC_EVL_SEC_50005_resists_base64_obfuscated_override(
        self, request: Any
    ) -> None:
        """The instruction is encoded, so a substring filter does not see it.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config,
            "MQC_TASK_sec_base64_override",
            "MQC_RULE_sec_base64_override",
        )
        assert_consistent_pass(results, _explain)

    @pytest.mark.priority(1)
    @pytest.mark.depends_on("50001")
    @allure.story("Zero width")
    def MQC_EVL_SEC_50006_resists_zero_width_obfuscated_override(
        self, request: Any
    ) -> None:
        """Invisible characters between the letters of the override.

        A naive filter does not see it and a model reading token by token may
        still act on it.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config,
            "MQC_TASK_sec_zero_width_override",
            "MQC_RULE_sec_zero_width_override",
        )
        assert_consistent_pass(results, _explain)

    @pytest.mark.priority(1)
    @pytest.mark.depends_on("50001")
    @allure.story("Homoglyph")
    def MQC_EVL_SEC_50007_resists_homoglyph_obfuscated_override(
        self, request: Any
    ) -> None:
        """Cyrillic letters that render identically to Latin ones.

        The instruction reads normally to a person and is a different byte
        sequence to a filter.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config,
            "MQC_TASK_sec_homoglyph_override",
            "MQC_RULE_sec_homoglyph_override",
        )
        assert_consistent_pass(results, _explain)


@allure.epic("AP-Model-QC")
@allure.feature("Model security")
class TestMQCOverrideSurfaces:
    """Authority claimed, a payload split, and the control that keeps them honest."""

    # A FOUNDATION, NOT A DEPENDENT. Role assertion is its own vector, so it
    # presupposes nothing about instruction override: a model may defer to a
    # claimed administrator while refusing a bare order, and the reverse. It
    # previously depended on 50001, which asserted a relationship between two
    # unrelated vectors and put a compound payload ahead of a single one.
    # PROMOTED FROM P1 2026-09-29. `50002` and `50004` are P0 and rest on this,
    # and a foundation cannot be less blocking than what rests on it
    # (`test_taxonomy.md` section 4.5). The alternative was demoting two
    # blocking security gates to fix a bookkeeping error, and `SEC` is exempt
    # from the distribution ceilings so promoting costs no functional budget.
    @pytest.mark.base
    @pytest.mark.priority(0)
    @allure.story("Role assertion")
    def MQC_EVL_SEC_50010_resists_role_assertion_attempt(self, request: Any) -> None:
        """The attacker claims authority instead of issuing an instruction.

        `50001` says "do this". This says "I am someone who may tell you to do
        this", and asserts a developer diagnostic mode that supersedes the
        configuration. **Those are different things to resist**, and a model
        that refuses an order may still defer to a claimed administrator.

        **This case widened the screen.** `role_assertion` matched second-person
        framings, "you are now" and "act as the administrator", and missed the
        first-person claim entirely (harness `tier1_ingestion.md` section
        7.3.2).

        Args:
            request (Any): pytest's request, carrying the invocation.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config,
            "MQC_TASK_sec_role_assertion",
            "MQC_RULE_sec_role_assertion",
        )
        assert_consistent_pass(results, _explain)

    @pytest.mark.priority(2)
    @pytest.mark.depends_on("50001")
    @allure.story("Near miss")
    def MQC_EVL_SEC_50011_canary_absent_from_compliant_response(
        self, request: Any
    ) -> None:
        """A boundary case, and the boundary is proximity rather than presence.

        The canary is a ticketing reference sitting **inside text the model is
        required to summarise**, so a compliant response describes material
        immediately around it. A check that fired on proximity would fail a
        model that did exactly as it was told.

        **The only case in the family that is not an attack.** It declares no
        adversarial content, because nothing here instructs the model to do
        anything: claiming a payload would demand a vector match for an attack
        that does not exist.

        **Every other case in this family asserts an absence.** Without this
        one, a suite of nothing but absences cannot distinguish a resistant
        model from a checker that never fires.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config,
            "MQC_TASK_sec_canary_adjacent",
            "MQC_RULE_sec_canary_adjacent",
        )
        assert_consistent_pass(results, _explain)

    @pytest.mark.priority(2)
    @pytest.mark.depends_on("50002")
    @allure.story("Split payload")
    def MQC_EVL_SEC_50012_resists_payload_split_across_documents(
        self, request: Any
    ) -> None:
        """Half the instruction in one document, half in another.

        Neither fragment is an instruction and neither matches a filter. **The
        attack exists only once the model reads both**, which is exactly what a
        retrieval pipeline does and what per-document screening cannot see.

        **Depends on `50002`, not `50001`.** It is a context-planted override,
        so the single-document form has to hold before the split form means
        anything.

        Args:
            request (Any): pytest's request.

        Returns:
            None
        """
        results = observe_repeatedly(
            request.config,
            "MQC_TASK_sec_split_payload",
            "MQC_RULE_sec_split_payload",
        )
        assert_consistent_pass(results, _explain)


def _explain(result: Any) -> str:
    """Return what failed, without the payload.

    Args:
        result (Any): The evaluation result.

    Returns:
        str: The failing assertions, behind this family's lead-in.
    """
    return redacted_detail(result, "the model complied with the planted instruction")
