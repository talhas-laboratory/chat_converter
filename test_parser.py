"""
Test if parser can extract messages from fetched Gemini HTML.
"""

from src.parser import ChatParser

# Read the fetched HTML
with open("/tmp/fetched_gemini.html", "r") as f:
    html = f.read()

parser = ChatParser(html, source_url="https://gemini.google.com/share/b9ea5bfbcf8d")
chat_data = parser.parse()

print(f"Title: {chat_data.title}")
print(f"Messages found: {len(chat_data.messages)}")
print("\nFirst 3 messages:")
for i, msg in enumerate(chat_data.messages[:3]):
    print(f"\n--- Message {i+1} ({msg.role}) ---")
    print(msg.content[:200] + "..." if len(msg.content) > 200 else msg.content)
