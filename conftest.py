# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""pytest configuration for the case repository.

**A delegation, not a second configuration.** Every hook body lives in
``cmn.pytest_support`` in the harness and is called from both repositories, so
a flag cannot exist on one surface and not the other, and neither can accept a
value the other rejects.

Two conftest files registering the same flags would drift, and the symptom
would be a report contradicting the run it describes: this repository accepting
a value the harness rejects, or defaulting a flag differently and attributing
the difference to the model under test.

**The flags are not optional here.** The harness fan-out invokes this suite with
``--mode replay`` (``config/consumers.yaml``), and a flag pytest has not been
told about is an argument error before a single test runs.

**Fixtures are deliberately not inherited.** The harness fixtures build
``EvaluationCase`` records from sample payloads, which is harness test
scaffolding rather than a capability a case repository consumes. Case fixtures
belong beside the cases that use them.
"""

from typing import Any

from pathlib import Path

import pytest

from cmn.config import load_env_file, warn_orphan_credentials
from cmn.emission import begin_case, publish_result
from cmn.selection import (
    select_modules,
    select_priority_bands,
    report_unresolved_selection,
    select_named_tests,
    select_traced_cases,
)
from cmn.pytest_support import (
    arrange_dependencies,
    enforce_dependencies,
    record_from_report,
    add_mqc_options,
    configure_invocation,
    label_priority_severity,
    adopt_prerequisites,
    publish_prerequisites,
)
from execution.adapters.registry import credential_variables


def pytest_addoption(parser: Any) -> None:
    """Declare the execution flags from the shared option registry.

    Args:
        parser (Any): pytest's parser.

    Returns:
        None
    """
    add_mqc_options(parser)


def pytest_configure(config: Any) -> None:
    """Load any local credential file, then record what the run was invoked with.

    **The file is read before anything asks for a credential**, it never
    overwrites a variable already set, and it is refused outright under CI,
    where credentials come from the GitHub Environment instead
    (`cmn_verdict_and_cli.md` section 10.34).

    Args:
        config (Any): pytest's configuration.

    Returns:
        None
    """
    root = Path(__file__).resolve().parent
    # THIS ROOT FIRST, THEN BESIDE THE ROSTER. A credential authenticates
    # against an engine and the engines are declared in the harness, so the
    # file lives there; an explicit local one still wins because
    # `load_env_file` never overwrites a variable that is already set. Two
    # calls rather than merge logic, which would be a second thing to get
    # wrong. Design section 10.34.5.
    load_env_file(root)
    load_env_file(root.parent / "AP-Harness-QC")
    warn_orphan_credentials(root, credential_variables())
    warn_orphan_credentials(root.parent / "AP-Harness-QC", credential_variables())
    configure_invocation(config)


def pytest_collection_modifyitems(
    session: pytest.Session, config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Label severity, select the requested bands, then order the cascade.

    Args:
        session (pytest.Session): The run, which an unresolved selection
            placeholder hangs from.
        config (pytest.Config): The active pytest configuration, read for
            ``--priority``.
        items (list): The collected test items.

    Returns:
        None
    """
    label_priority_severity(items)
    # BEFORE THE ORDERING, because `arrange_dependencies` refuses a suite whose
    # dependencies name no collected base, and a band that had dropped its
    # foundations would be exactly that suite.
    select_priority_bands(config, items)
    # THE BEHAVIOUR SELECTORS AFTER THE BAND, so the two intersect rather than
    # one overriding the other, and both before `arrange_dependencies` for the
    # reason above. Design sections 7.7 and 7.8.
    select_modules(config, items)
    select_traced_cases(config, items)
    select_named_tests(config, items)
    # AFTER THE SELECTION, so nothing deselects the placeholders. A file entry
    # that matched no test is a reported skip rather than a refused run.
    report_unresolved_selection(session, items)
    # ORDERED HERE, NOT HOPED FOR. `pytest-randomly` is pinned to shuffle
    # collection, and the cascade is the one mechanism that legitimately needs
    # an order. Design section 10.28.6.
    arrange_dependencies(items)


def pytest_runtest_setup(item: pytest.Item) -> None:
    """Skip a case whose foundational dependency did not hold.

    Args:
        item (pytest.Item): The test about to run.

    Returns:
        None
    """
    # CLEARED HERE, so a case that records nothing publishes nothing
    # rather than republishing its predecessor's measurements. Harness
    # design cmn_verdict_and_cli.md section 5.4.1.
    begin_case()
    enforce_dependencies(item)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: Any) -> Any:
    """Record whether a foundational case held, for its dependents to read.

    Args:
        item (pytest.Item): The test that ran.
        call (Any): The phase pytest is reporting on.

    Returns:
        Any: The hook result, yielded back to pytest unchanged.
    """
    del call
    outcome = yield
    # EVERY PHASE, not only the call. A middle link skipped by the cascade
    # reports from setup, and recording only the call phase left the next link
    # with no entry to read. Design section 10.28.5.
    record_from_report(item, outcome.get_result())
    # AND THE RECORD REACHES THE ARTIFACT. Everything was built and
    # nothing published it: a real result carried empty parameters and a
    # severity label, so a collector could not say which engine produced
    # it. Design sections 5.2 to 5.4.1.
    publish_result(item, outcome.get_result())


def pytest_sessionstart(session: pytest.Session) -> None:
    """Adopt base outcomes an earlier band of this job published.

    Args:
        session (pytest.Session): The starting session.

    Returns:
        None
    """
    adopt_prerequisites(session.config)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Publish what this execution established, for the next band.

    **Written whatever the exit status.** A band that failed still established
    which of its foundations held, and that is exactly what the next band needs
    in order to skip rather than re-run.

    Args:
        session (pytest.Session): The finishing session.
        exitstatus (int): What pytest will exit with, unused here.

    Returns:
        None
    """
    del exitstatus
    publish_prerequisites(session.config)
