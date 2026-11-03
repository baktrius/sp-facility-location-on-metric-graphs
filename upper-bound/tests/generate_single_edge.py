"""Untrusted, tiny stored-fixture producer; run from the subproject directory."""

import json
from pathlib import Path

from test_comparison import real_wire_bundle
from test_reader import records, write_records


def generate(directory: Path) -> None:
    """Keep the existing genuine meshes, but select only agent zero."""
    directory.mkdir(parents=True, exist_ok=True)
    real_wire_bundle(directory)
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["identity"]["selectors"] = [{"kind": "peak", "agent": 0}]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    for filename in ("attribution.jsonl", "sp.jsonl", "approximation.jsonl"):
        rows = records(directory, filename)
        for row in rows:
            if row["type"] != "simplex":
                continue
            if filename == "attribution.jsonl":
                row["weights"] = [["1"] for _ in row["vertices"]]
            else:
                keep = (0, 3) if filename == "sp.jsonl" else (0, 3, 6, 7)
                row["branches"] = [row["branches"][i] for i in keep]
        write_records(directory, filename, rows)


if __name__ == "__main__":
    generate(Path("tests/fixtures/single-edge-dictator"))
