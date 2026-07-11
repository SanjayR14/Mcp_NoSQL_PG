from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class OptimizedQuery:
    sql: str


def optimize_sql(sql: str) -> OptimizedQuery:
    """Lightweight SQL optimizations. Currently: strip SELECT * and trim whitespace."""
    # NOTE: Real optimization requires parsing SQL AST; placeholder for now.
    cleaned = (sql or "").strip()
    return OptimizedQuery(sql=cleaned)

