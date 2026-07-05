from __future__ import annotations

import ipaddress
import re
import socket
from html.parser import HTMLParser
from urllib.parse import urlparse

import requests

from .ingestion import IngestionService


class TextHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self._ignored = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "svg"}:
            self._ignored += 1
        if tag in {"h1", "h2", "h3"} and not self._ignored:
            self.parts.append("\n## ")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg"} and self._ignored:
            self._ignored -= 1
        if tag in {"p", "div", "article", "section", "li", "h1", "h2", "h3", "br"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._ignored and data.strip():
            self.parts.append(data.strip() + " ")

    def text(self) -> str:
        return re.sub(r"\n{3,}", "\n\n", "".join(self.parts)).strip()


class WebIngestionService:
    def __init__(self, ingestion: IngestionService):
        self.ingestion = ingestion

    def ingest_url(self, collection_id: str, url: str) -> dict:
        parsed = urlparse(url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Only public HTTP or HTTPS URLs are supported")
        self._reject_private_host(parsed.hostname)
        response = requests.get(
            url, timeout=(5, 20), allow_redirects=True,
            headers={"User-Agent": "AudioMind/1.0 study-indexer"}, stream=True,
        )
        response.raise_for_status()
        final_host = urlparse(response.url).hostname
        if not final_host:
            raise ValueError("The URL redirected to an invalid location")
        self._reject_private_host(final_host)
        content_type = response.headers.get("content-type", "").lower()
        if "text/html" not in content_type and "text/plain" not in content_type:
            raise ValueError("URL ingestion supports HTML and plain text pages")
        max_bytes = self.ingestion.settings.max_upload_mb * 1024 * 1024
        body = bytearray()
        for block in response.iter_content(65536):
            body.extend(block)
            if len(body) > max_bytes:
                raise ValueError("Web page exceeds the configured upload limit")
        decoded = bytes(body).decode(response.encoding or "utf-8", errors="replace")
        if "text/html" in content_type:
            parser = TextHTMLParser()
            parser.feed(decoded)
            decoded = parser.text()
        if len(decoded.strip()) < 40:
            raise ValueError("The page did not contain enough readable text")
        path_name = parsed.path.rstrip("/").split("/")[-1] or "index"
        safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "-", f"{parsed.hostname}-{path_name}")[:100]
        result = self.ingestion.ingest_bytes(
            collection_id, f"{safe_name}.txt", decoded.encode("utf-8"), use_ocr=False
        )
        result["source_url"] = response.url
        return result

    @staticmethod
    def _reject_private_host(hostname: str) -> None:
        try:
            addresses = {item[4][0] for item in socket.getaddrinfo(hostname, None)}
        except socket.gaierror as exc:
            raise ValueError("Could not resolve the URL hostname") from exc
        for address in addresses:
            if not ipaddress.ip_address(address).is_global:
                raise ValueError("Private, loopback, and link-local URLs are not allowed")
