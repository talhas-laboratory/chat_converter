"""
Count user vs assistant messages to verify we got everything
"""

from src.parser import ChatParser

# Read the fetched HTML
with open("/tmp/fetched_gemini.html", "r") as f:
    html = f.read()

parser = ChatParser(html, source_url="https://gemini.google.com/share/b9ea5bfbcf8d")
chat_data = parser.parse()

user_count = sum(1 for m in chat_data.messages if m.role == 'user')
assistant_count = sum(1 for m in chat_data.messages if m.role == 'assistant')

print(f"Total messages: {len(chat_data.messages)}")
print(f"User messages: {user_count}")
print(f"Assistant messages: {assistant_count}")
print(f"\nExpected: 34 total (17 user + 17 assistant)")

# Check first and last
if chat_data.messages:
    print(f"\nFirst message ({chat_data.messages[0].role}): {chat_data.messages[0].content[:80]}...")
    print(f"Last message ({chat_data.messages[-1].role}): {chat_data.messages[-1].content[-100:]}")
