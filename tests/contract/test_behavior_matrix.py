import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]
MATRIX = ROOT / "docs" / "behavior-matrix.md"
ROW = re.compile(
    r"^\|\s*(?P<feature>[^|]+?)\s*"
    r"\|\s*(?P<api>[^|]+?)\s*"
    r"\|\s*(?P<boundary>[^|]+?)\s*"
    r"\|\s*`(?P<node>[^`]+)`\s*\|$"
)


def _rows():
    return [
        match.groupdict()
        for line in MATRIX.read_text(encoding="utf-8").splitlines()
        if (match := ROW.match(line))
    ]


def test_behavior_matrix_has_unique_executable_evidence():
    rows = _rows()
    assert rows
    features = [row["feature"] for row in rows]
    nodes = [row["node"] for row in rows]
    assert len(features) == len(set(features))
    assert len(nodes) == len(set(nodes))
    assert all(
        row["api"] and row["boundary"] and row["node"]
        for row in rows
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            *nodes,
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    collected = [
        line.strip()
        for line in completed.stdout.splitlines()
        if "::test_" in line
    ]
    assert sorted(collected) == sorted(nodes)


def _source_text():
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "src").rglob("*.py")
    )


def test_v1_source_excludes_tcp_and_http_adapters():
    source = _source_text()
    assert all(
        term not in source
        for term in ("FastAPI", "Flask", "socket", "RESP")
    )


def test_v1_source_excludes_distributed_coordination():
    source = _source_text()
    assert all(
        term not in source
        for term in ("Raft", "Sentinel", "Cluster")
    )


def test_v1_source_excludes_vector_retrieval():
    source = _source_text()
    assert all(
        term not in source for term in ("HNSW", "VectorField")
    )


def test_v1_segment_format_disclaims_lucene_codec_compatibility():
    segment_format = (ROOT / "docs" / "segment-format.md").read_text(
        encoding="utf-8"
    )
    assert "not Apache\nLucene files" in segment_format


def test_v1_has_no_automatic_merge_scheduler():
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "src").rglob("*.py")
    )
    assert "merge_scheduler" not in source


def test_v1_repository_separates_course_material():
    assert not (ROOT / "course").exists()
    assert not (ROOT / "chapters").exists()
