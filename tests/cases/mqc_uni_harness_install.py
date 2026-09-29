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

from tests.cases.graded_support import _channel, engine_roster

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
