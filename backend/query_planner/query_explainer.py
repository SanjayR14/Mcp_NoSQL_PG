from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class QueryExplanation:
    selected_tables: List[str]
    relationships_detected: List[Dict[str, Any]]
    join_rationale: Optional[str]
    subquery_rationale: Optional[str]
    generated_sql: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "selected_tables": self.selected_tables,
            "relationships_detected": self.relationships_detected,
            "join_rationale": self.join_rationale,
            "subquery_rationale": self.subquery_rationale,
            "generated_sql": self.generated_sql,
            "execution_plan": "(not computed yet)"
        }

