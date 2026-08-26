import base64
import html
import re
from email.message import EmailMessage
from email.utils import parseaddr
from typing import Any
from urllib.parse import urlparse

import httpx
from google.adk.tools import FunctionTool, ToolContext
from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.google_oauth import decrypt_refresh_token
from app.models import OAuthConnection, PluginPermission


GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"
DRIVE_API = "https://www.googleapis.com/drive/v3"
DOCS_API = "https://docs.googleapis.com/v1/documents"
TOKEN_URL = "https://oauth2.googleapis.com/token"
WORKSPACE_API_PERMISSIONS = {
    "gmail.googleapis.com": "workspace.gmail",
    "www.googleapis.com": "workspace.drive",
    "docs.googleapis.com": "workspace.docs",
    "sheets.googleapis.com": "workspace.sheets",
    "slides.googleapis.com": "workspace.slides",
    "people.googleapis.com": "workspace.people",
    "tasks.googleapis.com": "workspace.tasks",
    "forms.googleapis.com": "workspace.forms",
    "meet.googleapis.com": "workspace.meet",
}


async def preflight_workspace(account_id: str) -> None:
    token = await workspace_access_token(account_id)
    permissions = _permission_map(account_id)
    async with httpx.AsyncClient(timeout=10) as client:
        if permissions.get("workspace.gmail", True):
            response = await client.get(f"{GMAIL_API}/profile", headers={"Authorization": f"Bearer {token}"})
            if response.is_error:
                raise RuntimeError(_google_error(response))
        if permissions.get("workspace.drive", True):
            response = await client.get(f"{DRIVE_API}/about", headers={"Authorization": f"Bearer {token}"}, params={"fields": "user"})
            if response.is_error:
                raise RuntimeError(_google_error(response))


def workspace_tools(account_id: str) -> list[FunctionTool]:
    permissions = _permission_map(account_id)
    functions = []
    if permissions.get("workspace.gmail", True):
        functions.extend((
            workspace_gmail_search,
            workspace_gmail_read,
            workspace_gmail_list_labels,
            workspace_gmail_create_draft,
            workspace_gmail_send_draft,
            workspace_gmail_send_message,
            workspace_gmail_reply,
            workspace_gmail_modify_message,
            workspace_gmail_trash_message,
        ))
    if permissions.get("workspace.drive", True):
        functions.append(workspace_drive_search)
    if permissions.get("workspace.docs", True) and permissions.get("workspace.drive", True):
        functions.append(workspace_docs_read)
        functions.append(workspace_docs_create)
    functions.append(workspace_google_api_request)
    return [FunctionTool(function) for function in functions]


async def workspace_gmail_search(query: str, tool_context: ToolContext, max_results: int = 10) -> dict[str, Any]:
    """Search the connected Gmail account using Gmail search syntax."""
    account_id = _account_id(tool_context)
    result = await workspace_request(account_id, "GET", f"{GMAIL_API}/messages", params={"q": query, "maxResults": max(1, min(25, max_results))})
    messages = result.get("messages", [])
    details = []
    for item in messages:
        message = await workspace_request(account_id, "GET", f"{GMAIL_API}/messages/{item['id']}", params={"format": "metadata", "metadataHeaders": ["From", "To", "Subject", "Date"]})
        details.append({
            "id": message.get("id"),
            "thread_id": message.get("threadId"),
            "from": _header(message, "From"),
            "to": _header(message, "To"),
            "subject": _header(message, "Subject"),
            "date": _header(message, "Date"),
            "snippet": message.get("snippet", ""),
            "url": f"https://mail.google.com/mail/u/0/#all/{message.get('id')}",
        })
    return {"messages": details}


