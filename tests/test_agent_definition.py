from __future__ import annotations

from dataclasses import dataclass

from commonsgate_agent.agent import (
    ALLOWED_TOOLS,
    app,
    enforce_tool_allowlist,
    root_agent,
)


@dataclass
class Tool:
    name: str


def test_adk_agent_constructs_with_scoped_workflow_capabilities() -> None:
    assert app.name == "commonsgate_agent"
    assert root_agent.name == "commonsgate_round_steward"
    assert {tool.__name__ for tool in root_agent.tools} == ALLOWED_TOOLS
    assert "advance_demo_round" in ALLOWED_TOOLS
    assert not any(name in {"allocate_round", "close_round"} for name in ALLOWED_TOOLS)


def test_tool_allowlist_blocks_unknown_or_allocation_tools() -> None:
    assert enforce_tool_allowlist(Tool("get_intake_program"), {}, None) is None
    blocked = enforce_tool_allowlist(Tool("allocate_round"), {}, None)
    assert blocked is not None
    assert blocked["error"]["code"] == "ACTION_NOT_PERMITTED"
