import base64
import json
import logging
import re
from uuid import uuid4

from app.config import get_settings
from tools.browser_use.playwright import connected_playwright_toolset

from .agent_session import create_agent_ticket
from .models import Meeting


logger = logging.getLogger("uvicorn.error")


async def join_meeting(meeting: Meeting, *, voice: str = "Kore", language: str = "en") -> dict[str, str]:
    if not meeting.meet_uri:
        raise ValueError("The meeting does not have a Google Meet link.")
    settings = get_settings()
    runtime_id = str(uuid4())
    bridge_id = str(uuid4())
    ticket = create_agent_ticket(meeting.account_id, meeting.id, runtime_id=runtime_id, bridge_id=bridge_id, ttl_seconds=86_400)
    socket_base = settings.public_api_url.rstrip("/").replace("https://", "wss://").replace("http://", "ws://")
    socket_url = f"{socket_base}/api/meetings/{meeting.id}/agent?ticket={ticket}&voice={voice}&language={language}"
    config = base64.urlsafe_b64encode(json.dumps({
        "meetingId": meeting.id,
        "runtimeId": runtime_id,
        "bridgeId": bridge_id,
        "socketUrl": socket_url,
    }, separators=(",", ":")).encode()).decode().rstrip("=")
    worker_url = f"{meeting.meet_uri}#front-desk-meet={config}"
    logger.info("meeting=%s worker=launch meet=%s", meeting.id, meeting.meet_uri)
    toolset = await connected_playwright_toolset()
    try:
        tools = await toolset.get_tools()
        navigate = next((tool for tool in tools if tool.name == "browser_navigate"), None)
        if not navigate:
            raise RuntimeError("Browser Use did not expose browser_navigate.")
        session = await navigate._mcp_session_manager.create_session()  # type: ignore[attr-defined]
        result = await session.call_tool("browser_navigate", arguments={"url": worker_url})
        if result.isError:
            message = " ".join(getattr(item, "text", "") for item in result.content).strip()
            raise RuntimeError(message or "Browser Use could not open Google Meet.")
        snapshot = await session.call_tool("browser_snapshot", arguments={})
        snapshot_text = " ".join(getattr(item, "text", "") for item in snapshot.content).strip()
        meeting_code = meeting.meet_uri.rstrip("/").rsplit("/", 1)[-1]
        if snapshot.isError or meeting_code not in snapshot_text:
            raise RuntimeError("Browser Use did not confirm the Google Meet page after navigation.")
        logger.info("meeting=%s worker=page_ready", meeting.id)
        if "Getting ready" in snapshot_text:
            await session.call_tool("browser_wait_for", arguments={"time": 10})
            snapshot = await session.call_tool("browser_snapshot", arguments={})
            snapshot_text = " ".join(getattr(item, "text", "") for item in snapshot.content).strip()
        microphone_match = re.search(r'button "Turn on microphone"[^\n]*\[ref=([^\]]+)\]', snapshot_text, re.IGNORECASE)
        if microphone_match:
            microphone = await session.call_tool("browser_click", arguments={
                "element": "Google Meet agent microphone button",
                "target": microphone_match.group(1),
            })
            if microphone.isError:
                message = " ".join(getattr(item, "text", "") for item in microphone.content).strip()
                raise RuntimeError(message or "Browser Use could not turn on the meeting agent microphone.")
            logger.info("meeting=%s worker=virtual_microphone_enabled", meeting.id)
        if re.search(r'button "Switch here"', snapshot_text, re.IGNORECASE):
            raise RuntimeError("Google Meet is active in another tab. Front Desk will not transfer that call.")
        join_match = re.search(r'button "(?:Join now|Ask to join)"[^\n]*\[ref=([^\]]+)\]', snapshot_text, re.IGNORECASE)
        if join_match:
            click = await session.call_tool("browser_click", arguments={
                "element": "Google Meet join button",
                "target": join_match.group(1),
            })
            if click.isError:
                message = " ".join(getattr(item, "text", "") for item in click.content).strip()
                raise RuntimeError(message or "Browser Use could not join Google Meet.")
            logger.info("meeting=%s worker=join_clicked", meeting.id)
    except Exception:
        logger.exception("meeting=%s worker=launch_failed", meeting.id)
        raise
    finally:
        await toolset.close()
    return {
        "meetingId": meeting.id,
        "runtimeId": runtime_id,
        "bridgeId": bridge_id,
        "meetUri": meeting.meet_uri,
        "state": "browser_opened",
    }
