"""The live Strawberry schema must match the reviewed SDL snapshot (lint & build gate)."""

import re
from pathlib import Path

ROOT = Path(__file__).parents[1]


def _definitions(sdl: str) -> set[str]:
    blocks = re.findall(r"((?:type|input|enum|scalar|interface|union|schema)\b[^{]*\{[^}]*\}|scalar \w+)", sdl)
    return {re.sub(r"\s+", " ", block).strip() for block in blocks}


def test_schema_matches_snapshot(backend):
    from strawberry.printer import print_schema

    live = print_schema(backend["gateway"].schema)
    snapshot = (ROOT / "docs/graphql/schema.graphql").read_text()
    missing = _definitions(snapshot) - _definitions(live)
    extra = _definitions(live) - _definitions(snapshot)
    assert not missing and not extra, f"schema drift: missing={missing} extra={extra}"
