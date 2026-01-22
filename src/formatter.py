"""
Markdown Formatter - Converts parsed chat data to clean Markdown with YAML frontmatter.
"""

from datetime import datetime
from pathlib import Path
import re

from .parser import ChatData


def format_to_markdown(chat: ChatData, notes: str = "") -> str:
    """Format chat data to Markdown with YAML frontmatter."""
    
    # Build YAML frontmatter
    frontmatter = [
        "---",
        f'title: "{_escape_yaml(chat.title)}"',
        f'date: {chat.extracted_at.strftime("%Y-%m-%d")}',
        f'time: "{chat.extracted_at.strftime("%H:%M")}"',
    ]
    
    if chat.source_url:
        frontmatter.append(f'source_url: "{chat.source_url}"')
    
    if notes:
        # Handle multi-line notes
        if '\n' in notes:
            frontmatter.append('notes: |')
            for line in notes.split('\n'):
                frontmatter.append(f'  {line}')
        else:
            frontmatter.append(f'notes: "{_escape_yaml(notes)}"')
    
    frontmatter.append("---")
    frontmatter.append("")
    
    # Build message content
    content = []
    for msg in chat.messages:
        role_header = "## User" if msg.role == "user" else "## Assistant"
        content.append(role_header)
        content.append("")
        content.append(msg.content)
        content.append("")
        content.append("---")
        content.append("")
    
    # Remove trailing separator
    if content and content[-2] == "---":
        content = content[:-2]
    
    return '\n'.join(frontmatter + content)


def _escape_yaml(s: str) -> str:
    """Escape special characters for YAML strings."""
    return s.replace('"', '\\"').replace('\n', ' ')


def generate_filename(chat: ChatData) -> str:
    """Generate a safe filename from chat data."""
    date_str = chat.extracted_at.strftime("%Y-%m-%d")
    
    # Sanitize title for filename
    safe_title = re.sub(r'[^\w\s-]', '', chat.title)
    safe_title = re.sub(r'\s+', '-', safe_title).strip('-').lower()
    safe_title = safe_title[:50]  # Limit length
    
    if not safe_title:
        safe_title = "chat"
    
    return f"{date_str}_{safe_title}.md"


def save_chat(chat: ChatData, notes: str, output_dir: Path) -> Path:
    """Save formatted chat to file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    content = format_to_markdown(chat, notes)
    filename = generate_filename(chat)
    filepath = output_dir / filename
    
    # Handle duplicates
    counter = 1
    while filepath.exists():
        base = filename.rsplit('.', 1)[0]
        filepath = output_dir / f"{base}_{counter}.md"
        counter += 1
    
    filepath.write_text(content, encoding='utf-8')
    return filepath
