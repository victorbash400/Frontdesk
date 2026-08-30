"""Read-only production smoke checks using the existing demo account."""

import argparse
import io
import os
import zipfile

import httpx


def check(url: str) -> None:
    with httpx.Client(base_url=url, timeout=45, follow_redirects=False) as client:
        for path in ("/api/health", "/sign-in", "/extension"):
            response = client.get(path)
            response.raise_for_status()
            assert response.status_code == 200, (path, response.status_code)
            print(f"PASS public {path}", flush=True)
        for path in ("/api/goals", "/api/plugins", "/api/mailbox", "/api/filesystem/snapshot"):
            response = client.get(path)
            assert response.status_code == 401, (path, response.status_code)
            print(f"PASS authentication required {path}", flush=True)

        response = client.get("/downloads/front-desk-extension.zip")
        response.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            names = archive.namelist()
            assert "manifest.json" in names and "lib/background.mjs" in names
            assert not any(".env" in name or "node_modules/" in name or name.endswith(".map") for name in names)
            assert url.encode() in archive.read("lib/content.js")
        print(f"PASS extension download ({len(response.content)} bytes)", flush=True)

        csrf = client.get("/api/auth/csrf").json()["csrfToken"]
        response = client.post("/api/auth/callback/credentials", data={
            "csrfToken": csrf,
            "email": os.environ.get("SMOKE_EMAIL", "demo@front-desk.local"),
            "password": os.environ.get("SMOKE_PASSWORD", "front-desk-demo"),
            "callbackUrl": url,
        }, headers={"X-Auth-Return-Redirect": "1"})
        response.raise_for_status()
        session = client.get("/api/auth/session").json()
        assert session.get("user", {}).get("id"), "Login did not create an authenticated session"
        print("PASS credential login and session", flush=True)
        for path in ("/", "/api/goals", "/api/plugins", "/api/skills", "/api/mailbox", "/api/mailbox/threads", "/api/filesystem/snapshot", "/api/notifications?open_questions=true"):
            response = client.get(path)
            response.raise_for_status()
            assert response.status_code == 200, (path, response.status_code)
            print(f"PASS authenticated {path}", flush=True)
        with client.stream("GET", "/api/events/stream") as response:
            response.raise_for_status()
            assert "text/event-stream" in response.headers.get("content-type", "")
            for line in response.iter_lines():
                if line.startswith("data:"):
                    print("PASS authenticated live event stream", flush=True)
                    break
            else:
                raise AssertionError("Event stream closed without an event")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    check(parser.parse_args().url.rstrip("/"))
