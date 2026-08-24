from uuid import uuid4

from .config import Settings


def artifact_key(workspace_id: str, client_id: str, filename: str) -> str:
    safe_name = "".join(character for character in filename if character.isalnum() or character in {".", "-", "_"}).strip(".")
    if not safe_name:
        raise ValueError("The artifact filename is invalid.")
    return f"workspaces/{workspace_id}/clients/{client_id}/artifacts/{uuid4()}/{safe_name}"


def require_gcs_bucket(settings: Settings) -> str:
    if not settings.gcs_bucket:
        raise RuntimeError("FRONT_DESK_GCS_BUCKET is required for artifact storage.")
    return settings.gcs_bucket
