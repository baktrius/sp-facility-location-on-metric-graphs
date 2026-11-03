"""Decode five fixed-name files into records, never mechanism acceptance.

``BundleReader`` retains the complete attribution and streams comparisons.
Both one-shot comparison iterators must be exhausted, including their final
EOF check. ``streams_exhausted`` means only that syntax/reference checks completed;
geometry, admissibility and residual checks still require later stages.
``read_bundle`` is a convenience that retains every comparison root as well.
"""

import json
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, replace
from itertools import product
from pathlib import Path
from types import MappingProxyType
from typing import Literal, NoReturn, cast

from flint import fmpq, fmpz

from .exact import parse_rational
from .failures import Failure, FailureKind, VerificationError
from .graph import (
    Graph,
    GraphPoint,
    Selector,
    parse_agent_count,
    parse_graph,
    parse_point,
    parse_selectors,
    point_in_chart,
)


@dataclass(frozen=True)
class AttributionKey:
    edges: tuple[int, ...]

    def to_data(self) -> dict[str, object]:
        return {"edges": list(self.edges)}


@dataclass(frozen=True)
class SPKey:
    agent: int
    edges: tuple[int, ...]

    def to_data(self) -> dict[str, object]:
        return {"agent": self.agent, "edges": list(self.edges)}


@dataclass(frozen=True)
class ReportCandidate:
    agent: int

    def to_data(self) -> dict[str, object]:
        return {"kind": "report", "agent": self.agent}


@dataclass(frozen=True)
class VertexCandidate:
    vertex: str

    def to_data(self) -> dict[str, object]:
        return {"kind": "vertex", "vertex": self.vertex}


type Candidate = ReportCandidate | VertexCandidate


@dataclass(frozen=True)
class ApproximationKey:
    candidate: Candidate
    edges: tuple[int, ...]

    def to_data(self) -> dict[str, object]:
        return {"candidate": self.candidate.to_data(), "edges": list(self.edges)}


type RootKey = AttributionKey | SPKey | ApproximationKey


@dataclass(frozen=True)
class SourceLocation:
    file: str
    line: int
    root: RootKey | None = None
    cell: str | None = None

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {"file": self.file, "line": self.line}
        if self.root is not None:
            result["root"] = self.root.to_data()
        if self.cell is not None:
            result["cell"] = self.cell
        return result


@dataclass(frozen=True)
class Manifest:
    schema_version: int
    graph: Graph
    agents: int
    selectors: tuple[Selector, ...]
    certified_value: fmpq
    location: SourceLocation


@dataclass(frozen=True)
class ProfileVertex:
    id: str
    point: tuple[GraphPoint, ...]
    location: SourceLocation


@dataclass(frozen=True)
class AttributionSimplex:
    id: str
    vertices: tuple[str, ...]
    weights: tuple[tuple[fmpq, ...], ...]
    location: SourceLocation


@dataclass(frozen=True)
class ComparisonSimplex:
    id: str
    vertices: tuple[str, ...]
    truthful: str
    deviated: str | None
    branches: tuple[int, ...]
    location: SourceLocation


type Simplex = AttributionSimplex | ComparisonSimplex


@dataclass(frozen=True)
class SplitNode:
    id: str
    normal: tuple[fmpq, ...]
    offset: fmpq
    minus: str
    plus: str
    location: SourceLocation


@dataclass(frozen=True)
class LeafNode:
    id: str
    simplex: str
    location: SourceLocation


type TreeNode = SplitNode | LeafNode


@dataclass(frozen=True)
class RootBlock:
    key: RootKey
    tree: str
    vertices: tuple[ProfileVertex, ...]
    simplices: tuple[Simplex, ...]
    nodes: tuple[TreeNode, ...]
    location: SourceLocation


@dataclass(frozen=True)
class DecodedBundle:
    """All decoded records. This type has no mathematical acceptance status."""

    manifest: Manifest
    vertices: Mapping[str, ProfileVertex]
    attribution: tuple[RootBlock, ...]
    sp: tuple[RootBlock, ...]
    approximation: tuple[RootBlock, ...]


def _reject(
    code: str,
    message: str,
    location: SourceLocation,
    kind: FailureKind = FailureKind.REFUSED,
) -> NoReturn:
    raise VerificationError(Failure(kind, code, message, location.to_dict()))


