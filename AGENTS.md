# Chat Converter Agent Orientation

## Purpose
This project captures shared LLM chats (ChatGPT, Gemini, Claude) and converts them into clean Markdown files stored in `output/`.

## Primary Interfaces
- HTTP API (FastAPI): `http://localhost:8080`
- MCP server (Model Context Protocol): tools + resources for agents

## MCP Tools
- `format_chat_from_url(url, notes="")`
  - Fetch a share URL, parse the chat, save Markdown.
- `upload_chat_html(html, notes="", source_url="", title="")`
  - Parse provided HTML and save Markdown.
- `list_chats(q="", platform="all", timeframe="all")`
  - Search/filter saved chats.
- `get_chat_markdown(filename)`
  - Return raw Markdown.
- `get_chat_json(filename)`
  - Return metadata + content.

## MCP Resources
- `orientation://chat-converter`
  - This file.

## Running Locally
1) Install deps
   - `uv sync`
   - `uv run python -m playwright install chromium`
2) Start HTTP API
   - `uv run uvicorn src.server:app --host 0.0.0.0 --port 8080`
3) Start MCP (stdio)
   - `uv run python -m src.mcp_server`
4) Start MCP (streamable HTTP)
   - `MCP_TRANSPORT=streamable-http MCP_HOST=0.0.0.0 MCP_PORT=8090 uv run python -m src.mcp_server`
   - Connect at `http://localhost:8090/mcp`

## Agent Workflow
1) Use `format_chat_from_url` (preferred) or `upload_chat_html`.
2) Call `list_chats` to find the saved filename.
3) Fetch content via `get_chat_markdown` or `get_chat_json`.

## Constraints and Notes
- ChatGPT requires a `/share/` link; non-share URLs will fail.
- Output files are saved to `output/` with YAML frontmatter.
- Do not attempt to read files outside `output/`.

## MCP Client Config (stdio example)
Use this as a starting point for local agents that launch the server:

```json
{
  "mcpServers": {
    "chat-converter": {
      "command": "uv",
      "args": ["run", "python", "-m", "src.mcp_server"]
    }
  }
}
```
