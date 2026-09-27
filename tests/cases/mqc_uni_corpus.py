# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""The authored corpus loads, and says what it was designed to say.

Covers ``MQC_CAS_UNI_10423`` through ``10425``, inventoried in
``docs/testing/model_evaluation_test_plan.md`` section 8.3.

**These run the real loaders over the shipped files.** The harness already has
88 cases proving the loaders work, and none of them say whether *this* corpus
loads. Authoring the instruction-following family hit two shape errors no
schema test could have caught: a wrapper key where the loader wanted a bare
list, and a flow mapping whose commas YAML read as key separators.

A failure here is our defect rather than a finding about a model, so the module
carries no priority marker.
"""

import csv
import base64
import unicodedata
from pathlib import Path
from typing import Any, Final

import allure
import pytest

from cmn.registries import (
    is_registered_constraint_kind,
    registered_codes,
    registered_evaluation_families,
)
from cmn.vectors import homoglyph_words, match_vectors
from evaluation.assertions import run_assertions
from ingestion.integrity import (
    check_referential_integrity,
    warn_unregistered_constraint_kinds,
)
from ingestion.loaders import load_rule_sets_from_yaml, load_tasks_from_yaml
from ingestion.schemas import GoldenRuleSet, TaskDataSet
from tools.generate_code_corpus import build

pytestmark = pytest.mark.unit

# A control task carries this tag. THE POPULATION IS DERIVED FROM THE CORPUS
# rather than named here, so a control added later is protected without editing
# this module, and a control that loses its tag is caught by the count
# assertion rather than passing silently.
_CONTROL_TAG = "control"

# How many ablation pairs the corpus is designed around. Stated so that losing
# a control tag fails rather than shrinking the population the checks run over.
_EXPECTED_CONTROLS = 2

# Which guarded fixture each inlined document carries. Named rather than
# inferred: a document identifier is authored text and a heuristic matching it
# to a filename would quietly stop matching when either is renamed.
_FIXTURE_BY_DOCUMENT = {
    "DOC_excerpt_top_scorers_syntactic": "top_scorers_syntactic",
    "DOC_excerpt_top_scorers_logical": "top_scorers_logical",
    "DOC_excerpt_settle_order": "settle_order_logical",
}


def _normalised(text: str) -> str:
    """Return text with line endings and trailing blank lines removed.

    Args:
        text (str): Either copy of an excerpt.

    Returns:
        str: A form comparable across platforms.
    """
    return text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")




# THE FAMILIES DECIDED WITHOUT A JUDGE, by corpus file. A security rule is
# settled by whether the canary appears and a tool rule by which tools were
# invoked; a rubric in either would never be evaluated (consumer_ci.md 4.8).
_UNJUDGED_FAMILIES: Final[frozenset[str]] = frozenset({"security", "tool_compliance"})

# EVAL RULES THAT NEED NO JUDGE, named so that a fourth is a decision rather
# than a habit. All three ask deterministic questions about the settlement
# excerpt: which causes are identified, what the remedy is, and whether coupon
# lifetime is raised. The project owner's framing was that most of these "don't
# even require a judge".
_DETERMINISTIC_EVAL_RULES: Final[frozenset[str]] = frozenset({
    "MQC_RULE_cod_settlement_causes",
    "MQC_RULE_cod_settlement_remedy",
    "MQC_RULE_cod_coupon_lifetime",
})


def _repository_root() -> Path:
    """Return this repository's root.

    Returns:
        Path: The directory holding ``data/``.
    """
    return Path(__file__).resolve().parents[2]


@pytest.fixture(name="corpus")
def fixture_corpus() -> tuple[list[TaskDataSet], list[GoldenRuleSet]]:
    """Load every shipped task and rule file.

    Returns:
        tuple: Every task and every rule set, across all corpus files.
    """
    root = _repository_root()
    tasks: list[TaskDataSet] = []
    rules: list[GoldenRuleSet] = []
    for source in sorted((root / "data" / "tasks").glob("*.yaml")):
        tasks.extend(load_tasks_from_yaml(source))
    for source in sorted((root / "data" / "rules").glob("*.yaml")):
        rules.extend(load_rule_sets_from_yaml(source))
    return tasks, rules


@allure.epic("AP-Model-QC")
@allure.feature("Corpus")
class TestMQCCorpus:
    """What the shipped data must satisfy before any case runs against it."""

    @allure.story("Ingestion")
    def MQC_CAS_UNI_10423_the_shipped_corpus_loads_and_passes_referential_integrity(
        self, corpus: tuple[list[TaskDataSet], list[GoldenRuleSet]]
    ) -> None:
        """The real loaders over the real files, not a constructed payload.

        R1 through R5 are what make the corpus coherent: every rubric
        reference resolves, every check names a constraint that was sent, and
        **every constraint sent is checked by something**. R3 is the one
        nobody writes by hand: a constraint stated to the model and never
        verified means the rule is untested and nothing surfaces it.

        Args:
            corpus (tuple): Every shipped task and rule set.

        Returns:
            None
        """
        tasks, rules = corpus

        assert tasks, "no task files loaded, so the corpus is empty or unreadable"
        assert rules, "no rule files loaded, so nothing can be judged"

        # It RAISES rather than returning findings, naming every violation in
        # one pass. Calling it inside pytest.raises would invert the case, so
        # the assertion is that it returns at all.
        check_referential_integrity(tasks, rules)

    @allure.story("Vocabulary")
    def MQC_CAS_UNI_10424_a_constraint_kind_outside_the_registry_is_reported(
        self, corpus: tuple[list[TaskDataSet], list[GoldenRuleSet]]
    ) -> None:
        """The harness warns rather than failing, so something must read it.

        ``count`` and ``ordering`` were promoted into the registry on the
        strength of this corpus (``tier1_ingestion.md`` section 8.1) and
        ``form`` was refused, because ``format`` already covered it. That
        refusal is worth something only if the next unregistered kind is
        noticed, and **a warning nobody reads is how a vocabulary fragments**.

        The vocabulary stays open at the harness level. This repository holds
        itself to the registered set, which is a stricter rule than the harness
        imposes and is this corpus's to keep.

        Args:
            corpus (tuple): Every shipped task and rule set.

        Returns:
            None
        """
        tasks, _ = corpus
        unregistered = warn_unregistered_constraint_kinds(tasks)

        assert not unregistered, (
            "every constraint kind this corpus uses should be registered or "
            f"promoted, per tier1_ingestion.md section 8: {unregistered}"
        )
        # Asserted directly as well, so the case does not pass merely because
        # the corpus happens to carry no constraints at all.
        kinds = {constraint.kind for task in tasks for constraint in task.constraints}
        assert kinds, "the corpus states no constraints, so nothing is being measured"
        assert all(is_registered_constraint_kind(kind) for kind in kinds)

    @allure.story("Ablation")
    def MQC_CAS_UNI_10425_the_ablation_control_states_no_constraint_and_checks_none(
        self, corpus: tuple[list[TaskDataSet], list[GoldenRuleSet]]
    ) -> None:
        """The control is the measurement, and no schema check can protect it.

        Cases 30001 and 30002 differ only in whether the format instruction is
        stated. That difference is the entire measurement: without it, a model
        returning JSON scores as instruction-following when it is following a
        habit.

        **An edit adding a constraint to the control would pass every
        integrity check**, because a constraint with a matching check is
        exactly what R2 and R3 want to see. The design intent is invisible to
        the schema, so it is asserted here.

        Args:
            corpus (tuple): Every shipped task and rule set.

        Returns:
            None
        """
        tasks, rules = corpus
        by_id = {rule.rule_id: rule for rule in rules}
        controls = [task for task in tasks if _CONTROL_TAG in task.tags]

        assert len(controls) == _EXPECTED_CONTROLS, (
            f"expected {_EXPECTED_CONTROLS} control tasks and found "
            f"{len(controls)}; a control that lost its tag would otherwise "
            f"shrink the population these checks run over"
        )

        for control in controls:
            assert not control.constraints, (
                f"{control.task_id} is an ablation control and states no "
                f"constraint by design; adding one destroys the control and "
                f"every integrity check still passes"
            )
            for rule_id in control.rubric_ids:
                control_rule = by_id[rule_id]
                assert not control_rule.assertions, (
                    f"{rule_id} would assert obedience to an instruction that "
                    f"was never given"
                )
                # It still has to judge something, or the control measures
                # nothing rather than measuring the absence of the instruction.
                assert control_rule.rubric is not None

    @allure.story("Taxonomy")
    def MQC_CAS_UNI_10426_a_corpus_taxonomy_code_outside_the_registry_is_reported(
        self, corpus: tuple[list[TaskDataSet], list[GoldenRuleSet]]
    ) -> None:
        """A finding may not carry a code the registry does not define.

        Nothing was checking this. ``MQC_CMN_UNI_10143`` through ``10145``
        verify that every code a **design document** names and every code the
        **harness emits** is registered. Neither reads a data file, and a
        ``taxonomy_code`` in a golden rule is exactly that: a code this corpus
        will attach to a finding, chosen by an author.

        **The invented codes were plausible**, which is what made this a defect
        rather than a typo. ``QC_LLM_ALTERED_VALUE`` reads like a registered
        code and means what ``QC_LLM_SOURCE_ALTERATION`` means, so a finding
        carrying it would aggregate into its own bucket and the analysis would
        report two populations where there is one.

        Args:
            corpus (tuple): Every shipped task and rule set.

        Returns:
            None
        """
        _, rules = corpus
        used = {
            assertion.taxonomy_code
            for rule in rules
            for assertion in rule.assertions
        }

        assert used, "no rule states a taxonomy code, so no finding could be classified"
        unregistered = sorted(used - registered_codes())
        assert not unregistered, (
            "the registry lives in the harness and this corpus reads it rather "
            f"than extending it: {unregistered}"
        )

    @allure.story("Taxonomy")
    def MQC_CAS_UNI_10427_a_family_named_here_and_not_registered_is_reported(
        self,
    ) -> None:
        """The check belongs here because the data does.

        It was first written in the harness, where ``rtm_harness.csv`` carries
        no ``families`` column at all: families apply to graded cases and a
        precondition performs no task, which ``MQC_CMN_UNI_10196`` asserts
        deliberately. It found zero values and passed, which is the shape of a
        vacuous check rather than a passing one.

        **T5 cannot cover this.** It compares a matrix row's ``families`` value
        against the cases named in the same row, which is a consistency check
        between two fields of one row. Neither field is the registry.

        Returns:
            None
        """
        matrix = _repository_root() / "docs" / "testing" / "rtm_model.csv"
        named: set[str] = set()
        with matrix.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                for value in (row.get("families") or "").split(";"):
                    if value.strip():
                        named.add(value.strip())

        assert named, (
            "no matrix row names a family, so either the column was dropped or "
            "the graded requirements lost their family assignment"
        )
        unregistered = sorted(named - registered_evaluation_families())
        assert not unregistered, (
            "the registry lives in the harness and this matrix reads it rather "
            f"than extending it: {unregistered}"
        )

    @allure.story("Fixtures")
    def MQC_CAS_UNI_10428_an_inlined_excerpt_differing_from_its_fixture_is_reported(
        self, corpus: tuple[list[TaskDataSet], list[GoldenRuleSet]]
    ) -> None:
        """The guarded copy is not the copy the model sees.

        ``ContextDocument`` carries inline ``content`` and has no file
        reference, so a task supplying a code excerpt holds a second copy of
        text that ``10401`` through ``10403`` guard by parsing and executing
        it. A fixture repaired by a formatter would be caught; the task file
        repaired by the same formatter would not.

        **Line endings are normalised before comparing**, for the reason
        ``hash_request`` does the same: the same commit checked out on Windows
        and on Linux would otherwise differ, and this would fail on whichever
        platform did not author the file.

        Returns:
            None
        """
        tasks, _ = corpus
        excerpts = _repository_root() / "tests" / "fixtures" / "excerpts"
        covered: set[str] = set()

        for task in tasks:
            for document in task.context_documents:
                fixture = _FIXTURE_BY_DOCUMENT.get(document.document_id)
                if fixture is None:
                    continue
                guarded = (excerpts / f"{fixture}.py.txt").read_text(encoding="utf-8")
                assert _normalised(document.content) == _normalised(guarded), (
                    f"{task.task_id} inlines {document.document_id}, which no "
                    f"longer matches the guarded fixture {fixture}.py.txt; the "
                    f"copy under guard is not the copy the model receives"
                )
                covered.add(fixture)

        # COVERAGE, NOT A COUNT. An excerpt legitimately serves several tasks:
        # the syntactic one is dispatched by 30032 and 30035, because literal
        # preservation and defect location are different requirements over the
        # same material. What must not happen is a fixture dispatched by
        # nothing, which would leave it guarded and unused while the cases
        # built on it assert against a copy this check never saw.
        unused = sorted(set(_FIXTURE_BY_DOCUMENT.values()) - covered)
        assert not unused, (
            f"these fixtures are mapped and dispatched by no task: {unused}"
        )

    @allure.story("Rubrics")
    def MQC_CAS_UNI_10447_a_graded_evaluation_rule_without_a_rubric_is_reported(
        self,
    ) -> None:
        """An `EVAL` rule exists to be judged; a tool or security rule does not.

        **This case was inventoried, cited by two docstrings as policing them,
        and never implemented.** `consumer_ci.md` section 4.8 described it,
        `mqc_tool_compliance.py` and the test plan both said it permitted their
        rubricless rules, and nothing ran. The reverse inventory check that
        would have caught it is `OPEN_QUESTIONS.md` section 2.1 and is not
        built; this was found by reconciling the inventory by hand before the
        first commit.

        **Family comes from the corpus file, which is where family lives.** A
        rule carries no family field, and the harness owns no case data, which
        is the reason section 4.8 gives for the check belonging here.

        **Three `EVAL` rules legitimately carry no rubric** and are named below
        rather than waved through. They decide settlement arithmetic and coupon
        lifetime, which are deterministic questions: the project owner's words
        were that most of these "don't even require a judge". Section 4.8's
        point is that omitting a rubric *decides something and so must be
        visible*, not that it is forbidden.

        Returns:
            None
        """
        rules_directory = _repository_root() / "data" / "rules"
        missing: list[str] = []
        stale: list[str] = []

        for source in sorted(rules_directory.glob("*.yaml")):
            judged = source.stem not in _UNJUDGED_FAMILIES
            for rule in load_rule_sets_from_yaml(source):
                if not judged:
                    # THE OTHER DIRECTION. A rubric here would never run, and
                    # its presence would suggest these families are judged.
                    assert rule.rubric is None, (
                        f"{rule.rule_id} carries a rubric in {source.name}, "
                        f"whose family is decided by deterministic checks, so "
                        f"the rubric would never be evaluated"
                    )
                    continue
                if rule.rubric is None and rule.rule_id not in _DETERMINISTIC_EVAL_RULES:
                    missing.append(rule.rule_id)
                if rule.rubric is not None and rule.rule_id in _DETERMINISTIC_EVAL_RULES:
                    stale.append(rule.rule_id)

        assert not missing, (
            f"{len(missing)} rule(s) serve a judged family and carry no rubric, "
            f"so a requirement about response quality is measured by nothing: "
            f"{sorted(missing)}. Either author the rubric, or name the rule in "
            f"_DETERMINISTIC_EVAL_RULES with the reason it needs no judge"
        )
        # A STALE EXEMPTION, policed the same way the screen_evasion tag is: an
        # allowance that outlived its reason reads as a decision nobody revisited.
        assert not stale, (
            f"{len(stale)} rule(s) are named as needing no judge and now carry "
            f"a rubric, so the exemption is obsolete: {sorted(stale)}"
        )

    @allure.story("Calibration")
    def MQC_CAS_UNI_10431_an_authored_anchor_without_an_exemplar_is_reported(
        self, corpus: tuple[list[TaskDataSet], list[GoldenRuleSet]]
    ) -> None:
        """An uncalibrated rubric accepts whatever the judge does.

        An anchor states what a level means; an exemplar shows it. Calibration
        sends each exemplar through the judge and compares the returned score
        against the level it was written for, and **that comparison is the only
        thing in the system that can say which judge is right** when two
        disagree. A fixture comparison says a score moved; an exemplar
        comparison says the judge no longer means what the anchors say.

        Returns:
            None
        """
        _, rules = corpus
        missing: list[str] = []
        counted = 0

        for rule in rules:
            if rule.rubric is None:
                continue
            for criterion in rule.rubric.criteria:
                for level, anchor in sorted(criterion.anchors.items()):
                    counted += 1
                    if not (anchor.exemplar or "").strip():
                        missing.append(
                            f"{rule.rule_id}/{criterion.criterion_id}/{level}"
                        )

        assert counted, "no anchors were read, so nothing is being checked"
        assert not missing, (
            f"{len(missing)} of {counted} anchors carry no exemplar, so "
            f"calibration cannot measure drift against them: "
            + ", ".join(missing[:6])
        )

    @allure.story("Calibration")
    def MQC_CAS_UNI_10432_a_top_exemplar_failing_its_own_assertions_is_reported(
        self, corpus: tuple[list[TaskDataSet], list[GoldenRuleSet]]
    ) -> None:
        """A case cannot award a top score through a failed gate.

        Assertions are conjunctive, so an exemplar written to score 5 that
        fails its own rule's assertions is incoherent: the case could never
        award that level however well the judge read it, and calibration would
        report drift every time the judge behaved correctly.

        **Levels 1 and 3 are deliberately unconstrained.** A response can be
        assertion-clean and still worthless, which is exactly what a rubric is
        for, and an exemplar demonstrating that is the most useful bottom
        anchor there is.

        Returns:
            None
        """
        _, rules = corpus
        incoherent: list[str] = []
        checked = 0

        for rule in rules:
            # A rule with no assertions has no gate for an exemplar to pass.
            # The ablation controls are the case: they check nothing by design.
            if rule.rubric is None or not rule.assertions:
                continue
            for criterion in rule.rubric.criteria:
                anchor = criterion.anchors.get(5)
                if anchor is None or not (anchor.exemplar or "").strip():
                    continue
                checked += 1
                failed = [
                    entry.assertion_id
                    for entry in run_assertions(rule.assertions, anchor.exemplar)
                    if not entry.passed
                ]
                if failed:
                    incoherent.append(
                        f"{rule.rule_id}/{criterion.criterion_id} fails {failed}"
                    )

        assert checked, "no top exemplars were read, so nothing is being checked"
        assert not incoherent, (
            "a level 5 exemplar claims a score the case cannot award through a "
            "failed gate: " + "; ".join(incoherent[:4])
        )

    @allure.story("Generation")
    def MQC_CAS_UNI_10433_the_shipped_task_file_differs_from_what_the_generator_builds(
        self,
    ) -> None:
        """A hand edit to a generated file is lost at the next regeneration.

        ``10428`` catches an inlined excerpt drifting from its fixture. This
        catches a different failure: the shipped file not being what the
        generator produces, which is what happens when someone corrects a
        prompt in the generated file directly. The correction survives until
        the corpus is regenerated and then vanishes, with nothing reporting it.

        **It calls the same ``build`` an author runs.** A check that rebuilt
        the expected output separately would assert that two copies of one
        algorithm agree, which is not the claim.

        Returns:
            None
        """
        shipped = (
            _repository_root() / "data" / "tasks" / "code_comprehension.yaml"
        ).read_text(encoding="utf-8")

        assert build() == shipped, (
            "data/tasks/code_comprehension.yaml is not what "
            "tools/generate_code_corpus.py builds; it is generated, so edit the "
            "generator and regenerate rather than editing the file"
        )


    @allure.story("Payload integrity")
    def MQC_CAS_UNI_10446_the_obfuscated_payloads_survive_a_load_as_code_points(
        self, corpus: tuple[list[TaskDataSet], list[GoldenRuleSet]]
    ) -> None:
        """The first data here whose meaning is not its text.

        A zero-width joiner is invisible and a Cyrillic small letter o is
        indistinguishable from a Latin one, so a corrupted payload **looks
        correct in every diff, review and editor**.

        **The canary assertions cannot catch this.** They are ASCII and would
        keep passing against a mangled payload, which is the failure mode
        exactly: the fixture goes on working and stops saying whether it still
        does.

        Written with escapes so this file stays ASCII, for the reason
        ``MQC_ING_UNI_10046`` gives: a literal would depend on this source
        surviving an editor that re-saves as cp1252, which is the failure
        being tested.

        Args:
            corpus (tuple): Every task and rule set the repository ships.

        Returns:
            None
        """
        tasks = {task.task_id: task for task in corpus[0]}

        # ZERO WIDTH, case 50006. They render as nothing, so only a count sees
        # them. U+200B, U+200C and U+200D.
        invisible = {"\u200b", "\u200c", "\u200d"}
        zero_width = tasks["MQC_TASK_sec_zero_width_override"].user_prompt
        present = [character for character in zero_width if character in invisible]
        assert len(present) >= 20, (
            f"the zero width payload carries {len(present)} invisible "
            f"characters, so it is no longer the attack it claims to be"
        )

        # HOMOGLYPHS, case 50007. Cyrillic letters inside Latin words, which
        # render identically. Counted by script rather than by literal.
        homoglyph = tasks["MQC_TASK_sec_homoglyph_override"].user_prompt
        cyrillic = [
            character for character in homoglyph
            if unicodedata.name(character, "").startswith("CYRILLIC ")
        ]
        assert len(cyrillic) >= 6, (
            f"the homoglyph payload carries {len(cyrillic)} Cyrillic "
            f"characters, so it reads as ordinary Latin and attacks nothing"
        )
        assert homoglyph_words(homoglyph), "no mixed script word survived"

        # BASE64, case 50005. It decodes to the override or it does not.
        encoded = tasks["MQC_TASK_sec_base64_override"].user_prompt
        blob = max(encoded.split(), key=len)
        decoded = base64.b64decode(blob).decode("utf-8")
        assert "CANARY_B64_50005" in decoded, (
            f"the base64 payload no longer decodes to its override: {decoded!r}"
        )

        # EVERY PAYLOAD STILL MATCHES ITS VECTOR, which is the cross-check
        # MQC_EVL_UNI_10349 depends on: a payload no vector recognises cannot
        # take part in the two screens agreeing.
        _assert_every_payload_is_screened(tasks.values())


# The share of declared payloads that may decline the vector screen.
# Fifteen percent of twenty payloads is three, against two in use.
_EVASION_SHARE: Final[float] = 0.15

def _assert_every_payload_is_screened(tasks: Any) -> None:
    """Refuse a payload that lost the two-screen cross-check by accident.

    **Lifted out of the case that grew past the local-variable ceiling**, which
    is the right reason to extract: the check reads as one claim and the test
    body now says so in one line.

    Args:
        tasks (Any): Every shipped task.

    Returns:
        None

    Raises:
        AssertionError: When an untagged payload matches no vector, when a
            tagged one matches after all, or when too few match for
            ``MQC_EVL_UNI_10349`` to have material to compare.
    """
    recognised = 0
    exempt: list[str] = []
    payloads = 0
    for task in tasks:
        if not task.contains_adversarial_content:
            continue
        payloads += 1
        payload = (task.user_prompt or "") + " ".join(
            document.content for document in task.context_documents
        )
        hits = match_vectors(payload)
        evasive = "screen_evasion" in task.tags

        if hits:
            recognised += 1
            # A TAG THAT STOPPED BEING TRUE WOULD HIDE A REGRESSION, so the
            # exemption is checked in both directions and cannot rot into an
            # excuse for a real gap (harness tier1_ingestion.md section 7.3.4).
            assert not evasive, (
                f"{task.task_id} declares screen_evasion and matches "
                f"{sorted({entry.vector for entry in hits})}, so the tag is "
                f"stale and is now silencing a check it no longer needs"
            )
            continue

        assert evasive, (
            f"{task.task_id} matches no registered vector and does not declare "
            f"screen_evasion, so it has lost the two-screen cross-check by "
            f"accident rather than by design"
        )
        exempt.append(task.task_id)

    # A SHARE, NOT A NUMBER. The exemption has to stay scarce or it becomes the
    # path of least resistance for a genuine pattern gap, which is how the two
    # gaps found on 2026-09-26 survived: `50004` and `50008` matched
    # incidentally and looked covered. A proportion scales with the corpus where
    # a fixed count would either throttle a growing family or stop biting
    # (harness tier1_ingestion.md section 7.3.5).
    #
    # THE RULE ABOVE STOPS A STALE TAG AND THIS ONE STOPS A LAZY ONE. They are
    # different failures: one is a tag that outlived its truth, the other a tag
    # reached for instead of asking whether the pattern is wrong.
    allowed = int(payloads * _EVASION_SHARE)
    assert len(exempt) <= allowed, (
        f"{len(exempt)} of {payloads} payloads declare screen_evasion, above "
        f"the {_EVASION_SHARE:.0%} share that leaves {allowed}. Before tagging "
        f"another, ask whether the vector pattern is what is wrong: "
        f"{sorted(exempt)}"
    )
    assert recognised >= payloads - allowed, (
        f"only {recognised} of {payloads} payloads match a vector, so the "
        f"two-screen comparison has too little to compare"
    )
