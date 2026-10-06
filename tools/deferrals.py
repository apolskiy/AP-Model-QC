# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Which cases each finding defers, read from the declarations and the registers.

**Not reported to vendors.** A vendor receives actual defects; a deferral is a
consequence of one, and `consumer_ci.md` section 4.14.1 records the reading: a
dependent only executes where its base holds, so a skip protects its result
rather than withholding it.

**Nothing stores this mapping**, which is why it is computed. Two sources:
``config/findings/<engine>.yaml`` for the findings, and the
``@pytest.mark.depends_on`` decorators in ``tests/cases/mqc_*.py`` for the
edges. The closure is transitive.

**Read from the parsed syntax, not the text**, for the reason
``MQC_CAS_UNI_115403`` gives about the same decorators: a ``depends_on`` inside
a string literal is data, and this repository embeds some deliberately.

Usage::

    python -m tools.deferrals
"""

import ast
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Final

import yaml

_CASE_NUMBER: Final[re.Pattern] = re.compile(r"_(\d{6})_")
_DEPENDS_ON: Final[re.Pattern] = re.compile(r"depends_on\(['\"](\d{6})['\"]\)")
_ENGINES: Final[tuple[str, ...]] = ("gemini", "openai", "claude", "grok")


def dependency_edges(root: Path) -> dict[str, set[str]]:
    """Return each case identifier mapped to the identifiers that rest on it.

    Args:
        root (Path): The repository root.

    Returns:
        dict[str, set[str]]: Base identifier to its direct dependents.
    """
    edges: dict[str, set[str]] = defaultdict(set)
    for source in sorted((root / "tests" / "cases").glob("mqc_*.py")):
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            named = _CASE_NUMBER.search(node.name)
            if named is None:
                continue
            for decorator in node.decorator_list:
                for base in _DEPENDS_ON.findall(ast.unparse(decorator)):
                    edges[base].add(named.group(1))
    return dict(edges)


def deferred_behind(base: str, edges: dict[str, set[str]]) -> set[str]:
    """Return every case transitively blocked by one base.

    Args:
        base (str): The foundational case identifier.
        edges (dict): Base to direct dependents.

    Returns:
        set[str]: The transitive closure, excluding the base itself.
    """
    blocked: set[str] = set()
    frontier = [base]
    while frontier:
        for dependent in edges.get(frontier.pop(), ()):
            if dependent not in blocked:
                blocked.add(dependent)
                frontier.append(dependent)
    return blocked


def findings_for(root: Path, engine: str) -> list[str]:
    """Return the case identifiers this engine's register carries.

    Args:
        root (Path): The repository root.
        engine (str): The engine whose register to read.

    Returns:
        list[str]: Six-digit identifiers, in file order.
    """
    register = root / "config" / "findings" / f"{engine}.yaml"
    if not register.is_file():
        return []
    payload = yaml.safe_load(register.read_text(encoding="utf-8")) or []
    entries = payload if isinstance(payload, list) else payload.get("findings", [])
    found: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        named = _CASE_NUMBER.search(str(entry.get("case", "")))
        if named is not None:
            found.append(named.group(1))
    return found


def main() -> int:
    """Print the deferral table.

    Returns:
        int: Zero.
    """
    root = Path(__file__).resolve().parents[1]
    edges = dependency_edges(root)

    print(f"{'engine':9s} {'finding':9s} {'defers':>6s}  cases")
    for engine in _ENGINES:
        total = 0
        for finding in findings_for(root, engine):
            blocked = deferred_behind(finding, edges)
            if blocked:
                print(
                    f"{engine:9s} {finding:9s} {len(blocked):6d}  "
                    f"{', '.join(sorted(blocked))}"
                )
                total += len(blocked)
        print(f"{engine:9s} {'TOTAL':9s} {total:6d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
