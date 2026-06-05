"""Diagnostic test for the two problem URLs."""
import asyncio
import json
import sys

sys.path.insert(0, "/app/src")


async def test_spa():
    from web_agent_mcp.tools.web_read import WebReadInput, run_web_read

    print("=== Test 1: SPA detection (fujisato.akita.jp) ===")
    r = json.loads(await run_web_read(WebReadInput(
        url="https://www.town.fujisato.akita.jp/",
        force_refresh=True,
    )))
    print(f"used_browser: {r['metadata']['used_browser']}")
    print(f"extraction_method: {r['extraction_method']}")
    print(f"content length: {len(r['content'])}")
    print(f"content[:400]:\n{r['content'][:400]}")
    has_template = "${" in r["content"]
    print(f"has template vars (\${{}}): {has_template}")


async def test_large():
    from web_agent_mcp.tools.web_read import WebReadInput, run_web_read

    print("\n=== Test 2: Large content (zck.or.jp) ===")
    r = json.loads(await run_web_read(WebReadInput(
        url="https://www.zck.or.jp/site/forum/16616.html",
        force_refresh=True,
    )))
    print(f"extraction_method: {r['extraction_method']}")
    print(f"content length: {len(r['content'])}")
    print(f"content_truncated: {r['metadata']['content_truncated']}")
    print(f"last 200 chars of content:\n{r['content'][-200:]}")


async def main():
    await test_spa()
    await test_large()


asyncio.run(main())
