import json

import pytest

from minilucene import KeywordField, Schema, TextField
from minilucene.cli import main


@pytest.fixture
def schema_file(tmp_path):
    schema = Schema(
        id=KeywordField(stored=True),
        title=TextField(stored=True, boost=2.0),
        body=TextField(stored=True),
    )
    path = tmp_path / "schema-input.json"
    path.write_text(
        json.dumps({"fields": schema.to_dict()}), encoding="utf-8"
    )
    return path


def _write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_cli_create_add_search_delete_and_merge(
    tmp_path, schema_file, capsys
):
    index_path = tmp_path / "index"
    first = _write_json(
        tmp_path / "first.json",
        {
            "id": "1",
            "title": "Kafka Replication",
            "body": "Kafka uses follower replicas.",
        },
    )
    second = _write_json(
        tmp_path / "second.json",
        {
            "id": "2",
            "title": "Rabbit",
            "body": "Rabbit queues messages.",
        },
    )

    assert main(
        ["create", str(index_path), "--schema", str(schema_file)]
    ) == 0
    assert main(["add", str(index_path), str(first)]) == 0
    assert main(["add", str(index_path), str(second)]) == 0
    capsys.readouterr()

    assert (
        main(
            [
                "search",
                str(index_path),
                '"follower replicas"',
                "--default-field",
                "body",
                "--top-k",
                "10",
                "--highlight",
                "body",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["total_hits"] == 1
    assert payload["hits"][0]["stored_fields"]["id"] == "1"
    assert payload["hits"][0]["highlights"]["body"] == (
        "Kafka uses <em>follower replicas</em>."
    )

    assert (
        main(["merge", str(index_path), "1", "2"]) == 0
    )
    capsys.readouterr()
    assert (
        main(["delete", str(index_path), "id", "1"]) == 0
    )
    delete_payload = json.loads(capsys.readouterr().out)
    assert delete_payload["deleted"] == 1
    assert (
        main(
            [
                "search",
                str(index_path),
                "kafka",
                "--default-field",
                "body",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["total_hits"] == 0


def test_cli_emits_canonical_json(tmp_path, schema_file, capsys):
    index_path = tmp_path / "index"
    main(["create", str(index_path), "--schema", str(schema_file)])
    capsys.readouterr()
    assert (
        main(
            [
                "search",
                str(index_path),
                "none",
                "--default-field",
                "body",
                "--top-k",
                "0",
            ]
        )
        == 0
    )
    assert capsys.readouterr().out == (
        '{"hits":[],"total_hits":0}\n'
    )


def test_domain_failure_exits_two_with_one_stderr_line(
    tmp_path, capsys
):
    assert (
        main(
            [
                "search",
                str(tmp_path / "missing"),
                "query",
                "--default-field",
                "body",
            ]
        )
        == 2
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error: ")
    assert captured.err.count("\n") == 1


def test_unexpected_failures_are_not_swallowed(monkeypatch, tmp_path):
    def explode(_path):
        raise RuntimeError("unexpected")

    monkeypatch.setattr("minilucene.cli.Index.open", explode)
    with pytest.raises(RuntimeError, match="unexpected"):
        main(
            [
                "search",
                str(tmp_path),
                "query",
                "--default-field",
                "body",
            ]
        )
