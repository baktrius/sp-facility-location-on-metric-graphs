"""Render the included exact endpoint inventory; this script does not verify bounds."""

import json
from fractions import Fraction
from pathlib import Path


def outward_decimal(value: str, *, upward: bool, places: int = 12) -> str:
    """Round an exact rational using integer arithmetic, preserving its bound."""
    scale = 10**places
    scaled = Fraction(value) * scale
    units = (
        -(-scaled.numerator // scaled.denominator)
        if upward
        else scaled.numerator // scaled.denominator
    )
    sign = "-" if units < 0 else ""
    whole, fractional = divmod(abs(units), scale)
    return f"{sign}{whole}.{fractional:0{places}d}"


root = Path(__file__).resolve().parents[1]
rows = json.loads((root / "scoreboard/results.json").read_text())
lines = [
    "# Selected certificate bounds",
    "",
    "Sixteen configurations: thirteen paired bounds and three lower-only highlights.",
    "These bounds concern ordinary SP in expectation and expected sum-distance cost.",
    "Exact values and artifact paths are in [results.json](results.json); explicit unit graphs",
    "and agent counts are in [configurations.json](configurations.json).",
    "",
    "Upper endpoints use the complete recorded acceptances described in",
    "[validation](../validation/README.md). Reproduction instructions are in the",
    "[main README](../README.md). A dash means no upper certificate is included for that row.",
    "",
    "Lower bounds are rounded downward and upper bounds upward to 12 decimal places,",
    "using exact rational arithmetic. Each displayed gap is an upper bound on the",
    "exact interval width, rounded upward from the exact difference.",
    "",
    "| Graph | Agents | Lower | Upper | Gap |",
    "| --- | ---: | ---: | ---: | ---: |",
]
for r in rows:
    expected_gap = (
        str(Fraction(r["upper"]) - Fraction(r["lower"])) if r["upper"] else None
    )
    if r["gap"] != expected_gap:
        raise ValueError(f"Incorrect exact gap for {r['id']}")
    lower = f"[{outward_decimal(r['lower'], upward=False)}](../{r['lower_certificate']})"
    upper = (
        f"[{outward_decimal(r['upper'], upward=True)}](../{r['upper_certificate']})"
        if r["upper"]
        else "—"
    )
    gap = outward_decimal(r["gap"], upward=True) if r["gap"] else "—"
    lines.append(f"| {r['label']} | {r['agents']} | {lower} | {upper} | {gap} |")
lines += [
    "",
    "The circle rows describe continuous circles up to uniform scaling, not different",
    "finite report domains. The bowtie row consists of two equal circles joined at",
    "one vertex. Parameterized theta and complete bipartite graphs are defined by",
    "their explicit edge lists. Equal metric graphs with different agent counts are",
    "different configurations. No row claims optimality among all mechanisms.",
    "",
]
(root / "scoreboard/README.md").write_text("\n".join(lines))
