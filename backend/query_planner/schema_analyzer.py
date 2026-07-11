from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ForeignKeyEdge:
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    constraint_name: Optional[str] = None


@dataclass
class TableSchema:
    name: str
    columns: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    primary_key: List[str] = field(default_factory=list)
    foreign_keys: List[ForeignKeyEdge] = field(default_factory=list)
    indexes: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class SchemaGraph:
    tables: Dict[str, TableSchema] = field(default_factory=dict)

    def ensure_table(self, name: str) -> TableSchema:
        if name not in self.tables:
            self.tables[name] = TableSchema(name=name)
        return self.tables[name]


def build_schema_graph(complete_schema: Dict[str, Any]) -> SchemaGraph:
    """Build an in-memory schema graph from MCP `get_complete_schema` payload."""
    graph = SchemaGraph()

    for t in complete_schema.get("tables", []):
        table_name = t["name"]
        ts = graph.ensure_table(table_name)
        ts.columns = t.get("columns", {}) or {}
        ts.primary_key = t.get("primary_key", []) or []
        ts.indexes = t.get("indexes", []) or []

    for fk in complete_schema.get("foreign_keys", []):
        edge = ForeignKeyEdge(
            from_table=fk["from_table"],
            from_column=fk["from_column"],
            to_table=fk["to_table"],
            to_column=fk["to_column"],
            constraint_name=fk.get("constraint_name"),
        )
        graph.ensure_table(edge.from_table).foreign_keys.append(edge)

    return graph

