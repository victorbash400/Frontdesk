import base64
import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WorkspaceEvent:
    id: str
    type: str
    source: str
    subject: str
    data: dict[str, object]


def decode_pubsub_event(envelope: dict[str, Any]) -> WorkspaceEvent:
    message = envelope.get("message")
    if not isinstance(message, dict):
        raise ValueError("Pub/Sub event is missing its message.")
    attributes = message.get("attributes")
    if not isinstance(attributes, dict):
        raise ValueError("Pub/Sub event is missing CloudEvent attributes.")
    event_id = str(attributes.get("ce-id") or "")
    event_type = str(attributes.get("ce-type") or "")
    source = str(attributes.get("ce-source") or "")
    subject = str(attributes.get("ce-subject") or "")
    if not event_id or not event_type or not source or not subject:
        raise ValueError("Pub/Sub event has incomplete CloudEvent attributes.")
    encoded = message.get("data")
    try:
        decoded = base64.b64decode(str(encoded or ""), validate=True)
        data = json.loads(decoded or b"{}")
    except (ValueError, json.JSONDecodeError) as error:
        raise ValueError("Pub/Sub event contains invalid resource data.") from error
    if not isinstance(data, dict):
        raise ValueError("Pub/Sub event resource data must be an object.")
    return WorkspaceEvent(event_id, event_type, source, subject, data)