def _object(value: object, fields: set[str], loc: SourceLocation) -> dict[str, object]:
    if type(value) is not dict or value.keys() != fields:
        _reject("schema_fields", "Missing or unknown object fields", loc)
    return cast(dict[str, object], value)


def _array(value: object, length: int, loc: SourceLocation) -> list[object]:
    if type(value) is not list or len(value) != length:
        _reject("schema_array", "Wrong JSON array shape", loc)
    return cast(list[object], value)


def _id(value: object, loc: SourceLocation) -> str:
    if type(value) is not str or not value:
        _reject("schema_id", "Expected a nonempty string ID", loc)
    return value


def _index(value: object, size: int, loc: SourceLocation) -> int:
    if type(value) is not int:
        _reject("schema_index", "Expected a JSON integer index", loc)
    if not 0 <= value < size:
        _reject(
            "reference_index",
            "Index outside the declared range",
            loc,
            FailureKind.INVALID_CERTIFICATE,
        )
    return value


class _JSONDecoder:
    """Small JSON grammar with token positions and no float ingress.

    String escaping uses the standard-library scanner. Object/number parsing
    stays here so duplicate keys and forbidden numbers retain their exact line.
    """

    _number = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?")

    def __init__(self, text: str, loc: SourceLocation):
        self.text = text
        self.loc = loc
        self.pos = 0

    def reject(self, message: str, position: int | None = None) -> NoReturn:
        position = self.pos if position is None else position
        line = self.loc.line + self.text.count("\n", 0, position)
        _reject("schema_json", message, replace(self.loc, line=line))

    def whitespace(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos] in " \t\r\n":
            self.pos += 1

    def string(self) -> str:
        try:
            result, self.pos = json.JSONDecoder().raw_decode(self.text, self.pos)
            return cast(str, result)
        except json.JSONDecodeError as error:
            self.reject(error.msg, error.pos)

    def value(self) -> object:
        self.whitespace()
        if self.pos == len(self.text):
            self.reject("Expected a JSON value")
        char = self.text[self.pos]
        if char == '"':
            return self.string()
        if char == "{":
            self.pos += 1
            result: dict[str, object] = {}
            self.whitespace()
            if self.pos < len(self.text) and self.text[self.pos] == "}":
                self.pos += 1
                return result
            while True:
                self.whitespace()
                position = self.pos
                if self.pos == len(self.text) or self.text[self.pos] != '"':
                    self.reject("Expected an object key")
                key = self.string()
                if key in result:
                    self.reject("Duplicate JSON object key", position)
                self.whitespace()
                if self.pos == len(self.text) or self.text[self.pos] != ":":
                    self.reject("Expected colon after object key")
                self.pos += 1
                result[key] = self.value()
                self.whitespace()
                if self.pos < len(self.text) and self.text[self.pos] == "}":
                    self.pos += 1
                    return result
                if self.pos == len(self.text) or self.text[self.pos] != ",":
                    self.reject("Expected comma or object end")
                self.pos += 1
        if char == "[":
            self.pos += 1
            items: list[object] = []
            self.whitespace()
            if self.pos < len(self.text) and self.text[self.pos] == "]":
                self.pos += 1
                return items
            while True:
                items.append(self.value())
                self.whitespace()
                if self.pos < len(self.text) and self.text[self.pos] == "]":
                    self.pos += 1
                    return items
                if self.pos == len(self.text) or self.text[self.pos] != ",":
                    self.reject("Expected comma or array end")
                self.pos += 1
        for token, decoded in (("true", True), ("false", False), ("null", None)):
            if self.text.startswith(token, self.pos):
                self.pos += len(token)
                return decoded
        match = self._number.match(self.text, self.pos)
        if match is None:
            self.reject("Invalid JSON token (nonfinite numbers are forbidden)")
        token = match.group()
        if "." in token or "e" in token.lower():
            self.reject("JSON floating values are forbidden")
        self.pos = match.end()
        # FLINT parses decimal digits before conversion to a native integer;
        # int(fmpz) avoids CPython's decimal string digit limit, without changing
        # process-global settings. JSON -0 deliberately becomes native zero.
        return int(fmpz(token))


