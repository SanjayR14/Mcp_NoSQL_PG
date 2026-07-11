from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .config import DEFAULT_CONFIG
from .audit_logger import log_decision


@dataclass(frozen=True)
class GuardrailResult:
    allowed: bool
    reason: str
    severity: str
    blocked_tool: Optional[str] = None


def _lower(s: str) -> str:
    return (s or "").lower()


def _contains_any(haystack: str, needles: list[str]) -> Optional[str]:
    hl = haystack
    for n in needles:
        if n and n.lower() in hl:
            return n
    return None


def check_request(user_prompt: str, tool_name: str = None) -> GuardrailResult:
    """Main guardrail entry point.

    Placed between user request and any MCP tool execution.
    """
    cfg = DEFAULT_CONFIG

    if not cfg.enabled:
        return GuardrailResult(
            allowed=True,
            reason="Guardrails disabled",
            severity="low",
            blocked_tool=None,
        )

    prompt_lc = _lower(user_prompt)

    # 1) Prompt injection protection
    inj = _contains_any(prompt_lc, [p.lower() for p in cfg.prompt_injection_phrases])
    if inj:
        result = GuardrailResult(
            allowed=False,
            reason=f"Prompt injection attempt detected: '{inj}'",
            severity="high",
            blocked_tool=tool_name,
        )
        log_decision(
            user_prompt=user_prompt,
            tool_name=tool_name,
            decision="blocked",
            reason=result.reason,
            severity=result.severity,
            blocked_tool=result.blocked_tool,
        )
        return result

    # 2) Dangerous intent detection
    # (Only prompt-level right now; SQL-level is handled next.)
    dang = _contains_any(prompt_lc, [p.lower() for p in cfg.dangerous_intent_phrases])
    if dang:
        result = GuardrailResult(
            allowed=False,
            reason=f"Dangerous intent detected: '{dang}'",
            severity="high",
            blocked_tool=tool_name,
        )
        log_decision(
            user_prompt=user_prompt,
            tool_name=tool_name,
            decision="blocked",
            reason=result.reason,
            severity=result.severity,
            blocked_tool=result.blocked_tool,
        )
        return result

    # 3) Sensitive data protection
    sensitive = _contains_any(prompt_lc, [p.lower() for p in cfg.sensitive_data_phrases])
    if sensitive:
        result = GuardrailResult(
            allowed=False,
            reason="This request violates security policies and cannot be executed.",
            severity="high",
            blocked_tool=tool_name,
        )
        log_decision(
            user_prompt=user_prompt,
            tool_name=tool_name,
            decision="blocked",
            reason=result.reason,
            severity=result.severity,
            blocked_tool=result.blocked_tool,
        )
        return result

    # 4) SQL safety validation
    # If the prompt/tool request contains blocked SQL keywords, block.
    combined = prompt_lc
    if tool_name:
        combined += " " + _lower(tool_name)

    blocked_sql_found = None
    for cmd in cfg.blocked_sql_commands:
        if cmd.lower() in combined:
            blocked_sql_found = cmd
            break

    if blocked_sql_found:
        result = GuardrailResult(
            allowed=False,
            reason=f"Blocked unsafe SQL command: {blocked_sql_found}",
            severity="high",
            blocked_tool=tool_name,
        )
        log_decision(
            user_prompt=user_prompt,
            tool_name=tool_name,
            decision="blocked",
            reason=result.reason,
            severity=result.severity,
            blocked_tool=result.blocked_tool,
        )
        return result

    # 5) RBAC: allow tools based on role
    role = cfg.default_role
    allowed_tools = (cfg.allowed_tools_by_role or {}).get(role, [])
    if tool_name:
        if tool_name not in allowed_tools:
            result = GuardrailResult(
                allowed=False,
                reason=f"Tool '{tool_name}' is not permitted for role '{role}'.",
                severity="medium",
                blocked_tool=tool_name,
            )
            log_decision(
                user_prompt=user_prompt,
                tool_name=tool_name,
                decision="blocked",
                reason=result.reason,
                severity=result.severity,
                blocked_tool=result.blocked_tool,
            )
            return result

    result = GuardrailResult(
        allowed=True,
        reason="Allowed",
        severity="low",
        blocked_tool=None,
    )
    log_decision(
        user_prompt=user_prompt,
        tool_name=tool_name,
        decision="allowed",
        reason=result.reason,
        severity=result.severity,
        blocked_tool=None,
    )
    return result

