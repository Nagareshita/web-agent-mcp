"""Measure actual response sizes and diagnose large content issue."""
import asyncio
import json
import sys

sys.path.insert(0, "/app/src")


async def main():
    from web_agent_mcp.tools.web_read import WebReadInput, run_web_read

    print("=== zck.or.jp response size analysis ===")
    r_json = await run_web_read(WebReadInput(
        url="https://www.zck.or.jp/site/forum/16616.html",
        force_refresh=True,
    ))
    r = json.loads(r_json)
    total_bytes = len(r_json.encode("utf-8"))
    content_bytes = len(r["content"].encode("utf-8"))
    chunks_bytes = len(json.dumps(r["chunks"]).encode("utf-8"))
    links_bytes = len(json.dumps(r["links"]).encode("utf-8"))
    print(f"  Total JSON size:    {total_bytes:,} bytes ({total_bytes/1024:.1f} KB)")
    print(f"  content field:      {content_bytes:,} bytes ({content_bytes/1024:.1f} KB)")
    print(f"  chunks field:       {chunks_bytes:,} bytes ({chunks_bytes/1024:.1f} KB)  ({len(r['chunks'])} chunks)")
    print(f"  links field:        {links_bytes:,} bytes ({links_bytes/1024:.1f} KB)  ({len(r['links'])} links)")
    print(f"  content_truncated:  {r['metadata']['content_truncated']}")
    print(f"  content length:     {len(r['content'])} chars")

    # Now check a bigger page
    print("\n=== iana.org domains/reserved response size ===")
    r2_json = await run_web_read(WebReadInput(
        url="https://www.iana.org/domains/reserved",
        force_refresh=True,
    ))
    r2 = json.loads(r2_json)
    total2 = len(r2_json.encode("utf-8"))
    print(f"  Total JSON size:    {total2:,} bytes ({total2/1024:.1f} KB)")
    print(f"  content field:      {len(r2['content'].encode())/1024:.1f} KB")
    print(f"  chunks:             {len(r2['chunks'])} chunks")
    print(f"  links:              {len(r2['links'])} links")


asyncio.run(main())