def _decode(text: str, loc: SourceLocation) -> object:
    decoder = _JSONDecoder(text, loc)
    try:
        result = decoder.value()
        decoder.whitespace()
        if decoder.pos != len(text):
            decoder.reject("Trailing non-JSON content")
        return result
    except RecursionError:
        _reject(
            "resource_limit_json_depth",
            "JSON nesting exceeds the runtime limit",
            loc,
            FailureKind.INCOMPLETE,
        )


def _certificate_reference_error(
    error: VerificationError, loc: SourceLocation
) -> NoReturn:
    """Translate resolving references in a bundle, preserving malformed syntax.

    The reusable graph parsers also serve decoded-data callers and retain their
    reviewed REFUSED behavior. Only point/selector references are translated
    here; malformed graph declarations still follow parse_graph unchanged.
    """
    kind = (
        FailureKind.INVALID_CERTIFICATE
        if error.failure.code in {"reference_vertex", "reference_index"}
        else error.failure.kind
    )
    raise VerificationError(
        replace(error.failure, kind=kind, location=loc.to_dict())
    ) from error


def _certificate_point(graph: Graph, value: object, loc: SourceLocation) -> GraphPoint:
    try:
        # Check canonical coordinate syntax before resolving an edge index. A
        # missing edge with a malformed coordinate must remain malformed input.
        if type(value) is dict and value.keys() == {"edge", "coordinate"}:
            point_data = cast(dict[str, object], value)
            coordinate = parse_rational(point_data["coordinate"])
            if not 0 < coordinate < 1:
                _reject(
                    "schema_point",
                    "Edge points require a strict interior rational",
                    loc,
                )
        return parse_point(graph, value)
    except VerificationError as error:
        _certificate_reference_error(error, loc)


def _certificate_selectors(
    graph: Graph, value: object, agents: int, loc: SourceLocation
) -> tuple[Selector, ...]:
    if type(value) is list:
        for selector in value:
            if type(selector) is dict:
                data = cast(dict[str, object], selector)
                if data.keys() == {"kind", "point"} and data["kind"] == "constant":
                    _certificate_point(graph, data["point"], loc)
    try:
        return parse_selectors(graph, value, agents)
    except VerificationError as error:
        _certificate_reference_error(error, loc)


def _read_manifest(path: Path) -> Manifest:
    loc = SourceLocation(path.name, 1)
    try:
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            _reject(
                "schema_encoding",
                "Invalid UTF-8",
                replace(loc, line=1 + raw[: error.start].count(b"\n")),
            )
        data = _object(
            _decode(text, loc),
            {"schema_version", "identity", "certified_value"},
            loc,
        )
        if type(data["schema_version"]) is not int:
            _reject("schema_version", "Schema version must be a JSON integer", loc)
        if data["schema_version"] != 1:
            _reject("unsupported_version", "Unsupported schema version", loc)
        identity = _object(
            data["identity"],
            {"formulation", "result", "graph", "agents", "selectors"},
            loc,
        )
        if (
            identity["formulation"] != "metric_graph_upper"
            or identity["result"] != "unconditional"
        ):
            _reject(
                "unsupported_identity", "Unsupported formulation or result scope", loc
            )
        graph = parse_graph(identity["graph"])
        agents = parse_agent_count(identity["agents"])
        selectors = _certificate_selectors(graph, identity["selectors"], agents, loc)
        alpha = parse_rational(data["certified_value"])
        if alpha < 1:
            _reject("schema_bound", "Certified value must be at least one", loc)
        return Manifest(1, graph, agents, selectors, alpha, loc)
    except (OSError, UnicodeError) as error:
        _reject("schema_read", str(error), loc)
    except VerificationError as error:
        if error.failure.location is None:
            raise VerificationError(
                replace(error.failure, location=loc.to_dict())
            ) from error
        raise


class _Lines:
    def __init__(self, path: Path):
        self.path = path
        self.line = 0

    def __iter__(self) -> Iterator[tuple[object, SourceLocation]]:
        try:
            with self.path.open("rb") as stream:
                for self.line, raw in enumerate(stream, 1):
                    loc = SourceLocation(self.path.name, self.line)
                    try:
                        text = raw.decode("utf-8")
                    except UnicodeError as error:
                        _reject("schema_encoding", str(error), loc)
                    if text.strip(" \t\r\n"):
                        yield _decode(text.rstrip("\r\n"), loc), loc
        except OSError as error:
            _reject("schema_read", str(error), self.eof)

    @property
    def eof(self) -> SourceLocation:
        return SourceLocation(self.path.name, self.line + 1)


