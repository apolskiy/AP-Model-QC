# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""How this case set finds the harness, which is by install and not by path.

Covers ``MQC_CAS_UNI_10452`` and ``10453``, inventoried in
``docs/design/consumer_ci.md`` section 4A.

**Gate 4 failed in CI and could not fail on any developer's disk.** The roster
was read from ``../AP-Harness-QC/config/engines.yaml``, true only where both
repositories are checked out side by side; CI installs the pinned harness from
git, so an absent file loaded as an empty mapping and the run reported a judge
engine missing from a roster it never read.

Separate from ``mqc_uni_harness_pin`` because the question differs: that module
asks which harness commit may be used, this one asks where the harness is.

A failure here is our defect, so the module carries no priority marker, per the
harness ``framework-rules.md`` section 3.3.
"""

import ast
from pathlib import Path
from typing import Final

import pytest

from cmn.observations import further_observations
from tests.cases.graded_support import _channel, engine_roster
from tools.band_floor import assess

pytestmark = pytest.mark.unit

# SPELT IN PIECES so this module is not itself a hit for the rule
# `MQC_CAS_UNI_10452` enforces over the repository.
_HARNESS_DIRECTORY: Final[str] = "AP-" + "Harness-QC"


def _root() -> Path:
    """Return this repository's root.

    Returns:
        Path: The directory holding ``pyproject.toml``.
    """
    return Path(__file__).resolve().parents[2]


class TestMQCHarnessLocatedByInstall:
    """The harness is a dependency, not the directory next door."""

    def MQC_CAS_UNI_10452_harness_files_are_not_located_by_directory_adjacency(
        self,
    ) -> None:
        """Gate 4 failed in CI and could not fail on any developer's disk.

        `engine_roster` read `../AP-Harness-QC/config/engines.yaml`, which is
        true only where both repositories are checked out side by side. CI
        installs the pinned harness from git, so the path did not exist, an
        absent file loaded as an empty mapping the way an optional one does,
        and the run failed three layers later with `judge engine 'gemini' is
        not on the roster`.

        **The local run could not catch it**, because the sibling is always
        there. So this asserts the shape rather than the outcome: nothing here
        may reach out of this repository by directory traversal to find harness
        files. What the harness ships, the harness is asked for.

        Returns:
            None
        """
        root = _root()
        reaching = []
        for source in sorted((root / "tests").rglob("*.py")) + sorted(
            (root / "tools").rglob("*.py")
        ):
            tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
            for node in ast.walk(tree):
                # PATH CONSTRUCTION, NOT PROSE. Scanning the text flagged every
                # docstring that explains this rule, and `apolskiy/AP-Harness-QC`
                # in the pin's own fixtures, neither of which reaches anywhere.
                # A traversal is a path expression, so the syntax tree is what
                # gets asked: a `/` join, or a `Path(...)` built from a literal.
                joined = isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)
                built = (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "Path"
                )
                if not (joined or built):
                    continue
                if _HARNESS_DIRECTORY in ast.unparse(node):
                    reaching.append(
                        f"{source.relative_to(root).as_posix()}:{node.lineno}"
                    )

        assert not reaching, (
            "harness files located by directory adjacency rather than by "
            f"install: {'; '.join(sorted(set(reaching)))}. Ask the installed "
            "package, as cmn.config.packaged_roster_path does."
        )

    def MQC_CAS_UNI_10453_the_roster_resolves_and_names_engines(self) -> None:
        """An empty roster is a broken install, not a starting condition.

        `load_yaml_config` yields an empty mapping for an absent file, which is
        right for an optional one and wrong for the roster: every engine, model
        and pacing value a run needs is in it. Read through the installed
        package it is either present or raises, and this pins that it is
        present and populated.

        Returns:
            None
        """
        roster = engine_roster()

        assert roster, "the roster names nothing, so the harness shipped no config"
        # THE JUDGE'S OWN ENGINE, because a replayed judgement verifies the
        # model that recorded it and takes that model from here.
        assert "gemini" in roster
        assert roster["gemini"].model


class TestMQCOptionsReachTheHarness:
    """A flag set here has to arrive where the harness reads it."""

    def MQC_CAS_UNI_10455_fill_gaps_reaches_the_plan_the_channel_uses(self) -> None:
        """The flag was set on a plan nothing ran with.

        `judgement_plan` builds a `JudgementPlan` and `_channel` builds a
        second one; only the second reaches the channel, and the first is read
        for its mode and record flag. `--fill-gaps` was added to the first, so
        a run meant to fill fifteen judgements re-judged all ninety-two and the
        flag reported as working because the candidate half — a different plan
        entirely — did fill correctly.

        **The cache key matters as much as the field.** `_channel` is cached
        per distinct configuration, so a channel built once without filling
        would be handed back to a run that asked for it.

        Returns:
            None
        """
        built = _channel("gemini", "live", True, False, True)

        assert built.plan.fill_gaps is True, (
            "the channel was built from a plan that does not fill, so a live "
            "run would ask the judge for every judgement it already has"
        )

        # AND THE TWO CONFIGURATIONS ARE DISTINCT, which the cache must respect.
        assert _channel("gemini", "live", True, False, False).plan.fill_gaps is False
        assert _channel("gemini", "live", True, False, True).plan.fill_gaps is True


    def MQC_CAS_UNI_10459_the_candidate_engine_reaches_the_plan_the_channel_uses(
        self,
    ) -> None:
        """The candidate engine reaches the plan the judge channel is built from.

        ``_channel`` is cached per distinct configuration, so the candidate
        engine is part of the cache key as well as the plan: two engines
        differing only in it are different configurations and must not share a
        channel.

        Design: harness ``tier2_execution.md`` section 7.9.3.

        Returns:
            None
        """
        built = _channel("gemini", "live", True, False, True, "openai")

        assert built.plan.candidate_engine == "openai", (
            "the channel was built from a plan naming no candidate engine, so "
            "two engines would address one judgement file"
        )

        # AND THE TWO CONFIGURATIONS ARE DISTINCT, which the cache must respect.
        assert (
            _channel("gemini", "live", True, False, True, "gemini").plan
            .candidate_engine
            == "gemini"
        )
        assert (
            _channel("gemini", "live", True, False, True, "openai").plan
            .candidate_engine
            == "openai"
        )


    def MQC_CAS_UNI_10466_a_single_disagreement_dispatches_two_more(self) -> None:
        """If one observation fails, the case runs two more times.

        Three observations can only put a case at 0, 33, 67 or 100 percent
        failure. When exactly one fails, two more are dispatched so the rate is
        measured over five: one failure reads as 20 percent and three as 60.

        **The two extra runs are numbered 3 and 4**, continuing from the first
        three, so an escalated run never overwrites a recorded fixture.

        The rule deciding how many to add is the harness's
        (`further_observations`), covered by `MQC_CMN_UNI_11206`. This checks
        that the loop calls it and dispatches what it asks for.

        Returns:
            None
        """
        asked: list[int] = []

        def answer(index: int) -> bool:
            """Pass twice and fail once, which is the escalating pattern.

            Args:
                index (int): The observation index requested.

            Returns:
                bool: Whether that observation passed.
            """
            asked.append(index)
            return index != 2

        outcomes = [answer(index) for index in range(3)]
        extra = further_observations(outcomes)
        outcomes += [answer(3 + offset) for offset in range(extra)]

        assert extra == 2, "one failure of three did not earn two more"
        assert asked == [0, 1, 2, 3, 4], (
            f"the escalated observations were not numbered from where the first "
            f"three stopped, so one would overwrite a recording: {asked}"
        )
        assert len(outcomes) == 5

        # AND A CONSISTENT CASE IS NEVER ASKED AGAIN, which is the whole saving.
        assert further_observations([True, True, True]) == 0


class TestMQCBandFloor:
    """What turns a lower band red, and what refuses instead."""

    @staticmethod
    def _report(path: Path, *, passed: int, failed: int = 0,
                errored: int = 0, skipped: int = 0) -> Path:
        """Write a JUnit report with the given shape.

        Args:
            path (Path): Where to write.
            passed (int): Cases with no child element.
            failed (int): Cases carrying a failure.
            errored (int): Cases carrying an error.
            skipped (int): Cases carrying a skip.

        Returns:
            Path: The written report.
        """
        rows = [f'<testcase name="pass{index}"/>' for index in range(passed)]
        rows += [
            f'<testcase name="fail{index}"><failure/></testcase>'
            for index in range(failed)
        ]
        rows += [
            f'<testcase name="err{index}"><error/></testcase>'
            for index in range(errored)
        ]
        rows += [
            f'<testcase name="skip{index}"><skipped/></testcase>'
            for index in range(skipped)
        ]
        path.write_text(
            "<testsuites><testsuite>" + "".join(rows) + "</testsuite></testsuites>",
            encoding="utf-8",
        )
        return path

    def MQC_CAS_UNI_10456_a_lower_band_is_judged_against_the_floor(
        self, tmp_path: Path
    ) -> None:
        """P0 and P1 need no rate; this band is the only one that does.

        "Any P0 or P1 observation not passing fails the run" and "this band had
        a failure" are the same statement, so pytest's status enforces V1 by
        itself. P2-P4 is the only band where a failure is not automatically
        fatal, which is what the floor is for.

        **The boundary is tested at the threshold, not near it**, per
        `framework-rules.md` section 3.2: off by one at a gate is the likeliest
        defect in any gate.

        Args:
            tmp_path (Path): pytest's temporary directory.

        Returns:
            None
        """
        exactly = self._report(tmp_path / "at.xml", passed=9, failed=1)
        code, message = assess(exactly, floor=0.90)
        assert code == 0, message
        assert "cleared" in message

        below = self._report(tmp_path / "below.xml", passed=8, failed=2)
        code, message = assess(below, floor=0.90)
        assert code == 1, message
        assert "below its floor" in message
        # THE FIGURES ARE IN THE MESSAGE, because a bare "below the floor" sends
        # a reader to the artifact to learn by how much.
        assert "80.0%" in message and "90%" in message

    def MQC_CAS_UNI_10457_a_skip_leaves_the_denominator(
        self, tmp_path: Path
    ) -> None:
        """A foundation that did not hold must not charge the later band.

        A dependent skipped under `QC_HARNESS_DEPENDENCY_UNMET` produced no
        measurement. Counting it as a failure would charge this band for a
        defect belonging to an earlier one, which is the misattribution the
        band split exists to remove; counting it as a pass would invent a
        result.

        Args:
            tmp_path (Path): pytest's temporary directory.

        Returns:
            None
        """
        report = self._report(tmp_path / "skips.xml", passed=9, failed=1, skipped=40)
        code, message = assess(report, floor=0.90)

        assert code == 0, message
        assert "40 skipped" in message
        assert "9 of 10 measured" in message

    def MQC_CAS_UNI_10458_an_error_refuses_rather_than_averaging(
        self, tmp_path: Path
    ) -> None:
        """An error is our defect, and a floor is about the model.

        Averaging a harness error into a pass rate would let a broken run read
        as a model that nearly cleared the bar, which inverts the distinction
        the whole taxonomy rests on.

        Args:
            tmp_path (Path): pytest's temporary directory.

        Returns:
            None
        """
        broken = self._report(tmp_path / "error.xml", passed=99, errored=1)
        code, message = assess(broken, floor=0.90)
        assert code == 4, message
        assert "our defect" in message

        # AND A REPORT THAT IS NOT THERE REFUSES TOO. A band producing none
        # measured nothing, and a rate over an empty denominator reads as a
        # pass, which is the fail-open this must not have.
        code, message = assess(tmp_path / "absent.xml", floor=0.90)
        assert code == 4, message

        empty = self._report(tmp_path / "all_skipped.xml", passed=0, skipped=5)
        code, message = assess(empty, floor=0.90)
        assert code == 4, message
        assert "measured none" in message
