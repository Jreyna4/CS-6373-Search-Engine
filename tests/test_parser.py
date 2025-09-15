
# Minimal smoke test (no Jan.zip in CI environment). Ensures the module imports.
def test_import():
    import mysearch.parser as p
    assert hasattr(p, "build_index")
    assert hasattr(p, "search_files")
