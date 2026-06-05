"""Tests for web_search tool (mocked SearXNG)."""
import json
import pytest
import httpx
import respx

from web_agent_mcp.tools.web_search import WebSearchInput, run_web_search


@pytest.mark.asyncio
@respx.mock
async def test_web_search_returns_results(tmp_path, monkeypatch):
    monkeypatch.setenv("WEB_AGENT_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("WEB_AGENT_SEARXNG_BASE_URL", "http://searxng:8080")

    respx.get("http://searxng:8080/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "Test Result",
                        "url": "https://example.com/test",
                        "content": "A test snippet",
                        "publishedDate": None,
                    }
                ]
            },
        )
    )

    params = WebSearchInput(query="test query", max_results=5)
    result_json = await run_web_search(params)
    result = json.loads(result_json)
    assert result["query"] == "test query"
    assert len(result["results"]) == 1
    assert result["results"][0]["title"] == "Test Result"