def attribution_root_keys(graph: Graph, agents: int) -> Iterator[AttributionKey]:
    """Every labeled attribution chart, lexicographically, independently of input."""
    agents = parse_agent_count(agents)
    try:
        tuples = product(range(len(graph.edges)), repeat=agents)
    except (OverflowError, MemoryError) as error:
        raise VerificationError(
            Failure(
                FailureKind.INCOMPLETE,
                "resource_limit_dimensions",
                "Cannot enumerate attribution roots within runtime resources",
            )
        ) from error
    return (AttributionKey(edges) for edges in tuples)


def sp_root_keys(graph: Graph, agents: int) -> Iterator[SPKey]:
    """Agents first, then every (x_0,...,x_(n-1),z) edge tuple."""
    agents = parse_agent_count(agents)
    for agent in range(agents):
        # Reuse the attribution Cartesian-product enumerator and its resource guard.
        for key in attribution_root_keys(graph, agents + 1):
            yield SPKey(agent, key.edges)


def approximation_candidates(graph: Graph, agents: int) -> tuple[Candidate, ...]:
    """Keep every labeled report, then branching vertices in document order."""
    agents = parse_agent_count(agents)
    return (
        *(ReportCandidate(i) for i in range(agents)),
        *(VertexCandidate(v) for v in graph.vertices if graph.degree(v) >= 3),
    )


def approximation_root_keys(graph: Graph, agents: int) -> Iterator[ApproximationKey]:
    """Every candidate independently of input, then lexicographic profile charts."""
    for candidate in approximation_candidates(graph, agents):
        for key in attribution_root_keys(graph, agents):
            yield ApproximationKey(candidate, key.edges)


