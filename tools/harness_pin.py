# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Resolve which harness to run against, and refuse an unverified one.

Specified by ``docs/design/consumer_ci.md``.

**This module imports nothing from the harness, and that is load-bearing.** It
runs *before* the harness is installed, so a harness import is not available to
it; and a check fetched from the harness would be asking an unverified ref to
vouch for itself, which is circular as an argument and not only as a
dependency. PyYAML breaks neither: it is a general-purpose parser installed
from an index rather than anything this project or the harness controls.

**The decision is pure and the fetch is thin.** :func:`assess_greenness` is a
function of the API payload, the workflow filename and the commit, on the same
reasoning that makes the harness verdict a pure function of observations: it is
the part with rules in it, so it is the part that gets tested.
:func:`head_commit` and :func:`fetch_runs` carry no policy.

**Absence of a result is never a pass.** A commit with no run is the normal
state of a branch pushed seconds ago, and treating it as green because nothing
failed is how an unverified harness becomes the instrument.
"""

import argparse
import fnmatch
import json
import logging
import os
import time
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Final, Optional

import yaml

logger = logging.getLogger(__name__)

_DEFAULT_MAPPING = Path("config/harness_pin.yaml")
_API_ROOT = "https://api.github.com"
_TAXONOMY_CODE = "QC_HARNESS_UPSTREAM_UNVERIFIED"
_UNMET_CODE = "QC_HARNESS_DEPENDENCY_UNMET"

# cmn_verdict_and_cli.md section 7.3. Named here rather than imported, because
# importing it would be the harness import this module exists without.
_EXIT_REFUSED = 4

# Only a concluded success establishes anything. Every other value, including
# the absence of a run, leaves the commit unestablished.
_SUCCESS = "success"
_COMPLETED = "completed"


@dataclass(frozen=True)
class Pairing:
    """Which harness ref a branch of this repository runs against.

    Attributes:
        harness_ref (str): The harness branch, tag or commit to use.
        require_green (bool): Whether a non-green ref refuses the run. **True on
            ``main`` only**: refusing everywhere would block case stabilization
            precisely while the harness is being stabilized.
        matched (str): The mapping entry that matched, or ``default``. Recorded
            so a surprising pairing is diagnosed by reading one line.
    """

    harness_ref: str
    require_green: bool
    matched: str


@dataclass(frozen=True)
class Greenness:
    """Whether a specific harness commit has been established.

    Attributes:
        green (bool): Whether the required workflow concluded success on it.
        reason (str): Why, in a form a run summary can print directly.
        conclusion (Optional[str]): The raw conclusion, or ``None`` when no run
            exists. **Absent is distinct from failed** and both are equally
            not-green, but only one of them means somebody should look at the
            harness.
    """

    green: bool
    reason: str
    conclusion: Optional[str] = None


def load_mapping(path: Path) -> dict[str, Any]:
    """Load the branch-to-harness mapping.

    Args:
        path (Path): The mapping file.

    Returns:
        dict: The parsed mapping.

    Raises:
        FileNotFoundError: When the mapping is absent. **Unlike the harness's
            consumer registry, an absent mapping here is an error**: a case
            repository with no declared pairing would silently install whatever
            ``pyproject.toml`` last said, which is the defect this file exists
            to remove.
    """
    if not path.is_file():
        raise FileNotFoundError(
            f"{_TAXONOMY_CODE}: no harness pin mapping at {path}, so nothing "
            f"states which harness this branch runs against"
        )
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


# The phrase `assess_greenness` uses for a run that has not concluded. Matched
# rather than re-derived, so the two cannot disagree about what pending means.
_STILL_RUNNING: Final[str] = "so nothing has been established yet"

# The phrase it uses for a commit no run has been recorded against yet. A push
# to both repositories lands seconds apart and the consumer resolves first, so
# for a few seconds the run is not missing but unregistered.
_NOT_YET_REGISTERED: Final[str] = "no run is recorded against it yet"


@dataclass(frozen=True)
class WaitPolicy:
    """How long to wait for a pending gate, and by whose clock.

    **One argument rather than four.** The budget, the interval and the two
    injected time functions are a single idea: the terms on which waiting
    happens. Passing them separately put `await_verdict` at eight arguments,
    which is the signature asking to be questioned rather than the limit asking
    to be raised.

    Attributes:
        timeout_sec (float): How long to wait before refusing. The harness gate
            finishes in two to three minutes, so ten absorbs a queued runner
            without letting a wedged run hold a consumer job all day.
        interval_sec (float): How long to pause between checks.
        monotonic (Callable): The clock, injected so a case can exercise a ten
            minute timeout without spending it.
        delay (Callable): The sleep, injected for the same reason.
    """

    timeout_sec: float = 600.0
    interval_sec: float = 15.0
    monotonic: Callable[[], float] = time.monotonic
    delay: Callable[[float], None] = time.sleep

def resolve_pairing(mapping: dict[str, Any], case_branch: str) -> Pairing:
    """Return the harness ref paired with a branch of this repository.

    **First match wins, in file order**, so literal names listed before patterns
    cannot be captured by a glob placed above them.

    Args:
        mapping (dict): The parsed mapping.
        case_branch (str): The branch of this repository being built.

    Returns:
        Pairing: The matched entry, or the declared default. **An unmatched
        branch takes the default rather than failing**: requiring an entry per
        branch would make the mapping the thing that stops a branch being
        tested.
    """
    for entry in mapping.get("branches") or []:
        pattern = str(entry.get("match", ""))
        if not pattern:
            continue
        if case_branch == pattern or fnmatch.fnmatchcase(case_branch, pattern):
            return Pairing(
                harness_ref=str(entry.get("harness_ref", "main")),
                require_green=bool(entry.get("require_green", False)),
                matched=pattern,
            )

    fallback = mapping.get("default") or {}
    return Pairing(
        harness_ref=str(fallback.get("harness_ref", "main")),
        require_green=bool(fallback.get("require_green", False)),
        matched="default",
    )


def assess_greenness(
    runs: list[dict[str, Any]], required_workflow: str, head_sha: str
) -> Greenness:
    """Decide whether a harness commit has a passing required run.

    **The latest attempt decides.** A workflow can be re-run, so the highest run
    number for the commit is authoritative and an earlier failed attempt does
    not veto a later success.

    Args:
        runs (list): Workflow runs as the GitHub API returns them.
        required_workflow (str): The workflow filename that defines green.
        head_sha (str): The commit under question.

    Returns:
        Greenness: The verdict. **Not green** when no run exists, when the run
        has not concluded, when it concluded anything but success, when it ran
        on a different commit, or when it was a different workflow. Each is a
        separate way for this gate to fail open, which is why each is excluded
        rather than defaulted.
    """
    matching = [
        run
        for run in runs
        if str(run.get("head_sha", "")) == head_sha
        and str(run.get("path", "")).endswith(required_workflow)
    ]
    if not matching:
        return Greenness(
            green=False,
            reason=(
                f"{_TAXONOMY_CODE}: no {required_workflow} run exists for commit "
                f"{head_sha[:12]}, {_NOT_YET_REGISTERED}. A commit with no run "
                f"is not a commit that passed"
            ),
        )

    latest = max(matching, key=lambda run: int(run.get("run_number") or 0))
    status = str(latest.get("status", ""))
    conclusion = latest.get("conclusion")

    if status != _COMPLETED:
        return Greenness(
            green=False,
            reason=(
                f"{_TAXONOMY_CODE}: {required_workflow} on {head_sha[:12]} is "
                f"{status}, so nothing has been established yet"
            ),
            conclusion=None,
        )

    if conclusion != _SUCCESS:
        return Greenness(
            green=False,
            reason=(
                f"{_TAXONOMY_CODE}: {required_workflow} on {head_sha[:12]} "
                f"concluded {conclusion}"
            ),
            conclusion=str(conclusion),
        )

    return Greenness(
        green=True,
        reason=f"{required_workflow} passed on {head_sha[:12]}",
        conclusion=_SUCCESS,
    )


def head_commit(repository: str, ref: str) -> str:
    """Resolve a harness ref to the commit it currently names.

    **The commit is what gets checked and what gets installed.** Checking the
    branch and then installing the branch leaves a window in which the two are
    not the same commit.

    Args:
        repository (str): Owner and repository.
        ref (str): A branch or tag name.

    Returns:
        str: The full commit hash.

    Raises:
        RuntimeError: When the ref names nothing, which on a paired branch
            usually means the harness does not carry it yet.
    """
    url = f"https://github.com/{repository}.git"
    completed = subprocess.run(
        ["git", "ls-remote", url, f"refs/heads/{ref}", f"refs/tags/{ref}"],
        capture_output=True, text=True, check=False, shell=False,
    )
    for line in completed.stdout.splitlines():
        parts = line.split()
        if len(parts) == 2:
            return parts[0]
    # UNMET, NOT UNVERIFIED. Unmet means unavailable and unverified means
    # available but not established, and the operator response differs: create
    # the paired branch on the harness, or change this branch's entry.
    raise RuntimeError(
        f"{_UNMET_CODE}: {repository} has no ref named {ref}, so the pairing "
        f"this branch declares cannot be resolved. A case branch may legitimately "
        f"name a harness branch that has not been created yet"
    )



def await_verdict(
    repository: str,
    commit: str,
    token: Optional[str],
    required_workflow: str,
    policy: Optional[WaitPolicy] = None,
) -> Greenness:
    """Return the harness verdict, waiting while it is still being decided.

    **An in-progress run is a pending decision, not a missing one**, and the two
    deserve different treatment. Refusing on a pending decision made every paired
    push produce a red consumer run that a manual re-run then cleared, which is
    toil carrying no information: the answer was always going to arrive.

    **A run not yet registered is pending too**, which this first missed. The
    consumer resolved seven seconds after the harness was pushed, before GitHub
    had recorded a run at all, and refused a commit whose gate started moments
    later and passed. Nothing distinguishes that from a commit that will never
    have a run except how long you look, so it is waited on and the timeout
    still refuses.

    **Section 3.2 is not weakened by this.** "Absence of a result is not a pass"
    refuses to read an unknown as a success. Waiting is the opposite of assuming:
    nothing is concluded until the upstream gate concludes it, a red stays red,
    and a run that never finishes is still refused when the wait runs out.

    Args:
        repository (str): The harness repository.
        commit (str): The harness commit under question.
        token (Optional[str]): The API token, if any.
        required_workflow (str): The workflow filename that defines green.
        policy (Optional[WaitPolicy]): The terms of the wait. **Defaulted rather
            than required**, so a caller that has no opinion states none.

    Returns:
        Greenness: The verdict once the run concludes, or the last unconcluded
        verdict when the wait runs out. **The timeout refuses**, because a gate
        that has not finished has still established nothing.
    """
    terms = policy or WaitPolicy()
    started = terms.monotonic()
    verdict = assess_greenness(fetch_runs(repository, commit, token), required_workflow, commit)

    while verdict.conclusion is None and not verdict.green:
        # AN UNCONCLUDED RUN AND AN UNREGISTERED ONE ARE BOTH PENDING. A run
        # that concluded red carries its conclusion and waiting cannot change
        # it, so only that returns immediately.
        #
        # THIS ONCE EXCLUDED ABSENCE, on the reasoning that a commit with no run
        # "is not going to grow one". A paired push disproved it: the consumer
        # resolved seven seconds after the harness was pushed, GitHub had not
        # registered the run yet, and the gate refused a commit whose run
        # started moments later and passed. Absence a second after a push and
        # absence a minute later are the same API response.
        #
        # THE SAFETY PROPERTY IS UNCHANGED. Nothing is accepted without a
        # concluded green run; the wait only postpones concluding that there is
        # none, and a timeout still refuses.
        if _STILL_RUNNING not in verdict.reason and (
            _NOT_YET_REGISTERED not in verdict.reason
        ):
            return verdict
        if terms.monotonic() - started >= terms.timeout_sec:
            return Greenness(
                green=False,
                reason=(
                    f"{verdict.reason}. Waited {terms.timeout_sec:.0f}s and it has not "
                    f"concluded, so nothing is established"
                ),
            )
        terms.delay(terms.interval_sec)
        verdict = assess_greenness(
            fetch_runs(repository, commit, token), required_workflow, commit
        )

    return verdict

def fetch_runs(
    repository: str, head_sha: str, token: Optional[str] = None
) -> list[dict[str, Any]]:
    """Fetch the workflow runs recorded against a commit.

    Args:
        repository (str): Owner and repository.
        head_sha (str): The commit to query.
        token (Optional[str]): A GitHub token. Unauthenticated calls are limited
            to 60 an hour per address, which a busy branch exceeds.

    Returns:
        list[dict]: The runs, or an **empty list** when the query fails. A
        rate-limited or unreachable API establishes nothing, so it lands in the
        same bucket as no run at all. Returning an empty list rather than
        raising keeps the gate failing closed: an error that fell back to
        proceeding would fail open under exactly the load that would hide it.
    """
    url = f"{_API_ROOT}/repos/{repository}/actions/runs?head_sha={head_sha}&per_page=100"
    request = urllib.request.Request(url)  # noqa: S310
    request.add_header("Accept", "application/vnd.github+json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        logger.warning("Could not query workflow runs: %s", error)
        return []
    return list(payload.get("workflow_runs") or [])


def _emit(outputs: dict[str, str]) -> None:
    """Write resolved values where a workflow step can read them.

    Args:
        outputs (dict): Key to value.

    Returns:
        None
    """
    destination = os.environ.get("GITHUB_OUTPUT")
    lines = [f"{key}={value}" for key, value in outputs.items()]
    if destination:
        with open(destination, "a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    for line in lines:
        print(line)



def apply_target_strictness(
    pairing: Pairing, mapping: dict, base_branch: str
) -> Pairing:
    """Return the pairing a pull request runs under.

    **The ref and the strictness come from different ends**, because they
    answer different questions. Which harness this runs against is a property
    of the work, so it comes from the head branch. How strict the verdict is
    belongs to the destination, which sets the bar it will accept.

    **The result is the stricter of the two, never the looser.** There is no
    arrangement in which a pull request is more permissive than either end
    alone, which is the property that stops the rule being routed around by
    choosing a lenient source.

    Args:
        pairing (Pairing): What the head branch resolved.
        mapping (dict): The parsed mapping.
        base_branch (str): The branch being merged into, empty for a push.

    Returns:
        Pairing: The head pairing, with strictness raised to the target's when
        the target is stricter. A push supplies no base and is unchanged,
        because there is no other end.
    """
    if not base_branch:
        return pairing
    target = resolve_pairing(mapping, base_branch)
    if not target.require_green or pairing.require_green:
        return pairing
    return Pairing(
        harness_ref=pairing.harness_ref,
        require_green=True,
        matched=f"{pairing.matched} into {target.matched}",
    )


def main(argv: Optional[list[str]] = None) -> int:
    """Resolve the pairing, assess it, and refuse when required.

    Args:
        argv (Optional[list]): Command line arguments.

    Returns:
        int: ``0`` when the run may proceed, ``4`` when it is refused. **Exit 4
        is not exit 1**: a refusal says no verdict was computable, and a red
        suite says one was computed and failed. Collapsing them would let CI
        read "the harness was never verified" as "the model underperformed".
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-branch", required=True)
    # THE BRANCH BEING MERGED INTO, empty for a push. Merging into main
    # means main's rules apply, whatever branch the work came from.
    parser.add_argument("--base-branch", default="")
    parser.add_argument("--mapping", type=Path, default=_DEFAULT_MAPPING)
    arguments = parser.parse_args(argv)

    mapping = load_mapping(arguments.mapping)
    repository = str(mapping.get("repository", ""))
    required_workflow = str(mapping.get("required_workflow", "gate-on-change.yml"))

    pairing = resolve_pairing(mapping, arguments.case_branch)
    pairing = apply_target_strictness(pairing, mapping, arguments.base_branch)

    # A REF THAT DOES NOT RESOLVE REFUSES ON ANY BRANCH, and letting this raise
    # would exit 1, which means a suite measured something and it failed. A
    # harness branch that does not exist is the opposite of a finding about a
    # model, and an unhandled exception must not pick that code.
    #
    # Strictness does not apply here. It governs whether an UNVERIFIED harness
    # may be used, and cannot govern whether a NONEXISTENT one may be: there is
    # no commit to install and nothing to fall back to.
    try:
        commit = head_commit(repository, pairing.harness_ref)
    except RuntimeError as error:
        _emit(
            {
                "harness_repository": repository,
                "harness_ref": pairing.harness_ref,
                "harness_sha": "",
                "matched_entry": pairing.matched,
                "require_green": str(pairing.require_green).lower(),
                "green": "false",
                "gated": "false",
                "reason": str(error),
            }
        )
        print(f"::error::{error}", file=sys.stderr)
        return _EXIT_REFUSED

    verdict = await_verdict(
        repository, commit, os.environ.get("GITHUB_TOKEN"), required_workflow
    )

    _emit(
        {
            "harness_repository": repository,
            "harness_ref": pairing.harness_ref,
            "harness_sha": commit,
            "matched_entry": pairing.matched,
            "require_green": str(pairing.require_green).lower(),
            "green": str(verdict.green).lower(),
            "gated": str(verdict.green).lower(),
            "reason": verdict.reason,
        }
    )

    if verdict.green:
        return 0

    if pairing.require_green:
        print(f"::error::{verdict.reason}", file=sys.stderr)
        return _EXIT_REFUSED

    # Advisory. The run proceeds and yields no verdict, which is the same
    # object a manual selection produces: the instrument was not established,
    # so what it measures cannot be counted.
    print(f"::warning::{verdict.reason}. This run is UNGATED and yields no verdict")
    return 0


if __name__ == "__main__":
    sys.exit(main())
