import numpy as np
import pytest

from cursor_case_mini.indexing import (
    EMBED_DIM,
    CodebaseIndex,
    chunk_code,
    content_hash,
    embed_text,
    merkle_root,
    obfuscate_path,
)

PY_SRC = (
    "def connect(host):\n"
    "    return Client(host)\n"
    "\n"
    "\n"
    "def query(sql):\n"
    "    return conn.execute(sql)\n"
    "\n"
    "\n"
    "class Pool:\n"
    "    def __init__(self, size):\n"
    "        self.size = size\n"
)

BIG_SRC = "\n".join(f"line_{i} = {i}" for i in range(100))


class TestChunk:
    def test_empty_source(self):
        assert chunk_code("") == []

    def test_respects_blank_line_boundaries(self):
        chunks = chunk_code(PY_SRC)
        # 三个逻辑块：connect / query / Pool
        assert len(chunks) == 3

    def test_line_numbers_cover_source(self):
        chunks = chunk_code(PY_SRC)
        covered: set[int] = set()
        for s, e, _ in chunks:
            covered.update(range(s, e + 1))
        for i, ln in enumerate(PY_SRC.split("\n")):
            if ln.strip():
                assert i in covered  # 每个非空行都被恰好一个块覆盖

    def test_max_lines_cap(self):
        chunks = chunk_code(BIG_SRC, max_lines=10)
        assert all((e - s + 1) <= 10 for s, e, _ in chunks)

    def test_no_empty_chunks(self):
        src = "a\n\n\n\nb"
        assert all(c[2].strip() for c in chunk_code(src))

    def test_deterministic(self):
        assert chunk_code(PY_SRC) == chunk_code(PY_SRC)


class TestEmbed:
    def test_shape_and_norm(self):
        v = embed_text("hello world")
        assert v.shape == (EMBED_DIM,)
        assert abs(np.linalg.norm(v) - 1.0) < 1e-9

    def test_deterministic(self):
        assert np.allclose(embed_text("foo bar"), embed_text("foo bar"))

    def test_similarity_ordering(self):
        a = embed_text("database connection pool")
        b = embed_text("database connection handler")
        c = embed_text("banana split recipe")
        assert a @ b > a @ c

    def test_empty_text_zero_vector(self):
        v = embed_text("")
        assert np.allclose(v, 0.0)

    def test_case_insensitive(self):
        assert np.allclose(embed_text("Select Query"), embed_text("select query"))


class TestMerkle:
    def test_root_changes_with_content(self):
        r1 = merkle_root({"a.py": content_hash("x")})
        r2 = merkle_root({"a.py": content_hash("y")})
        assert r1 != r2

    def test_path_participates(self):
        h = content_hash("x")
        assert merkle_root({"a.py": h}) != merkle_root({"b.py": h})

    def test_order_independent(self):
        files = {"a.py": content_hash("1"), "b.py": content_hash("2")}
        assert merkle_root(files) == merkle_root(dict(reversed(list(files.items()))))

    def test_empty_root_stable(self):
        assert merkle_root({}) == merkle_root({})

    def test_odd_leaves_ok(self):
        files = {f"{i}.py": content_hash(str(i)) for i in range(5)}
        assert len(merkle_root(files)) == 64  # sha256 hex


class TestObfuscate:
    def test_deterministic(self):
        assert obfuscate_path("src/db.py", "k") == obfuscate_path("src/db.py", "k")

    def test_key_sensitive(self):
        assert obfuscate_path("src/db.py", "k1") != obfuscate_path("src/db.py", "k2")

    def test_hides_plaintext(self):
        out = obfuscate_path("secret_project/db.py", "k")
        assert "secret_project" not in out
        assert "db" not in out

    def test_structure_preserved(self):
        assert obfuscate_path("a/b/c.py", "k").count("/") == 2


class TestIndex:
    @pytest.fixture()
    def idx(self):
        index = CodebaseIndex()
        index.sync(
            {
                "src/db.py": PY_SRC,
                "src/net.py": "def fetch(url):\n    return get(url)\n\n\ndef retry(n):\n    return n\n",
            }
        )
        return index

    def test_first_sync_embeds_all(self, idx):
        st = idx.stats()
        assert st["files"] == 2
        assert st["chunks"] > 0

    def test_noop_sync_touches_nothing(self, idx):
        before = idx.stats()["chunks"]
        res = idx.sync(
            {
                "src/db.py": PY_SRC,
                "src/net.py": "def fetch(url):\n    return get(url)\n\n\ndef retry(n):\n    return n\n",
            }
        )
        assert res["unchanged"] == 2
        assert res["chunks_reembedded"] == 0
        assert idx.stats()["chunks"] == before

    def test_incremental_only_changed(self, idx):
        res = idx.sync(
            {
                "src/db.py": PY_SRC + "\ndef extra():\n    pass\n",
                "src/net.py": "def fetch(url):\n    return get(url)\n\n\ndef retry(n):\n    return n\n",
            }
        )
        assert res["updated"] == 1
        assert res["unchanged"] == 1
        assert res["chunks_reembedded"] == 1

    def test_remove_file_drops_chunks(self, idx):
        idx.sync({"src/db.py": PY_SRC})
        st = idx.stats()
        assert st["files"] == 1
        assert all(r.obfuscated_path == obfuscate_path("src/db.py", idx.obfuscation_key) for r in idx.records)

    def test_search_topk(self, idx):
        hits = idx.search("connection pool class", k=2)
        assert len(hits) == 2
        # db.py 的 Pool 块应排第一
        assert hits[0].obfuscated_path == obfuscate_path("src/db.py", idx.obfuscation_key)

    def test_search_scores_descending(self, idx):
        hits = idx.search("fetch url retry", k=2)
        sims = [h.embedding @ embed_text("fetch url retry") for h in hits]
        assert sims[0] >= sims[1]

    def test_root_changes_after_sync(self, idx):
        r0 = idx.root_hash
        idx.sync({"src/db.py": PY_SRC + "\n# touched\n"})
        assert idx.root_hash != r0
