"""Small bounded HTTPS transport with no redirect handling."""

from __future__ import annotations

import http.client
from dataclasses import dataclass
from typing import Protocol

from .config import ProviderConfig


@dataclass(frozen=True, slots=True)
class HttpRequest:
    host: str
    target: str
    user_agent: str


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status: int
    content_type: str
    body: bytes
    host: str


class HttpTransport(Protocol):
    def send(
        self, request: HttpRequest, credential: str, config: ProviderConfig
    ) -> HttpResponse: ...


class BoundedHttpsTransport:
    def send(
        self, request: HttpRequest, credential: str, config: ProviderConfig
    ) -> HttpResponse:
        if request.host != config.provider_host:
            raise RuntimeError("unexpected request host")
        connection = http.client.HTTPSConnection(
            request.host, timeout=config.connect_timeout_seconds
        )
        try:
            connection.request(
                "GET",
                request.target,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"apikey {credential}",
                    "User-Agent": request.user_agent,
                },
            )
            response = connection.getresponse()
            if connection.sock is not None:
                connection.sock.settimeout(config.read_timeout_seconds)
            content_length = response.getheader("Content-Length")
            if content_length and int(content_length) > config.max_response_bytes:
                raise ResponseTooLarge("response exceeds configured byte limit")
            body = response.read(config.max_response_bytes + 1)
            if len(body) > config.max_response_bytes:
                raise ResponseTooLarge("response exceeds configured byte limit")
            return HttpResponse(
                status=response.status,
                content_type=response.getheader("Content-Type", ""),
                body=body,
                host=request.host,
            )
        finally:
            connection.close()


class ResponseTooLarge(RuntimeError):
    pass
