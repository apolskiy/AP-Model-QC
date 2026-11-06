# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""The measuring half of the findings recorder: what a run measured.

Created: 2026-11-01
Last updated: 2026-11-06

This file contains ``results_directory``, which empties the directory a run
writes its Allure results to, ``observe``, which runs the graded suite for one
engine and returns the JUnit XML and Allure results it wrote, ``parse_passed``,
``parse_warnings`` and ``parse_failures``, which read what that run measured out
of the XML,
``expected_by_case``, which reads what each case was asserting out of the
matrix, and ``models_by_case``, which reads the model that served each case out
of the published results.

It is the first half of ``tools/findings.py``, which holds the second: this
module answers what a run measured and that one answers what the register does
with it. Nothing here reads or writes a register, so a change to how a finding
is recorded cannot change how a run is read.

Specified by ``docs/design/consumer_ci.md`` section 9.

**It is a module of its own because reading a run and keeping a register are
two subjects**, and ``findings.py`` reached the nine-hundred-line runway on the
change that cleared a stale reproduction mark (``code-style.md`` section 5.1).
"""

import csv
import json
import re
import shutil
import subprocess
import sys
import tempfile
from xml.etree import ElementTree
from pathlib import Path
from typing import Any, Final

from cmn.registries import most_critical

_MODEL_CODE: Final[re.Pattern] = re.compile(r"\b(QC_LLM_[A-Z_]+|QC_SEC_[A-Z_]+)\b")
_POPULATION: Final[re.Pattern] = re.compile(r"(\d+) of (\d+) observations passed")

# WHERE A FAILURE MESSAGE STOPS BEING THE FINDING AND STARTS BEING OUR
# TRACEBACK. Declared as constants rather than written inline, because an
# escape inside an edited literal is the one class of change this project
# has lost four times (`code-style.md` section 8.1).
_TEST_FRAME: Final[str] = "tests" + chr(92)
_TEST_FRAME_POSIX: Final[str] = "tests/"
_ERROR_LINE: Final[str] = chr(10) + "E "
_IN_CASE: Final[str] = " in MQC_"


def results_directory(scratch: Path) -> Path:
    """Return the directory one run writes its Allure results to, ready for that run.

    Args:
        scratch (Path): The run's scratch directory.

    Returns:
        Path: ``scratch / "allure"``, existing and empty.

    Design: ``consumer_ci.md`` section 9.3.1.
    """
    results = scratch / "allure"
    # EMPTIED FIRST. The path is fixed, so a result an earlier run left would
    # be read as this run's, and the last file for a case names its model.
    if results.exists():
        shutil.rmtree(results)
    # CREATED FIRST. allure-pytest does not create an intermediate directory,
    # and a path whose parent is absent makes pytest exit 5 having collected
    # nothing at all rather than reporting the bad path.
    results.mkdir(parents=True, exist_ok=True)
    return results


def observe(engine: str, mode: str, *, timeout: int = 1800) -> tuple[Path, str]:
    """Run the graded suite for one engine and return its JUnit XML.

    **The XML rather than the terminal output.** A first version scraped the
    failure headers pytest prints and **silently dropped a finding**: two cases
    whose identifiers differ by one digit produced headers it associated with
    the wrong one, so `154109` went unrecorded while 9 of 10 were captured. A
    tool that loses a finding without saying so is worse than one that refuses.

    JUnit XML attaches each failure message to its own test element, which is
    what makes the association exact rather than inferred. It is also a format
    this project already mandates.

    Args:
        engine (str): Which engine to measure.
        mode (str): ``replay`` or ``live``.
        timeout (int): Seconds to allow.

    Returns:
        tuple: The written XML path, and the directory of Allure results.

    Raises:
        RuntimeError: With ``QC_HARNESS_PREFLIGHT_FAILURE`` when pytest could
            not be started, or produced no XML. Neither says anything about a
            model.
    """
    scratch = Path(tempfile.gettempdir()) / f"mqc-findings-{engine}-{mode}"
    report = scratch.with_suffix(".xml")
    results = results_directory(scratch)
    try:
        completed = subprocess.run(
            [
                sys.executable, "-m", "pytest", "-q", "-p", "no:randomly",
                # PINNED, BECAUSE AN ABSOLUTE --alluredir MOVES THE ROOTDIR.
                # pytest includes an existing path among the arguments when it
                # computes rootdir, so a scratch directory under the user's
                # home pulls rootdir above the repository: pytest.ini is never
                # found, testpaths is never applied, no conftest loads, and the
                # run collects nothing while exiting 5. The first run into a
                # fresh path works and every later one collects nothing, which
                # is what made it look intermittent. Found 2026-10-04.
                "-c", "pytest.ini", "--rootdir", ".",
                "--engine", engine, "--mode", mode,
                "-m", "evaluator or tool or sec",
                "--junitxml", str(report),
                # THE RESOLVED MODEL IS PUBLISHED HERE AND NOWHERE ELSE. The
                # reporting hook writes it as a parameter, so a finding records
                # what actually served it rather than what the roster asked
                # for. Harness `cmn_verdict_and_cli.md` section 5.2.
                "--alluredir", str(results),
            ],
            capture_output=True, text=True, check=False, shell=False,
            timeout=timeout, stdin=subprocess.DEVNULL,
        )
    except OSError as error:
        raise RuntimeError(
            f"QC_HARNESS_PREFLIGHT_FAILURE: pytest could not be started, so "
            f"nothing was measured about {engine}"
        ) from error

    if not report.is_file():
        raise RuntimeError(
            f"QC_HARNESS_PREFLIGHT_FAILURE: the run wrote no JUnit XML, so "
            f"nothing can be read about {engine}"
        )
    del completed

    # A RUN THAT COLLECTED NOTHING IS NOT AN ENGINE WITH NO FINDINGS, and the
    # two are indistinguishable from the register alone: both produce an empty
    # file. pytest exits 5 for it, and that is how a missing Allure parent
    # directory reached here on 2026-10-04.
    collected = len(list(ElementTree.parse(report).getroot().iter("testcase")))
    if collected == 0:
        raise RuntimeError(
            f"QC_HARNESS_PREFLIGHT_FAILURE: the run collected no case at all, "
            f"so nothing was measured about {engine}. An empty register and an "
            f"engine that passed everything read the same, which is why this "
            f"refuses rather than writing one"
        )
    return report, results


def parse_passed(report: Path) -> frozenset[str]:
    """Return every case the run measured as passing.

    Args:
        report (Path): The JUnit XML a run wrote.

    Returns:
        frozenset[str]: Each case whose element carries no failure, error or
        skip. **A skip is not a pass**: a case skipped behind a failed
        foundation was not measured (``consumer_ci.md`` section 9.4.7.1).
    """
    return frozenset(
        str(element.get("name", ""))
        for element in ElementTree.parse(report).getroot().iter("testcase")
        if all(element.find(tag) is None for tag in ("failure", "error", "skipped"))
    )


def parse_warnings(report: Path) -> dict[str, dict[str, Any]]:
    """Return each case that passed with a warning, as a warning finding.

    Args:
        report (Path): The JUnit XML a run wrote.

    Returns:
        dict: Case identifier to its taxonomy code, the most critical of the
        ``mqc_warning_code`` properties it carries, an ``actual`` sentence, and
        ``severity`` ``warning``. Only cases carrying ``mqc_outcome`` ``passw``
        and no failure (``consumer_ci.md`` section 6.4.6).
    """
    warnings: dict[str, dict[str, Any]] = {}
    for element in ElementTree.parse(report).getroot().iter("testcase"):
        marks = [(str(prop.get("name")), str(prop.get("value")))
                 for prop in element.iter("property")]
        if ("mqc_outcome", "passw") not in marks or element.find("failure") is not None:
            continue
        codes = [value for name, value in marks if name == "mqc_warning_code"]
        classified = most_critical(codes) or (codes[0] if codes else "")
        warnings[str(element.get("name", ""))] = {
            "taxonomy_code": classified,
            "observations": "",
            "actual": (
                f"{classified} stated and corrected later in the same response, "
                f"so the case passed with a warning"
            ),
            "severity": "warning",
        }
    return warnings


def parse_failures(report: Path) -> dict[str, dict[str, Any]]:
    """Return each failing case and what the run said about it.

    **Each failure message is read from its own test element**, so a case
    cannot be attributed the message of the one before it.

    Args:
        report (Path): The JUnit XML a run wrote.

    Returns:
        dict: Case identifier to its taxonomy code and observation population.
        **A failure carrying no model code is omitted and counted**, so the
        caller can report that rather than quietly recording fewer findings
        than the run produced.
    """
    failures: dict[str, dict[str, Any]] = {}
    for element in ElementTree.parse(report).getroot().iter("testcase"):
        failure = element.find("failure")
        if failure is None:
            continue
        case = str(element.get("name", ""))
        message = f"{failure.get('message', '')}\n{failure.text or ''}"
        # THE MOST CRITICAL CODE, NOT THE FIRST ONE. A disagreement emits
        # `QC_LLM_INCONSISTENT` and then names what the failing observations
        # reported, and taking the first match catalogued a security
        # compromise as a consistency observation. `most_critical` ranks them
        # per `harness_test_taxonomy.md` section 6.4. Section 9.8 here.
        found = _MODEL_CODE.findall(message)
        if not found:
            failures[case] = {"taxonomy_code": "", "observations": ""}
            continue
        population = _POPULATION.search(message)
        classified = most_critical(found) or found[0]
        failures[case] = {
            "taxonomy_code": classified,
            # EMPTY WHERE THE RUN DID NOT SAY, rather than "1 of 1". A
            # consistency finding states its population and a deterministic
            # one does not, and inventing a population would put a figure
            # into a ticket that nothing measured.
            "observations": (
                f"{population.group(1)} of {population.group(2)} passed"
                if population is not None else ""
            ),
            # NAMED BY THE CLASSIFICATION, NOT THE WRAPPER. The consistency
            # message opens with `QC_LLM_INCONSISTENT` and names what the
            # failing observations reported afterwards, so taking the first
            # sentence described the disagreement where the finding is a
            # compromise. Where the two differ, the sentence is built from the
            # classification and the population, which is what a reader needs:
            # what went wrong, and how often. Section 9.8.
            "actual": _classified_sentence(message, classified, population),
        }
    return failures


def _classified_sentence(
    message: str, classified: str, population: Any
) -> str:
    """Return one sentence naming what failed, and how often where it varied.

    **The wrapper fires first and is not the finding.** A disagreement emits
    `QC_LLM_INCONSISTENT` and then names what the failing observations
    reported, so the message's first sentence describes variance where the
    finding may be a compromise.

    Args:
        message (str): The failure message.
        classified (str): The code the finding is named by.
        population (Any): The population match, or None where the run stated
            none.

    Returns:
        str: The run's own words where the classification leads the message,
        and a sentence built from the classification and the population where
        it does not.
    """
    if message.lstrip().startswith(("AssertionError: " + classified, classified)):
        return _first_sentence(message, classified)
    if population is not None:
        passed, total = int(population.group(1)), int(population.group(2))
        return (
            f"{classified} on {total - passed} of {total} observations, "
            f"the other {passed} passing"
        )
    return _first_sentence(message, classified)


def _first_sentence(message: str, code: str) -> str:
    """Return what the run said, without the code or the assertion scaffolding.

    Args:
        message (str): The failure message.
        code (str): The taxonomy code, which the entry already carries.

    Returns:
        str: One sentence, trimmed. **The run's own words**, because a finding
        is what was observed and paraphrasing it would put this tool's reading
        into a vendor ticket.
    """
    body = message.replace("AssertionError:", " ").replace(code + ":", " ")
    # THE ASSERTION, NOT THE TRACEBACK. pytest appends the frames that led
    # here, and a ticket wants what was observed rather than which line of
    # ours noticed it.
    for frame in (_TEST_FRAME, _TEST_FRAME_POSIX, _ERROR_LINE, _IN_CASE):
        if frame in body:
            body = body.split(frame)[0]
    collapsed = " ".join(body.split())
    for terminator in (", so ", ". ", " so that "):
        if terminator in collapsed:
            collapsed = collapsed.split(terminator, maxsplit=1)[0]
            break
    # A CUT INSIDE A BRACKET CLOSES IT (consumer_ci.md section 9.5.5.1).
    collapsed = collapsed.strip()[:300]
    return collapsed + "]" * max(0, collapsed.count("[") - collapsed.count("]"))


def expected_by_case(matrix: Path) -> dict[str, str]:
    """Return what each case was asserting, from the requirement it traces to.

    **The requirement text, not a restatement.** A ticket opens with what the
    model was required to do, and the matrix already holds that sentence; a
    second wording maintained here would drift from it.

    Args:
        matrix (Path): This repository's traceability matrix.

    Returns:
        dict[str, str]: Case name to the requirement text, joined where a case
        serves several. **Absent where a case traces to no row**, which T7
        reports as untraced coverage rather than this tool papering over.
    """
    expected: dict[str, str] = {}
    if not matrix.is_file():
        return expected
    with matrix.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            requirement = str(row.get("requirement_text", "")).strip()
            for case in str(row.get("test_ids", "")).split(";"):
                name = case.strip()
                if not name or not requirement:
                    continue
                if name in expected and requirement not in expected[name]:
                    expected[name] = f"{expected[name]} Also: {requirement}"
                else:
                    expected.setdefault(name, requirement)
    return expected


def models_by_case(results: Path) -> dict[str, str]:
    """Return the model each case was served by, from the published results.

    **Per case rather than per run.** A run can be served more than one model,
    and `resolved_models` is published precisely when it was; recording one
    model for a whole file would name the wrong one for some findings, and a
    ticket would quote it.

    Args:
        results (Path): The Allure raw results directory.

    Returns:
        dict[str, str]: Case name to the model that served it, omitting any
        case whose result did not publish one. **Absent rather than guessed**:
        an entry naming the wrong model is worse than one naming none.
    """
    served: dict[str, str] = {}
    if not results.is_dir():
        return served
    for found in sorted(results.glob("*-result.json")):
        try:
            published = json.loads(found.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        parameters = {
            str(entry.get("name")): str(entry.get("value", ""))
            for entry in published.get("parameters", ())
        }
        model = parameters.get("resolved_models") or parameters.get("resolved_model", "")
        name = str(published.get("name", ""))
        if name and model:
            served[name] = model.strip("'")
    return served
