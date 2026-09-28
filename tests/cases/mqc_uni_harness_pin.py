# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Which harness this case set runs against, and what it refuses to use.

Covers ``MQC_CAS_UNI_10406`` through ``10418``, inventoried in
``docs/design/consumer_ci.md`` section 4.

**Every negative here is a way for the gate to fail open**, and a gate that
fails open is indistinguishable from no gate at all until the day it matters.
They are written separately rather than as one case asserting "not green",
because a single such case would pass against an implementation that returned
``False`` unconditionally.

A failure here is our defect, so the module carries no priority marker, per the
harness ``framework-rules.md`` section 3.3.
"""

import ast
import csv
import re
from pathlib import Path
from typing import Any

import allure
import pytest

from ingestion.loaders import load_tasks_from_yaml
from cmn.branch_policy import BRANCH_KINDS, referent_problems
from tools import harness_pin
from tools.harness_pin import (
    Pairing,
    apply_target_strictness,
    assess_greenness,
    load_mapping,
    resolve_pairing,
)
from tools.harness_pin import main as harness_pin_main

pytestmark = pytest.mark.unit

# A HARNESS COMMIT, as the API spells one. The value is arbitrary and the
# width is not: the resolver truncates it for its messages.
_PINNED_SHA = "d793908f3325e109da63fc05e1ddd1f2329c3f0f"
_REQUIRED_WORKFLOW = "gate-on-change.yml"

_WORKFLOW = "gate-on-change.yml"
_SHA = "a" * 40
_OTHER_SHA = "b" * 40


def _run(
    sha: str = _SHA,
    workflow: str = _WORKFLOW,
    status: str = "completed",
    conclusion: str = "success",
    run_number: int = 1,
) -> dict[str, object]:
    """Build one workflow run as the GitHub API returns it.

    Args:
        sha (str): The commit the run executed on.
        workflow (str): The workflow filename.
        status (str): ``queued``, ``in_progress`` or ``completed``.
        conclusion (str): The concluded result.
        run_number (int): Which attempt this was.

    Returns:
        dict: The run record.
    """
    return {
        "head_sha": sha,
        "path": f".github/workflows/{workflow}",
        "status": status,
        "conclusion": conclusion,
        "run_number": run_number,
    }


@pytest.fixture(name="mapping")
def fixture_mapping() -> dict[str, object]:
    """Return the real mapping this repository ships.

    Returns:
        dict: The parsed mapping.
    """
    root = Path(__file__).resolve().parents[2]
    return load_mapping(root / "config" / "harness_pin.yaml")



def _running() -> list[dict[str, Any]]:
    """Return the API shape of a run that has not concluded.

    Returns:
        list[dict]: One in-progress run for the pinned commit.
    """
    return [
        {
            "head_sha": _PINNED_SHA,
            "path": f".github/workflows/{_REQUIRED_WORKFLOW}",
            "run_number": 1,
            "status": "in_progress",
            "conclusion": None,
        }
    ]


def _concluded(conclusion: str) -> list[dict[str, Any]]:
    """Return the API shape of a run that has finished.

    Args:
        conclusion (str): What it concluded.

    Returns:
        list[dict]: One completed run for the pinned commit.
    """
    return [
        {
            "head_sha": _PINNED_SHA,
            "path": f".github/workflows/{_REQUIRED_WORKFLOW}",
            "run_number": 1,
            "status": "completed",
            "conclusion": conclusion,
        }
    ]


def _drive(
    sequence: list[list[dict[str, Any]]], timeout: float = 600.0
) -> tuple[Any, int, float]:
    """Run the wait against scripted answers, spending no wall clock.

    **The clock and the sleep are injected**, so a case that exercises a ten
    minute timeout finishes instantly and asserts the interval rather than
    enduring it.

    Args:
        sequence (list): One list of runs per poll, the last repeated.
        timeout (float): The wait budget.

    Returns:
        tuple: The verdict, how many times the API was polled, and how long the
        wait believed it had spent.
    """
    remaining = list(sequence)
    polls = 0
    now = [0.0]

    def fetch(_repository: str, _commit: str, _token: Any) -> list[dict[str, Any]]:
        nonlocal polls
        polls += 1
        return remaining.pop(0) if len(remaining) > 1 else remaining[0]

    original = harness_pin.fetch_runs
    harness_pin.fetch_runs = fetch
    try:
        verdict = harness_pin.await_verdict(
            "apolskiy/AP-Harness-QC", _PINNED_SHA, None, _REQUIRED_WORKFLOW,
            harness_pin.WaitPolicy(
                timeout_sec=timeout, interval_sec=15.0,
                monotonic=lambda: now[0],
                delay=lambda seconds: now.__setitem__(0, now[0] + seconds),
            ),
        )
    finally:
        harness_pin.fetch_runs = original
    return verdict, polls, now[0]


@allure.epic("AP-Model-QC")
@allure.feature("Consumer CI")
class TestMQCHarnessPairing:
    """Which harness ref a branch of this repository declares."""

    @allure.story("Declared pairings")
    def MQC_CAS_UNI_10406_a_named_case_branch_resolves_to_its_declared_harness_ref(
        self, mapping: dict[str, object]
    ) -> None:
        """Stabilization on one side is verified against the other.

        Args:
            mapping (dict): The shipped mapping.

        Returns:
            None
        """
        assert resolve_pairing(mapping, "main").harness_ref == "main"

        # A DATED INTEGRATION BRANCH MATCHES ITS PATTERN, not the default. The
        # floor pairs it with main; a cycle pinning a specific harness branch
        # adds a literal entry above the pattern when it is cut.
        stabilizing = resolve_pairing(mapping, "stabilization-MQC-1234-09-24-2026")
        assert stabilizing.matched == "stabilization-*"
        assert stabilizing.harness_ref == "main"

    @allure.story("Declared pairings")
    def MQC_CAS_UNI_10407_a_glob_entry_matches_an_expansion_branch(
        self, mapping: dict[str, object]
    ) -> None:
        """The branch that needs a harness extension pairs with the branch carrying it.

        ``extend-`` is the case the whole mechanism exists for: a case that
        cannot be written until the harness grows a capability has nowhere to
        run except against the branch that has it.

        **The shipped entry is a floor, not that pairing.** Branches are dated
        now, so an extend branch names the harness branch carrying its
        capability in a literal entry added when it is cut. Forgetting pairs it
        with ``main``, where the missing capability fails loudly, rather than
        with a stale stabilization branch where it might appear to work.

        Args:
            mapping (dict): The shipped mapping.

        Returns:
            None
        """
        expanding = resolve_pairing(mapping, "expand-10428-09-24-2026")
        assert expanding.matched == "expand-*"
        assert expanding.harness_ref == "main"

        extending = resolve_pairing(mapping, "extend-MQC-1234-09-24-2026")
        assert extending.matched == "extend-*"
        assert extending.harness_ref == "main"

        # Debugging pairs with main and is always advisory, because
        # withholding the tool while the harness is red withholds it exactly
        # when it is needed.
        debugging = resolve_pairing(mapping, "debug-10428-09-24-2026")
        assert debugging.matched == "debug-*"
        assert debugging.require_green is False

    @allure.story("Declared pairings")
    def MQC_CAS_UNI_10408_an_unmatched_branch_takes_the_default_pairing(
        self, mapping: dict[str, object]
    ) -> None:
        """A branch outside the convention is tested, not rejected.

        Requiring an entry per branch would make the mapping the thing that
        stops a branch being tested.

        Args:
            mapping (dict): The shipped mapping.

        Returns:
            None
        """
        resolved = resolve_pairing(mapping, "some/other-name")

        assert resolved.matched == "default"
        assert resolved.harness_ref == "main"
        assert resolved.require_green is False

    @allure.story("Declared pairings")
    def MQC_CAS_UNI_10409_an_explicit_entry_wins_over_a_glob_listed_after_it(
        self,
    ) -> None:
        """First match wins in file order, so ordering is the whole rule.

        **The boundary is a literal that a later pattern would also match.** A
        glob placed above ``main`` would capture it, and the symptom would be
        the strict branch quietly becoming advisory.

        Returns:
            None
        """
        ordered = {
            "branches": [
                {"match": "main", "harness_ref": "main", "require_green": True},
                {"match": "*", "harness_ref": "stabilization", "require_green": False},
            ],
            "default": {"harness_ref": "main", "require_green": False},
        }

        resolved = resolve_pairing(ordered, "main")

        assert resolved.matched == "main"
        assert resolved.require_green is True

    @allure.story("Strictness")
    def MQC_CAS_UNI_10417_main_requires_green_and_a_stabilization_branch_does_not(
        self, mapping: dict[str, object]
    ) -> None:
        """One strictness cannot serve both branches.

        Refusing everywhere would block case stabilization precisely while the
        harness is being stabilized, which is when the pairing exists to be
        used. Refusing nowhere would let a red harness produce results on main.

        Args:
            mapping (dict): The shipped mapping.

        Returns:
            None
        """
        assert resolve_pairing(mapping, "main").require_green is True

        # DATED NAMES, because the undated ones resolved to the default rather
        # than to the entries this case is about, so it passed while
        # establishing nothing.
        lenient = (
            "stabilization-MQC-1234-09-24-2026",
            "extend-MQC-1234-09-24-2026",
            "expand-10428-09-24-2026",
            "debug-10428-09-24-2026",
        )
        for branch in lenient:
            pairing = resolve_pairing(mapping, branch)
            assert pairing.matched != "default", (
                f"{branch} fell through to the default, so its strictness is "
                f"not the one this mapping declares"
            )
            assert pairing.require_green is False


@allure.epic("AP-Model-QC")
@allure.feature("Consumer CI")
class TestMQCGreenness:
    """What establishes a harness commit, and what does not."""

    @allure.story("Green")
    def MQC_CAS_UNI_10410_a_successful_required_run_on_the_commit_is_green(
        self,
    ) -> None:
        """The one case that permits a gated run.

        Returns:
            None
        """
        verdict = assess_greenness([_run()], _WORKFLOW, _SHA)

        assert verdict.green is True
        assert verdict.conclusion == "success"

    @allure.story("Not green")
    def MQC_CAS_UNI_10411_a_failed_required_run_is_not_green(self) -> None:
        """The obvious case, and the only one most implementations get right.

        Returns:
            None
        """
        verdict = assess_greenness([_run(conclusion="failure")], _WORKFLOW, _SHA)

        assert verdict.green is False
        assert verdict.conclusion == "failure"
        assert "QC_HARNESS_UPSTREAM_UNVERIFIED" in verdict.reason

    @allure.story("Not green")
    def MQC_CAS_UNI_10412_no_run_at_all_for_the_commit_is_not_green(self) -> None:
        """A commit with no run is the normal state of a fresh push.

        **Treating absence as a pass is how an unverified harness becomes the
        instrument**, and it is the same shape as a mistyped selector matching
        zero tests and exiting clean.

        Returns:
            None
        """
        verdict = assess_greenness([], _WORKFLOW, _SHA)

        assert verdict.green is False
        # Absent is distinct from failed. Both are not-green, and only one of
        # them means somebody should look at the harness.
        assert verdict.conclusion is None
        assert "no gate-on-change.yml run exists" in verdict.reason

    @allure.story("Not green")
    def MQC_CAS_UNI_10413_a_run_still_in_progress_is_not_green(self) -> None:
        """A run that has not concluded has established nothing yet.

        Returns:
            None
        """
        verdict = assess_greenness(
            [_run(status="in_progress", conclusion=None)], _WORKFLOW, _SHA
        )

        assert verdict.green is False
        assert verdict.conclusion is None
        assert "in_progress" in verdict.reason

    @allure.story("Not green")
    def MQC_CAS_UNI_10414_a_success_on_a_different_commit_does_not_make_this_one_green(
        self,
    ) -> None:
        """Green is a property of a commit, never of a branch.

        The branch moves. A run that passed on its previous head says nothing
        about the head being installed now, and accepting it is exactly the
        window the resolve-then-install ordering exists to close.

        Returns:
            None
        """
        verdict = assess_greenness([_run(sha=_OTHER_SHA)], _WORKFLOW, _SHA)

        assert verdict.green is False
        assert verdict.conclusion is None

    @allure.story("Not green")
    def MQC_CAS_UNI_10415_a_success_from_an_unrequired_workflow_is_not_green(
        self,
    ) -> None:
        """Naming one workflow keeps green single-valued.

        A rule accepting any passing workflow would be satisfied by a
        documentation lint, which establishes nothing about the harness.

        Returns:
            None
        """
        verdict = assess_greenness(
            [_run(workflow="probe-model-version-nightly.yml")], _WORKFLOW, _SHA
        )

        assert verdict.green is False
        assert verdict.conclusion is None

    @allure.story("Green")
    def MQC_CAS_UNI_10416_the_latest_attempt_decides_when_a_run_was_retried(
        self,
    ) -> None:
        """An earlier failure does not veto a later success, or the reverse.

        **The boundary is that both directions have to hold.** An
        implementation taking the first matching run passes the failure case
        and silently rejects every re-run that fixed something.

        Returns:
            None
        """
        recovered = assess_greenness(
            [_run(conclusion="failure", run_number=1), _run(run_number=2)],
            _WORKFLOW,
            _SHA,
        )
        regressed = assess_greenness(
            [_run(run_number=1), _run(conclusion="failure", run_number=2)],
            _WORKFLOW,
            _SHA,
        )

        assert recovered.green is True
        assert regressed.green is False


@allure.epic("AP-Model-QC")
@allure.feature("Consumer CI")
class TestMQCUnresolvablePairing:
    """A harness branch that does not exist is not a finding about a model."""

    @allure.story("Refusal")
    def MQC_CAS_UNI_10422_an_unresolvable_paired_ref_refuses_rather_than_crashing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Exit 1 is the one code this must never produce.

        Exit 1 means a suite measured something and it failed, which CI reads
        as the model underperforming. Letting an unhandled exception pick the
        code hands the attribution inversion the design guards against to a
        stack trace.

        **It refuses on an advisory branch too.** Strictness governs whether an
        unverified harness may be used, and cannot govern whether a nonexistent
        one may be: there is no commit to install and nothing to fall back to.

        Args:
            monkeypatch (pytest.MonkeyPatch): Fixture for patching the lookup.
            tmp_path (Path): pytest's temporary directory.

        Returns:
            None
        """
        mapping = tmp_path / "harness_pin.yaml"
        mapping.write_text(
            "\n".join(
                [
                    "repository: owner/harness",
                    "required_workflow: gate-on-change.yml",
                    "branches:",
                    "  - match: stabilization",
                    "    harness_ref: stabilization",
                    "    require_green: false",
                    "default:",
                    "  harness_ref: main",
                    "  require_green: false",
                ]
            ),
            encoding="utf-8",
        )

        def _absent(repository: str, ref: str) -> str:
            raise RuntimeError(
                f"QC_HARNESS_DEPENDENCY_UNMET: {repository} has no ref named {ref}"
            )

        monkeypatch.setattr("tools.harness_pin.head_commit", _absent)
        monkeypatch.delenv("GITHUB_OUTPUT", raising=False)

        code = harness_pin_main(
            ["--case-branch", "stabilization", "--mapping", str(mapping)]
        )

        # 4, never 1. A refusal says no verdict was computable; a red suite says
        # one was computed and failed.
        assert code == 4


