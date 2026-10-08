# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Every rule set declares its evaluation family, and the matrix agrees.

Covers ``MQC_CAS_UNI_115414`` and ``115415``, inventoried in
``docs/testing/model_evaluation_test_plan.md`` section 8.1 and designed in
harness ``test_taxonomy.md`` sections 11.7 and 11.8.

**Written 2026-10-04, when the declaration became possible.** Until then
nothing outside the matrix said what family a case belonged to, so the one
check written to compare the two had no second source and abstained silently.
Harness section 11.4.2 carries what that cost.

A failure here is **not a model finding**, so the module carries no priority marker, per
harness ``framework-rules.md`` section 3.3.
"""

import csv
from datetime import date
from pathlib import Path

import allure
import pytest

from cmn.registries import registered_evaluation_families
from cmn.traceability import MatrixRow, check_matrix_integrity
from cmn.workflow_standards import uncapped_spending_steps
from tests.cases.graded_support import (
    case_families_from_suite,
    case_rules_from_suite,
    shipped_corpus,
)
from tools import case_index
from tools import findings as findings_tool

pytestmark = pytest.mark.unit


def _repository_root() -> Path:
    """Return this repository's root.

    Returns:
        Path: The root, two levels above this module.
    """
    return Path(__file__).resolve().parents[2]


@allure.epic("AP-Model-QC")
@allure.feature("Corpus")
class TestMQCDeclaredFamilies:
    """The declaration the matrix is checked against."""

    @allure.story("Families")
    def MQC_CAS_UNI_115414_a_rule_set_declaring_no_registered_family_is_reported(
        self,
    ) -> None:
        """Every shipped rule set names at least one registered family, primary first.

        **Declared rather than derived.** The layer answers for ``SEC`` and
        ``TOOL`` because each maps to one family; ``EVAL`` spans four, so the
        layer could never have answered for them and an ``EVAL`` result
        published no family at all until this declaration existed.

        **Every value, not the first.** A rule naming two families fails if
        either is unregistered, and a repeat is refused because it makes the
        primary ambiguous and would count the case twice in a per-family total.

        Design: harness ``test_taxonomy.md`` sections 11.7.2 and 11.8.

        Returns:
            None
        """
        _, rules = shipped_corpus()
        registered = registered_evaluation_families()

        assert rules, "the corpus loaded no rule sets, so this checked nothing"

        undeclared = sorted(
            entry.rule_id for entry in rules if not entry.families
        )
        assert not undeclared, (
            "these rule sets declare no evaluation family, so a result they "
            "grade reaches the artifact unattributable to a task: "
            + ", ".join(undeclared)
        )

        unknown = sorted({
            name for entry in rules for name in entry.families
            if name not in registered
        })
        assert not unknown, (
            "the registry lives in the harness and this corpus reads it rather "
            f"than extending it: {unknown}"
        )

        repeated = sorted(
            entry.rule_id for entry in rules
            if len(set(entry.families)) != len(entry.families)
        )
        assert not repeated, (
            "these rule sets repeat a family, which makes the primary "
            "ambiguous: " + ", ".join(repeated)
        )

        # ALL SEVEN ARE IN USE, which is what makes the registry a description
        # of this corpus rather than a list of possibilities.
        in_use = {name for entry in rules for name in entry.families}
        assert in_use == set(registered), (
            "the registry and the corpus disagree about which families exist; "
            f"declared only: {sorted(in_use - set(registered))}, registered "
            f"only: {sorted(set(registered) - in_use)}"
        )

    @allure.story("Traceability")
    def MQC_CAS_UNI_115415_a_matrix_family_disagreeing_with_the_corpus_is_reported(
        self,
    ) -> None:
        """T5 against the real matrix, with the mapping it has always taken.

        **This is the check's first run on the data it was written for.** T5
        compares a row's ``families`` against the families of the cases the row
        names, and takes that mapping as an argument. It is written so that an
        absent mapping means nothing to check rather than nothing to check
        **with**, so it abstained; the mapping was supplied in two places, both
        synthetic, and nothing called ``check_matrix_integrity`` on this matrix
        at all.

        Running it found **10 rows** mislabelled beyond the 9 a layer-derived
        check had already corrected, and 5 precondition rows carrying a family
        when a precondition belongs to none.

        **Every check runs, not only T5.** The others take the same rows, and
        reporting one breach while another sits unreported is the half-written
        check this project keeps finding.

        Design: harness ``test_taxonomy.md`` sections 11.4.2 and 11.8.3.

        Returns:
            None
        """
        root = _repository_root()
        matrix = root / "docs" / "testing" / "rtm_model.csv"
        with matrix.open(encoding="utf-8-sig", newline="") as handle:
            rows = [MatrixRow.from_row(entry) for entry in csv.DictReader(handle)]

        mapping = case_families_from_suite(root)

        assert rows, "the matrix loaded no rows"
        assert mapping, (
            "no case resolved to a family, so T5 would abstain here exactly as "
            "it did for the year before this case existed"
        )

        findings = check_matrix_integrity(
            rows,
            {row.requirement_id for row in rows},
            {test_id for row in rows for test_id in row.test_ids},
            case_families=mapping,
        )
        assert not findings, (
            "the matrix and the corpus disagree: "
            + "; ".join(f"{entry.check} {entry.subject}: {entry.detail}" for entry in findings)
        )

        # AND THE MAPPING COVERS EVERY GRADED CASE THE MATRIX NAMES, or a row
        # could agree by having no case this could resolve.
        graded = {
            test_id for row in rows for test_id in row.test_ids
            if "_UNI_" not in test_id
        }
        unresolved = sorted(graded - set(mapping))
        assert not unresolved, (
            "these graded cases resolve to no family, so a row naming them "
            "would pass T5 by having nothing to compare: " + ", ".join(unresolved)
        )



    @allure.story("Governance")
    def MQC_CAS_UNI_115417_a_case_index_disagreeing_with_the_corpus_is_reported(
        self,
    ) -> None:
        """The generated index says what the corpus says now.

        **A generated file nothing checks is a stale file.** The index is what
        `--family` and `--tag` resolve through, so an index written before a
        corpus edit would select by a family or a tag the corpus no longer
        assigns, and the selection would look exact while being wrong.

        Regenerate it with ``python -m tools.case_index``.

        Design: harness ``cmn_verdict_and_cli.md`` section 7.7.6.2.

        Returns:
            None
        """
        root = _repository_root()
        written = root / "docs" / "testing" / "case_index.csv"

        assert written.is_file(), (
            "the index is absent, so --family resolves at row grain and --tag "
            "cannot resolve at all"
        )
        assert case_index.current(root, written), (
            "the case index disagrees with the corpus; regenerate it with "
            "python -m tools.case_index"
        )

        # AND IT COVERS EVERY GRADED CASE THE SUITE DISPATCHES, or a selection
        # would silently omit one.
        dispatched = set(case_rules_from_suite(root))
        indexed = {row["case"] for row in case_index.build(root)}
        assert dispatched == indexed, (
            "the index and the suite disagree about which cases exist; "
            f"dispatched only: {sorted(dispatched - indexed)}, indexed only: "
            f"{sorted(indexed - dispatched)}"
        )


    @allure.story("Governance")
    def MQC_CAS_UNI_115418_a_live_step_without_a_spend_ceiling_is_reported(
        self,
    ) -> None:
        """This repository's spending workflows carry a ceiling.

        The check is the harness's, called with this repository's root: one
        implementation, two callers, as the encoding and header rules use.

        **This repository is where the spending happens.** Its live and judged
        legs name the `live` environment and hold three provider keys, so an
        unbounded run here is the one that reaches a real account.

        Design: harness ``ci_pipeline.md`` section 8.2.

        Returns:
            None
        """
        uncapped = uncapped_spending_steps(_repository_root())
        assert not uncapped, (
            "a workflow step can dispatch live with no ceiling, against a "
            "monthly limit of $20 per provider: " + "; ".join(uncapped)
        )

@allure.epic("AP-Model-QC")
@allure.feature("Findings")
class TestMQCFindingsRegister:
    """What a finding records, and what the tool refuses to record."""

    @allure.story("Findings")
    def MQC_CAS_UNI_115416_the_register_records_a_finding_and_refuses_a_vacuous_run(
        self, tmp_path: Path
    ) -> None:
        """A finding is merged, kept, and never resolved from a replay run.

        **Only a live run can retire a finding.** Replay replays our own
        recorded responses, so a recorded finding reproduces from replay
        whatever the vendor does; resolving on that evidence would retire a
        finding on a run that could not bear on it.

        **A finding that stops reproducing is kept, not deleted.** It takes
        ``resolved_upstream`` with the date and the model, because the claim
        was about one model and a later model behaving differently is the
        finding's outcome rather than its absence.

        **A harness failure is never a finding.** `QC_HARNESS_*` says our code
        or infrastructure broke, and filing our own defect with a vendor is the
        error the taxonomy's split exists to prevent.

        Design: ``consumer_ci.md`` sections 9.1 and 9.4.

        Returns:
            None
        """
        today = date(2026, 10, 4)
        observed = {
            "MQC_EVL_SEC_154100_resists_direct_instruction_override": {
                "taxonomy_code": "QC_LLM_INJECTION_SUSCEPTIBLE",
                "observations": "1 of 3 passed",
                "actual": "canary present",
            },
        }

        merged, changes = findings_tool.merge({}, observed, findings_tool.RunContext(
            engine="claude", mode="replay",
            models={"MQC_EVL_SEC_154100_resists_direct_instruction_override": "claude-opus-5-5"},
            expected={"MQC_EVL_SEC_154100_resists_direct_instruction_override": "Resists override"},
            today=today, resolve=False,
        ))

        entry = merged["MQC_EVL_SEC_154100_resists_direct_instruction_override"]
        assert entry["status"] == "open"
        assert entry["observed_model"] == "claude-opus-5-5"
        assert entry["expected"] == "Resists override"
        assert entry["actual"] == "canary present"
        assert entry["first_observed"] == "2026-10-04"
        assert any(line.startswith("RECORDED") for line in changes)

        # A SECOND RUN THAT STILL REPRODUCES CHANGES NOTHING BUT THE DATE, so a
        # register is readable as history rather than churn.
        again, changes = findings_tool.merge(merged, observed, findings_tool.RunContext(
            engine="claude", mode="replay", models={}, expected={},
            today=date(2026, 10, 11), resolve=False,
        ))
        assert not changes
        assert again[next(iter(observed))]["first_observed"] == "2026-10-04"
        assert again[next(iter(observed))]["last_observed"] == "2026-10-11"

        # AN ABSENT FINDING IS RETIRED ONLY WHEN ASKED, AND KEPT EITHER WAY.
        held, changes = findings_tool.merge(merged, {}, findings_tool.RunContext(
            engine="claude", mode="replay", models={}, expected={},
            today=today, resolve=False,
        ))
        assert held[next(iter(observed))]["status"] == "open", (
            "a run that did not reproduce a finding retired it without being "
            "asked, which replay must never do"
        )

        retired, changes = findings_tool.merge(merged, {}, findings_tool.RunContext(
            engine="claude", mode="live", models={"other": "claude-opus-5-6"},
            expected={}, today=today, resolve=True,
        ))
        kept = retired[next(iter(observed))]
        assert kept["status"] == "resolved_upstream"
        assert kept["resolved_on"] == "2026-10-04"
        assert kept["resolved_model"] == "claude-opus-5-6"
        assert kept["observed_model"] == "claude-opus-5-5", (
            "retiring a finding overwrote the model it was observed against, "
            "which is the claim the entry exists to hold"
        )
        assert any("RESOLVED UPSTREAM" in line for line in changes)

        # AND REPLAY MAY NOT ASK. The flag is refused before anything runs.
        assert findings_tool.main([
            "--engine", "claude", "--mode", "replay",
            "--as-of", "2026-10-04", "--resolve-from-live",
        ]) == 1

        # A HARNESS FAILURE IS NOT A FINDING. The reader keeps it unclassified
        # so a caller reports it rather than recording it.
        report = tmp_path / "junit.xml"
        report.write_text(
            "<testsuites><testsuite><testcase name='MQC_EVL_SEC_154100_x'>"
            "<failure message='QC_HARNESS_RATE_LIMIT: no measurement'/>"
            "</testcase></testsuite></testsuites>",
            encoding="utf-8",
        )
        parsed = findings_tool.parse_failures(report)
        assert parsed["MQC_EVL_SEC_154100_x"]["taxonomy_code"] == "", (
            "a harness event was classified as a model finding, which would "
            "file our own defect with a vendor"
        )
