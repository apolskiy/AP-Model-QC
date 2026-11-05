# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Support code that builds numbered answers for the gates reading one list item.

Created: 2026-11-05
Last updated: 2026-11-05

This file contains ``shipped_rule``, which returns one rule from the corpus, and
``share_answer`` and ``match_answer``, which build the numbered answers
``mqc_uni_list_item_gates.py`` runs through the gates of ``134203``, ``134207``
and ``134402``. It is not collected itself, as its name carries no ``mqc_``
prefix.

Specified by ``docs/testing/model_evaluation_test_plan.md`` sections 9.4.2 and 9.8.2.3.
"""

from typing import Any

from tests.cases.graded_support import shipped_corpus


def shipped_rule(rule_id: str) -> Any:
    """Return one shipped rule.

    Args:
        rule_id (str): The rule's identifier.

    Returns:
        Any: The ``GoldenRuleSet``.

    Raises:
        StopIteration: When the corpus carries no such rule.
    """
    _, rules = shipped_corpus()
    return next(entry for entry in rules if entry.rule_id == rule_id)


def share_answer(share: str) -> str:
    """Return a four-item answer to the quarterly report stating this share in item 3.

    Item 4 carries the true share, so a gate reading past item 3 finds it.

    Args:
        share (str): The share as the answer writes it, such as ``47.1%``.

    Returns:
        str: The answer.
    """
    return (
        "1. North America 41.2 million, EMEA 28.7 million, Japan 11.4 million, "
        "Australia 6.1 million.\n"
        "2. North America.\n"
        f"3. {share}\n"
        "4. 41.2 / 87.4 = 0.4714, so North America holds 47.14% of the total.\n"
    )


def match_answer(percentage: str, disclosure: str) -> str:
    """Return a three-item answer to the open enumeration.

    Args:
        percentage (str): Item 1.
        disclosure (str): Item 2.

    Returns:
        str: The answer.
    """
    return (
        f"1. {percentage}\n"
        f"2. {disclosure}\n"
        "3. The requirement asks for one database, PostgreSQL, Redis or a similar "
        "one. MySQL is a relational database like PostgreSQL.\n"
    )