@allure.epic("AP-Model-QC")
@allure.feature("Consumer CI")
class TestMQCResolverIndependence:
    """The check cannot come from the thing it checks."""

    @allure.story("Independence")
    def MQC_CAS_UNI_10418_the_module_imports_nothing_from_the_harness(self) -> None:
        """A harness import here is circular twice over.

        It runs **before** the harness is installed, so the import is not
        available; and a check fetched from the harness would be asking an
        unverified ref to vouch for itself.

        **A source check rather than a behavioural one**, deliberately: the
        defect it guards works perfectly on a developer machine where the
        harness is already installed, and fails only in CI at the one moment
        the gate is supposed to run.

        Returns:
            None
        """
        root = Path(__file__).resolve().parents[2]
        source = (root / "tools" / "harness_pin.py").read_text(encoding="utf-8")
        forbidden = {"cmn", "ingestion", "execution", "evaluation"}
        reached: list[str] = []

        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                reached.extend(
                    alias.name
                    for alias in node.names
                    if alias.name.split(".")[0] in forbidden
                )
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module.split(".")[0] in forbidden:
                    reached.append(node.module)

        assert not reached, (
            "the resolver must run before the harness is installed, and reached "
            f"{', '.join(reached)}"
        )

        # The dataclass is ours, not borrowed. Asserted so the check cannot be
        # satisfied by a module that imports nothing because it does nothing.
        assert Pairing(harness_ref="main", require_green=True, matched="main")


