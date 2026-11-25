"""Helpers that keep ``position`` values as a clean 0..n-1 sequence."""

from __future__ import annotations


def resequence(items: list) -> None:
    for index, item in enumerate(items):
        item.position = index


def place(items: list, moving, position: int | None) -> None:
    """Re-number ``items`` so ``moving`` sits at 0-based ``position`` (clamped; ``None`` = last).

    ``items`` is every sibling including ``moving``, in their current order.
    """
    others = [item for item in items if item.id != moving.id]
    index = len(others) if position is None else max(0, min(position, len(others)))
    others.insert(index, moving)
    resequence(others)