async def workspace_gmail_read(message_id: str, tool_context: ToolContext) -> dict[str, Any]:
    """Read one Gmail message by ID, including its decoded body and browser URL."""
    message = await workspace_request(_account_id(tool_context), "GET", f"{GMAIL_API}/messages/{message_id}", params={"format": "full"})
    return {
        "id": message.get("id"),
        "thread_id": message.get("threadId"),
        "from": _header(message, "From"),
        "to": _header(message, "To"),
        "subject": _header(message, "Subject"),
        "date": _header(message, "Date"),
        "body": _decoded_body(message.get("payload", {})),
        "url": f"https://mail.google.com/mail/u/0/#all/{message.get('id')}",
    }


async def workspace_gmail_list_labels(tool_context: ToolContext) -> dict[str, Any]:
    """List Gmail system and user labels."""
    result = await workspace_request(_account_id(tool_context), "GET", f"{GMAIL_API}/labels")
    return {"labels": result.get("labels", [])}


async def workspace_gmail_create_draft(
    to: list[str],
    subject: str,
    body: str,
    tool_context: ToolContext,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
) -> dict[str, Any]:
    """Create a Gmail draft without sending it."""
    raw = _encoded_message(to, subject, body, cc, bcc)
    result = await workspace_request(_account_id(tool_context), "POST", f"{GMAIL_API}/drafts", json={"message": {"raw": raw}})
    return {"draft_id": result.get("id"), "message_id": result.get("message", {}).get("id"), "status": "drafted"}


async def workspace_gmail_send_draft(draft_id: str, tool_context: ToolContext) -> dict[str, Any]:
    """Send an existing Gmail draft."""
    result = await workspace_request(_account_id(tool_context), "POST", f"{GMAIL_API}/drafts/send", json={"id": draft_id})
    return {"message_id": result.get("id"), "thread_id": result.get("threadId"), "status": "sent"}


async def workspace_gmail_send_message(
    to: list[str],
    subject: str,
    body: str,
    tool_context: ToolContext,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
) -> dict[str, Any]:
    """Send a plain-text email through the connected Gmail account."""
    raw = _encoded_message(to, subject, body, cc, bcc)
    result = await workspace_request(_account_id(tool_context), "POST", f"{GMAIL_API}/messages/send", json={"raw": raw})
    return {"message_id": result.get("id"), "thread_id": result.get("threadId"), "status": "sent"}


async def workspace_gmail_reply(message_id: str, body: str, tool_context: ToolContext) -> dict[str, Any]:
    """Reply to a Gmail message while preserving its thread."""
    account_id = _account_id(tool_context)
    original = await workspace_request(account_id, "GET", f"{GMAIL_API}/messages/{message_id}", params={"format": "metadata", "metadataHeaders": ["From", "Reply-To", "Subject", "Message-ID", "References"]})
    recipient = parseaddr(_header(original, "Reply-To") or _header(original, "From"))[1]
    if not recipient:
        raise RuntimeError("The original message has no reply address.")
    subject = _header(original, "Subject")
    if not subject.casefold().startswith("re:"):
        subject = f"Re: {subject}"
    message = EmailMessage()
    message["To"] = recipient
    message["Subject"] = subject
    original_message_id = _header(original, "Message-ID")
    if original_message_id:
        message["In-Reply-To"] = original_message_id
        message["References"] = " ".join(filter(None, (_header(original, "References"), original_message_id)))
    message.set_content(body)
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode().rstrip("=")
    result = await workspace_request(account_id, "POST", f"{GMAIL_API}/messages/send", json={"raw": raw, "threadId": original.get("threadId")})
    return {"message_id": result.get("id"), "thread_id": result.get("threadId"), "status": "sent"}


