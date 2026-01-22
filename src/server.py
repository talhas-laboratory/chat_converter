"""
FastAPI Server - Web app for formatting LLM chats.
"""

from datetime import datetime, timedelta
from pathlib import Path
import re
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .fetcher import fetch_url_content
from .parser import ChatParser
from .formatter import format_to_markdown, save_chat


# Configuration
OUTPUT_DIR = Path(__file__).parent.parent / "output"
STATIC_DIR = Path(__file__).parent.parent / "static"

app = FastAPI(title="Chat Converter")


class FormatRequest(BaseModel):
    url: str
    notes: str = ""


class FormatResponse(BaseModel):
    success: bool
    filename: str = ""
    title: str = ""
    message_count: int = 0
    preview: str = ""
    error: str = ""


class UploadRequest(BaseModel):
    html: str
    notes: str = ""
    source_url: str = ""
    title: str = ""


class ChatInfo(BaseModel):
    filename: str
    title: str
    date: float
    size: int
    platform: str = "unknown"


class ChatDocument(BaseModel):
    filename: str
    title: str
    date: float
    size: int
    platform: str = "unknown"
    source_url: str = ""
    notes: str = ""
    content: str = ""
    extracted_at: str = ""
    frontmatter: dict[str, str] = Field(default_factory=dict)


