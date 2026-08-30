"""Authenticated Agent Engine transport; no local execution fallback."""

import asyncio
import codecs
import json
import re
from collections.abc import AsyncIterator
from typing import Any

import google.auth
import httpx
from google.adk.events import Event
from google.auth.transport.requests import Request


class JsonEventDecoder:
    """Agent Engine streams adjacent JSON values, including split UTF-8 bytes."""

    def __init__(self) -> None:
        self._utf8 = codecs.getincrementaldecoder("utf-8")()
        self._json = json.JSONDecoder()
        self._buffer = ""

    def feed(self, chunk: bytes, *, final: bool = False) -> list[dict[str, Any]]:
        self._buffer += self._utf8.decode(chunk, final=final)
        events = []
        while self._buffer.strip():
            self._buffer = self._buffer.lstrip()
            try:
                value, offset = self._json.raw_decode(self._buffer)
            except json.JSONDecodeError:
                if final:
                    raise RuntimeError("Agent Engine ended with an incomplete JSON event.")
                break
            self._buffer = self._buffer[offset:]
            for item in value if isinstance(value, list) else [value]:
                if not isinstance(item, dict):
                    raise RuntimeError("Agent Engine returned a non-object event.")
                if "error" in item:
                    raise RuntimeError(f"Agent Engine failed: {item['error']}")
                events.append(item)
        return events


class AgentEngineClient:
    def __init__(self, resource: str) -> None:
        match = re.fullmatch(r"projects/([a-z0-9-]+)/locations/([a-z0-9-]+)/reasoningEngines/([a-zA-Z0-9_-]+)", resource)
        if not match:
            raise ValueError("A complete Agent Engine resource name is required.")
        self.resource = resource
        self._url = f"https://{match[2]}-aiplatform.googleapis.com/v1/{resource}"
        self._credentials = None
        self._auth_lock = asyncio.Lock()

    async def _headers(self, method: str, url: str) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        async with self._auth_lock:
            if self._credentials is None:
                self._credentials, _ = await asyncio.to_thread(
                    google.auth.default, scopes=["https://www.googleapis.com/auth/cloud-platform"],
                )
            await asyncio.to_thread(self._credentials.before_request, Request(), method, url, headers)
        return headers

    async def query(self, method: str, parameters: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._url}:query"
        headers = await self._headers("POST", url)
        async with httpx.AsyncClient(timeout=httpx.Timeout(120, connect=30)) as client:
            response = await client.post(url, headers=headers, json={"classMethod": method, "input": parameters})
            response.raise_for_status()
            result = response.json()
        output = result.get("output")
        if not isinstance(output, dict):
            raise RuntimeError("Agent Engine query returned no object output.")
        return output

    async def stream(self, method: str, parameters: dict[str, Any]) -> AsyncIterator[Event]:
        url = f"{self._url}:streamQuery"
        headers = await self._headers("POST", url)
        decoder = JsonEventDecoder()
        received = False
        async with httpx.AsyncClient(timeout=httpx.Timeout(3600, connect=30)) as client:
            async with client.stream("POST", url, headers=headers, json={"classMethod": method, "input": parameters}) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    for payload in decoder.feed(chunk):
                        received = True
                        yield Event.model_validate(payload)
                for payload in decoder.feed(b"", final=True):
                    received = True
                    yield Event.model_validate(payload)
        if not received:
            raise RuntimeError("Agent Engine returned no events.")