def _root() -> Path:
    """Return this repository's root.

    Returns:
        Path: The directory holding ``pyproject.toml``.
    """
    return Path(__file__).resolve().parents[2]


def _inventoried_case_ids() -> frozenset[str]:
    """Return every case identifier this repository inventories.

    Returns:
        frozenset[str]: The five-digit identifiers named by collected case
        callables. **Read from the tests rather than from a design table**,
        because a referent points at a case that exists, and the inventory
        tables are already checked against the tests elsewhere.
    """
    found: set[str] = set()
    for source in (_root() / "tests").rglob("mqc_*.py"):
        text = source.read_text(encoding="utf-8")
        found.update(re.findall(r"def MQC_[A-Z]+_[A-Z]+_(\d{5})_", text))
    return frozenset(found)


@allure.epic("AP-Model-QC")
@allure.feature("Consumer CI")
class TestMQCBranchPolicyHere:
    """What the branch policy means on the side that owns the cases.

    The grammar, the staleness bands and the merge route are one
    implementation in ``cmn.branch_policy``, checked by ``MQC_CMN_UNI_11144``
    through ``11148``. These two are the parts that depend on this repository,
    designed in ``docs/design/consumer_ci.md`` section 4.3.
    """

    @allure.story("Referents resolve here")
    def MQC_CAS_UNI_10442_a_case_referent_naming_no_inventoried_case_is_reported(
        self,
    ) -> None:
        """One rule over two inventories, not two rules.

        A branch referent naming a case identifier is checked for existence,
        and **the inventory it resolves against is this repository's**. The
        harness checks its own identifiers against its own, through the same
        function.

        Returns:
            None
        """
        known = _inventoried_case_ids()
        assert known, (
            "no case identifiers were found, so this check would pass for any "
            "referent and establish nothing"
        )

        sample = sorted(known)[0]
        assert not referent_problems(f"expand-09-24-2026-{sample}", known)

        # A five-digit identifier outside the CAS block cannot be a case here.
        assert referent_problems("expand-99999-09-24-2026", known)

        # A harness identifier is not inventoried in this repository, which is
        # the boundary this case exists to hold: the two blocks are separate
        # and a branch here names a case here.
        assert referent_problems("extend-11144-09-24-2026", known)

    @allure.story("The pairing covers every kind")
    def MQC_CAS_UNI_10443_a_pairing_not_covering_a_dated_branch_is_reported(
        self,
    ) -> None:
        """A kind falling through to the default is configured by accident.

        The default exists so an unconventional branch still runs, not so a
        registered kind can quietly take a pairing nobody chose. **A
        stabilization branch matching no entry would run against ``main``
        while looking configured**, and the artifact would say so nowhere.

        Returns:
            None
        """
        mapping = load_mapping(_root() / "config" / "harness_pin.yaml")
        declared = {
            str(entry.get("match", ""))
            for entry in (mapping.get("branches") or [])
        }

        for kind in sorted(BRANCH_KINDS):
            pattern = f"{kind}-*"
            assert pattern in declared, (
                f"no entry matches {pattern}, so a {kind} branch takes the "
                f"default pairing and nothing records that it did"
            )

        # Every registered kind resolves to a named entry rather than the
        # default, checked through the resolver rather than by reading the file
        # twice.
        for kind in sorted(BRANCH_KINDS):
            pairing = resolve_pairing(mapping, f"{kind}-10428-09-24-2026")
            assert pairing.matched == f"{kind}-*", (
                f"a dated {kind} branch matched {pairing.matched!r}"
            )

        # main keeps its literal entry and stays the only strict one.
        assert resolve_pairing(mapping, "main").require_green is True


