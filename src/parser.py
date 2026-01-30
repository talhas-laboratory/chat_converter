"""
LLM Chat Parser - Extracts and formats chat content from LLM shared links.
"""

import re
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional
from bs4 import BeautifulSoup, Tag


@dataclass
class Message:
    """A single message in a chat."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: Optional[datetime] = None


@dataclass
class ChatData:
    """Parsed chat data with metadata."""
    title: str
    messages: list[Message] = field(default_factory=list)
    source_url: str = ""
    extracted_at: datetime = field(default_factory=datetime.now)
    notes: str = ""


class ChatParser:
    """Parse chat content from HTML."""
    
    # Common patterns for detecting user/assistant roles
    USER_PATTERNS = [
        r'\buser\b', r'\bhuman\b', r'\byou\b', r'\bme\b',
        'data-message-author-role="user"',
        'class="user"', 'class="human"',
    ]
    ASSISTANT_PATTERNS = [
        r'\bassistant\b', r'\bmodel\b', r'\bai\b', r'\bbot\b',
        r'\bchatgpt\b', r'\bgemini\b', r'\bclaude\b', r'\bgpt\b',
        'data-message-author-role="assistant"',
        'class="assistant"', 'class="model"',
    ]
    
    def __init__(self, html: str, source_url: str = ""):
        self.soup = BeautifulSoup(html, 'html.parser')
        self.source_url = source_url
    
    def parse(self) -> ChatData:
        """Parse the HTML and extract chat data."""
        title = self._extract_title()
        messages = self._extract_messages()

        # If title is generic or empty, try to derive from first user message
        generic_titles = [
            "direct access to google ai",
            "untitled chat",
            "gemini"
        ]
        
        # Check if cleaned title is in generic titles (exact match)
        cleaned_title = title.lower().strip()
        is_generic = not title or cleaned_title in generic_titles

        if is_generic and messages:
            # Find first user message
            user_msg = next((m for m in messages if m.role == 'user'), None)
            if user_msg:
                # Use first 50 chars of content
                new_title = user_msg.content.strip().split('\n')[0]
                # Remove markdown formatting if simple
                new_title = new_title.replace('#', '').replace('*', '').strip()
                if len(new_title) > 50:
                    new_title = new_title[:47] + "..."
                
                if new_title:
                    title = new_title
        
        return ChatData(
            title=title,
            messages=messages,
            source_url=self.source_url,
            extracted_at=datetime.now(),
        )
    
    def _extract_title(self) -> str:
        """Extract chat title from page."""
        # Try <title> tag
        if self.soup.title and self.soup.title.string:
            title = self.soup.title.string.strip()
            
            # Remove ltr mark if present
            title = title.replace('\u200e', '')
            
            # Clean common prefixes
            # Gemini often prefixes with "Gemini - "
            if title.startswith("Gemini - "):
                title = title[9:]
                
            # Clean common suffixes
            for suffix in [' - ChatGPT', ' - Gemini', ' | Claude', ' - Claude']:
                if title.endswith(suffix):
                    title = title[:-len(suffix)]
            return title.strip()
        
        # Try first h1
        h1 = self.soup.find('h1')
        if h1:
            return h1.get_text(strip=True)
        
        return "Untitled Chat"
    
    def _extract_messages(self) -> list[Message]:
        """Extract messages from the chat."""
        messages = []
        
        # Strategy 1: Try ChatGPT-style structure
        messages = self._try_chatgpt_structure()
        if messages:
            return messages
        
        # Strategy 2: Try Gemini-style structure
        messages = self._try_gemini_structure()
        if messages:
            return messages
        
        # Strategy 3: Generic heuristic - look for alternating content blocks
        messages = self._try_generic_structure()
        return messages
    
    def _try_chatgpt_structure(self) -> list[Message]:
        """Parse ChatGPT shared link structure."""
        messages = []

        # ChatGPT share pages wrap turns in article elements
        turns = self.soup.find_all('article', attrs={
            'data-testid': lambda v: v and v.startswith('conversation-turn')
        })
        if turns:
            for turn in turns:
                role = turn.get('data-turn')
                if role not in ("user", "assistant"):
                    role = self._detect_role(turn)

                role_nodes = []
                for elem in turn.find_all(attrs={"data-message-author-role": True}):
                    if elem.get("data-message-author-role") == role:
                        role_nodes.append(elem)

                if role_nodes:
                    content = self._combine_unique_contents(role_nodes)
                else:
                    content = self._extract_formatted_content(turn)

                if content.strip():
                    messages.append(Message(role=role, content=content))

            if messages:
                return messages

        # Fallback: ChatGPT uses data-message-author-role attribute
        for elem in self.soup.find_all(attrs={"data-message-author-role": True}):
            role_attr = elem.get("data-message-author-role", "")
            role = "user" if role_attr == "user" else "assistant"
            content = self._extract_formatted_content(elem)
            if content.strip():
                messages.append(Message(role=role, content=content))

        return messages
    
    def _try_gemini_structure(self) -> list[Message]:
        """Parse Gemini shared link structure."""
        # Preferred: share-turn-viewer preserves turn order
        turns = self.soup.find_all('share-turn-viewer')
        if turns:
            ordered_messages: list[Message] = []
            for turn in turns:
                user_containers = turn.find_all(class_='user-query-container')
                user_content = self._select_best_content(user_containers)
                if user_content:
                    ordered_messages.append(Message(role='user', content=user_content))

                response_containers = turn.find_all(class_='response-container')
                assistant_contents = []
                for container in response_containers:
                    message_content = container.find(class_='message-content')
                    target = message_content if message_content else container
                    assistant_contents.append(self._extract_formatted_content(target))
                assistant_content = self._select_best_text(assistant_contents)
                if assistant_content:
                    ordered_messages.append(Message(role='assistant', content=assistant_content))

            if ordered_messages:
                return ordered_messages

        # Fallback: collect in DOM order, de-duplicate
        ordered_messages: list[Message] = []
        def is_gemini_message(tag: Tag) -> bool:
            if not tag or not tag.has_attr('class'):
                return False
            classes = tag.get('class', [])
            return 'user-query-container' in classes or 'message-content' in classes

        for elem in self.soup.find_all(is_gemini_message):
            if 'user-query-container' in elem.get('class', []):
                content = self._extract_formatted_content(elem)
                role = 'user'
            else:
                if elem.find_parent(class_='user-query-container'):
                    continue
                content = self._extract_formatted_content(elem)
                role = 'assistant'

            if content.strip() and len(content) > 3:
                if not ordered_messages or ordered_messages[-1].content != content:
                    ordered_messages.append(Message(role=role, content=content))

        return ordered_messages
    
    def _try_generic_structure(self) -> list[Message]:
        """Generic parsing using heuristics."""
        messages = []
        
        # Look for any elements with user/assistant indicators
        for elem in self.soup.find_all(['div', 'article', 'section']):
            elem_str = str(elem)[:500].lower()  # Check first 500 chars
            
            is_user = any(re.search(p, elem_str, re.I) for p in self.USER_PATTERNS[:4])
            is_assistant = any(re.search(p, elem_str, re.I) for p in self.ASSISTANT_PATTERNS[:4])
            
            if is_user or is_assistant:
                role = "user" if is_user else "assistant"
                content = self._extract_formatted_content(elem)
                if content.strip() and len(content) > 10:
                    # Avoid duplicates from nested elements
                    if not messages or content != messages[-1].content:
                        messages.append(Message(role=role, content=content))
        
        return messages
    
    def _detect_role(self, elem: Tag) -> str:
        """Detect if an element is from user or assistant."""
        elem_str = str(elem)[:1000].lower()
        
        user_score = sum(1 for p in self.USER_PATTERNS if re.search(p, elem_str, re.I))
        assistant_score = sum(1 for p in self.ASSISTANT_PATTERNS if re.search(p, elem_str, re.I))
        
        return "user" if user_score > assistant_score else "assistant"
    
    def _extract_formatted_content(self, elem: Tag) -> str:
        """Extract content preserving tables, lists, and code blocks."""
        # Work on a local copy so we can replace nodes safely.
        fragment = BeautifulSoup(str(elem), 'html.parser')

        # Remove non-content/UI elements
        for tag in fragment.find_all(['script', 'style', 'noscript', 'svg', 'button', 'mat-icon', 'img']):
            tag.decompose()

        # Inline code first so list/table extraction keeps backticks.
        for code in fragment.find_all('code'):
            if code.parent and code.parent.name == 'pre':
                continue
            code.replace_with(f"`{code.get_text(strip=True)}`")

        # Convert code blocks
        for pre in fragment.find_all('pre'):
            code_text = pre.get_text()
            lang = ''
            if pre.code and pre.code.get('class'):
                lang = pre.code.get('class')[0].replace('language-', '')
            pre.replace_with(f"\n```{lang}\n{code_text}\n```\n")

        # Convert tables
        for table in fragment.find_all('table'):
            table.replace_with(self._table_to_markdown(table))

        # Convert lists
        for list_elem in fragment.find_all(['ul', 'ol']):
            list_elem.replace_with(self._list_to_markdown(list_elem))

        text = fragment.get_text(separator='\n', strip=True)
        return self._normalize_whitespace(text)

    def _normalize_whitespace(self, text: str) -> str:
        """Normalize whitespace while preserving paragraph breaks."""
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        lines = [line.rstrip() for line in text.split('\n')]
        normalized = []
        blank = False
        for line in lines:
            if not line.strip():
                if not blank:
                    normalized.append('')
                blank = True
            else:
                normalized.append(line)
                blank = False
        return '\n'.join(normalized).strip()

    def _select_best_content(self, elems: list[Tag]) -> str:
        """Select the best content from a list of duplicated elements."""
        contents = [self._extract_formatted_content(elem) for elem in elems]
        return self._select_best_text(contents)

    def _select_best_text(self, contents: list[str]) -> str:
        """Choose the most complete unique text from a list."""
        seen = set()
        unique = []
        for content in contents:
            normalized = self._normalize_whitespace(content)
            if not normalized or normalized in seen:
                continue
            unique.append(normalized)
            seen.add(normalized)
        if not unique:
            return ""
        return max(unique, key=len)

    def _combine_unique_contents(self, elems: list[Tag]) -> str:
        """Combine unique contents from multiple elements in order."""
        combined = []
        seen = set()
        for elem in elems:
            content = self._normalize_whitespace(self._extract_formatted_content(elem))
            if not content or content in seen:
                continue
            combined.append(content)
            seen.add(content)
        return "\n\n".join(combined)
    
    def _table_to_markdown(self, table: Tag) -> str:
        """Convert HTML table to Markdown table."""
        rows = []
        
        for tr in table.find_all('tr'):
            cells = []
            for cell in tr.find_all(['th', 'td']):
                cells.append(cell.get_text(strip=True).replace('|', '\\|'))
            if cells:
                rows.append('| ' + ' | '.join(cells) + ' |')
        
        if len(rows) >= 1:
            # Add header separator after first row
            num_cols = rows[0].count('|') - 1
            separator = '| ' + ' | '.join(['---'] * num_cols) + ' |'
            rows.insert(1, separator)
        
        return '\n' + '\n'.join(rows) + '\n'
    
    def _list_to_markdown(self, list_elem: Tag, indent: int = 0) -> str:
        """Convert HTML list to Markdown list."""
        lines = []
        is_ordered = list_elem.name == 'ol'
        
        for i, li in enumerate(list_elem.find_all('li', recursive=False), 1):
            prefix = f"{i}." if is_ordered else "-"
            indent_str = "  " * indent
            
            # Get direct text content
            text = li.get_text(strip=True)
            lines.append(f"{indent_str}{prefix} {text}")
            
            # Handle nested lists
            for nested in li.find_all(['ul', 'ol'], recursive=False):
                lines.append(self._list_to_markdown(nested, indent + 1))
        
        return '\n'.join(lines)
