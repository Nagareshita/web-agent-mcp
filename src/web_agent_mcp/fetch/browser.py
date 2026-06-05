"""Playwright-based headless browser fetch for JavaScript-rendered pages."""
from __future__ import annotations

from web_agent_mcp.fetch.safety import validate_url
from web_agent_mcp.fetch.http import FetchResult

_DEFAULT_VIEWPORT = {"width": 1280, "height": 900}
_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


async def fetch_url_browser(
    url: str,
    timeout_seconds: int = 30,
) -> FetchResult:
    """Fetch a URL using Playwright Chromium headless browser.

    Waits for network idle so JavaScript-rendered content is fully loaded.
    Raises ImportError if playwright is not installed.
    Raises ValueError for SSRF violations.
    """
    validate_url(url)

    try:
        from playwright.async_api import async_playwright, Error as PlaywrightError
    except ImportError as exc:
        raise ImportError(
            "playwright is not installed. "
            "Install it with: pip install playwright && playwright install chromium"
        ) from exc

    timeout_ms = timeout_seconds * 1000

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        try:
            context = await browser.new_context(
                user_agent=_DEFAULT_USER_AGENT,
                viewport=_DEFAULT_VIEWPORT,
                java_script_enabled=True,
                accept_downloads=False,
                extra_http_headers={
                    "Accept-Language": "ja,en;q=0.9",
                },
            )
            page = await context.new_page()

            response = await page.goto(
                url,
                timeout=timeout_ms,
                wait_until="networkidle",
            )

            if response is None:
                raise RuntimeError(f"No response received from {url}")

            # Extra wait for async-rendered components (Vue/React/Angular) that
            # continue populating DOM bindings after networkidle fires.
            await page.wait_for_timeout(2000)

            status_code = response.status
            content_type = response.headers.get("content-type", "text/html")
            final_url = page.url

            # Get rendered HTML (after JS execution)
            html_content = await page.content()
            content_bytes = html_content.encode("utf-8", errors="replace")

            return FetchResult(
                content=content_bytes,
                content_type=content_type,
                status_code=status_code,
                final_url=final_url,
            )
        finally:
            await browser.close()
