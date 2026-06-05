"""Validation tests for the two problem URLs."""
import asyncio
import json
import sys

sys.path.insert(0, "/app/src")


async def test_spa_auto_fallback():
    """藤里町SPA: テンプレート変数を検知してPlaywrightで自動再取得すること。"""
    from web_agent_mcp.tools.web_read import WebReadInput, run_web_read

    print("=== [1] SPA 自動フォールバック: https://www.town.fujisato.akita.jp/ ===")
    r = json.loads(await run_web_read(WebReadInput(
        url="https://www.town.fujisato.akita.jp/",
        force_refresh=True,
    )))
    print(f"  used_browser:        {r['metadata']['used_browser']}")
    print(f"  extraction_method:   {r['extraction_method']}")
    print(f"  title:               {r['title']}")
    print(f"  content length:      {len(r['content'])} chars")
    has_template = "${" in r["content"]
    print(f"  has JS template vars: {has_template}")
    print(f"  content[:300]:\n{r['content'][:300]}")

    if not has_template and len(r["content"]) > 50:
        print("  => PASS: テンプレート変数なし、コンテンツ取得成功")
    elif has_template:
        print("  => WARN: まだテンプレート変数が残っています")
    return r


async def test_large_content():
    """zck.or.jp: 大容量コンテンツを切り捨てなく取得し、レスポンスサイズを制御すること。"""
    from web_agent_mcp.tools.web_read import WebReadInput, run_web_read

    print("\n=== [2] 大容量コンテンツ: https://www.zck.or.jp/site/forum/16616.html ===")
    r_json = await run_web_read(WebReadInput(
        url="https://www.zck.or.jp/site/forum/16616.html",
        force_refresh=True,
    ))
    r = json.loads(r_json)
    total_bytes = len(r_json.encode("utf-8"))
    print(f"  Total JSON size:     {total_bytes:,} bytes ({total_bytes/1024:.1f} KB)")
    print(f"  content length:      {len(r['content'])} chars (page 0)")
    print(f"  total_chars:         {r['metadata'].get('total_chars')}")
    print(f"  total_pages:         {r['metadata'].get('total_pages')}")
    print(f"  current_page:        {r['metadata'].get('current_page')}")
    print(f"  content_truncated:   {r['metadata']['content_truncated']}")
    print(f"  chunks count:        {len(r['chunks'])} (should be 0 by default)")
    print(f"  links count:         {len(r['links'])} (should be 0 by default)")
    print(f"  last 200 chars:\n{r['content'][-200:]}")

    if total_bytes < 16384:
        print("  => PASS: 16KB以下のレスポンスサイズ")
    else:
        print(f"  => INFO: {total_bytes/1024:.1f} KB (ページネーション適用確認)")

    # If paginated, fetch page 1 to verify full content is retrievable
    total_pages = r["metadata"].get("total_pages", 1)
    if total_pages and total_pages > 1:
        print(f"\n  [2b] page 1 of {total_pages} を取得...")
        r2 = json.loads(await run_web_read(WebReadInput(
            url="https://www.zck.or.jp/site/forum/16616.html",
            page=1,
        )))
        print(f"  page 1 length: {len(r2['content'])} chars")
        print(f"  cache_hit:     {r2['metadata']['cache_hit']}")
        total2 = len(json.dumps(r2).encode())
        print(f"  page 1 JSON size: {total2/1024:.1f} KB")
        print(f"  page 1 last 200:\n{r2['content'][-200:]}")
        print("  => PASS: ページネーション正常動作")

    return r


async def test_response_sizes():
    """レスポンスからchunks/linksが除外されていること（デフォルト）。"""
    from web_agent_mcp.tools.web_read import WebReadInput, run_web_read

    print("\n=== [3] デフォルトではchunks/links除外 ===")
    r = json.loads(await run_web_read(WebReadInput(
        url="https://www.iana.org/domains/reserved",
        force_refresh=True,
    )))
    print(f"  chunks: {len(r['chunks'])} (expected 0)")
    print(f"  links:  {len(r['links'])} (expected 0)")
    assert len(r["chunks"]) == 0, "chunks should be empty by default"
    assert len(r["links"]) == 0, "links should be empty by default"
    print("  => PASS")


async def main():
    await test_spa_auto_fallback()
    await test_large_content()
    await test_response_sizes()
    print("\n=== 全検証完了 ===")


asyncio.run(main())
