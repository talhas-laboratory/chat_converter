"""
MCP server for Chat Converter tools and resources.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from mcp.server.fastmcp import FastMCP

from .fetcher import fetch_url_content
from .formatter import format_to_markdown, save_chat
from .parser import ChatParser
from .server import OUTPUT_DIR, _build_index, _filter_index, _load_chat_document

ORIENTATION_PATH = Path(__file__).parent.parent / "AGENTS.md"

mcp = FastMCP("Chat Converter", json_response=True)


def _preview_markdown(content: str, limit: int = 500) -> str:
    if len(content) <= limit:
        return content
    return content[:limit] + "..."


def _safe_output_path(filename: str) -> Path:
    if not filename:
        raise ValueError("filename is required")
    if not filename.endswith(".md"):
        raise ValueError("filename must end with .md")
    output_root = OUTPUT_DIR.resolve()
    candidate = (OUTPUT_DIR / filename).resolve()
    if output_root not in candidate.parents and candidate != output_root:
        raise ValueError("invalid filename")
    return candidate


def _error_response(message: str) -> dict[str, Any]:
    return {
        "success": False,
        "filename": "",
        "title": "",
        "message_count": 0,
        "preview": "",
        "error": message,
    }


@mcp.resource("orientation://chat-converter")
def get_orientation() -> str:
    """Agent orientation for this project."""
    try:
        return ORIENTATION_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "Chat Converter agent orientation file is missing."


@mcp.tool()
async def format_chat_from_url(url: str, notes: str = "") -> dict[str, Any]:
    """Fetch a share URL, parse the chat, and save as Markdown."""
    try:
        html = await fetch_url_content(url)
        parser = ChatParser(html, source_url=url)
        chat_data = parser.parse()

        if not chat_data.messages:
            return _error_response(
                "No messages found. The page may require login or have a different structure."
            )

        chat_data.notes = notes
        filepath = save_chat(chat_data, notes, OUTPUT_DIR)

        content = format_to_markdown(chat_data, notes)
        preview = _preview_markdown(content)

        return {
            "success": True,
            "filename": filepath.name,
            "title": chat_data.title,
            "message_count": len(chat_data.messages),
            "preview": preview,
            "error": "",
        }
    except TimeoutError as exc:
        return _error_response(str(exc))
    except Exception as exc:
        return _error_response(f"Error: {exc}")


@mcp.tool()
def upload_chat_html(
    html: str,
    notes: str = "",
    source_url: str = "",
    title: str = "",
) -> dict[str, Any]:
    """Upload HTML content, parse the chat, and save as Markdown."""
    try:
        html = html.strip()
        if not html:
            return _error_response("HTML content is required.")

        parser = ChatParser(html, source_url=source_url)
        chat_data = parser.parse()

        title = title.strip()
        if title:
            chat_data.title = title

        if not chat_data.messages:
            return _error_response("No messages found. The HTML may have a different structure.")

        chat_data.notes = notes
        filepath = save_chat(chat_data, notes, OUTPUT_DIR)

        content = format_to_markdown(chat_data, notes)
        preview = _preview_markdown(content)

        return {
            "success": True,
            "filename": filepath.name,
            "title": chat_data.title,
            "message_count": len(chat_data.messages),
            "preview": preview,
            "error": "",
        }
    except Exception as exc:
        return _error_response(f"Error: {exc}")


@mcp.tool()
def list_chats(q: str = "", platform: str = "all", timeframe: str = "all") -> list[dict[str, Any]]:
    """List saved chats with optional search and filters."""
    entries = _build_index()
    filtered = _filter_index(entries, q, platform, timeframe)
    return [
        {
            "filename": entry["filename"],
            "title": entry["title"],
            "date": entry["date"],
            "size": entry["size"],
            "platform": entry["platform"],
        }
        for entry in filtered
    ]


@mcp.tool()
def get_chat_markdown(filename: str) -> str:
    """Return the raw Markdown for a saved chat."""
    filepath = _safe_output_path(filename)
    if not filepath.exists() or not filepath.is_file():
        raise ValueError("Chat not found")
    return filepath.read_text(encoding="utf-8")


@mcp.tool()
def get_chat_json(filename: str) -> dict[str, Any]:
    """Return chat metadata and content as structured JSON."""
    try:
        return _load_chat_document(filename)
    except HTTPException as exc:
        raise ValueError(exc.detail) from exc


def _resolve_transport(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"streamable-http", "streamable_http", "http"}:
        return "streamable-http"
    if normalized in {"sse", "stdio"}:
        return normalized
    return "stdio"


def main() -> None:
    transport = _resolve_transport(os.getenv("MCP_TRANSPORT", "stdio"))

    if transport in ("streamable-http", "sse"):
        # For HTTP-based transports, use uvicorn directly with the FastMCP app
        import uvicorn
        
        host = os.getenv("MCP_HOST", "127.0.0.1")
        port = int(os.getenv("MCP_PORT", "8000"))
        
        # Get the ASGI app from FastMCP using the correct method
        app = mcp.streamable_http_app()
        
        uvicorn.run(app, host=host, port=port)
        return

    # For stdio transport, use the standard run method
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
