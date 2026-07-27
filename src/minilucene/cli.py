import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from minilucene import Index, Schema
from minilucene.errors import MiniLuceneError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="minilucene",
        description="Direct-first MiniLucene reference CLI",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create")
    create.add_argument("index", type=Path)
    create.add_argument("--schema", type=Path, required=True)

    add = commands.add_parser("add")
    add.add_argument("index", type=Path)
    add.add_argument("documents", type=Path, nargs="+")

    search = commands.add_parser("search")
    search.add_argument("index", type=Path)
    search.add_argument("query")
    search.add_argument("--default-field", required=True)
    search.add_argument("--top-k", type=int, default=10)
    search.add_argument(
        "--highlight", action="append", default=[]
    )

    delete = commands.add_parser("delete")
    delete.add_argument("index", type=Path)
    delete.add_argument("field")
    delete.add_argument("term")

    merge = commands.add_parser("merge")
    merge.add_argument("index", type=Path)
    merge.add_argument("segments", type=int, nargs="+")
    return parser


def _read_json(path: Path) -> object:
    return json.loads(
        path.read_text(encoding="utf-8", errors="strict")
    )


def _require_mapping(
    value: object, description: str
) -> Mapping[str, object]:
    if not isinstance(value, dict) or any(
        not isinstance(key, str) for key in value
    ):
        raise ValueError(f"{description} must be a JSON object")
    return value


def _emit(payload: Mapping[str, object]) -> None:
    print(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def _create(args: argparse.Namespace) -> None:
    payload = _require_mapping(
        _read_json(args.schema), "schema file"
    )
    fields = _require_mapping(
        payload.get("fields"), "schema fields"
    )
    schema = Schema.from_dict(
        {
            name: _require_mapping(value, f"field {name}")
            for name, value in fields.items()
        }
    )
    with Index.create(args.index, schema):
        pass
    _emit({"index": str(args.index), "status": "created"})


def _add(args: argparse.Namespace) -> None:
    with Index.open(args.index) as index, index.writer() as writer:
        for path in args.documents:
            document = _require_mapping(
                _read_json(path), f"document {path}"
            )
            writer.add_document(**document)
        manifest = writer.commit()
    _emit(
        {
            "added": len(args.documents),
            "commit_generation": manifest.commit_generation,
        }
    )


def _search(args: argparse.Namespace) -> None:
    with (
        Index.open(args.index) as index,
        index.open_reader() as reader,
    ):
        results = reader.search_text(
            args.query,
            default_field=args.default_field,
            top_k=args.top_k,
            highlight_fields=tuple(args.highlight),
        )
    _emit(
        {
            "total_hits": results.total_hits,
            "hits": [
                {
                    "score": hit.score,
                    "segment_generation": (
                        hit.segment_generation
                    ),
                    "local_doc_id": hit.local_doc_id,
                    "stored_fields": dict(hit.stored_fields),
                    "highlights": dict(hit.highlights),
                }
                for hit in results.hits
            ],
        }
    )


def _delete(args: argparse.Namespace) -> None:
    with Index.open(args.index) as index, index.writer() as writer:
        deleted = writer.delete_by_term(args.field, args.term)
        manifest = writer.commit()
    _emit(
        {
            "deleted": deleted,
            "commit_generation": manifest.commit_generation,
        }
    )


def _merge(args: argparse.Namespace) -> None:
    with Index.open(args.index) as index, index.writer() as writer:
        descriptor = writer.merge(tuple(args.segments))
        manifest = writer.commit()
    _emit(
        {
            "merged_segment_generation": descriptor.generation,
            "commit_generation": manifest.commit_generation,
        }
    )


_COMMANDS = {
    "create": _create,
    "add": _add,
    "search": _search,
    "delete": _delete,
    "merge": _merge,
}


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        _COMMANDS[args.command](args)
    except (
        MiniLuceneError,
        ValueError,
        OSError,
        UnicodeError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0