_INDEX_CACHE: list[dict] = []
_INDEX_STATE: tuple[float, int] | None = None


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse minimal YAML frontmatter and return metadata + body."""
    if not content.startswith("---"):
        return {}, content

    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, content

    end_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break

    if end_idx is None:
        return {}, content

    meta_lines = lines[1:end_idx]
    body = "\n".join(lines[end_idx + 1:]).lstrip("\n")
    meta: dict[str, str] = {}
    i = 0
    while i < len(meta_lines):
        line = meta_lines[i]
        if not line.strip():
            i += 1
            continue

        if line.startswith("notes: |"):
            i += 1
            notes_lines = []
            while i < len(meta_lines) and meta_lines[i].startswith("  "):
                notes_lines.append(meta_lines[i][2:])
                i += 1
            meta["notes"] = "\n".join(notes_lines).strip()
            continue

        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1].replace('\\"', '"')
            meta[key] = value
        i += 1

    return meta, body


def _parse_frontmatter_datetime(meta: dict, fallback_timestamp: float) -> datetime:
    """Parse date/time from frontmatter or fall back to file timestamp."""
    date_str = meta.get("date", "")
    time_str = meta.get("time", "")
    if date_str:
        try:
            if time_str:
                return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            return datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            pass
    return datetime.fromtimestamp(fallback_timestamp)


def _detect_platform(source_url: str, title: str, filename: str) -> str:
    """Infer chat platform from URL/title/filename."""
    host = ""
    if source_url:
        host = urlparse(source_url).netloc.lower()
    haystack = " ".join([host, source_url, title, filename]).lower()

    if any(token in haystack for token in ("chat.openai.com", "chatgpt.com", "openai.com")):
        return "chatgpt"
    if any(token in haystack for token in ("gemini.google.com", "gemini", "ai.google.com", "bard.google.com")):
        return "gemini"
    if any(token in haystack for token in ("claude.ai", "anthropic.com", "claude")):
        return "claude"
    return "unknown"


def _build_index() -> list[dict]:
    """Index saved chats for search and filtering."""
    global _INDEX_CACHE, _INDEX_STATE
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    files = list(OUTPUT_DIR.glob("*.md"))
    latest_mtime = max((f.stat().st_mtime for f in files), default=0)
    current_state = (latest_mtime, len(files))

    if _INDEX_STATE == current_state:
        return _INDEX_CACHE

    index: list[dict] = []
    for chat_file in sorted(files, reverse=True):
        content = chat_file.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(content)
        title = meta.get("title", "Untitled")
        source_url = meta.get("source_url", "")
        notes = meta.get("notes", "")
        size = chat_file.stat().st_size
        extracted_at = _parse_frontmatter_datetime(meta, chat_file.stat().st_mtime)
        platform = _detect_platform(source_url, title, chat_file.name)
        search_blob = " ".join([title, notes, body, chat_file.name, source_url]).lower()

        index.append({
            "filename": chat_file.name,
            "title": title,
            "date": extracted_at.timestamp(),
            "size": size,
            "platform": platform,
            "search_blob": search_blob,
        })

    index.sort(key=lambda entry: entry["date"], reverse=True)

    _INDEX_CACHE = index
    _INDEX_STATE = current_state
    return index


def _filter_index(entries: list[dict], query: str, platform: str, timeframe: str) -> list[dict]:
    filtered = entries

    query = query.strip()
    if query:
        terms = [term for term in re.split(r"\s+", query.lower()) if term]
        if terms:
            filtered = [
                entry for entry in filtered
                if all(term in entry["search_blob"] for term in terms)
            ]

    platform = platform.strip().lower()
    if platform and platform != "all":
        filtered = [entry for entry in filtered if entry["platform"] == platform]

    timeframe = timeframe.strip().lower()
    if timeframe and timeframe != "all":
        days = {
            "7d": 7,
            "30d": 30,
            "90d": 90,
            "365d": 365,
        }.get(timeframe)
        if days:
            cutoff = datetime.now() - timedelta(days=days)
            filtered = [entry for entry in filtered if entry["date"] >= cutoff.timestamp()]

    return filtered


def _load_chat_document(filename: str) -> dict:
    """Load a saved chat with metadata and content."""
    filepath = OUTPUT_DIR / filename
    if not filepath.exists() or not filepath.is_file():
        raise HTTPException(status_code=404, detail="Chat not found")

    content = filepath.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(content)
    title = meta.get("title", "Untitled")
    source_url = meta.get("source_url", "")
    notes = meta.get("notes", "")
    extracted_at = _parse_frontmatter_datetime(meta, filepath.stat().st_mtime)
    platform = _detect_platform(source_url, title, filename)

    return {
        "filename": filename,
        "title": title,
        "date": extracted_at.timestamp(),
        "size": filepath.stat().st_size,
        "platform": platform,
        "source_url": source_url,
        "notes": notes,
        "content": body,
        "extracted_at": extracted_at.isoformat(),
        "frontmatter": meta,
    }


@app.post("/api/format", response_model=FormatResponse)
async def format_chat(request: FormatRequest):
    """Fetch a URL, parse the chat, and save as Markdown."""
    try:
        # Fetch the page content
        html = await fetch_url_content(request.url)
        
        # Parse the chat
        parser = ChatParser(html, source_url=request.url)
        chat_data = parser.parse()
        
        if not chat_data.messages:
            return FormatResponse(
                success=False,
                error="No messages found. The page may require login or have a different structure."
            )
        
        # Add notes
        chat_data.notes = request.notes
        
        # Save to file
        filepath = save_chat(chat_data, request.notes, OUTPUT_DIR)
        
        # Generate preview (first 500 chars)
        content = format_to_markdown(chat_data, request.notes)
        preview = content[:500] + "..." if len(content) > 500 else content
        
        return FormatResponse(
            success=True,
            filename=filepath.name,
            title=chat_data.title,
            message_count=len(chat_data.messages),
            preview=preview,
        )
        
    except TimeoutError as e:
        return FormatResponse(success=False, error=str(e))
    except Exception as e:
        return FormatResponse(success=False, error=f"Error: {str(e)}")


@app.post("/api/upload", response_model=FormatResponse)
async def upload_chat(request: UploadRequest):
    """Upload HTML content, parse the chat, and save as Markdown."""
    try:
        html = request.html.strip()
        if not html:
            return FormatResponse(success=False, error="HTML content is required.")

        parser = ChatParser(html, source_url=request.source_url)
        chat_data = parser.parse()

        title = request.title.strip()
        if title:
            chat_data.title = title

        if not chat_data.messages:
            return FormatResponse(
                success=False,
                error="No messages found. The HTML may have a different structure."
            )

        chat_data.notes = request.notes
        filepath = save_chat(chat_data, request.notes, OUTPUT_DIR)

        content = format_to_markdown(chat_data, request.notes)
        preview = content[:500] + "..." if len(content) > 500 else content

        return FormatResponse(
            success=True,
            filename=filepath.name,
            title=chat_data.title,
            message_count=len(chat_data.messages),
            preview=preview,
        )

    except Exception as e:
        return FormatResponse(success=False, error=f"Error: {str(e)}")


@app.get("/api/chats")
async def list_chats(q: str = "", platform: str = "all", timeframe: str = "all"):
    """List all saved chats (with optional search and filters)."""
    entries = _build_index()
    filtered = _filter_index(entries, q, platform, timeframe)

    return [
        ChatInfo(
            filename=entry["filename"],
            title=entry["title"],
            date=entry["date"],
            size=entry["size"],
            platform=entry["platform"],
        )
        for entry in filtered
    ]


@app.get("/api/chats/{filename}/json", response_model=ChatDocument)
async def get_chat_json(filename: str):
    """Get a specific chat as JSON with metadata and content."""
    return ChatDocument(**_load_chat_document(filename))


@app.get("/api/chats/{filename}")
async def get_chat(filename: str):
    """Get a specific chat's content."""
    filepath = OUTPUT_DIR / filename
    
    if not filepath.exists() or not filepath.is_file():
        raise HTTPException(status_code=404, detail="Chat not found")
    
    return FileResponse(filepath, media_type="text/markdown")


# Serve static files
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
