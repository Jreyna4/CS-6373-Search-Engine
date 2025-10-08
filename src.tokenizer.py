from bs4 import BeautifulSoup
import re

stopwords = {"a", "an", "the", "of", "and", "in", "on", "for", "to"}

def tokenize_file(file_path):
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        html_content = f.read()

    soup = BeautifulSoup(html_content, "html.parser")

    # extract text
    text = soup.get_text(separator=" ")

    # extract links
    urls = [a['href'] for a in soup.find_all('a', href=True)]

    # tokenize into words
    tokens = re.findall(r"\b[a-zA-Z]+\b", text.lower())
    tokens = [t for t in tokens if t not in stopwords]

    return tokens, urls
