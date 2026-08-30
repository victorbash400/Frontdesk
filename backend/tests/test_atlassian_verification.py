import asyncio
from unittest.mock import AsyncMock

import pytest
from mcp.types import CallToolResult, TextContent

from app.mcp_oauth import _verify_atlassian_tools


TOOLS = {
    "getAccessibleAtlassianResources",
    "getVisibleJiraProjects",
    "searchJiraIssuesUsingJql",
}


def result(text: str, *, error: bool = False) -> CallToolResult:
    return CallToolResult(content=[TextContent(type="text", text=text)], isError=error)


def test_verification_accepts_real_mcp_results() -> None:
    session = AsyncMock()
    session.call_tool.side_effect = [result('[{"id":"site-1"}]'), result('{}'), result('{}')]
    asyncio.run(_verify_atlassian_tools(session, TOOLS))
    assert session.call_tool.await_count == 3


@pytest.mark.parametrize("failed_call", [0, 1, 2])
def test_verification_surfaces_tool_errors(failed_call: int) -> None:
    responses = [result('[{"id":"site-1"}]'), result('{}'), result('{}')]
    responses[failed_call] = result("Site permission denied", error=True)
    session = AsyncMock()
    session.call_tool.side_effect = responses
    with pytest.raises(RuntimeError, match="Site permission denied"):
        asyncio.run(_verify_atlassian_tools(session, TOOLS))
    assert session.call_tool.await_count == failed_call + 1
