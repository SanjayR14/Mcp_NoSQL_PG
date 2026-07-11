from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .schema_analyzer import ForeignKeyEdge, SchemaGraph




@dataclass
class JoinStep:
    left_table: str
    right_table: str
    left_column: str
    right_column: str
    join_type: str = "INNER"  # INNER/LEFT/etc
    via_constraint: Optional[str] = None


class RelationshipDetector:
    """Finds join paths between tables using FK edges."""

    def __init__(self, graph: SchemaGraph):
        self.graph = graph

    def find_join_path(self, start_table: str, target_table: str, max_hops: int = 4) -> Optional[List[JoinStep]]:
        if start_table == target_table:
            return []

        # BFS on table nodes; edges follow FK relationships in either direction.
        # We treat an FK as joinable from either side.
        queue: List[Tuple[str, List[JoinStep]]] = [(start_table, [])]
        visited = {start_table}

        for _ in range(max_hops):
            next_queue: List[Tuple[str, List[JoinStep]]] = []
            for table, steps in queue:
                if table == target_table:
                    return steps

                ts = self.graph.tables.get(table)
                if not ts:
                    continue

                # outgoing FK edges
                for fk in ts.foreign_keys:
                    # join from table.fk.from_column -> fk.to_table.fk.to_column
                    if fk.to_table not in visited:
                        visited.add(fk.to_table)
                        next_queue.append(
                            (
                                fk.to_table,
                                steps + [
                                    JoinStep(
                                        left_table=table,
                                        right_table=fk.to_table,
                                        left_column=fk.from_column,
                                        right_column=fk.to_column,
                                        join_type="INNER",
                                        via_constraint=fk.constraint_name,
                                    )
                                ],
                            )
                        )

                # Also allow reverse joins by scanning all tables for edges pointing to this table
                for other_name, other_ts in self.graph.tables.items():
                    for fk in other_ts.foreign_keys:
                        if fk.to_table == table and fk.from_table not in visited:
                            visited.add(fk.from_table)
                            next_queue.append(
                                (
                                    fk.from_table,
                                    steps + [
                                        JoinStep(
                                            left_table=fk.to_table,
                                            right_table=fk.from_table,
                                            left_column=fk.to_column,
                                            right_column=fk.from_column,
                                            join_type="INNER",
                                            via_constraint=fk.constraint_name,
                                        )
                                    ],
                                )
                            )

            queue = next_queue

        # final check
        for table, steps in queue:
            if table == target_table:
                return steps
        return None