async def workspace_gmail_modify_message(
    message_id: str,
    tool_context: ToolContext,
    add_label_ids: list[str] | None = None,
    remove_label_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Add or remove Gmail labels, including read, unread, starred, and archived state."""
    if not add_label_ids and not remove_label_ids:
        raise RuntimeError("Provide at least one Gmail label to add or remove.")
    result = await workspace_request(_account_id(tool_context), "POST", f"{GMAIL_API}/messages/{message_id}/modify", json={"addLabelIds": add_label_ids or [], "removeLabelIds": remove_label_ids or []})
    return {"message_id": result.get("id"), "label_ids": result.get("labelIds", []), "status": "updated"}


async def workspace_gmail_trash_message(message_id: str, tool_context: ToolContext, trashed: bool = True) -> dict[str, Any]:
    """Move a Gmail message to trash or restore it."""
    action = "trash" if trashed else "untrash"
    result = await workspace_request(_account_id(tool_context), "POST", f"{GMAIL_API}/messages/{message_id}/{action}")
    return {"message_id": result.get("id"), "thread_id": result.get("threadId"), "trashed": trashed}


async def workspace_google_api_request(
    method: str,
    url: str,
    tool_context: ToolContext,
    params: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Call any Google Workspace REST API operation allowed by the connected OAuth scopes.

    Use an absolute official Google API URL. This provides complete scoped access when a
    specialized Workspace tool is not present, including Drive, Docs, Sheets, Slides,
    Calendar, People, Tasks, Forms, and Meet operations.
    """
    parsed = urlparse(url)
    permission_id = WORKSPACE_API_PERMISSIONS.get(parsed.hostname or "")
    if parsed.scheme != "https" or not permission_id:
        raise RuntimeError("Use an official HTTPS Google Workspace API URL.")
    if parsed.hostname == "www.googleapis.com" and "/calendar/" in parsed.path:
        permission_id = "workspace.calendar"
    permissions = _permission_map(_account_id(tool_context))
    if not permissions.get(permission_id, True):
        raise RuntimeError(f"{permission_id} is disabled for this account.")
    verb = method.strip().upper()
    if verb not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
        raise RuntimeError("Google Workspace requests support GET, POST, PUT, PATCH, or DELETE.")
    return await workspace_request(_account_id(tool_context), verb, url, params=params, json=payload)


async def workspace_drive_search(query: str, tool_context: ToolContext, max_results: int = 20) -> dict[str, Any]:
    """Search connected Google Drive files by name or full text."""
    escaped = query.replace("'", "\\'")
    result = await workspace_request(_account_id(tool_context), "GET", f"{DRIVE_API}/files", params={
        "q": f"trashed = false and (name contains '{escaped}' or fullText contains '{escaped}')",
        "pageSize": max(1, min(50, max_results)),
        "fields": "files(id,name,mimeType,modifiedTime,webViewLink,parents)",
        "orderBy": "modifiedTime desc",
    })
    return {"files": result.get("files", [])}


async def workspace_docs_create(title: str, content: str, tool_context: ToolContext) -> dict[str, Any]:
    """Create a Google Doc and write the supplied text into it."""
    account_id = _account_id(tool_context)
    document = await workspace_request(account_id, "POST", DOCS_API, json={"title": title})
    document_id = str(document.get("documentId") or "")
    if not document_id:
        raise RuntimeError("Google Docs did not return a document ID.")
    if content:
        await workspace_request(account_id, "POST", f"{DOCS_API}/{document_id}:batchUpdate", json={"requests": [{"insertText": {"location": {"index": 1}, "text": content}}]})
    return {"document_id": document_id, "title": title, "url": f"https://docs.google.com/document/d/{document_id}/edit", "preview": workspace_preview(document_id, title, "application/vnd.google-apps.document")}


async def workspace_docs_read(document_id: str, tool_context: ToolContext) -> dict[str, Any]:
    """Read a Google Doc through the Docs API and return its text and preview identity."""
    clean_id = google_resource_id(document_id)
    result = await workspace_request(_account_id(tool_context), "GET", f"{DOCS_API}/{clean_id}")
    return {
        "document_id": clean_id,
        "title": result.get("title"),
        "text": document_text(result),
        "preview": workspace_preview(clean_id, result.get("title"), "application/vnd.google-apps.document"),
    }


async def workspace_access_token(account_id: str) -> str:
    with SessionLocal() as session:
        connection = session.scalar(select(OAuthConnection).where(OAuthConnection.account_id == account_id, OAuthConnection.provider == "google_workspace"))
        if not connection:
            raise RuntimeError("Google Workspace is not connected.")
        refresh_token = decrypt_refresh_token(connection)
    client_id, client_secret = get_settings().google_oauth_credentials
    if not client_id or not client_secret:
        raise RuntimeError("Google Workspace OAuth is not configured.")
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(TOKEN_URL, data={"client_id": client_id, "client_secret": client_secret, "refresh_token": refresh_token, "grant_type": "refresh_token"})
    if response.is_error:
        raise RuntimeError(_google_error(response))
    token = str(response.json().get("access_token") or "")
    if not token:
        raise RuntimeError("Google Workspace did not return an access token.")
    return token


async def workspace_request(account_id: str, method: str, url: str, *, params: dict[str, Any] | None = None, json: Any = None) -> dict[str, Any]:
    token = await workspace_access_token(account_id)
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.request(method, url, headers={"Authorization": f"Bearer {token}"}, params=params, json=json)
    if response.is_error:
        raise RuntimeError(_google_error(response))
    return response.json() if response.content else {}


def _account_id(tool_context: ToolContext) -> str:
    account_id = str(tool_context.state.get("account_id") or "")
    if not account_id:
        raise RuntimeError("The goal worker account scope is missing.")
    return account_id


def google_resource_id(value: str) -> str:
    clean = value.strip()
    if "/d/" in clean:
        clean = clean.split("/d/", 1)[1].split("/", 1)[0]
    if not re.fullmatch(r"[A-Za-z0-9_-]{10,}", clean):
        raise RuntimeError("A valid Google resource ID or URL is required.")
    return clean


def workspace_preview(resource_id: str, title: str | None = None, mime_type: str | None = None) -> dict[str, Any]:
    return {"kind": "workspace", "resource_id": resource_id, "title": title, "mime_type": mime_type}


def document_text(document: dict[str, Any]) -> str:
    return "".join(
        str(element.get("textRun", {}).get("content") or "")
        for block in document.get("body", {}).get("content", [])
        for element in block.get("paragraph", {}).get("elements", [])
    )


def _permission_map(account_id: str) -> dict[str, bool]:
    with SessionLocal() as session:
        return {
            row.permission_id: row.enabled
            for row in session.scalars(select(PluginPermission).where(PluginPermission.account_id == account_id))
        }


def _header(message: dict[str, Any], name: str) -> str:
    return next((str(item.get("value", "")) for item in message.get("payload", {}).get("headers", []) if str(item.get("name", "")).casefold() == name.casefold()), "")


def _encoded_message(
    to: list[str],
    subject: str,
    body: str,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
) -> str:
    recipients = [address.strip() for address in to if address.strip()]
    if not recipients:
        raise RuntimeError("Provide at least one email recipient.")
    message = EmailMessage()
    message["To"] = ", ".join(recipients)
    if cc:
        message["Cc"] = ", ".join(address.strip() for address in cc if address.strip())
    if bcc:
        message["Bcc"] = ", ".join(address.strip() for address in bcc if address.strip())
    message["Subject"] = subject
    message.set_content(body)
    return base64.urlsafe_b64encode(message.as_bytes()).decode().rstrip("=")


def _decoded_body(payload: dict[str, Any]) -> str:
    data = payload.get("body", {}).get("data")
    if data and payload.get("mimeType") in {"text/plain", "text/html"}:
        decoded = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode(errors="replace")
        return html.unescape(re.sub(r"<[^>]+>", " ", decoded)) if payload.get("mimeType") == "text/html" else decoded
    children = payload.get("parts", [])
    plain = next((text for part in children if part.get("mimeType") == "text/plain" and (text := _decoded_body(part))), "")
    return plain or next((text for part in children if (text := _decoded_body(part))), "")


def _google_error(response: httpx.Response) -> str:
    try:
        message = response.json().get("error", {}).get("message")
    except ValueError:
        message = response.text[:300]
    return f"Google Workspace returned {response.status_code}: {message or response.reason_phrase}"
