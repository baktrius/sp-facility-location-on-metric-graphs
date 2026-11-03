"""Check certificate identity, graph correspondence, archive hashes and recorded code hashes.

This does not run either mathematical certificate verifier.
"""

import json
import zipfile
from pathlib import Path

from metric import correspondence, normalize
from verify import sha256
from certificate_io import materialize, packaging_entries

ROOT = Path(__file__).resolve().parents[1]


def check():
    rows = json.loads((ROOT / "scoreboard/results.json").read_text())
    configs = json.loads((ROOT / "scoreboard/configurations.json").read_text())
    receipts = {
        r["configuration"]: r
        for r in json.loads(
            (ROOT / "validation/recorded-upper-acceptances.json").read_text()
        )
    }
    packages = {e["path"]: e for e in packaging_entries(ROOT)} if (ROOT / "certificates/packaging.json").exists() else {}
    reports = []
    for row in rows:
        config = configs[row["id"]]
        if row["lower_certificate"].endswith(".xz"):
            with materialize(ROOT, packages[row["lower_certificate"]]) as path:
                lower = json.loads(path.read_text())
        else:
            lower = json.loads((ROOT / row["lower_certificate"]).read_text())
        if not lower["certified_value"] == row["lower"]:
            raise ValueError(
                'Inventory requirement failed: lower["certified_value"] == row["lower"]'
            )
        if not lower["identity"]["agents"] == config["agents"] == row["agents"]:
            raise ValueError(
                'Inventory requirement failed: lower["identity"]["agents"] == config["agents"] == row["agents"]'
            )
        target = normalize(config["graph"])
        match = correspondence(normalize(lower["identity"]["graph"]), target)
        if not match is not None:
            raise ValueError(row["id"])
        report = {"configuration": row["id"], "lower_metric_correspondence": match}
        if row["upper_certificate"]:
            receipt = receipts[row["id"]]
            path = ROOT / row["upper_certificate"]
            if path.suffix == ".xz":
                with materialize(ROOT, packages[row["upper_certificate"]]) as expanded:
                    manifest = json.loads((expanded / "manifest.json").read_text())
            else:
                if not sha256(path) == receipt["archive_sha256"]:
                    raise ValueError(
                        'Inventory requirement failed: sha256(path) == receipt["archive_sha256"]'
                    )
                with zipfile.ZipFile(path) as archive:
                    if not len(archive.namelist()) == 5:
                        raise ValueError(
                            "Inventory requirement failed: len(archive.namelist()) == 5"
                        )
                    if not set(archive.namelist()) == set(receipt["members"]):
                        raise ValueError(
                            'Inventory requirement failed: set(archive.namelist()) == set(receipt["members"])'
                        )
                    for name, member in receipt["members"].items():
                        if not archive.getinfo(name).file_size == member["bytes"]:
                            raise ValueError(
                                'Inventory requirement failed: archive.getinfo(name).file_size == member["bytes"]'
                            )
                    manifest = json.loads(archive.read("manifest.json"))
            if not str(manifest["certified_value"]) == row["upper"]:
                raise ValueError(
                    'Inventory requirement failed: str(manifest["certified_value"]) == row["upper"]'
                )
            if not manifest["identity"]["agents"] == config["agents"]:
                raise ValueError(
                    'Inventory requirement failed: manifest["identity"]["agents"] == config["agents"]'
                )
            upper_match = correspondence(
                normalize(manifest["identity"]["graph"]), target
            )
            if not upper_match is not None:
                raise ValueError(
                    "Inventory requirement failed: upper_match is not None"
                )
            report["upper_metric_correspondence"] = upper_match
            for name, digest in receipt["verifier_reference"]["files"].items():
                if not sha256(ROOT / "upper-bound" / name) == digest:
                    raise ValueError(name)
            report["recorded_upper_code_and_pins_match"] = True
        reports.append(report)
    return reports


if __name__ == "__main__":
    print(json.dumps(check(), indent=2))
