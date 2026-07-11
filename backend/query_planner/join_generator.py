from __future__ import annotations

from typing import List

from .relationship_detector import JoinStep


def generate_join_clauses(base_table: str, join_steps: List[JoinStep]) -> str:
    """Generate SQL JOIN clauses from join steps."""
    if not join_steps:
        return ""

    # We will build joins in the order provided.
    clauses: List[str] = []
    for step in join_steps:
        join_type = step.join_type.upper().replace(" ", "")
        # step.left_table / right_table are conceptual. We'll alias using table names directly.
        left = f'"{step.left_table}"."{step.left_column}"'
        right = f'"{step.right_table}"."{step.right_column}"'
        clauses.append(f'{join_type} JOIN "{step.right_table}" ON {left} = {right}')

    return "\n".join(clauses)