class BundleReader:
    """Retain attribution; decode each comparison root only when requested.

    Constructing this reader reads manifest, vertices and attribution through
    EOF. The SP and approximation iterators are one-shot and must both reach
    EOF. Merely receiving their final root is insufficient: the next iteration
    checks trailing content. No decoded object is a mechanism acceptance.
    """

    def __init__(self, directory: str | Path):
        self.directory = Path(directory)
        self.manifest = _read_manifest(self.directory / "manifest.json")
        vertices: dict[str, ProfileVertex] = {}
        points: set[tuple[GraphPoint, ...]] = set()
        for value, loc in _Lines(self.directory / "vertices.jsonl"):
            try:
                data = _object(value, {"id", "point"}, loc)
                vertex = self._vertex(data, self.manifest.agents, loc)
                if vertex.id in vertices or vertex.point in points:
                    _reject(
                        "reference_duplicate_vertex",
                        "Duplicate global vertex ID or canonical profile",
                        loc,
                        FailureKind.INVALID_CERTIFICATE,
                    )
                vertices[vertex.id] = vertex
                points.add(vertex.point)
            except VerificationError as error:
                self._located(error, loc)
        self.vertices: Mapping[str, ProfileVertex] = MappingProxyType(vertices)
        self._attribution_simplices: dict[str, AttributionSimplex] = {}
        self.attribution = tuple(self._roots("attribution"))
        self.attribution_simplices: Mapping[str, AttributionSimplex] = MappingProxyType(
            self._attribution_simplices
        )
        self._started: set[str] = set()
        self._finished: set[str] = set()

    @staticmethod
    def _located(error: VerificationError, loc: SourceLocation) -> NoReturn:
        raise VerificationError(
            replace(error.failure, location=loc.to_dict())
        ) from error

    def _vertex(
        self, data: dict[str, object], dimension: int, loc: SourceLocation
    ) -> ProfileVertex:
        point = tuple(
            _certificate_point(self.manifest.graph, item, loc)
            for item in _array(data["point"], dimension, loc)
        )
        return ProfileVertex(_id(data["id"], loc), point, loc)

    def _key(self, value: object, stream: str, loc: SourceLocation) -> RootKey:
        fields = {"edges"} | (
            {"agent"}
            if stream == "sp"
            else {"candidate"}
            if stream == "approximation"
            else set()
        )
        data = _object(value, fields, loc)
        dimension = self.manifest.agents + (stream == "sp")
        edges = tuple(
            _index(item, len(self.manifest.graph.edges), loc)
            for item in _array(data["edges"], dimension, loc)
        )
        if stream == "attribution":
            return AttributionKey(edges)
        if stream == "sp":
            return SPKey(_index(data["agent"], self.manifest.agents, loc), edges)
        candidate = data["candidate"]
        if type(candidate) is dict and candidate.get("kind") == "report":
            candidate = _object(candidate, {"kind", "agent"}, loc)
            return ApproximationKey(
                ReportCandidate(_index(candidate["agent"], self.manifest.agents, loc)),
                edges,
            )
        candidate = _object(candidate, {"kind", "vertex"}, loc)
        if candidate["kind"] != "vertex":
            _reject("schema_candidate", "Expected report or vertex candidate", loc)
        vertex = candidate["vertex"]
        if type(vertex) is not str:
            _reject("schema_candidate", "Vertex candidate requires a string label", loc)
        if vertex not in self.manifest.graph.vertices:
            _reject(
                "reference_candidate",
                "Candidate names an undeclared graph vertex",
                loc,
                FailureKind.INVALID_CERTIFICATE,
            )
        return ApproximationKey(VertexCandidate(vertex), edges)

    def _rank(self, key: RootKey) -> tuple[int, ...]:
        if isinstance(key, AttributionKey):
            return key.edges
        if isinstance(key, SPKey):
            return (key.agent, *key.edges)
        candidate = key.candidate
        index = (
            candidate.agent
            if isinstance(candidate, ReportCandidate)
            else self.manifest.agents
            + self.manifest.graph.vertices.index(candidate.vertex)
        )
        return (index, *key.edges)

    def _roots(
        self, stream: Literal["attribution", "sp", "approximation"]
    ) -> Iterator[RootBlock]:
        lines = _Lines(self.directory / f"{stream}.jsonl")
        records = iter(lines)
        previous: tuple[int, ...] | None = None
        try:
            expected = (
                attribution_root_keys(self.manifest.graph, self.manifest.agents)
                if stream == "attribution"
                else sp_root_keys(self.manifest.graph, self.manifest.agents)
                if stream == "sp"
                else approximation_root_keys(self.manifest.graph, self.manifest.agents)
            )
        except VerificationError as error:
            self._located(error, lines.eof)
        for value, loc in records:
            try:
                header = _object(value, {"type", "key", "tree"}, loc)
                if header["type"] != "root":
                    _reject(
                        "schema_order", "Expected a root header outside a block", loc
                    )
                key = self._key(header["key"], stream, loc)
                loc = replace(loc, root=key)
                rank = self._rank(key)
                required = next(expected, None)
                if stream == "attribution" and key != required:
                    _reject(
                        "reference_root_sequence",
                        "Attribution root does not match the next required root",
                        loc,
                        FailureKind.INVALID_CERTIFICATE,
                    )
                if previous is not None and rank <= previous:
                    _reject(
                        "reference_root_order",
                        "Repeated or out-of-order root",
                        loc,
                        FailureKind.INVALID_CERTIFICATE,
                    )
                if key != required:
                    _reject(
                        "reference_root_sequence",
                        "Root does not match the next required root",
                        loc,
                        FailureKind.INVALID_CERTIFICATE,
                    )
                previous = rank
                root = self._block(records, lines, header, key, stream, loc)
                yield root
            except VerificationError as error:
                # Preserve a more precise inner-record location.
                if error.failure.location is None:
                    self._located(error, loc)
                raise
        if next(expected, None) is not None:
            _reject(
                "reference_root_sequence",
                "Stream ended before every required root",
                lines.eof,
                FailureKind.INVALID_CERTIFICATE,
            )

    @staticmethod
    def _root_records(
        records: Iterator[tuple[object, SourceLocation]], key: RootKey
    ) -> Iterator[tuple[object, SourceLocation]]:
        while True:
            try:
                record = next(records)
            except StopIteration:
                return
            except VerificationError as error:
                location = dict(error.failure.location or {})
                location["root"] = key.to_data()
                raise VerificationError(
                    replace(error.failure, location=location)
                ) from error
            yield record

    def _block(
        self,
        records: Iterator[tuple[object, SourceLocation]],
        lines: _Lines,
        header: dict[str, object],
        key: RootKey,
        stream: str,
        loc: SourceLocation,
    ) -> RootBlock:
        tree = _id(header["tree"], loc)
        dimension = len(key.edges)
        vertices: dict[str, ProfileVertex] = {}
        points: set[tuple[GraphPoint, ...]] = set()
        simplices: dict[str, Simplex] = {}
        nodes: dict[str, TreeNode] = {}
        phase = 0
        for value, record_loc in self._root_records(records, key):
            record_loc = replace(record_loc, root=key)
            try:
                if type(value) is not dict or "type" not in value:
                    _reject("schema_record", "Expected a typed record", record_loc)
                record = cast(dict[str, object], value)
                kind = record["type"]
                if kind == "end":
                    _object(record, {"type"}, record_loc)
                    break
                if kind == "vertex":
                    if stream == "attribution" or phase != 0:
                        _reject(
                            "schema_order",
                            "Auxiliary vertices must precede simplices",
                            record_loc,
                        )
                    _object(record, {"type", "id", "point"}, record_loc)
                    vertex = self._vertex(record, dimension, record_loc)
                    if vertex.id in vertices or vertex.point in points:
                        _reject(
                            "reference_duplicate_vertex",
                            "Duplicate local vertex ID or point",
                            record_loc,
                            FailureKind.INVALID_CERTIFICATE,
                        )
                    if not all(
                        point_in_chart(self.manifest.graph, point, edge)
                        for point, edge in zip(vertex.point, key.edges, strict=True)
                    ):
                        _reject(
                            "reference_chart",
                            "Auxiliary point is outside its root charts",
                            record_loc,
                            FailureKind.INVALID_CERTIFICATE,
                        )
                    vertices[vertex.id] = vertex
                    points.add(vertex.point)
                elif kind == "simplex":
                    if phase == 2:
                        _reject(
                            "schema_order",
                            "Simplices must precede tree nodes",
                            record_loc,
                        )
                    phase = 1
                    record_loc = replace(
                        record_loc, cell=_id(record.get("id"), record_loc)
                    )
                    simplex = self._simplex(
                        record, dimension, stream, vertices, record_loc
                    )
                    if simplex.id in simplices or (
                        stream == "attribution"
                        and simplex.id in self._attribution_simplices
                    ):
                        _reject(
                            "reference_duplicate_simplex",
                            "Duplicate simplex ID",
                            record_loc,
                            FailureKind.INVALID_CERTIFICATE,
                        )
                    simplices[simplex.id] = simplex
                    if isinstance(simplex, AttributionSimplex):
                        self._attribution_simplices[simplex.id] = simplex
                elif kind in ("split", "leaf"):
                    phase = 2
                    node = self._node(record, dimension, record_loc)
                    if node.id in nodes:
                        _reject(
                            "reference_duplicate_node",
                            "Duplicate tree node ID",
                            record_loc,
                            FailureKind.INVALID_CERTIFICATE,
                        )
                    nodes[node.id] = node
                else:
                    _reject(
                        "schema_record", "Unknown or misplaced record type", record_loc
                    )
            except VerificationError as error:
                self._located(error, record_loc)
        else:
            _reject(
                "schema_truncated",
                "Root block is missing its end record",
                replace(lines.eof, root=key),
            )
        if tree not in nodes:
            _reject(
                "reference_tree",
                "Tree header names an undeclared node",
                loc,
                FailureKind.INVALID_CERTIFICATE,
            )
        for node in nodes.values():
            refs = (
                (node.minus, node.plus)
                if isinstance(node, SplitNode)
                else (node.simplex,)
            )
            namespace = nodes if isinstance(node, SplitNode) else simplices
            if any(ref not in namespace for ref in refs):
                _reject(
                    "reference_tree",
                    "Tree node names an undeclared child or local simplex",
                    node.location,
                    FailureKind.INVALID_CERTIFICATE,
                )
        return RootBlock(
            key,
            tree,
            tuple(vertices.values()),
            tuple(simplices.values()),
            tuple(nodes.values()),
            loc,
        )

    def _simplex(
        self,
        record: dict[str, object],
        dimension: int,
        stream: str,
        local_vertices: Mapping[str, ProfileVertex],
        loc: SourceLocation,
    ) -> Simplex:
        fields = {"type", "id", "vertices"} | (
            {"weights"} if stream == "attribution" else {"truthful", "branches"}
        )
        if stream == "sp":
            fields.add("deviated")
        _object(record, fields, loc)
        identifier = _id(record["id"], loc)
        vertices = tuple(
            _id(item, loc) for item in _array(record["vertices"], dimension + 1, loc)
        )
        namespace = self.vertices if stream == "attribution" else local_vertices
        if len(set(vertices)) != len(vertices) or any(
            vertex not in namespace for vertex in vertices
        ):
            _reject(
                "reference_simplex_vertex",
                "Simplex needs distinct vertices in its vertex namespace",
                loc,
                FailureKind.INVALID_CERTIFICATE,
            )
        selectors = len(self.manifest.selectors)
        if stream == "attribution":
            weights = tuple(
                tuple(parse_rational(item) for item in _array(row, selectors, loc))
                for row in _array(record["weights"], dimension + 1, loc)
            )
            return AttributionSimplex(identifier, vertices, weights, loc)
        truthful = _id(record["truthful"], loc)
        deviated = _id(record["deviated"], loc) if stream == "sp" else None
        if truthful not in self._attribution_simplices or (
            deviated is not None and deviated not in self._attribution_simplices
        ):
            _reject(
                "reference_region",
                "Comparison names an undeclared attribution simplex",
                loc,
                FailureKind.INVALID_CERTIFICATE,
            )
        count = (
            2 * selectors
            if stream == "sp"
            else self.manifest.agents * selectors + self.manifest.agents
        )
        branches = []
        for branch in _array(record["branches"], count, loc):
            if type(branch) is not int:
                _reject("schema_branch", "Expected a JSON integer branch number", loc)
            if branch < 0:
                _reject(
                    "reference_branch",
                    "Branch number is outside every branch range",
                    loc,
                    FailureKind.INVALID_CERTIFICATE,
                )
            branches.append(branch)
        return ComparisonSimplex(
            identifier, vertices, truthful, deviated, tuple(branches), loc
        )

    def _node(
        self, record: dict[str, object], dimension: int, loc: SourceLocation
    ) -> TreeNode:
        if record["type"] == "leaf":
            _object(record, {"type", "id", "simplex"}, loc)
            return LeafNode(_id(record["id"], loc), _id(record["simplex"], loc), loc)
        _object(record, {"type", "id", "normal", "offset", "minus", "plus"}, loc)
        normal = tuple(
            parse_rational(item) for item in _array(record["normal"], dimension, loc)
        )
        if not any(normal):
            _reject("schema_normal", "Split normal must be nonzero", loc)
        return SplitNode(
            _id(record["id"], loc),
            normal,
            parse_rational(record["offset"]),
            _id(record["minus"], loc),
            _id(record["plus"], loc),
            loc,
        )

    def _comparison(
        self, stream: Literal["sp", "approximation"]
    ) -> Iterator[RootBlock]:
        if stream in self._started:
            raise ValueError(f"{stream} is a one-shot stream")
        self._started.add(stream)
        return self._consume(stream)

    def _consume(self, stream: Literal["sp", "approximation"]) -> Iterator[RootBlock]:
        yield from self._roots(stream)
        self._finished.add(stream)

    def iter_sp_roots(self) -> Iterator[RootBlock]:
        """One-shot SP stream; consume through StopIteration to check EOF."""
        return self._comparison("sp")

    def iter_approximation_roots(self) -> Iterator[RootBlock]:
        """One-shot approximation stream; consume through StopIteration."""
        return self._comparison("approximation")

    @property
    def streams_exhausted(self) -> bool:
        """Both comparison EOF checks ran; this is not global admissibility."""
        return self._finished == {"sp", "approximation"}


def read_bundle(directory: str | Path) -> DecodedBundle:
    """Decode all five files to EOF. Return records, never verifier success."""
    reader = BundleReader(directory)
    sp = tuple(reader.iter_sp_roots())
    approximation = tuple(reader.iter_approximation_roots())
    return DecodedBundle(
        reader.manifest, reader.vertices, reader.attribution, sp, approximation
    )
