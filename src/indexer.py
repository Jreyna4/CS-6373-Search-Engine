from collections import defaultdict

class InvertedIndex:
    def __init__(self):
        # word -> { "df": int, "postings": [ {docID, tf, positions} ] }
        self.index = defaultdict(lambda: {"df": 0, "postings": []})
        # docID -> { "name": str, "length": int, "urls": list }
        self.doc_info = {}

    def add_document(self, docID, name, tokens, urls):
        """
        Add one document to the inverted index.
        docID: unique number
        name: filename or doc name
        tokens: list of words
        urls: list of hyperlinks
        """
        positions = defaultdict(list)

        # track positions of each word in the doc
        for pos, word in enumerate(tokens):
            positions[word].append(pos)

        # save doc info
        self.doc_info[docID] = {
            "name": name,
            "length": len(tokens),
            "urls": urls
        }

        # add to index
        for word, pos_list in positions.items():
            tf = len(pos_list)
            posting = {"docID": docID, "tf": tf, "positions": pos_list}
            self.index[word]["postings"].append(posting)

        # update df (document frequency)
        for word in positions.keys():
            self.index[word]["df"] = len(self.index[word]["postings"])
