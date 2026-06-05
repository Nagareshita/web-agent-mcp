"""Integration tests for the 3 improvements."""
import asyncio
import json
import sys

sys.path.insert(0, "/app/src")


async def run_all_tests() -> None:
    print("=== 統合検証 ===\n")

    # --- Test 1: Playwright JS rendering ---
    print("[1] Playwright ブラウザ取得 (use_browser=True)")
    from web_agent_mcp.tools.web_read import WebReadInput, run_web_read

    r = json.loads(
        await run_web_read(
            WebReadInput(url="https://example.com", use_browser=True, force_refresh=True)
        )
    )
    assert r["metadata"]["used_browser"] is True, "used_browser should be True"
    assert r["title"], "title should not be empty"
    assert len(r["content"]) > 10, "content should not be empty"
    print(f"  title: {r['title']}")
    print(f"  used_browser: {r['metadata']['used_browser']}")
    print(f"  extraction_method: {r['extraction_method']}")
    print("  PASS\n")

    # --- Test 2: Pagination ---
    print("[2] 大容量コンテンツのページネーション (page_size=500)")
    r0 = json.loads(
        await run_web_read(
            WebReadInput(
                url="https://www.iana.org/domains/reserved",
                page_size=500,
                page=0,
                force_refresh=True,
            )
        )
    )
    total = r0["metadata"]["total_chars"]
    pages = r0["metadata"]["total_pages"]
    assert total and total > 500, f"total_chars should be > 500, got {total}"
    assert pages and pages > 1, f"total_pages should be > 1, got {pages}"
    assert len(r0["content"]) == 500, f"page 0 content should be 500 chars, got {len(r0['content'])}"
    print(f"  total_chars={total}, total_pages={pages}")
    print(f"  page 0 content length: {len(r0['content'])}")

    r1 = json.loads(
        await run_web_read(
            WebReadInput(
                url="https://www.iana.org/domains/reserved",
                page_size=500,
                page=1,
            )
        )
    )
    assert r1["metadata"]["cache_hit"] is True, "page 1 should be cache hit"
    assert r1["metadata"]["current_page"] == 1
    print(f"  page 1 cache_hit={r1['metadata']['cache_hit']}, current_page={r1['metadata']['current_page']}")
    print("  PASS\n")

    # --- Test 3: Deduplication ---
    print("[3] 重複ブロック除去 (_remove_duplicate_blocks)")
    from web_agent_mcp.extract.html import _remove_duplicate_blocks

    t = "Paragraph A\n\nParagraph A\n\nParagraph B"
    out = _remove_duplicate_blocks(t)
    assert out.count("Paragraph A") == 1, f"Expected 1, got {out.count('Paragraph A')}"
    assert "Paragraph B" in out
    print(f"  Input occurrences=2 → Output occurrences={out.count('Paragraph A')}")
    print("  PASS\n")

    print("=== 全テスト PASS ===")


asyncio.run(run_all_tests())
