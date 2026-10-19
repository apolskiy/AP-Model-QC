# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Scripted ref heads and gate verdicts, for the cases that follow a replaced harness commit.

**A sibling module collection does not reach**, so the case module holds cases
and nothing else. Designed in ``docs/design/consumer_ci.md`` section 3.11.3.
"""

from typing import Final

from tools.harness_pin import Greenness, follow_replaced

FIRST: Final[str] = "1" * 40
SECOND: Final[str] = "2" * 40
THIRD: Final[str] = "3" * 40
FOURTH: Final[str] = "4" * 40
FIFTH: Final[str] = "5" * 40


def cancelled() -> Greenness:
    """Return the verdict of a gate that was cancelled.

    Returns:
        Greenness: Not green, concluded ``cancelled``.
    """
    return Greenness(green=False, reason="gate concluded cancelled", conclusion="cancelled")


def passed() -> Greenness:
    """Return the verdict of a gate that passed.

    Returns:
        Greenness: Green, concluded ``success``.
    """
    return Greenness(green=True, reason="gate passed", conclusion="success")


def follow(
    heads: list[str], verdicts: dict[str, Greenness]
) -> tuple[str, Greenness, list[str]]:
    """Run the follower from :data:`FIRST` against scripted ref heads and gate verdicts.

    Args:
        heads (list[str]): What the ref names at each re-resolution, in order.
        verdicts (dict[str, Greenness]): Each commit's gate verdict.

    Returns:
        tuple[str, Greenness, list[str]]: The commit followed to, its verdict,
        and every commit whose verdict was asked for.
    """
    remaining = list(heads)
    asked: list[str] = []

    def verdict_of(commit: str) -> Greenness:
        asked.append(commit)
        return verdicts[commit]

    commit, verdict = follow_replaced("main", FIRST, lambda: remaining.pop(0), verdict_of)
    return commit, verdict, asked
