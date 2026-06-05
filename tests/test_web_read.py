"""Tests for web_read tool (mocked HTTP fetch)."""
import json
import pytest
import httpx
import respx

from web_agent_mcp.tools.web_read import WebReadInput, run_web_read


@pytest.mark.asyncio
@respx.mock
async def test_web_read_html(tmp_path, monkeypatch):
    monkeypatch.setenv("WEB_AGENT_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("WEB_AGENT_INDEX_DIR", str(tmp_path / "index"))
    monkeypatch.setenv("WEB_AGENT_ALLOW_PRIVATE_NETWORK", "true")

    html = b"<html><head><title>Test Page</title></head><body><p>Hello world content here.</p></body></html>"
    respx.get("https://example.com/page").mock(
        return_value=httpx.Response(200, content=html, headers={"content-type": "text/html"})
    )

    params = WebReadInput(url="https://example.com/page", return_links=False)
    result_json = await run_web_read(params)
    result = json.loads(result_json)
    assert result["source_type"] == "html"
    assert "Hello" in result["content"] or "Test Page" in result.get("title", "")


@pytest.mark.asyncio
async def test_web_read_local_path_denied(tmp_path, monkeypatch):
    monkeypatch.setenv("WEB_AGENT_ALLOWED_LOCAL_ROOTS", str(tmp_path / "docs"))

    with pytest.raises(ValueError, match="Access denied"):
        params = WebReadInput(local_path="/etc/passwd")
        await run_web_read(params)
