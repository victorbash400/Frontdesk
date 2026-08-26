from app.goal_tool_ui import describe_goal_tool, goal_requires_browser
from tools.tool_failures import stop_on_tool_error
from unittest.mock import MagicMock


def test_workspace_calendar_call_has_a_specific_preview() -> None:
    message, service = describe_goal_tool(
        "workspace_google_api_request",
        {"url": "https://www.googleapis.com/calendar/v3/calendars/primary/events"},
    )
    assert (message, service) == ("Updating Google Calendar", "calendar")


def test_meeting_goal_does_not_eagerly_open_browser_use() -> None:
    meeting = "Schedule a Google Meet, have the meeting agent join, then verify its meeting tab is closed."
    assert not goal_requires_browser(meeting)
    assert goal_requires_browser("Open YouTube in the browser and summarize the latest video.")


def test_tool_exceptions_are_returned_without_ending_the_agent() -> None:
    tool = MagicMock()
    tool.name = "workspace_google_api_request"
    context = MagicMock()
    context.state = {"goal_tool_in_flight": True}
    context.actions = MagicMock()
    error = RuntimeError("Only files with binary content can be downloaded. Use Export with Docs Editors files.")

    result = stop_on_tool_error(tool, {}, context, error)
    assert result["status"] == "failed"
    assert "Only files with binary content" in result["error"]
    assert context.state["goal_tool_in_flight"] is False
    assert context.actions.end_of_agent is not True
