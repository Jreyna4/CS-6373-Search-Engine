from tokenizer import tokenize_html
from indexer import InvertedIndex

# Fake documents for now (so you don’t need Jan.zip yet)
docs = [
    ("doc1.html", "<html><body>cat dog cat</body></html>"),
    ("doc2.html", "<html><body>dog rat</body></html>")
]

# Build the index
index = InvertedIndex()

for i, (name, html) in enumerate(docs):
    tokens, urls = tokenize_html(html)   # use tokenizer
    index.add_document(i, name, tokens, urls)

# Print some checks
print("Doc info:", index.doc_info)
print("Index for 'cat':", index.index.get("cat"))
print("Index for 'dog':", index.index.get("dog"))
print("Index for 'rat':", index.index.get("rat"))
