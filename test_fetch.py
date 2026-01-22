"""
Test script to see what Playwright fetches from a Gemini link.
"""

import asyncio
from src.fetcher import fetch_url_content

async def main():
    url = "https://gemini.google.com/share/b9ea5bfbcf8d"
    print(f"Fetching: {url}")
    
    html = await fetch_url_content(url)
    
    # Save to file for inspection
    with open("/tmp/fetched_gemini.html", "w") as f:
        f.write(html)
    
    print(f"Saved to /tmp/fetched_gemini.html")
    print(f"HTML length: {len(html)} bytes")
    print("\nFirst 500 chars:")
    print(html[:500])

if __name__ == "__main__":
    asyncio.run(main())
