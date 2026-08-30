import base64
import json
import logging
from uuid import uuid4

from app.config import get_settings
from app.database import SessionLocal
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
    logger.info(
        "meeting=%s runtime=%s bridge=%s worker=launch meet=%s",
        meeting.id, runtime_id, bridge_id, meeting.meet_uri,
    )
    toolset = await connected_playwright_toolset(meeting.account_id)
    logger.info("meeting=%s runtime=%s worker=browser_preflight_passed", meeting.id, runtime_id)
    browser_opened = False
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
        browser_opened = True
        snapshot = await session.call_tool("browser_snapshot", arguments={})
        snapshot_text = " ".join(getattr(item, "text", "") for item in snapshot.content).strip()
        meeting_code = meeting.meet_uri.rstrip("/").rsplit("/", 1)[-1]
        if snapshot.isError or meeting_code not in snapshot_text:
            raise RuntimeError("Browser Use did not confirm the Google Meet page after navigation.")
        logger.info("meeting=%s runtime=%s worker=page_ready control_owner=meet_worker", meeting.id, runtime_id)
    except Exception as error:
        if browser_opened:
            close = await session.call_tool("browser_close", arguments={})
            logger.info("meeting=%s runtime=%s worker=failed_tab_closed success=%s", meeting.id, runtime_id, not close.isError)
        with SessionLocal() as database:
            current = database.get(Meeting, meeting.id)
            if current and current.active_runtime_id == runtime_id:
                current.state = "failed"
                current.failure = str(error).strip() or type(error).__name__
                database.commit()
        logger.exception("meeting=%s runtime=%s bridge=%s worker=launch_failed", meeting.id, runtime_id, bridge_id)
        raise
    finally:
        await toolset.close()
    with SessionLocal() as database:
        current = database.get(Meeting, meeting.id)
        if current and current.active_runtime_id == runtime_id and current.state == "launching":
            current.state = "browser_opened"
            database.commit()
    return {
        "meetingId": meeting.id,
        "runtimeId": runtime_id,
        "bridgeId": bridge_id,
        "meetUri": meeting.meet_uri,
        "state": "browser_opened",
    }
