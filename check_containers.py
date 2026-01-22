from bs4 import BeautifulSoup

with open('/tmp/fetched_gemini.html') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')
queries = soup.find_all(class_='query-container')
results = soup.find_all(class_='result-container')

print(f'query-containers: {len(queries)}')
print(f'result-containers: {len(results)}')
print(f'Total expected messages: {len(queries) + len(results)}')

# Check first query
if queries:
    first_query = queries[0].find(class_='query-content')
    if first_query:
        print(f'\nFirst query text: {first_query.get_text(strip=True)[:100]}')
