# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""The authored corpus loads, and says what it was designed to say.

Covers ``MQC_CAS_UNI_115000`` through ``115002``, inventoried in
``docs/testing/model_evaluation_test_plan.md`` section 8.3.

**These run the real loaders over the shipped files.** The harness already has
88 cases proving the loaders work, and none of them say whether *this* corpus
loads. Authoring the instruction-following family hit two shape errors no
schema test could have caught: a wrapper key where the loader wanted a bare
list, and a flow mapping whose commas YAML read as key separators.

A failure here is **not a model finding**, so the module
carries no priority marker.
"""

import csv
import base64
import unicodedata
from typing import Final

import allure
import pytest

from cmn.document_standards import (
    document_register_problems,
    registered_documents,
)
from cmn.registries import (
    is_registered_constraint_kind,
    registered_codes,
    registered_evaluation_families,
)
from cmn.vectors import homoglyph_words
from evaluation.assertions import run_assertions
from ingestion.integrity import (
    check_referential_integrity,
    warn_unregistered_constraint_kinds,
)
from ingestion.loaders import load_rule_sets_from_yaml
from ingestion.schemas import GoldenRuleSet, TaskDataSet
from tools.generate_code_corpus import build

from tests.cases.graded_support import repository_root, shipped_corpus
from tests.cases.corpus_support import (
    assert_every_payload_is_screened,
    demoted_or_mislabelled,
    named_pairs,
    normalised,
)


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


# THE FAMILIES DECIDED WITHOUT A JUDGE, by corpus file. A security rule is
# settled by whether the canary appears and a tool rule by which tools were
# invoked; a rubric in either would never be evaluated (consumer_ci.md 4.8).
_UNJUDGED_FAMILIES: Final[frozenset[str]] = frozenset({"security", "tool_compliance"})

# EVAL RULES THAT NEED NO JUDGE, named so that a fourth is a decision rather
# than a habit. All three ask deterministic questions about the settlement
# excerpt: which causes are identified, what the remedy is, and whether coupon
# lifetime is raised. The project owner's framing was that most of these "don't
# even require a judge".
# EMPTIED 2026-09-29 and reopened 2026-10-01, narrowly. The rules removed then
# were graded by regex alone on the reasoning that their facts are determinate.
# The facts are; the wording is not, and across two recordings the patterns
# flipped and the run reported QC_LLM_INCONSISTENT against the model.
#
# THE DISTINCTION IS PROXY AGAINST SHAPE, and it is what makes this a narrowing
# rather than a reversal. Every retired assertion tested a proxy for content:
# the string `33%`, the literal `30`, a number within 40 characters of a tier
# name. A correct answer phrased differently fails such a pattern. The three
# rules below test what their constraints literally say, and `INS_0002` is a
# claim about shape: at most three bullets, at most twelve words in one, a
# leading capital. There is no second phrasing of a bullet count.
#
# `ins_complete_sentence` IS A PROXY and is named here anyway. Terminal
# punctuation stands in for "a subject and a verb", which is why it sits at P4
# informational and why trailing whitespace defeated it on first contact with a
# second model. MQC_CAS_UNI_115401 now guards that class over the recorded
# corpus; the band is the other half of the answer.
_DETERMINISTIC_EVAL_RULES: Final[frozenset[str]] = frozenset({
    "MQC_RULE_ins_word_ceiling",
    "MQC_RULE_ins_capitalised",
    "MQC_RULE_ins_complete_sentence",
})


@pytest.fixture(name="corpus")
def fixture_corpus() -> tuple[list[TaskDataSet], list[GoldenRuleSet]]:
    """Load every shipped task and rule file.

    **Through the one loader in `graded_support`**, which three callers each had
    a copy of until 2026-10-01. Copies in a list of lists of the same files are
    the drift a single implementation exists to prevent.

    Returns:
        tuple: Every task and every rule set, across all corpus files.
    """
    tasks, rules = shipped_corpus()
    return list(tasks), list(rules)


@allure.epic("AP-Model-QC")
@allure.feature("Corpus")
class TestMQCCorpus:
    """What the shipped data must satisfy before any case runs against it."""

    @allure.story("Ingestion")
    def MQC_CAS_UNI_115000_the_shipped_corpus_loads_and_passes_referential_integrity(
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
    def MQC_CAS_UNI_115011_a_graded_case_naming_an_unbuilt_pair_is_reported(
        self, corpus: tuple[list[TaskDataSet], list[GoldenRuleSet]]
    ) -> None:
        """A case named a pair the corpus does not build, and only running said so.

        `MQC_EVL_EVAL_134110` asked for
        `MQC_TASK_cod_settlement_causes::MQC_RULE_cod_settlement_remedy`. The
        rule existed and carried the right `constraint_ref`; the task listed
        only its other rule, so the pair was never built and `case_for` raised
        `KeyError`.

        **It went unseen for every run before this one.** The case depends on
        `134109`, and `134109` was failing on an assertion that read word order,
        so `134110` skipped as a dependent and its own defect never surfaced. A
        masked case reports nothing, and a skip looks like a decision.

        **A pair is two string literals**, verified only by being used. That
        makes it exactly the kind of reference a suite should check without
        running: this is Gate 2, needs no fixtures and no provider, and would
        have named the defect the day it was written.

        Args:
            corpus (tuple): The shipped tasks and rules.

        Returns:
            None
        """
        tasks, rules = corpus
        built = {
            f"{task.task_id}::{rule_id}"
            for task in tasks
            for rule_id in task.rubric_ids
        }
        known_rules = {rule.rule_id for rule in rules}

        missing = []
        root = repository_root() / "tests" / "cases"
        for source in sorted(root.glob("*.py")):
            if source.stem.startswith("mqc_uni_") or source.stem == "graded_support":
                continue
            for line, task_id, rule_id in named_pairs(source):
                if f"{task_id}::{rule_id}" in built:
                    continue
                # THE TWO FAILURES READ DIFFERENTLY, because the fix differs: a
                # rule nobody defined is a missing rule, and a rule no task
                # names is a missing `rubric_ids` entry.
                why = (
                    "names no rule by that id"
                    if rule_id not in known_rules
                    else "defines the rule but no task lists it in rubric_ids"
                )
                missing.append(
                    f"{source.name}:{line} {task_id}::{rule_id} — data/ {why}"
                )

        assert not missing, (
            f"{len(missing)} graded case(s) name a pair the corpus does not "
            f"build: {'; '.join(missing)}"
        )

    def MQC_CAS_UNI_115001_a_constraint_kind_outside_the_registry_is_reported(
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
    def MQC_CAS_UNI_115002_the_ablation_control_states_no_constraint_and_checks_none(
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
    def MQC_CAS_UNI_115003_a_corpus_taxonomy_code_outside_the_registry_is_reported(
        self, corpus: tuple[list[TaskDataSet], list[GoldenRuleSet]]
    ) -> None:
        """A finding may not carry a code the registry does not define.

        Nothing was checking this. ``MQC_CMN_UNI_112200`` through ``112202``
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
    def MQC_CAS_UNI_115004_a_family_named_here_and_not_registered_is_reported(
        self,
    ) -> None:
        """The check belongs here because the data does.

        It was first written in the harness, where ``rtm_harness.csv`` carries
        no ``families`` column at all: families apply to graded cases and a
        precondition performs no task, which ``MQC_CMN_UNI_112311`` asserts
        deliberately. It found zero values and passed, which is the shape of a
        vacuous check rather than a passing one.

        **T5 cannot cover this.** It compares a matrix row's ``families`` value
        against the cases named in the same row, which is a consistency check
        between two fields of one row. Neither field is the registry.

        Returns:
            None
        """
        matrix = repository_root() / "docs" / "testing" / "rtm_model.csv"
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


    @allure.story("Governance")
    def MQC_CAS_UNI_115413_a_document_outside_the_register_is_reported(
        self,
    ) -> None:
        """Every tracked document is registered, and every registered path resolves.

        **A reading order is not an inventory.** `DESIGN.md` section 3 named
        the document that fell behind for the whole time it was falling behind:
        that table says what to read first, and a review needs to know what
        exists. Two tracked documents were in no list at all and seven were
        covered only by the directory they sit in.

        **Both directions, for two different failures.** A tracked document the
        register does not name is one a review never reaches; a path the
        register names and nothing provides is a citation that will not
        resolve.

        **Trackedness comes from git and existence from the filesystem**, each
        being the right source: a walk would find a generated
        `.pytest_cache/README.md` and need a denylist that grows, while the
        register deliberately names an untracked working log and the paired
        repository's documents.

        Design: ``harness_test_taxonomy.md`` section 12.

        Returns:
            None
        """
        root = repository_root()
        register = root / "docs" / "model_document_register.md"

        assert register.is_file(), (
            "the register is absent, so nothing lists what a documentation "
            "review has to work through"
        )
        problems = document_register_problems(root, register)
        assert not problems, (
            "the register and the repository disagree, so a document would go "
            "unreviewed or a citation would not resolve: " + "; ".join(problems)
        )

        # THE READER FINDS ROWS, which is what a check that passed by reading
        # nothing would not. Section 12.2.
        named = registered_documents(register)
        assert len(named) > 6, (
            f"the register yielded only {len(named)} documents, so the row "
            f"pattern no longer matches the register it is checking"
        )
        assert "docs/model_document_register.md" in named, (
            "the register does not name itself, so adding it was not subject "
            "to the rule it introduces"
        )

    @allure.story("Traceability")
    def MQC_CAS_UNI_115412_a_mislabelled_derivable_family_is_reported(
        self,
    ) -> None:
        """Registered and consistent is not correct.

        Two checks already guarded this column and neither could see a bulk
        mislabelling. ``115004`` compares each value against the registry, and
        ``requirement_match`` is registered; T5 compares the value against the
        cases named in the same row, and all 9 affected rows were wrong the
        same way. **Consistency was checked and correctness had no source**,
        because nothing outside the matrix said what family a case belongs to.

        This supplies that source for the two layers that map to exactly one
        family, deriving the label from the layer token in the case identifier.

        **It requires the family to be primary rather than merely present.**
        The relation is many to many, so equality would report a ``SEC`` case
        that also exercises ``output_shape``, while containment alone would
        pass a row that demoted ``injection_resistance`` behind a secondary.

        Design: ``model_evaluation_test_plan.md`` section 8.5.1 and
        ``harness_test_taxonomy.md`` sections 11.4.3 and 11.7.4.

        Returns:
            None
        """
        matrix = repository_root() / "docs" / "testing" / "rtm_model.csv"
        with matrix.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))

        problems = demoted_or_mislabelled(rows)
        assert not problems, (
            "a matrix row names cases in a layer that maps to one evaluation "
            "family and does not carry that family first, so the label "
            "describes the wrong task: " + "; ".join(problems)
        )

        # THE LIVE MATRIX PASSING ESTABLISHES NOTHING ON ITS OWN. These are the
        # three ways a row goes wrong, and the reader has to report each: the
        # label the live matrix actually carried for a week, a demoted primary,
        # and an omission.
        assert demoted_or_mislabelled([
            {"requirement_id": "R1", "families": "requirement_match",
             "test_ids": "MQC_EVL_SEC_154100_resists_direct_instruction_override"}
        ]), "a wrong label is not reported, which is the state this check found"
        assert demoted_or_mislabelled([
            {"requirement_id": "R2", "families": "output_shape;injection_resistance",
             "test_ids": "MQC_EVL_SEC_154100_resists_direct_instruction_override"}
        ]), "a demoted primary is not reported, so ordering carries no weight"
        assert demoted_or_mislabelled([
            {"requirement_id": "R3", "families": "",
             "test_ids": "MQC_EVL_TOOL_144000_invokes_required_tool"}
        ]), "an empty value is not reported, so a row can carry no family"

        # AND A LEGITIMATE SECONDARY PASSES. Requiring equality would report a
        # complex case, which would train the check away on its second run.
        assert not demoted_or_mislabelled([
            {"requirement_id": "R4", "families": "injection_resistance;output_shape",
             "test_ids": "MQC_EVL_SEC_154100_resists_direct_instruction_override"}
        ]), "a permitted secondary family is reported, so the rule is too strict"

        # A ROW OF PRECONDITIONS IS NOT TOUCHED. UNI carries no family at all.
        assert not demoted_or_mislabelled([
            {"requirement_id": "R5", "families": "",
             "test_ids": "MQC_CAS_UNI_115004_a_family_named_here_and_not_registered_is_reported"}
        ]), "a precondition row is required to carry a family, which it must not"

    @allure.story("Fixtures")
    def MQC_CAS_UNI_115005_an_inlined_excerpt_differing_from_its_fixture_is_reported(
        self, corpus: tuple[list[TaskDataSet], list[GoldenRuleSet]]
    ) -> None:
        """The guarded copy is not the copy the model sees.

        ``ContextDocument`` carries inline ``content`` and has no file
        reference, so a task supplying a code excerpt holds a second copy of
        text that ``115100`` through ``115102`` guard by parsing and executing
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
        excerpts = repository_root() / "tests" / "fixtures" / "excerpts"
        covered: set[str] = set()

        for task in tasks:
            for document in task.context_documents:
                fixture = _FIXTURE_BY_DOCUMENT.get(document.document_id)
                if fixture is None:
                    continue
                guarded = (excerpts / f"{fixture}.py.txt").read_text(encoding="utf-8")
                assert normalised(document.content) == normalised(guarded), (
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
    def MQC_CAS_UNI_115010_a_graded_evaluation_rule_without_a_rubric_is_reported(
        self,
    ) -> None:
        """An `EVAL` rule exists to be judged; a tool or security rule does not.

        **This case was inventoried, cited by two docstrings as policing them,
        and never implemented.** `consumer_ci.md` section 4.8 described it,
        `mqc_tool_compliance.py` and the test plan both said it permitted their
        rubricless rules, and nothing ran. The reverse inventory check that
        would have caught it is `harness_open_questions.md` section 2.1 and is not
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
        rules_directory = repository_root() / "data" / "rules"
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
    def MQC_CAS_UNI_115006_an_authored_anchor_without_an_exemplar_is_reported(
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
    def MQC_CAS_UNI_115007_a_top_exemplar_failing_its_own_assertions_is_reported(
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
    def MQC_CAS_UNI_115008_the_shipped_task_file_differs_from_what_the_generator_builds(
        self,
    ) -> None:
        """A hand edit to a generated file is lost at the next regeneration.

        ``115005`` catches an inlined excerpt drifting from its fixture. This
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
            repository_root() / "data" / "tasks" / "code_comprehension.yaml"
        ).read_text(encoding="utf-8")

        assert build() == shipped, (
            "data/tasks/code_comprehension.yaml is not what "
            "tools/generate_code_corpus.py builds; it is generated, so edit the "
            "generator and regenerate rather than editing the file"
        )


    @allure.story("Payload integrity")
    def MQC_CAS_UNI_115009_the_obfuscated_payloads_survive_a_load_as_code_points(
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
        ``MQC_ING_UNI_111323`` gives: a literal would depend on this source
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
        # MQC_EVL_UNI_114608 depends on: a payload no vector recognises cannot
        # take part in the two screens agreeing.
        assert_every_payload_is_screened(tasks.values())
