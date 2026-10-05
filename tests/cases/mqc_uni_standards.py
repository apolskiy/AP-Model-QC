# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""The code-style rules pylint cannot express, enforced on this tree.

Covers ``MQC_CAS_UNI_115500`` through ``115502``, inventoried in
``docs/design/consumer_ci.md`` section 4.

**One project spans two repositories**, and a rule enforced on one side only is
a rule that holds until somebody moves a file. The checkers live in
``cmn.code_standards`` and are called here with this repository's root and
licence, so the two enforcements differ in exactly one value and in nothing
else.

Copying the checkers to state that one difference would be two implementations
of one rule, and the copy would drift toward whichever repository was edited
less often.

A failure here is our defect, so the module carries no priority marker.
"""

from datetime import date
from pathlib import Path

import allure
import pytest

from cmn.case_module_standards import (
    extraction_problems,
    unbounded_subprocess_calls,
)
from cmn.code_standards import (
    identifier_block_problems,
    annotation_gaps,
    encoding_gaps,
    future_annotation_imports,
    header_problems,
    runbook_problems,
    markup_header_problems,
    markup_sources,
)

# This repository's root, two levels above a case module.
_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.unit

# MIT here, Apache-2.0 in the harness. THE ONLY DIFFERENCE between the two
# enforcements, and the reason the checkers take it as an argument.
_REPOSITORY_LICENCE = "MIT"


def _root() -> Path:
    """Return this repository's root.

    Returns:
        Path: The directory holding ``pyproject.toml``.
    """
    return Path(__file__).resolve().parents[2]


@allure.epic("AP-Model-QC")
@allure.feature("Governance parity")
class TestMQCCodeStandards:
    """The rules that stood in a document while nothing checked them."""

    @allure.story("Annotations")
    def MQC_CAS_UNI_115500_every_callable_carries_parameter_and_return_hints(
        self,
    ) -> None:
        """Pylint does not check annotation presence, so nothing else does.

        **Test code is held to it identically.** A test callable is a function
        like any other, and its fixtures are its parameters. An audit of the
        harness against this rule found production code at zero gaps and test
        code at 597, which is what a rule nothing checks looks like after a
        year.

        Returns:
            None
        """
        gaps = annotation_gaps(_root())
        assert not gaps, f"{len(gaps)} annotation gaps: " + "; ".join(gaps[:10])

    @allure.story("Annotations")
    def MQC_CAS_UNI_115501_pep_563_future_annotations_import_is_rejected(self) -> None:
        """Laziness comes from the interpreter, not from stringizing.

        Python 3.14 implements PEP 649, so annotations are already evaluated
        lazily and the import buys nothing. What it does instead is select PEP
        563, which turns every annotation into a string and removes
        ``annotationlib.Format.VALUE``.

        Returns:
            None
        """
        offending = future_annotation_imports(_root())
        assert not offending, (
            "PEP 563 stringized annotations are prohibited, and 3.14 already "
            f"defers evaluation without them: {', '.join(offending)}"
        )

    @allure.story("Authorship")
    def MQC_CAS_UNI_115502_every_python_file_carries_its_mit_spdx_header(self) -> None:
        """This repository is MIT, and its files have to say so themselves.

        **The licence is named rather than accepted as any valid tag**, which is
        the entire point: harness code installs into this repository under a
        different licence, so a file separated from its repository has to carry
        its own correct answer. A check accepting any SPDX identifier would pass
        a file that had been copied here from the harness unchanged.

        Returns:
            None
        """
        problems = header_problems(_root(), _REPOSITORY_LICENCE)
        assert not problems, (
            f"{len(problems)} header problems: " + "; ".join(problems[:8])
        )

    @allure.story("Authorship")
    def MQC_CAS_UNI_115503_a_document_or_data_file_without_its_mit_header_is_reported(
        self,
    ) -> None:
        """The corpus is the material this licence rationale names.

        The README justifies MIT here because the cases are material people
        copy and adapt. **That material carried no licence marker at all**,
        which made it the most likely file to travel and the least likely to
        say what it was when it arrived.

        Returns:
            None
        """
        root = _root()
        problems = markup_header_problems(root, _REPOSITORY_LICENCE)

        assert markup_sources(root), "no documents or data files were read"
        assert not problems, (
            f"{len(problems)} header problems: " + "; ".join(problems[:8])
        )


@allure.epic("AP-Model-QC")
@allure.feature("Governance parity")
class TestMQCRunbook:
    """The operating procedure, checked against the workflows it describes."""

    @allure.story("The runbook works")
    def MQC_CAS_UNI_115504_a_runbook_command_naming_an_undeclared_input_is_reported(
        self,
    ) -> None:
        """A documented dispatch that GitHub rejects is worse than none.

        **The failure is silent at authoring time and lands on the reader.** A
        dispatch naming an input the workflow does not declare is rejected with
        a message about the input, and somebody following the documented
        procedure concludes the procedure is broken rather than the page.

        The runbook exists so that starting a run costs nobody a design read,
        and a runbook that does not work costs them that read plus the time
        spent trusting it.

        Returns:
            None
        """
        problems = runbook_problems(_root())
        assert not problems, (
            "the runbook documents a dispatch that would be rejected, so the "
            "procedure fails for whoever follows it: " + "; ".join(problems)
        )


class TestMQCEncodingDeclared:
    """The rule that fails more quietly than any other here."""

    def MQC_CAS_UNI_115505_a_file_open_declaring_no_encoding_is_reported(
        self, tmp_path: Path
    ) -> None:
        """A missing encoding raises nothing and changes the value.

        It reads ``cp1252`` on Windows and ``utf-8`` on Linux, so the same
        commit produces different values on the two platforms CI runs, and
        **both runs report success**. Every other rule in
        ``code_standards`` guards something that is merely invisible; this one
        guards something that is invisible and platform dependent.

        Args:
            tmp_path (Path): A directory for the positive control.

        Returns:
            None
        """
        gaps = encoding_gaps(_root())

        assert not gaps, (
            "a file is read or written without an encoding, so this commit "
            "yields different values on Windows and Linux: " + "; ".join(gaps)
        )

        # THE POSITIVE CONTROL, and this case is vacuous without it. Asserting
        # "no gaps found" cannot tell a clean repository from a checker that
        # stopped looking, which is exactly what injecting a narrowed
        # _ENCODED_CALLS demonstrated: the repository stayed clean, the case
        # stayed green, and the check had gone blind.
        probe = tmp_path / "mqc_probe.py"
        probe.write_text(
            "from pathlib import Path\n"
            "def read(path):\n"
            "    return path.read_text()\n"
            "def write(path):\n"
            "    return path.write_text('x')\n"
            "def plain(path):\n"
            "    return open(path).read()\n"
            "def binary(path):\n"
            "    return open(path, 'rb').read()\n"
            "def declared(path):\n"
            "    return path.read_text(encoding='utf-8')\n",
            encoding="utf-8",
        )
        reported = encoding_gaps(tmp_path)

        # ALL THREE CALL KINDS, because a checker covering two of them reports
        # nothing on the third and looks identical from here.
        assert len(reported) == 3, (
            f"the checker found {len(reported)} of three bare calls, so it is "
            f"blind to a kind: {reported}"
        )
        # AND NEITHER CORRECT CALL. A binary open carries no encoding and must
        # not claim one; a declared read is simply right.
        assert not any("binary" in entry or "declared" in entry for entry in reported)


    @allure.story("Identifiers sit in their own block")
    def MQC_CAS_UNI_115506_an_identifier_outside_its_module_block_is_reported(
        self,
    ) -> None:
        """Every identifier's digits say what its tokens say.

        An identifier is six positional digits: domain, layer, module,
        category, case. This reads the layer and module tokens off each name
        and checks the digits that encode them.

        **Nothing checked the previous allocation**, which is how `EXE/UNI`
        came to sit inside `EVL`'s block, `EVL/UNI` inside `CAS`'s and
        `CMN/UNI` past its last allocated block, all at once and silently.

        **The duplicate-binding check cannot see this.** Two modules occupying
        one block are two distinct identifiers, so counting bindings balances.

        Design: ``test_taxonomy.md`` section 3.2.1.4.

        Returns:
            None
        """
        problems = identifier_block_problems(_REPOSITORY_ROOT)

        assert not problems, (
            "identifiers carry digits their tokens contradict, so a module "
            "occupies a block it was not allocated: " + "; ".join(problems)
        )


@allure.epic("AP-Model-QC")
@allure.feature("Suite governance")
class TestMQCCaseModuleContents:
    """What a collected case module is allowed to define."""

    @allure.story("Cases here, apparatus next door")
    def MQC_CAS_UNI_115711_a_case_module_holding_support_code_is_reported(
        self,
    ) -> None:
        """A collected test module holds cases, not the library supporting them.

        **The convention existed and was unwritten**, which is what it cost:
        ``repository_root`` stood four times, byte-identical, once public in
        ``graded_support`` and once privately in each of three case modules. A
        helper nobody owned was cheaper to rewrite than to find.

        **``pytest.ini`` already draws the boundary** with
        ``python_files = mqc_*.py``, so a module outside that glob is support by
        construction. This asserts the other half: that a module inside it holds
        no support.

        **Fixtures are not support.** A ``@pytest.fixture`` is wiring for one
        module's cases, bound to them by name, and moving it would make the
        cases harder to read for a tidier line count.

        **The backlog is declared, not exempted.** Modules predating the rule
        are named in ``config/support_extraction.yaml`` with a reason and an
        expiry, and an expired entry fails this. The list shrinks and never
        grows, because anything undeclared fails here on the day it is written.

        Design: ``test_taxonomy.md`` section 13.

        Returns:
            None
        """
        root = Path(__file__).resolve().parents[2]
        problems = extraction_problems(
            root / "tests", root, root / "config" / "support_extraction.yaml",
            date.today(),
        )
        assert not problems, (
            f"{len(problems)} case module(s) hold support code that belongs in "
            f"a sibling module, or carry a lapsed declaration: "
            + "; ".join(problems)
        )


@allure.epic("AP-Model-QC")
@allure.feature("Suite governance")
class TestMQCBoundedSubprocesses:
    """What this repository is allowed to wait for, and for how long."""

    @allure.story("A bound turns a hang into a failure")
    def MQC_CAS_UNI_115712_a_subprocess_without_a_timeout_is_reported(
        self,
    ) -> None:
        """No subprocess invocation here waits without a bound.

        **A hang is the worst failure shape available.** A crash names itself;
        a hang names nothing, arrives after the longest possible delay, and
        presents as an environmental fault on whichever platform stalled. One
        cancelled a Windows job 22 minutes into a run that reported `failure`
        with no failing job and no log, while Ubuntu passed.

        **Six calls existed and none carried a timeout.** Five spawned a nested
        pytest; the sixth asked git. The case repository had a seventh, and it
        was the one that mattered most: `git ls-remote` over HTTPS, in the
        resolve job of every gate there.

        **No local run could have found this.** Those cases take 0.6s to 3.4s
        here. The defect was never that something hung; it was that nothing
        bounded how long it could.

        **The keyword is checked, not the value.** Whether 300s is right is a
        judgement; whether a bound exists is not, and only the second is
        mechanical.

        Design: ``test_taxonomy.md`` section 14.

        Returns:
            None
        """
        problems = unbounded_subprocess_calls(
            Path(__file__).resolve().parents[2]
        )
        assert not problems, (
            f"{len(problems)} subprocess invocation(s) carry no timeout, so a "
            f"child that stalls blocks until a runner cancels the job: "
            + "; ".join(problems)
        )
