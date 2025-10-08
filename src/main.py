from tokenizer import tokenize_html
from indexer import InvertedIndex
from query_processor import boolean_query

# Fake docs (later replace with Jan.zip files)
docs = [
    ("doc1.html", "<html><body>cat dog cat</body></html>"),
    ("doc2.html", "<html><body>dog rat</body></html>")
]

# Build index
index = InvertedIndex()
for i, (name, html) in enumerate(docs):
    tokens, urls = tokenize_html(html)
    index.add_document(i, name, tokens, urls)

# Try Boolean queries
print("Q1 (cat OR dog):", boolean_query(index, ["cat", "dog"], "OR"))
print("Q2 (cat AND dog):", boolean_query(index, ["cat", "dog"], "AND"))
print("Q3 (cat BUT dog):", boolean_query(index, ["cat", "dog"], "BUT"))
