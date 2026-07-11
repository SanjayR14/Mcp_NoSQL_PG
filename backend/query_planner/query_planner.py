from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .join_generator import generate_join_clauses
from .query_explainer import QueryExplanation
from .relationship_detector import RelationshipDetector
from .schema_analyzer import SchemaGraph
from .sql_optimizer import optimize_sql




@dataclass
class PlanResult:
    sql: str
    explanation: Dict[str, Any]


class QueryPlanner:
    def __init__(self, graph: SchemaGraph):
        self.graph = graph
        self.detector = RelationshipDetector(graph)

    def _select_tables(self, user_intent: str) -> List[str]:
        """Heuristic table selection based on column names.

        In later iterations this will be LLM-assisted but grounded by schema.
        """
        intent_lc = (user_intent or "").lower()

        candidates: List[str] = []
        # Simple vocabulary mapping
        vocab = {
            "customer": ["customer"],
            "order": ["order"],
            "product": ["product"],
            "department": ["department"],
            "employee": ["employee"],
            "salary": ["salary"],
        }

        for table, ts in self.graph.tables.items():
            cols_lc = " ".join(ts.columns.keys()).lower()
            if any(k in intent_lc and any(v in cols_lc or v in table.lower() for v in vs) for k, vs in vocab.items()):
                candidates.append(table)
            elif any(word in table.lower() for word in intent_lc.split()):
                candidates.append(table)

        # Fallback: include all tables if nothing detected (safer than empty, later refined)
        if not candidates:
            candidates = list(self.graph.tables.keys())

        # De-dup preserving order
        seen = set()
        out = []
        for t in candidates:
            if t not in seen:
                seen.add(t)
                out.append(t)
        return out

    def plan(self, user_intent: str, database: str = "postgres") -> PlanResult:
        selected_tables = self._select_tables(user_intent)
        if not selected_tables:
            selected_tables = list(self.graph.tables.keys())

        # Pick first as base
        base = selected_tables[0]

        join_steps_all: List[Any] = []
        relationships: List[Dict[str, Any]] = []

        # Try to join every other selected table to base via a path
        joined = {base}
        for t in selected_tables[1:]:
            path = self.detector.find_join_path(base, t)
            if path is None:
                continue
            for step in path:
                relationships.append(
                    {
                        "left_table": step.left_table,
                        "left_column": step.left_column,
                        "right_table": step.right_table,
                        "right_column": step.right_column,
                        "join_type": step.join_type,
                        "via_constraint": step.via_constraint,
                    }
                )
                join_steps_all.append(step)
            joined.add(t)

        join_sql = generate_join_clauses(base, join_steps_all)

        # Projection heuristic: pick columns containing keywords or IDs.
        projection_cols: List[str] = []
        base_ts = self.graph.tables.get(base)
        if base_ts:
            for col in base_ts.columns.keys():
                if col.lower().endswith("name") or col.lower() in ("customer_id", "order_id"):
                    projection_cols.append(f'"{base}"."{col}"')
        if not projection_cols:
            # fallback: select all columns from base table only (not '*')
            if base_ts:
                for col in base_ts.columns.keys():
                    projection_cols.append(f'"{base}"."{col}"')

        # Basic WHERE/aggregation placeholder.
        where_sql = ""  # later: build from intent

        from_sql = f'FROM "{base}"'
        if join_sql:
            from_sql = from_sql + "\n" + join_sql

        sql = f"SELECT DISTINCT {', '.join(projection_cols)}\n{from_sql}"
        if where_sql:
            sql += f"\nWHERE {where_sql}"

        optimized = optimize_sql(sql)

        explanation = QueryExplanation(
            selected_tables=selected_tables,
            relationships_detected=relationships,
            join_rationale="Auto-joined using FK graph paths from base table.",
            subquery_rationale="(not implemented yet)",
            generated_sql=optimized.sql,
        ).to_dict()

        return PlanResult(sql=optimized.sql, explanation=explanation)

