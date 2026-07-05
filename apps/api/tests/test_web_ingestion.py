import socket

import pytest

from audiomind.web_ingestion import TextHTMLParser, WebIngestionService


def test_html_parser_ignores_scripts_and_preserves_headings():
    parser = TextHTMLParser()
    parser.feed("<h1>Deadlocks</h1><script>steal()</script><p>Four conditions apply.</p>")
    text = parser.text()
    assert "## Deadlocks" in text
    assert "Four conditions apply" in text
    assert "steal" not in text


def test_private_urls_are_rejected(monkeypatch):
    monkeypatch.setattr(
        socket, "getaddrinfo",
        lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))],
    )
    with pytest.raises(ValueError, match="Private"):
        WebIngestionService._reject_private_host("localhost")
