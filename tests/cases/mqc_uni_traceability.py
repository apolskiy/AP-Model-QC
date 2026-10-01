# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""The matrix checked against the two things that are not the matrix.

Covers ``MQC_CAS_UNI_10448``, ``10449`` and ``10460``, inventoried in
``docs/design/consumer_ci.md`` section 3.2. The checks themselves are the
harness's, specified in ``cmn_verdict_and_cli.md`` section 6.

**Three directions, and each one was blind to the others.** `10448` compares
the matrix against the test plan, `10449` the matrix against the suite, and
`10460` the suite against the matrix. The first two passed over two cases that
ran traced to nothing, because neither of them looks that way.

**Extracted from ``mqc_uni_harness_pin.py`` on 2026-10-01**, which had grown
past the thousand-line ceiling. Matrix integrity is not what that module is
about: it is about which harness this repository runs against. The harness keeps
these checks in a file of this name too, which is the vocabulary rule applied to
a filename.

A failure here is our defect, so the module carries no priority marker, per the
harness ``framework-rules.md`` section 3.3.
"""

import ast
import csv
import re
from pathlib import Path

import allure
import pytest

from cmn.traceability import MatrixRow, untraced_tests

pytestmark = pytest.mark.unit


def _root() -> Path:
    """Return this repository's root.

    Returns:
        Path: The directory holding ``pyproject.toml``.
    """
    return Path(__file__).resolve().parents[2]


@allure.epic("AP-Model-QC")
@allure.feature("Consumer CI")
class TestMQCMatrixIntegrity:
    """Every requirement stated, every test traced, both ways round.

    Designed in ``docs/design/consumer_ci.md`` section 4.8.
    """

    def MQC_CAS_UNI_10448_a_requirement_traced_but_stated_in_no_plan_is_reported(
        self,
    ) -> None:
        """Thirty-nine requirements were traced and stated nowhere.

        They existed only as rows in ``rtm_model.csv``, so what this
        repository promises could be read only by opening a CSV and
        reconstructing it. **Nothing reported it, because the check that would
        have found it lived on one side of the split**: the harness has had
        ``MQC_CMN_UNI_11131`` since the matrices were written.

        **Both directions.** A requirement stated and never traced is
        uncovered; one traced and never stated is a claim nobody wrote down.
        The second is quieter, because a matrix row looks like completeness.

        Returns:
            None
        """
        root = _root()
        matrix = root / "docs" / "testing" / "rtm_model.csv"
        plan = (root / "docs" / "testing" / "model_evaluation_test_plan.md").read_text(
            encoding="utf-8"
        )

        with matrix.open(encoding="utf-8-sig", newline="") as handle:
            traced = {
                row["requirement_id"].strip()
                for row in csv.DictReader(handle)
                if row.get("requirement_id")
            }
        stated = set(re.findall(r"\bMQC_REQ_[A-Z]+_[A-Z]+_\d{4}\b", plan))

        assert traced and stated, "one of the two artefacts was not read"

        untraced = sorted(stated - traced)
        assert not untraced, (
            f"{len(untraced)} requirements are stated and never traced, so "
            f"nothing covers them: {untraced[:6]}"
        )

        unstated = sorted(traced - stated)
        assert not unstated, (
            f"{len(unstated)} requirements are traced and stated in no plan, "
            f"so the promise exists only as a matrix row: {unstated[:6]}"
        )

    def MQC_CAS_UNI_10449_a_matrix_row_naming_a_test_the_suite_lacks_is_reported(
        self,
    ) -> None:
        """`10447` was traced, cited by two docstrings, and never written.

        **A matrix row looks exactly like completeness.** `MQC_REQ_CAS_CI_0019`
        named `MQC_CAS_UNI_10447`, `consumer_ci.md` section 4.8 described it,
        and `mqc_tool_compliance.py` said it policed the rubricless tool rules.
        Nothing ran. It was found by reconciling the inventory by hand before
        the first commit, which is not a check.

        **`10448` runs the other way** and could not see this: it compares the
        matrix against the plan, and both agreed. Neither of them is the suite.
        The harness has had `MQC_CMN_UNI_11122` for this direction since the
        matrices were written, and it scans the harness's own tests.

        **Read from parsed syntax, not from source text.** A `def` inside a
        string literal is data, and this repository embeds several in
        docstrings that quote case names — including the ones that quoted
        `10447` while it did not exist.

        Returns:
            None
        """
        root = _root()
        matrix = root / "docs" / "testing" / "rtm_model.csv"

        with matrix.open(encoding="utf-8-sig", newline="") as handle:
            named: set[str] = set()
            for row in csv.DictReader(handle):
                for value in (row.get("test_ids") or "").split(";"):
                    if value.strip():
                        named.add(value.strip())

        defined: set[str] = set()
        for source in sorted((root / "tests").rglob("*.py")):
            tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name.startswith("MQC_"):
                        defined.add(node.name)

        assert named and defined, "one of the two artefacts was not read"

        absent = sorted(named - defined)
        assert not absent, (
            f"{len(absent)} matrix row(s) name a test this suite does not "
            f"define, so a requirement reads as covered by nothing: {absent[:6]}"
        )

    def MQC_CAS_UNI_10460_a_collected_test_named_in_no_matrix_row_is_reported(
        self,
    ) -> None:
        """`10449` built both sets and asserted one of the two directions.

        It compares the matrix against the suite and reports a row naming a test
        that does not exist. **The reverse was one line away and absent**, so
        `MQC_CAS_UNI_10454` and `10455` were inventoried, written, collected and
        traced to nothing, and these preconditions ran green over them.

        **The harness had the check and this repository did not**, which is what
        the duplication cost: `10449` rebuilt the comparison inline rather than
        calling the harness implementation, so it inherited none of the second
        half. `cmn.traceability.untraced_tests` is now the one implementation
        and `MQC_CMN_UNI_11122` is the other caller.

        **T4 is not a substitute.** It reads the requirements a test declares
        for itself, and a test declaring none satisfies it by declaring none.
        Harness design `cmn_verdict_and_cli.md` section 6.0.1 carries the
        difference.

        Returns:
            None
        """
        root = _root()
        matrix = root / "docs" / "testing" / "rtm_model.csv"

        with matrix.open(encoding="utf-8-sig", newline="") as handle:
            rows = [MatrixRow.from_row(entry) for entry in csv.DictReader(handle)]

        defined: set[str] = set()
        for source in sorted((root / "tests").rglob("*.py")):
            tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name.startswith("MQC_"):
                        defined.add(node.name)

        assert rows and defined, "one of the two artefacts was not read"

        untraced = untraced_tests(rows, defined)

        assert not untraced, (
            f"{len(untraced)} collected test(s) appear in no matrix row, so the "
            f"requirement each satisfies is unrecorded: "
            f"{[entry.subject for entry in untraced[:6]]}"
        )
