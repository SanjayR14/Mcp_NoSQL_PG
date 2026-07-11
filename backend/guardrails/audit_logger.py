from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass(frozen=True)
class GuardrailAuditRecord:
    timestamp: str
    user_prompt: str
    tool_name: Optional[str]
    decision: str
    reason: str
    severity: str
    blocked_tool: Optional[str] = None


def _ensure_log_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


def log_decision(
    *,
    user_prompt: str,
    tool_name: Optional[str],
    decision: str,
    reason: str,
    severity: str,
    blocked_tool: Optional[str] = None,
    log_path: str = "logs/guardrail.log",
) -> None:
    """Append a JSON line to guardrail.log."""
    try:
        _ensure_log_dir(log_path)
        record = GuardrailAuditRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            user_prompt=user_prompt,
            tool_name=tool_name,
            decision=decision,
            reason=reason,
            severity=severity,
            blocked_tool=blocked_tool,
        )
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
    except Exception:
        # Guardrails must never break the app.
        pass

