import re
from typing import Any
from urllib.parse import urlparse

from tools.browser_use.intent import describe_browser_action


def describe_goal_tool(name: str, args: dict[str, Any]) -> tuple[str, str]:
    if name == "create_client_meeting":
        return "Creating the client meeting", "meet"
    if name == "create_instant_client_meeting":
        return "Creating the support call link", "meet"
    if name == "join_client_meeting":
        return "Starting the dedicated meeting worker", "meet"
    if name == "wait_for_client_in_meeting":
        return "Waiting for the client to join", "meet"
    if name == "titan_email_client":
        return "Emailing the meeting link to the client", "mail"
    if name.startswith("workspace_gmail_"):
        action = name.removeprefix("workspace_gmail_").replace("_", " ")
        return f"{action.capitalize()} in Gmail", "gmail"
    if name == "workspace_drive_search":
        query = str(args.get("query") or "client documents").strip()
        return f"Searching Drive for {query}", "drive"
    if name == "workspace_docs_create":
        title = str(args.get("title") or "a document").strip()
        return f"Creating {title} in Google Docs", "docs"
    if name == "workspace_google_api_request":
        url = str(args.get("url") or "")
        path = urlparse(url).path.casefold()
        if "calendar" in path:
            return "Updating Google Calendar", "calendar"
        if "documents" in path:
            return "Reading Google Docs", "docs"
        if "spreadsheets" in path:
            return "Working in Google Sheets", "sheets"
        if "messages" in path or "gmail" in url.casefold():
            return "Working in Gmail", "gmail"
        if "files" in path:
            return "Reading Google Drive", "drive"
        if "meet" in url.casefold():
            return "Working in Google Meet", "meet"
        return "Working in Google Workspace", "workspace"
    if name.startswith("browser_"):
        return describe_browser_action(name, args), "browser"
    if name == "update_goal_progress":
        message = str(args.get("message") or "Updating goal progress").strip()
        return message, "goal"
    return name.replace("_", " ").capitalize(), "goal"


def goal_requires_browser(instruction: str) -> bool:
    text = instruction.casefold()
    explicit_web_target = re.search(r"\b(?:browse|open|visit)\s+(?:https?://|www\.|[a-z0-9-]+\.(?:com|net|org|io|app))", text)
    return bool(explicit_web_target) or any(phrase in text for phrase in (
        "browse the web",
        "browser automation",
        "in the browser",
        "navigate to",
        "open the website",
        "open youtube",
        "search online",
        "visit the website",
    ))
