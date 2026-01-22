"""
URL Fetcher - Uses Playwright to fetch JavaScript-rendered pages.
"""

import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout


async def fetch_url_content(url: str, timeout_ms: int = 30000) -> str:
    """
    Fetch a URL and return its fully-rendered HTML content.
    Uses Playwright to handle JavaScript-rendered pages.
    """
    if ("chatgpt.com/c/" in url or "chat.openai.com/c/" in url) and "/share/" not in url:
        raise ValueError(
            "ChatGPT conversation URLs require login cookies. Use a /share/ link instead."
        )
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        try:
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            # Navigate and wait for content
            wait_until = "networkidle"
            if "chatgpt.com/share" in url or "chat.openai.com/share" in url:
                wait_until = "domcontentloaded"
            await page.goto(url, wait_until=wait_until, timeout=timeout_ms)
            
            # Check if we hit Google's GDPR consent page
            current_url = page.url
            if "consent.google.com" in current_url:
                try:
                    # Wait for consent page to load
                    await page.wait_for_timeout(1000)
                    
                    # Try to click "Accept all" or "Reject all" button
                    # Common selectors for Google consent buttons
                    accept_selectors = [
                        'button:has-text("Accept all")',
                        'button:has-text("I agree")',
                        'button:has-text("Alle akzeptieren")',  # German
                        'button:has-text("Tout accepter")',  # French
                        'form[action*="consent"] button[type="submit"]',
                    ]
                    
                    clicked = False
                    for selector in accept_selectors:
                        try:
                            await page.click(selector, timeout=2000)
                            clicked = True
                            break
                        except:
                            continue
                    
                    if clicked:
                        # Wait for redirect back to actual content
                        await page.wait_for_load_state("networkidle", timeout=10000)
                        await page.wait_for_timeout(2000)
                except Exception as e:
                    # If consent handling fails, continue anyway
                    pass
            else:
                # Extra wait for dynamic content
                await page.wait_for_timeout(2000)

            # Wait for ChatGPT conversation to render if applicable
            if "chatgpt.com/share" in url or "chat.openai.com/share" in url:
                try:
                    await page.wait_for_selector(
                        '[data-message-author-role], article[data-testid^="conversation-turn"]',
                        timeout=5000
                    )
                except Exception:
                    pass
            
            # Get the full HTML
            html = await page.content()
            
            return html
            
        except PlaywrightTimeout:
            raise TimeoutError(f"Timeout fetching {url}")
        finally:
            await browser.close()


# Removed sync wrapper - use fetch_url_content directly with await
