from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class SubqueryPlan:
    where_sql: str
    uses_cte: bool = False


def generate_subquery(intent: str, table: str, join_column: Optional[str] = None) -> Optional[SubqueryPlan]:
    """Very small heuristic placeholder.

    Full capability will be improved once relationship detector + semantic mapping is richer.
    """
    intent_lc = (intent or "").lower()

    # Example patterns
    if "no orders" in intent_lc or "never" in intent_lc or "without" in intent_lc:
        # Caller is expected to provide correct join_column/table mapping later.
        return SubqueryPlan(where_sql="/* subquery TBD */")

    if "above average" in intent_lc or "average" in intent_lc:
        return SubqueryPlan(where_sql="/* subquery TBD */")

    return None

