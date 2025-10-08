def boolean_query(index, query_terms, query_type="OR"):
    """
    Process a simple Boolean query.
    index: InvertedIndex object
    query_terms: list of words, e.g., ["cat", "dog"]
    query_type: "OR", "AND", or "BUT"
    """
    sets = []

    for word in query_terms:
        if word in index.index:
            postings = {p["docID"] for p in index.index[word]["postings"]}
            sets.append(postings)
        else:
            sets.append(set())  # word not found in any doc

    if not sets:
        return set()

    if query_type == "OR":
        return set.union(*sets)
    elif query_type == "AND":
        return set.intersection(*sets)
    elif query_type == "BUT":
        if len(sets) >= 2:
            return sets[0] - sets[1]
        return sets[0]
    else:
        return set()