@allure.epic("AP-Model-QC")
@allure.feature("Consumer CI")
class TestMQCTargetStrictness:
    """The destination sets the bar it will accept.

    Designed in ``docs/design/consumer_ci.md`` section 4.4.
    """

    @allure.story("Strictness")
    def MQC_CAS_UNI_10444_a_pull_request_taking_its_source_strictness_is_reported(
        self, mapping: dict[str, object]
    ) -> None:
        """Code could land on main never measured with a green harness.

        The gate resolved the pairing from the head branch alone, so a pull
        request from a stabilization branch into ``main`` took the advisory
        entry. It could run ungated, yield no verdict, and merge.

        **Stabilization conforms to main, not the other way around**, which is
        what makes ``main`` a branch anybody can roll back to.

        Args:
            mapping (dict): The shipped mapping.

        Returns:
            None
        """
        source = "stabilization-MQC-1234-09-24-2026"
        head = resolve_pairing(mapping, source)
        assert head.require_green is False, (
            "the source entry is advisory, which is the premise of this case"
        )

        # INTO MAIN, the target's strictness applies.
        merging = apply_target_strictness(head, mapping, "main")
        assert merging.require_green is True, (
            "a pull request into main took its source strictness, so work "
            "could land on main never measured with an established instrument"
        )

        # THE HARNESS REF IS UNCHANGED. Which harness this runs against is a
        # property of the work; only the bar comes from the destination.
        #
        # ASSERTED AGAINST A MAPPING WHERE THE TWO ENDS DIFFER. In the shipped
        # mapping every floor is `main`, so comparing against the head's ref
        # would pass even if the ref followed the target, which is how this
        # assertion was first written and what injecting that defect exposed.
        diverging = {
            "branches": [
                {"match": "main", "harness_ref": "main", "require_green": True},
                {
                    "match": "extend-*",
                    "harness_ref": "harness-capability-branch",
                    "require_green": False,
                },
            ],
            "default": {"harness_ref": "main", "require_green": False},
        }
        extending = resolve_pairing(diverging, "extend-MQC-1234-09-24-2026")
        assert extending.harness_ref == "harness-capability-branch"

        raised = apply_target_strictness(extending, diverging, "main")
        assert raised.require_green is True, "the target's bar was not applied"
        assert raised.harness_ref == "harness-capability-branch", (
            "the harness ref followed the target, so a branch needing a "
            "capability would run against a harness that lacks it"
        )

        # INTO AN ADVISORY TARGET, nothing is raised.
        onto_stabilization = apply_target_strictness(
            resolve_pairing(mapping, "expand-10428-09-24-2026"),
            mapping,
            source,
        )
        assert onto_stabilization.require_green is False

        # A PUSH HAS NO OTHER END, so it is unchanged.
        assert apply_target_strictness(head, mapping, "") is head

        # NEVER LOOSER. A strict head into an advisory target stays strict,
        # which is the property that stops the rule being routed around.
        strict_head = resolve_pairing(mapping, "main")
        assert strict_head.require_green is True
        relaxed = apply_target_strictness(strict_head, mapping, source)
        assert relaxed.require_green is True


    @allure.story("Plan and matrix agree")

    def MQC_CAS_UNI_10451_a_pending_harness_gate_is_waited_for_not_refused(
        self,
    ) -> None:
        """Four paired pushes in a row produced a red run that meant nothing.

        The consumer gate fires on push and the harness gate takes minutes, so
        the resolver met an `in_progress` run every time and refused. Each was
        cleared by re-running the identical job by hand, which is toil carrying
        no information: the answer was always going to arrive.

        **Section 3.2 is not weakened.** "Absence of a result is not a pass"
        refuses to read an unknown as a success, and waiting is the opposite of
        assuming: nothing concludes until the upstream gate concludes it.

        **Four outcomes, and only one of them waits.** A red conclusion is a
        decision and is refused at once. A commit with no run at all is refused
        at once too, because no amount of waiting grows one. A wait that runs out
        refuses, because a gate that has not finished has established nothing.

        Returns:
            None
        """
        for name, sequence, expect_green, expect_waited in (
            ("pending then green", [_running()] * 3 + [_concluded("success")], True, True),
            ("pending then red", [_running(), _concluded("failure")], False, True),
            ("red at once", [_concluded("failure")], False, False),
            ("no run at all", [[]], False, False),
        ):
            verdict, polls, waited = _drive(sequence)
            assert verdict.green is expect_green, f"{name}: green was {verdict.green}"
            assert (waited > 0) is expect_waited, (
                f"{name}: waited {waited}s, which is the wrong side of zero"
            )
            assert polls >= 1

        # A GATE THAT NEVER FINISHES IS STILL REFUSED, and the wait is bounded so
        # a wedged upstream run cannot hold a consumer job indefinitely.
        stuck, _, waited = _drive([_running()], timeout=60.0)
        assert stuck.green is False
        assert waited == 60.0
        assert "has not concluded" in stuck.reason

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

    def MQC_CAS_UNI_10450_a_readme_figure_disagreeing_with_the_repository_is_reported(
        self,
    ) -> None:
        """Every figure on the front page had drifted, and one was false.

        The README claimed 66 graded cases against 69, 67 requirements against
        71, 47 preconditions against 49, and six corpora against seven. It also
        said graded cases were **"designed, not yet written"** when all 69 were
        written. **That last one is the reason this check exists**: a stale
        number misleads a reader, and a stale claim misleads them about whether
        the work exists at all.

        **Nothing checked the README**, here or in the harness, until
        `MQC_CMN_UNI_11180` was written the same day for the same reason.

        **It recomputes rather than storing the numbers again**, because a
        second copy is what drifted in the first place.

        Returns:
            None
        """
        root = _root()
        readme = (root / "README.md").read_text(encoding="utf-8")
        wrong: list[str] = []

        def compare(label: str, pattern: str, actual: int) -> None:
            """Record a disagreement between a stated figure and a real one.

            Args:
                label (str): What the figure counts, for the failure message.
                pattern (str): A regex whose first group is the stated number.
                actual (int): What the repository actually contains.

            Returns:
                None
            """
            found = re.search(pattern, readme)
            if found is None:
                wrong.append(f"the README states no {label}")
            elif int(found.group(1)) != actual:
                wrong.append(f"{label}: README says {found.group(1)}, actual is {actual}")

        inventoried = 0
        for document in sorted((root / "docs").rglob("*.md")):
            stated = re.search(
                r"^\*\*Inventory:\s*(\d+)\s+cases",
                document.read_text(encoding="utf-8"),
                re.M,
            )
            if stated is not None:
                inventoried += int(stated.group(1))
        compare("preconditions", r"\*\*(\d+) cases, all passing\*\*", inventoried)

        with (root / "docs" / "testing" / "rtm_model.csv").open(
            encoding="utf-8-sig", newline=""
        ) as handle:
            compare("requirements", r"\| (\d+) requirements, traced \|",
                    len(list(csv.DictReader(handle))))

        graded = 0
        for source in sorted((root / "tests" / "cases").glob("*.py")):
            if source.stem.startswith("mqc_uni_") or source.stem == "graded_support":
                continue
            tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
            graded += sum(
                1
                for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name.startswith("MQC_")
            )
        compare("graded cases", r"\*\*(\d+) written\*\*", graded)

        corpora = sorted((root / "data" / "tasks").glob("*.yaml"))
        compare("corpora", r"\*\*(\d+) corpora", len(corpora))
        compare(
            "tasks",
            r"\*\*\d+ corpora, (\d+) tasks\*\*",
            sum(len(load_tasks_from_yaml(source)) for source in corpora),
        )

        assert not wrong, (
            f"{len(wrong)} README figure(s) disagree with the repository they "
            f"describe: {'; '.join(wrong)}"
        )
