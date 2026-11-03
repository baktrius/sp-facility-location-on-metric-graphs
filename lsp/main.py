import functools as fn
import gc
import hashlib
import importlib.metadata
import itertools as it
import json
import math
import operator
import os
import pickle
import random
import resource
import shutil
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from math import floor
from pathlib import Path
from typing import (
    Any,
    Callable,
    Iterable,
    Mapping,
    NoReturn,
    Optional,
    TypeAlias,
    TypeVar,
    overload,
)

import networkx as nx
import numpy as np
import psutil
import pulp as pl
import pytest
import sympy as sp
import typer
from IPython import embed
from matplotlib import pyplot as plt
from rich import print  # noqa
from rich.console import Console
from rich.pretty import Pretty
from rich.progress import track
from rich.table import Table

# import tracemalloc

app = typer.Typer(pretty_exceptions_enable=False)
console = Console()

Real: TypeAlias = float


def div(a: int, b: int) -> Real:
    return a / b


# from sympy import Rational, Number

# Real: TypeAlias = Number


# def div(a: int, b: int) -> Real:
#     return Rational(a, b)


T = TypeVar("T")
U = TypeVar("U")
V = TypeVar("V")
Graph: TypeAlias = nx.Graph
Node: TypeAlias = str
NodesTuple: TypeAlias = tuple[Node, ...]
GeneralNodesLottery: TypeAlias = Mapping[Node, T]
NodesLottery: TypeAlias = GeneralNodesLottery[Real]
ExGeneralMechanism: TypeAlias = Callable[[NodesTuple], Mapping[U, T]]
GeneralMechanism: TypeAlias = ExGeneralMechanism[Node, T]
Mechanism: TypeAlias = GeneralMechanism[Real]
MechanismDict: TypeAlias = dict[NodesTuple, NodesLottery]
GraphAutomorphism: TypeAlias = Callable[[Node], Node]


def assert_false() -> NoReturn:
    raise AssertionError()


def str_lottery(lot: GeneralNodesLottery[T]) -> str:
    # skip the nodes with zero probability
    return str({node: prob for node, prob in lot.items() if prob != 0})


class Lottery(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __str__(self):
        return str_lottery(self)

    def __repr__(self):
        return str(self)


def add_edge_with_nodes(
    graph: Graph,
    start_node: Node,
    end_node: Node,
    num_intermediate_nodes: int,
    edge_label: str,
) -> None:
    prev = start_node
    for i in range(num_intermediate_nodes):
        node = edge_label + str(i)
        graph.add_node(node)
        graph.add_edge(prev, node)
        prev = node
    graph.add_edge(prev, end_node)


def get_median_node(
    graph: nx.DiGraph,
    root: Node,
    agents_nodes: NodesTuple,
    threshold: None | int = None,
) -> tuple[Optional[Node], int]:
    """
    Find the median node in the tree with respect to the agents nodes.
    """
    if threshold is None:
        threshold = len(agents_nodes) // 2
    result = 0
    for child in graph.successors(root):
        node, agents_num = get_median_node(graph, child, agents_nodes, threshold)
        if node is not None:
            return node, agents_num
        result += agents_num
    result += sum(node == root for node in agents_nodes)
    if result > threshold:
        return root, result
    return None, result


def get_simple_graph(edges: Iterable[tuple[Node, Node, int, str]]) -> Graph:
    graph = nx.Graph()
    for edge in edges:
        add_edge_with_nodes(graph, *edge)
    return graph


def get_circle_graph(n: int, prefix: str = "") -> Graph:
    graph = nx.Graph()
    for i in range(n):
        graph.add_edge(prefix + str(i), prefix + str((i + 1) % n))
    return graph


def get_circle_graph_automorphisms(n: int, prefix: str = "") -> list[GraphAutomorphism]:
    def mapper(f: Callable[[int], int]) -> Callable[[Node], Node]:
        return lambda node: prefix + str(f(int(node[len(prefix) :])))

    cyclic_shift = mapper(lambda x: (x + 1) % n)
    mirror1 = mapper(lambda x: n - x - 1)
    mirror2 = mapper(lambda x: (n - x) % n)

    if n % 2 == 0:
        return [cyclic_shift, mirror1, mirror2]
    return [cyclic_shift, mirror1]


def get_sample_graph1(m: int = 1, labels: str = "ab") -> Graph:
    return get_simple_graph([("1", "2", m, label) for label in labels])


def get_sample_graph1_automorphisms(
    m: int = 1, labels: str = "ab"
) -> list[GraphAutomorphism]:
    def swap_ab(node: Node) -> Node:
        if node.startswith(labels[0]):
            return labels[1] + node[1:]
        if node.startswith(labels[1]):
            return labels[0] + node[1:]
        return node

    def cyclic_swap(node: Node) -> Node:
        if node in ["1", "2"]:
            return node
        return labels[(labels.index(node[0]) + 1) % len(labels)] + node[1:]

    def mirror(node: Node) -> Node:
        if node == "1":
            return "2"
        if node == "2":
            return "1"
        edge, index = node[0], int(node[1:])
        new_index = m - index - 1
        return edge + str(new_index)

    if len(labels) <= 1:
        return [mirror]
    elif len(labels) == 2:
        return [swap_ab, mirror]
    return [swap_ab, cyclic_swap, mirror]


class FunctionDict(Mapping[T, U]):
    def __init__(self, fun: Callable):
        self.fun = fun
        self.cache = {}

    def __getitem__(self, key: T) -> U:
        if key not in self.cache:
            self.cache[key] = self.fun(key)
        return self.cache[key]

    def __iter__(self):
        raise NotImplementedError

    def __len__(self) -> int:
        raise NotImplementedError


def is_automorphism(graph: Graph, automorphism: GraphAutomorphism) -> bool:
    return nx.utils.graphs_equal(
        graph,
        nx.relabel_nodes(graph, FunctionDict(automorphism)),  # type: ignore
    )


def is_vertex_important(graph: Graph, v: Node, agents_nodes: NodesTuple) -> bool:
    """
    Check if the vertex is important for the agents (can't be contracted).
    """
    return v in agents_nodes or graph.degree[v] > 2  # type: ignore


@overload
def rotate(seq: list[U], n: int = 1) -> list[U]: ...


@overload
def rotate(seq: tuple[U, ...], n: int = 1) -> tuple[U, ...]: ...


def rotate(seq: list[U] | tuple[U, ...], n: int = 1) -> list[U] | tuple[U, ...]:
    return seq[n:] + seq[:n]


def get_basic_paths(
    graph: Graph, agents_nodes: NodesTuple
) -> list[list[tuple[Node, Node]]]:
    """
    Simplify the graph by contracting the edges.
    """
    ears = list(nx.chain_decomposition(graph))
    basic_paths = []
    for ear in ears:
        while not is_vertex_important(graph, ear[0][0], agents_nodes):
            ear = rotate(ear)
        for e in ear:
            if is_vertex_important(graph, e[0], agents_nodes):
                basic_paths.append([])
            basic_paths[-1].append(e)
    return basic_paths


SimplePaths = list[tuple[Node, Node, int]]


def simplify_basic_paths(basic_paths: list[list[tuple[Node, Node]]]) -> SimplePaths:
    return [(path[0][0], path[-1][1], len(path)) for path in basic_paths]


def get_simplified_graph(simple_basic_paths: SimplePaths) -> nx.MultiGraph:
    return nx.MultiGraph([(v1, v2) for v1, v2, _ in simple_basic_paths])


def gen_relevant_trees(
    simple_basic_paths: SimplePaths, constructed_graph: nx.MultiGraph, weight: int = 1
):
    path = simple_basic_paths.pop()
    v1, v2, v_weight = path
    constructed_graph.remove_edge(v1, v2)
    if simple_basic_paths:
        yield from gen_relevant_trees(
            simple_basic_paths, constructed_graph, v_weight * weight
        )
    elif nx.is_tree(constructed_graph):
        yield constructed_graph, v_weight * weight
    constructed_graph.add_edge(v1, v2)
    if simple_basic_paths:
        yield from gen_relevant_trees(simple_basic_paths, constructed_graph, weight)
    elif nx.is_tree(constructed_graph):
        yield constructed_graph, weight
    simple_basic_paths.append(path)


def normalize_lottery(lot: dict[Any, int]) -> NodesLottery:
    total_weight = sum(lot.values())
    return {key: div(val, total_weight) for key, val in lot.items()}


def gpcd(graph: Graph) -> Mechanism:
    def m(agents_nodes: NodesTuple) -> NodesLottery:
        # check if the agents_nodes are in the graph
        assert all(node in graph.nodes for node in agents_nodes)
        basic_paths = get_basic_paths(graph, agents_nodes)
        simple_basic_paths = simplify_basic_paths(basic_paths)
        simple_graph = get_simplified_graph(simple_basic_paths)
        res = {}
        for relevant_tree, weight in gen_relevant_trees(
            simple_basic_paths, simple_graph
        ):
            root = agents_nodes[0]
            oriented_tree = nx.dfs_tree(relevant_tree, root)
            median_node, _ = get_median_node(oriented_tree, root, agents_nodes)
            res[median_node] = res.get(median_node, 0) + weight
        return normalize_lottery(res)

    return m


# pylint: disable-next=unused-argument
def rd(graph: Optional[Graph] = None) -> Mechanism:
    def m(agents_nodes: NodesTuple) -> NodesLottery:
        res = {}
        for agent in agents_nodes:
            res[agent] = res.get(agent, 0) + 1
        return normalize_lottery(res)

    return m


def combine_mechanisms(m1: Mechanism, m2: Mechanism, w1: Real) -> Mechanism:
    def merged_mechanism(agents_nodes: NodesTuple) -> NodesLottery:
        res1 = m1(agents_nodes)
        res2 = m2(agents_nodes)
        return {
            node: w1 * res1.get(node, 0) + (1 - w1) * res2.get(node, 0)
            for node in res1.keys() | res2.keys()
        }

    return merged_mechanism


def gen_states_of_world(graph: Graph, num_of_agents: int, ordered: bool = True):
    if ordered:
        return it.combinations_with_replacement(graph.nodes, num_of_agents)
    return it.product(graph.nodes, repeat=num_of_agents)


def mechanism_as_dict(
    graph: Graph, num_of_agents: int, mechanism: Mechanism
) -> MechanismDict:
    res = dict()
    for state_of_world in gen_states_of_world(graph, num_of_agents):
        res[state_of_world] = mechanism(state_of_world)
    return res


NodesDistances: TypeAlias = Callable[[Node, Node], Real]


def distances(graph: Graph) -> NodesDistances:
    dis = dict(nx.all_pairs_shortest_path_length(graph))
    return lambda v1, v2: dis[v1][v2]


def isum(iterable: Iterable[T], start: int | T = 0) -> T:
    for i in iterable:
        start += i  # type: ignore
    return start  # type: ignore


def cost(v1: Node, lot: GeneralNodesLottery[T], dis: NodesDistances, **kwargs) -> T:
    return isum((p * dis(v1, v2, **kwargs) for v2, p in lot.items()))  # type: ignore


def social_cost(
    agents_nodes: NodesTuple, lot: GeneralNodesLottery[T], dis: NodesDistances, **kwargs
) -> T:
    return isum((cost(v, lot, dis, **kwargs) for v in agents_nodes))


def all_argmin(iterable: Iterable[tuple[Real, Any]]) -> tuple[Real, tuple]:
    value = float("inf")
    res = []
    for v, el in iterable:
        if v < value:
            value = v
            res = [el]
        elif v == value:
            res.append(el)
    return value, tuple(res)


def get_opt(
    candidates: Iterable[Node],
    state: NodesTuple,
    dis: NodesDistances,
) -> tuple[Real, tuple[Node, ...]]:
    return all_argmin((social_cost(state, {v: 1}, dis), v) for v in candidates)


def tuple_assign(t: tuple[U, ...], i: int, el: U) -> tuple[U, ...]:
    return t[:i] + (el,) + t[i + 1 :]


def gen_deviations(s: NodesTuple, graph: Graph):
    for i, el in enumerate(s):
        for v in graph.nodes:
            if el != v:
                yield tuple_assign(s, i, v), el, i


def get_deviations_gen(states_of_world: set[NodesTuple]):
    def gen(s: NodesTuple, graph: Graph):
        return filter(lambda x: x[0] in states_of_world, gen_deviations(s, graph))

    return gen


def gen_sp_checks(
    graph: Graph,
    state_of_worlds: Iterable[NodesTuple],
    mechanism: GeneralMechanism[Any],
    epsilon: float = 0,
    deviations: Optional[Callable[[NodesTuple, Graph], Iterable[tuple]]] = None,
    dis: Optional[NodesDistances] = None,
):
    if deviations is None:
        deviations = gen_deviations
    if dis is None:
        dis = distances(graph)
    for state_of_world in state_of_worlds:
        real_res = mechanism(state_of_world)
        for deviated_state, agent, agent_i in deviations(state_of_world, graph):
            real_cost = cost(agent, real_res, dis)
            potential_res = mechanism(deviated_state)
            potential_cost = cost(agent, potential_res, dis)
            yield (
                real_cost <= potential_cost + epsilon,
                (
                    state_of_world,
                    real_res,
                    real_cost,
                    deviated_state,
                    potential_res,
                    potential_cost,
                    agent,
                    agent_i,
                ),
            )


def gen_lsp_checks(
    graph: Graph,
    state_of_worlds: Iterable[NodesTuple],
    mechanism: GeneralMechanism[Any],
    epsilon: float = 0,
    deviations: Optional[Callable[[NodesTuple, Graph], Iterable[tuple]]] = None,
    dis: Optional[NodesDistances] = None,
):
    assert deviations is None
    if dis is None:
        dis = distances(graph)
    for state_of_world in state_of_worlds:
        for agent_i, agent in enumerate(state_of_world):
            for d1, d2 in nx.bfs_edges(graph, agent):
                s1 = tuple_assign(state_of_world, agent_i, d1)
                s2 = tuple_assign(state_of_world, agent_i, d2)
                res1 = mechanism(s1)
                res2 = mechanism(s2)
                cost1 = cost(agent, res1, dis)
                cost2 = cost(agent, res2, dis)
                yield (
                    cost1 <= cost2 + epsilon,
                    (
                        state_of_world,
                        res1,
                        cost1,
                        s1,
                        res2,
                        cost2,
                        agent,
                        agent_i,
                    ),
                )


def get_apx_for_state(
    opt_candidates: Iterable[Node],
    state: NodesTuple,
    mechanism: Mechanism,
    dis: NodesDistances,
):
    real_res = mechanism(state)
    real_cost = social_cost(state, real_res, dis)
    opt_cost, _ = get_opt(opt_candidates, state, dis)
    return real_cost, opt_cost


def gen_apx(
    graph: Graph,
    state_of_worlds: Iterable[NodesTuple],
    mechanism: GeneralMechanism[Any],
    dis: Optional[NodesDistances] = None,
    opt_candidates: Optional[Callable[[NodesTuple], Iterable[Node]]] = None,
):
    if dis is None:
        dis = distances(graph)
    for state_of_world in state_of_worlds:
        if opt_candidates is None:
            yield get_apx_for_state(graph.nodes, state_of_world, mechanism, dis)
        else:
            yield get_apx_for_state(
                opt_candidates(state_of_world), state_of_world, mechanism, dis
            )


def apx(n: Real, d: Real) -> Real:
    if d == 0:
        return 1 if n == 0 else float("inf")
    return n / d


def get_apx(*args, **kwargs):
    return max(apx(*costs) for costs in gen_apx(*args, **kwargs))


def gen_sp_counterexamples(*args, **kwargs):
    return (exp for cond, exp in gen_sp_checks(*args, **kwargs) if not cond)


def gen_mechanism_definition_checks(
    mechanism: GeneralMechanism[Any],
    states_of_world: Iterable[NodesTuple],
):
    for state in states_of_world:
        res = mechanism(state)
        yield isum(res.values()) == 1


# Subclass of pl.LpVariable which __str__ and __repr__ also returns its value
class LpVariable(pl.LpVariable):
    def __str__(self):
        return f"{super().__str__()} ({pl.value(self)})"

    def __repr__(self):
        return f"{super().__repr__()} ({pl.value(self)})"


def get_lp_var(
    el,
    agents_nodes: NodesTuple,
    randomized: bool = True,
    suffix: str = "",
    initialValue: Optional[Real] = None,
) -> pl.LpVariable:
    lp_var = LpVariable(
        name=f"v_{','.join(map(str, agents_nodes))};{el}{suffix}",
        lowBound=0,
        upBound=1,
        cat=pl.LpContinuous if randomized else pl.LpBinary,
    )
    if initialValue is not None:
        lp_var.setInitialValue(initialValue)
    return lp_var


def get_sp_var(el, agents_nodes: NodesTuple, randomized: bool) -> sp.Symbol:
    return sp.Symbol(
        f"v_{''.join(map(str, agents_nodes))}{el}",
        real=True,
        positive=True,
    )


def get_general_mechanism(
    graph: Graph,
    res_lottery_support: Callable[[NodesTuple], tuple[T, ...]],
    automorphisms: Optional[list[GraphAutomorphism]] = None,
    anonymous: bool = False,
    unanimous: bool = False,
    randomized: bool = True,
    check_automorphisms: bool = True,
    agents: Optional[Iterable[int]] = None,
    get_variable: Optional[Callable[[T, NodesTuple, bool], U]] = None,
) -> ExGeneralMechanism[T, Real | U]:
    # TODO: vertex mechanism might not work well with automorphisms
    # in current implementation
    if automorphisms is None:
        automorphisms = []

    if check_automorphisms:
        for automorphism in automorphisms:
            assert is_automorphism(graph, automorphism)

    def get_abstraction_class(nodes: NodesTuple) -> list[NodesTuple]:
        res = set()
        res.add(nodes)
        stable = False
        while not stable:
            stable = True
            for automorphism in automorphisms:
                for el in res.copy():
                    new_el = tuple(automorphism(node) for node in el)
                    if anonymous:
                        new_el = new_el[:1] + tuple(sorted(new_el[1:]))
                    if new_el in res:
                        continue
                    res.add(new_el)
                    stable = False
        return list(res)

    abstraction_classes = nx.utils.UnionFind()

    def get_representative(nodes: NodesTuple) -> NodesTuple:
        if nodes not in abstraction_classes.parents:  # type: ignore
            new_class = get_abstraction_class(nodes)
            abstraction_classes.union(*new_class)
        return abstraction_classes[nodes]

    if get_variable is None:
        get_variable = fn.cache(get_lp_var)

    def get_or_id(d: Mapping[T, U], el: T) -> U | T:
        return d.get(el, el)

    def mechanism(
        agents_nodes: NodesTuple,
    ) -> Mapping[T, Real | U]:
        # check if the agents_nodes are in the graph
        assert all(node in graph.nodes for node in agents_nodes)
        support_map = {}
        agents_eq = {}
        if anonymous:
            if agents:
                ordered_agents = list(sorted(agents, key=agents_nodes.__getitem__))
                support_map = dict(zip(ordered_agents, agents, strict=True))
                # nodes_to_agent = {
                #     node: agent for agent, node in zip(agents, agents_nodes)
                # }
                # agents_eq = {
                #     agent: nodes_to_agent[node]
                #     for agent, node in zip(agents, agents_nodes)
                # }
            agents_nodes = tuple(sorted(agents_nodes))
        if unanimous and all(node == agents_nodes[0] for node in agents_nodes):
            return {agents_nodes[0]: 1.0}  # type: ignore
        res_support = res_lottery_support(agents_nodes)
        assert len(res_support) > 0
        if len(res_support) == 1:
            return {res_support[0]: 1.0}
        res = {}
        for el in res_support:
            _el, *_agents_nodes = get_representative(
                (get_or_id(support_map, get_or_id(agents_eq, el)),) + agents_nodes
            )
            res[el] = get_variable(_el, tuple(_agents_nodes), randomized=randomized)
        return res

    return mechanism


def is_sp(
    graph: Graph,
    states_of_world: Iterable[NodesTuple],
    mechanism: Mechanism,
    dis: Optional[NodesDistances] = None,
    epsilon: float = 0,
) -> bool:
    return not any(
        gen_sp_counterexamples(
            graph, states_of_world, mechanism, dis=dis, epsilon=epsilon
        )
    )


def assert_not_none(v: Optional[T]) -> T:
    assert v is not None
    return v


def general_mechanism_to_mechanism(
    mechanism: ExGeneralMechanism[T, Real | pl.LpVariable],
) -> ExGeneralMechanism[T, Real]:
    def res_m(agents_nodes: NodesTuple, **kwargs) -> Mapping[T, Real]:
        return {
            node: assert_not_none(pl.value(v))
            for node, v in mechanism(agents_nodes, **kwargs).items()
        }  # type: ignore

    return res_m


def solve_lp_mechanism(
    graph: Graph,
    states_of_world: Iterable[NodesTuple],
    mechanism: GeneralMechanism[Real | pl.LpVariable],
    epsilon: float = 0,
    minimize_apx: bool = False,
    suppress_output: bool = False,
    deviations: Optional[Callable[[NodesTuple, Graph], Iterable[tuple]]] = None,
    return_model: Optional[dict] = None,
    secondary_objective: Optional[Callable[[pl.LpProblem], None]] = None,
    dis: Optional[NodesDistances] = None,
    additional_constraints: Optional[Iterable[pl.LpConstraint]] = None,
    enforce_lsp: bool = False,
) -> Mechanism:
    model = pl.LpProblem(name="sp_mechanism", sense=pl.LpMinimize)

    if return_model is not None:
        return_model["value"] = model

    states = list(states_of_world)
    for constraint in gen_mechanism_definition_checks(mechanism, states):
        model += constraint
    gen_next_checks = gen_lsp_checks if enforce_lsp else gen_sp_checks
    for check, description in gen_next_checks(
        graph, states, mechanism, epsilon, deviations=deviations, dis=dis
    ):
        if check is sp.true:
            check = True
        if check is False:
            raise ValueError(description)
        model += check
    if minimize_apx:
        alpha = pl.LpVariable(name="alpha", lowBound=0)
        for real_cost, opt_cost in gen_apx(graph, states, mechanism, dis=dis):
            model += real_cost <= alpha * opt_cost
        model.setObjective(alpha)
    if additional_constraints is not None:
        for constraint in additional_constraints:
            model += constraint
    status = model.solve(pl.COIN_CMD(msg=not suppress_output, path=get_cbc_path()))
    if status != pl.LpStatusOptimal:
        raise ValueError(
            f"Fails to solve the LP problem. Status: {pl.LpStatus[status]}"
        )

    # Apply the secondary objective if provided
    if secondary_objective is not None:
        # Fix the primary objective value
        primary_objective_value = pl.value(model.objective)
        model.addConstraint(model.objective <= primary_objective_value + 0.000001)  # type: ignore

        secondary_objective(model)
        status = model.solve(pl.COIN_CMD(msg=not suppress_output, path=get_cbc_path()))
        if status != pl.LpStatusOptimal:
            raise ValueError(
                f"Fails to solve the LP problem with secondary objective. Status: {pl.LpStatus[status]}"
            )

    return general_mechanism_to_mechanism(mechanism)


def union_mechanism(*ms: Mechanism) -> Mechanism:
    def m(agents_nodes: NodesTuple) -> NodesLottery:
        res = None
        for mechanism in ms:
            try:
                lot = mechanism(agents_nodes)
                if res is None:
                    res = lot
                else:
                    # check consistency with the previous mechanisms
                    for node, prob in lot.items():
                        if res.get(node, 0) != prob:
                            raise ValueError("The mechanisms are not compatible.")
            except AssertionError:
                continue
        if res is None:
            raise ValueError("No compatible mechanism found.")
        return res

    return m


def fallback_mechanism(
    m1: GeneralMechanism[T], m2: GeneralMechanism[U]
) -> GeneralMechanism[T | U]:
    def m(agents_nodes: NodesTuple) -> GeneralNodesLottery[T | U]:
        try:
            return m1(agents_nodes)
        except (AssertionError, ValueError):
            return m2(agents_nodes)

    return m


def opt_mechanism(graph: Graph) -> Mechanism:
    def m(agents_nodes: NodesTuple) -> NodesLottery:
        dis = distances(graph)
        _, opt_nodes = get_opt(graph.nodes, agents_nodes, dis)
        return {node: 1 / len(opt_nodes) for node in opt_nodes}

    return m


def opt_mechanism2(
    graph: Graph,
    states_of_world: Iterable[NodesTuple],
    *args,
    epsilon: float = 0,
    suppress_output: bool = True,
    minimize_apx: bool = False,
    return_model: Optional[dict] = None,
    **kwargs,
) -> Mechanism:
    dis = distances(graph)
    lp_mechanism = get_general_mechanism(
        graph, lambda s: get_opt(graph.nodes, s, dis)[1], *args, **kwargs
    )
    return solve_lp_mechanism(
        graph,
        states_of_world,
        lp_mechanism,
        epsilon=epsilon,
        suppress_output=suppress_output,
        minimize_apx=minimize_apx,
        return_model=return_model,
    )


def has_optimal_sp_mechanism(
    graph: nx.Graph,
    *args,
    states_of_world: Optional[Iterable[NodesTuple]] = None,
    **kwargs,
) -> bool:
    if states_of_world is None:
        states_of_world = gen_states_of_world(graph, 3)
    try:
        opt_mechanism2(graph, states_of_world, *args, **kwargs)
        return True
    except ValueError:
        return False


def test_rd_is_sp():
    graph = get_sample_graph1(3, "abc")
    assert is_sp(graph, gen_states_of_world(graph, 3), rd(graph))


def test_gpcd_is_not_sp():
    graph = get_sample_graph1(3, "abc")
    assert not is_sp(graph, gen_states_of_world(graph, 3), gpcd(graph))


def main1():
    """
    Generates the sp counterexamples for of the gpcd mechanism on circle with 3 medians.
    """
    graph = get_sample_graph1(3, "abcde")
    # print(G.nodes)
    # print("=" * 80)
    # for state_of_world, res_lottery in mechanism_as_dict(G, 3, gpcd).items():
    #     print(str(state_of_world).ljust(20), ":", res_lottery)
    # print(distances(G))
    num_of_agents = 3
    states = list(gen_states_of_world(graph, num_of_agents))
    for ce in gen_sp_counterexamples(graph, states, fn.cache(gpcd(graph))):
        gain = ce[2] - ce[5]
        if gain > 0.1:
            print(gain / (num_of_agents + 1), ce)


# pylint: disable-next=invalid-name
def test_pcd_is_not_extensible_to_K3_2():
    # TODO: this seems to be unfinished because there is no assertion at the end
    """
    Checks that there aren't extensions of pcd mechanism to the K3,2 graph which are SP
    (up to some epsilon).
    """
    graph_config = (3, "abc")
    graph = get_sample_graph1(*graph_config)
    graph_automorphisms = get_sample_graph1_automorphisms(*graph_config)
    graph_ab = nx.induced_subgraph(
        graph, ["1", "2", "a0", "a1", "a2", "b0", "b1", "b2"]
    )
    graph_ac = nx.induced_subgraph(
        graph, ["1", "2", "a0", "a1", "a2", "c0", "c1", "c2"]
    )
    graph_bc = nx.induced_subgraph(
        graph, ["1", "2", "b0", "b1", "b2", "c0", "c1", "c2"]
    )
    # construct the lp mechanism for the K3,2 graph
    # which has fixed results for states with 3 agents on one circle subgraph
    mechanism_ab = gpcd(graph_ab)
    mechanism_ac = gpcd(graph_ac)
    mechanism_bc = gpcd(graph_bc)
    mechanism_abc = union_mechanism(mechanism_ab, mechanism_ac, mechanism_bc)
    mechanism = get_general_mechanism(
        graph, lambda s: tuple(graph.nodes), graph_automorphisms, anonymous=True
    )
    mechanism_lp = fallback_mechanism(mechanism_abc, mechanism)
    states = list(gen_states_of_world(graph, 3))
    # with pytest.raises(ValueError):
    model_wrapper = {}
    solve_lp_mechanism(
        graph,
        states,
        mechanism_lp,
        epsilon=0,
        return_model=model_wrapper,
        minimize_apx=True,
    )
    # model = model_wrapper["value"]
    # M2 = solve_lp_mechanism(graph, states, mechanism_lp, epsilon=0.1)

    # for state in gen_states_of_world(graph, 3):
    #     v = M2(state)
    #     print(state, v)

    # for ce in gen_sp_counterexamples(graph, states, M2):
    #     gain = ce[2] - ce[5]
    #     if gain > 0.000001:
    #         print(ce)


# pylint: disable-next=invalid-name
def get_best_sp_mechanism_on_K3_2():
    graph_config = (3, "abc")
    graph = get_sample_graph1(*graph_config)
    graph_automorphisms = get_sample_graph1_automorphisms(*graph_config)
    mechanism = get_general_mechanism(
        graph, lambda s: tuple(set(s) | {"1", "2"}), graph_automorphisms, anonymous=True
    )
    states = list(gen_states_of_world(graph, 3))
    model_wrapper = {}
    res_mechanism = solve_lp_mechanism(
        graph, states, mechanism, minimize_apx=True, return_model=model_wrapper
    )
    return res_mechanism, model_wrapper["value"], states


# pylint: disable-next=invalid-name
def test_existence_of_optimal_sp_mechanism_on_K3_2():
    _, model, _ = get_best_sp_mechanism_on_K3_2()
    assert model.objective.value() == 1


def main3():
    """
    Investigates the best mechanism for the K3,2 graph (it's optimal).
    """
    mechanism, _, states = get_best_sp_mechanism_on_K3_2()

    for state in states:
        v = mechanism(state)
        print(state, v)

    embed()


# pylint: disable-next=invalid-name
def test_uniformly_mixed_optimal_mechanism_on_K3_2_is_not_sp():
    graph = get_sample_graph1(3, "abc")
    opt_m = opt_mechanism(graph)
    assert not is_sp(graph, gen_states_of_world(graph, 3), opt_m)


def test_compare_search_of_optimal_sp_mechanism_on_circles_with_meirs_result():
    N = 15
    assert N > 12

    circle_sizes_with_optimal_sp_mechanism = [
        n for n in range(3, N) if has_optimal_sp_mechanism(get_circle_graph(n))
    ]

    assert circle_sizes_with_optimal_sp_mechanism == [*range(3, 11), 12]


def test_anonymous_neutral_mechanisms_admits_same_optimal_mechanism():
    N = 15
    assert N > 12

    circle_sizes_with_optimal_sp_mechanism = []
    for n in range(3, N):
        graph = get_circle_graph(n)
        graph_automorphisms = get_circle_graph_automorphisms(n)
        if has_optimal_sp_mechanism(
            graph, anonymous=True, automorphisms=graph_automorphisms
        ):
            circle_sizes_with_optimal_sp_mechanism.append(n)

    assert circle_sizes_with_optimal_sp_mechanism == [*range(3, 11), 12]


def test_compare_search_of_deterministic_anonymous_sp_mechanism_on_circles_with_dakovs_result():
    N = 8
    M = 3

    circle_sizes_with_anonymous_sp_mechanism = []
    for n in range(M, N):
        graph = get_circle_graph(n)
        graph_nodes = tuple(graph.nodes)
        states = list(gen_states_of_world(graph, M))
        # G_automorphisms = get_circle_graph_automorphisms(n)
        anonymous_m = get_general_mechanism(
            graph,
            lambda s, nodes=graph_nodes: nodes,
            anonymous=True,
            unanimous=True,
            # automorphisms=G_automorphisms,
            randomized=False,
        )
        try:
            solve_lp_mechanism(graph, states, anonymous_m, suppress_output=True)
            circle_sizes_with_anonymous_sp_mechanism.append(n)
            # print(f"{n} admits anonymous SP mechanism")
        except ValueError:
            pass
            # print(f"{n} doesn't admit anonymous SP mechanism")

    assert circle_sizes_with_anonymous_sp_mechanism == [*range(M, N)]


def main5():
    """
    Search for graph for which the optimal mechanism isn't SP.
    """

    graphs = [
        *[
            (
                f"sample_1_{n}_abc",
                get_sample_graph1(n, "abc"),
                get_sample_graph1_automorphisms(n, "abc"),
            )
            for n in range(4, 5)
        ],
    ]
    for name, graph, automorphisms in graphs:
        states = list(gen_states_of_world(graph, 3))
        try:
            opt_mechanism2(
                graph,
                states,
                randomized=True,
                anonymous=True,
                automorphisms=automorphisms,
            )
            print(f"{name} admits optimal SP mechanism")
        except ValueError as e:
            print(f"{name} doesn't admit optimal SP mechanism reason")
            print(e)
            vertex_m = get_general_mechanism(
                graph,
                lambda s, nodes=tuple(graph.nodes): nodes,
                # automorphisms,
                # anonymous=True,
            )
            model_wrapper = {}
            m = solve_lp_mechanism(
                graph,
                states,
                vertex_m,
                minimize_apx=True,
                suppress_output=True,
                return_model=model_wrapper,
            )
            print(f"Minimal apx: {get_apx(graph, states, m)}")

            embed()


def get_best_apx_with_restricted_states(graph, states):
    lp_mechanism = get_general_mechanism(graph, lambda s: tuple(graph.nodes))
    model_wrapper = {}
    res_mechanism = solve_lp_mechanism(
        graph,
        states,
        lp_mechanism,
        minimize_apx=True,
        return_model=model_wrapper,
        suppress_output=True,
        deviations=get_deviations_gen(set(states)),
    )
    model = model_wrapper["value"]
    return res_mechanism, model.objective.value()


def test_apx_on_two_states():
    graph = get_sample_graph1(4, "abc")
    states = [("a1", "b1", "c2"), ("a1", "b1", "2")]
    _, res_apx = get_best_apx_with_restricted_states(graph, states)
    assert res_apx == 1.04


def get_two_states_apx(args):
    # max found: (1.0734733, 19, 8, 5)
    # max with different length: (1.0735806, (18, 9, -2))
    dis1, diff, len_mod = args
    num_of_agents = 4
    letters = "abcdefghijklmnopqrstuvwxy"[:num_of_agents]
    graph = get_sample_graph1(199, letters)
    last_edge_len = 200 + 2 * len_mod
    add_edge_with_nodes(graph, "1", "2", last_edge_len - 1, "z")
    pos1 = str(100 - dis1)
    states_prefix = tuple(letter + pos1 for letter in letters)
    states = [
        states_prefix + ("z" + str(last_edge_len // 2 + dis1 + diff),),
        states_prefix + ("2",),
    ]
    return get_best_apx_with_restricted_states(graph, states)[1], args


def test_variants_of_two_states():
    pool = ProcessPoolExecutor()
    results = pool.map(
        get_two_states_apx, it.product(range(17, 20), range(8, 11), range(-3, 0))
    )
    best_config = max(results)
    assert best_config[0] >= 1.0735805
    assert best_config[1] == (18, 9, -2)
    # for res in sorted(results):
    #     print(res)


@app.command()
def inspect_best_mechanisms_on_circle(n: int = 12):
    graph = get_circle_graph(n)
    dis = distances(graph)
    graph_automorphisms = get_circle_graph_automorphisms(n)
    states = list(gen_states_of_world(graph, 3))
    # states = [("0",) + s for s in gen_states_of_world(G, 2)]
    model_wrapper = {}
    lp_m = get_general_mechanism(
        graph, lambda s: s, automorphisms=graph_automorphisms, anonymous=True
    )

    def secondary_objective(model: pl.LpProblem):
        beta = pl.LpVariable(name="beta", lowBound=0)
        avg_social_cost = isum(
            social_cost(state, lp_m(state), distances(graph)) for state in states
        )
        model += beta == avg_social_cost
        model.setObjective(beta)

    m = solve_lp_mechanism(
        graph,
        states,
        lp_m,
        minimize_apx=True,
        return_model=model_wrapper,
        suppress_output=False,
        secondary_objective=secondary_objective,
    )
    res_apx = get_apx(graph, states, m)
    print(f"{n}: Minimal apx: {res_apx}")
    if res_apx > 1:
        states_with_fixed_agent1 = [s for s in states if s[0] == "0"]
        suboptimal_states = [
            (s, v)
            for s in states_with_fixed_agent1
            if (v := apx(*get_apx_for_state(graph.nodes, s, m, dis))) > 1
        ]
        num_of_suboptimal_states = len(suboptimal_states)
        print(f"Suboptimal states: {num_of_suboptimal_states}")
        print(f"All states: {len(states_with_fixed_agent1)}")
        coordinates = [s[0][1:] for s in suboptimal_states]
        plt.scatter(
            *zip(*coordinates, strict=True), c=[s[1] for s in suboptimal_states]
        )
        plt.colorbar()
        # for 3d plot
        # coordinates = [[int(u) for u in s[1:]] for s, _ in suboptimal_states]
        # fig = plt.figure()
        # ax = fig.add_subplot(111, projection="3d")
        # ax.scatter(*zip(*coordinates), marker="o", c="r")
        # plt.show()

        embed()


def check_whether_big_deviations_implies_small():
    v = 12
    circle = get_circle_graph(v)
    # circle_automorphisms = get_circle_graph_automorphisms(v)
    lp_m = get_general_mechanism(
        circle,
        lambda s: tuple(circle.nodes),
        # circle_automorphisms,
        anonymous=True,
        unanimous=True,
        randomized=False,
    )
    states = list(gen_states_of_world(circle, 3))
    dis = distances(circle)
    model = pl.LpProblem(name="sp_mechanism", sense=pl.LpMaximize)
    deviations = get_deviations_gen(set(states))
    suppress_output = False
    for constraint in gen_mechanism_definition_checks(lp_m, states):
        model += constraint
    # first_big_dev = True
    # real_costs_in_big_dev = []
    # potential_costs_in_big_dev = []
    for check, description in gen_sp_checks(
        circle, states, lp_m, 0, deviations=deviations
    ):
        state_of_world, _, real_cost, deviated_state, _, potential_cost, _, agent_i = (
            description
        )
        # check that agent_i deviated to vertex which is neighbor of real vertex
        if dis(state_of_world[agent_i], deviated_state[agent_i]) <= 1:
            model += check
        else:
            # add the opposite constraint
            model += real_cost >= potential_cost + 0.001
        # first_big_dev = False
        # real_costs_in_big_dev.append(real_cost)
        # potential_costs_in_big_dev.append(potential_cost)

    status = model.solve(pl.COIN_CMD(msg=not suppress_output, path=get_cbc_path()))
    if status != pl.LpStatusOptimal:
        print(f"Fails to solve the LP problem. Status: {pl.LpStatus[status]}")
    # for real_cost, potential_cost in zip(
    #     real_costs_in_big_dev, potential_costs_in_big_dev
    # ):
    #     model.setObjective(real_cost - potential_cost)
    #     status = model.solve(pl.COIN_CMD(
    #         msg=not suppress_output, path=get_cbc_path())
    #     )
    #     if status != pl.LpStatusOptimal:
    #         raise ValueError(
    #             f"Fails to solve the LP problem. Status: {pl.LpStatus[status]}"
    #         )
    #         # print(f"Fails to solve the LP problem. Status: {pl.LpStatus[status]}")
    #         # continue
    #     value = pl.value(model.objective)
    #     print(value)
    #     if value > 0:
    #         print(real_cost, potential_cost)
    #         embed()
    #         break

    # def res_m(agents_nodes: NodesTuple) -> NodesLottery:
    #     return Lottery({node: pl.value(v) for node, v in lp_m(agents_nodes).items()})

    # embed()

    status = model.solve(pl.COIN_CMD(msg=not suppress_output, path=get_cbc_path()))
    if status != pl.LpStatusOptimal:
        print(f"Fails to solve the LP problem. Status: {pl.LpStatus[status]}")


def map_dict_keys(d: Mapping[T, U], mapping: Mapping[T, V]) -> Mapping[V, U]:
    res = {}
    for k, v in d.items():
        mapped_key = mapping[k]
        res[mapped_key] = res.get(mapped_key, 0) + v
    return res


def vertex_mechanism_to_mechanism(
    mechanism: ExGeneralMechanism[T, U],
) -> ExGeneralMechanism[Node, U]:
    def res_m(state: NodesTuple, *args, **kwargs) -> Mapping[Node, U]:
        state_map = dict(enumerate(state))
        return map_dict_keys(mechanism(state, *args, **kwargs), state_map)

    return res_m


def get_spline0_mechanism(s, anonymous=True):
    agents = tuple(range(3))
    inner_g = get_circle_graph(s, prefix="v")
    support = agents  # tuple(list(inner_g.nodes) + list(agents))
    inner_m = get_general_mechanism(inner_g, lambda _: support, anonymous=anonymous)
    graph = nx.Graph(inner_g)
    # set weight of each existing edge in graph to 1
    for u, v in graph.edges:
        graph[u][v]["weight"] = 1
    # create copy of each node in graph
    # (node which is connected to the original node with edge of length 0)
    for node in list(graph.nodes):
        graph.add_edge(node, (42, node), weight=0)
    cyclic_shift, *_ = get_circle_graph_automorphisms(s, prefix="v")

    def nodes_map(node: Node) -> Node:
        if isinstance(node, tuple) and node[0] == 42:
            if node[1] in agents:
                return node[1]
            return cyclic_shift(node[1])
        return node

    def extended_mechanism(state: NodesTuple):
        return inner_m(tuple(nodes_map(node) for node in state))

    mechanism = vertex_mechanism_to_mechanism(extended_mechanism)

    # warm start for the mechanism by setting it to RD
    # for state in gen_states_of_world(inner_g, 3):
    #     res = inner_m(state)
    #     for key, val in res.items():
    #         assert isinstance(val, pl.LpVariable)
    #         val.setInitialValue(1 / 3 if key in agents else 0)

    _dis = dict(nx.all_pairs_dijkstra_path_length(graph))
    dis = lambda v1, v2, c=_dis: c[v1][v2]
    states = list(gen_states_of_world(graph, 3, ordered=anonymous))
    # res0 = extended_mechanism(("v0", "v0", "v0"))
    # res1 = extended_mechanism(("v3", "v0", "v0"))
    return (
        solve_lp_mechanism(
            graph,
            states,
            mechanism,
            dis=dis,
            minimize_apx=True,
            # additional_constraints=[
            #     res0[0] >= 1 / 2,
            #     res1[0] <= 6 / 13,
            # ],
        ),
        inner_g,
        inner_m,
    )


# pylint: disable-next=invalid-name
@pytest.mark.skip(reason="Takes too long time to run")
def test_best_anonymous_spline0_mechanism_is_RD():
    res_m, graph, _ = get_spline0_mechanism(8, anonymous=False)
    rd_mechanism = rd()

    for state in gen_states_of_world(graph, 3, ordered=False):
        res = res_m(state)
        res2 = rd_mechanism(state)
        for key in res:
            if abs(res[key] - res2.get(key, 0)) > 0.0001:
                print(f"Mismatch for state {state}: {res} != {res2}")
                embed()
                assert_false()


@pytest.mark.skip(reason="Takes too long time to run")
# pylint: disable-next=invalid-name
def test_spline0_mechanism_is_SP():
    _, graph, inner_m = get_spline0_mechanism(8, anonymous=False)
    # add 3 intermediate nodes on each edge of the circle graph
    for u, v in list(graph.edges):
        graph.remove_edge(u, v)
        graph.add_edge(u, f"{v};0")
        graph.add_edge(f"{v};0", f"{v};1")
        graph.add_edge(f"{v};1", f"{v};2")
        graph.add_edge(f"{v};2", v)

    def nodes_map(node: Node) -> Node:
        return node.split(";")[0]

    def inner_ex_g(state):
        return inner_m(tuple(nodes_map(node) for node in state))

    extended_mechanism = vertex_mechanism_to_mechanism(
        general_mechanism_to_mechanism(inner_ex_g)
    )

    states = lambda: gen_states_of_world(graph, 3, ordered=False)
    # for example in gen_sp_counterexamples(graph, states(), extended_mechanism):
    #     print(example)
    #     embed()
    #     break
    assert is_sp(graph, states(), extended_mechanism)


def dict_mul(d: Mapping[T, U], c: U) -> Mapping[T, U]:
    if c == 0:
        return {}
    return {k: v * c for k, v in d.items()}


def dict_add(d1: Mapping[T, U], d2: Mapping[T, U]) -> Mapping[T, U]:
    res = dict(d1)
    for k, v in d2.items():
        res[k] = res.get(k, 0) + v
    return res


def get_order(
    t: tuple[Any, ...], order: Optional[tuple[int, ...]] = None
) -> tuple[int, ...]:
    # set order to be equal to tuple in which
    # at the first position is index of the lowest value in t
    # at the second position is index of the second lowest value in t
    # and so on
    if order is None:
        return tuple(sorted(range(len(t)), key=t.__getitem__))
    return order


def extend_mechanism_to_continuous(
    mechanism: ExGeneralMechanism[T, U], successors: Callable[[Node], Node]
) -> ExGeneralMechanism[T, U]:
    def res_m(
        agents_nodes: tuple[tuple[Node, Real], ...],
        order: Optional[tuple[int, ...]] = None,
    ) -> Mapping[T, U]:
        base_nodes, further_movement = zip(*agents_nodes, strict=True)
        next_nodes = tuple(successors(node) for node in base_nodes)
        prev = res = dict(mechanism(base_nodes))
        if further_movement == (0,) * len(further_movement):
            return res
        order = get_order(further_movement, order)
        curr_nodes = list(base_nodes)
        shift = 0
        n = len(agents_nodes)
        agents = tuple(range(n))
        for i in reversed(order):
            if int(next_nodes[i]) < int(curr_nodes[i]):
                shift += 1
            curr_nodes[i] = next_nodes[i]
            next_res = map_dict_keys(
                dict(mechanism(rotate(tuple(curr_nodes), n - shift))),
                dict(zip(rotate(agents, shift), agents, strict=True)),
            )
            res = dict_add(
                dict_add(res, dict_mul(next_res, further_movement[i])),
                dict_mul(prev, -further_movement[i]),
            )
            prev = next_res
        return res

    return res_m


def d_of_continuos_mechanism(
    mechanism: ExGeneralMechanism[T, U], successors: Callable[[Node], Node]
) -> ExGeneralMechanism[T, U]:
    def res_m(
        agents_nodes: tuple[tuple[Node, Real], ...],
        order: Optional[tuple[int, ...]] = None,
        coord: Optional[int] = None,
    ) -> Mapping[T, U]:
        assert coord is not None
        base_nodes, further_movement = zip(*agents_nodes, strict=True)
        next_nodes = tuple(successors(node) for node in base_nodes)
        order = get_order(further_movement, order)
        curr_nodes = list(base_nodes)
        shift = 0
        n = len(agents_nodes)
        agents = tuple(range(n))
        for i in reversed(order):
            if i == coord:
                break
            if int(next_nodes[i]) < int(curr_nodes[i]):
                shift += 1
            curr_nodes[i] = next_nodes[i]

        prev_res = map_dict_keys(
            dict(mechanism(rotate(tuple(curr_nodes), n - shift))),
            dict(zip(rotate(agents, shift), agents, strict=True)),
        )
        if int(next_nodes[coord]) < int(curr_nodes[coord]):
            shift += 1
        curr_nodes[coord] = next_nodes[coord]
        next_res = map_dict_keys(
            dict(mechanism(rotate(tuple(curr_nodes), n - shift))),
            dict(zip(rotate(agents, shift), agents, strict=True)),
        )
        return dict_add(next_res, dict_mul(prev_res, -1))

    return res_m


def map_mechanism_domain(
    mechanism: ExGeneralMechanism[T, U], mapping: Callable[[V], U]
) -> ExGeneralMechanism[V, U]:
    def res_m(agents_nodes: tuple[T, ...], *args, **kwargs) -> Mapping[V, U]:
        return mechanism(tuple(mapping(v) for v in agents_nodes), *args, **kwargs)

    return res_m


class ComparableSymbol(sp.Symbol):
    is_comparable = True

    __slots__ = ("lb", "ub")

    def __new__(cls, name, lb=None, ub=None, **assumptions):
        res = super().__new__(cls, name, **assumptions)
        res.lb = lb if lb is not None else set()
        res.ub = ub if ub is not None else set()
        return res

    def le(self, other):
        if self == other:
            return True
        if other in self.ub:
            return True
        if isinstance(other, ComparableSymbol):
            if self in other.lb:
                return True
            if self.ub & other.lb:
                return True
        return False

    def __le__(self, other):
        if self.le(other):
            return sp.true
        if other != self and other.le(self):
            return sp.false
        return sp.Expr.__le__(self, other)


def anonymize_mechanism(
    mechanism: ExGeneralMechanism[T, U],
) -> ExGeneralMechanism[T, U]:
    def res_m(agents_nodes: tuple[T, ...], *args, **kwargs) -> Mapping[T, U]:
        res = {}
        i = 0
        for reordered_nodes in it.permutations(agents_nodes):
            res = dict_add(res, mechanism(reordered_nodes, *args, **kwargs))
            i += 1
        res = dict_mul(res, 1 / i)
        return res

    return res_m


def real_to_node(real: Real | tuple[Node, Real]) -> tuple[Node, Real]:
    if isinstance(real, Real) or isinstance(real, int):
        return str(floor(real)), real - floor(real)
    return real


def extend_dis_to_continuous(
    dis: NodesDistances, successors: Callable[[Node], Node]
) -> Callable[[Real | tuple[Node, Real], Real | tuple[Node, Real]], Real]:
    def ex_dis(v1: Real | tuple[Node, Real], v2: Real | tuple[Node, Real]) -> Real:
        a1, b1 = real_to_node(v1)
        a2, b2 = real_to_node(v2)
        if a1 == a2:
            return abs(b1 - b2)
        s1 = successors(a1)
        s2 = successors(a2)
        return min(
            dis(a1, a2) + b1 + b2,
            dis(a1, s2) + b1 + dis(s2, a2) - b2,
            dis(s1, a2) + dis(s1, a1) - b1 + b2,
            dis(s1, s2) + dis(s1, a1) - b1 + dis(s2, a2) - b2,
        )

    return ex_dis


def get_continuous_dis_on_cycle(
    n: int,
) -> Callable[[tuple[Real, T], tuple[Real, T]], T]:
    # TODO: this function might not work correctly when several agents reports equal vertices
    def dis(
        v1: tuple[Real, T],
        v2: tuple[Real, T],
        state: NodesTuple,
        order: Optional[tuple[int]] = None,
    ) -> T:
        a1, b1 = v1
        a2, b2 = v2
        a1 = int(a1)
        a2 = int(a2)
        assert order is not None
        n1 = state.index(v1)
        n2 = state.index(v2)

        if order.index(n1) < order.index(n2):
            a2 = (a2 + n - a1) % n
            a1 = 0
            if a2 < n // 2:
                return a2 + b2 - b1
            return n - a2 - b2 + b1

        a1 = (a1 + n - a2) % n
        a2 = 0
        if a1 < n // 2:
            return a1 + b1 - b2
        return n - a1 - b1 + b2

    return dis


def get_continuous_vertex_dis_on_cycle(
    n: int,
) -> Callable[[int, int], Real]:
    def dis(
        n1: int,
        n2: int,
        state: Optional[tuple[tuple[str, Real], ...]] = None,
        order: Optional[tuple[int]] = None,
    ) -> Real:
        assert order is not None
        assert state is not None
        v1 = state[n1]
        v2 = state[n2]
        a1, b1 = v1
        a2, b2 = v2
        a1 = int(a1)
        a2 = int(a2)

        if order.index(n1) < order.index(n2):
            a2 = (a2 + n - a1) % n
            a1 = 0
            if a2 < n // 2:
                return a2 + b2 - b1
            return n - a2 - b2 + b1

        a1 = (a1 + n - a2) % n
        a2 = 0
        if a1 < n // 2:
            return a1 + b1 - b2
        return n - a1 - b1 + b2

    return dis


def test_median_is_lsp():
    graph = get_circle_graph(8)
    lp_m = get_general_mechanism(
        graph, lambda s: tuple(graph.nodes), anonymous=True, unanimous=True
    )
    states = list(gen_states_of_world(graph, 3))
    model_wrapper = {}
    res_m = solve_lp_mechanism(
        graph,
        states,
        lp_m,
        minimize_apx=True,
        enforce_lsp=True,
        return_model=model_wrapper,
    )
    model = model_wrapper["value"]
    assert model.objective.value() == 1
    assert is_sp(graph, states, res_m)


@app.command()
def lsp_for_bigger_circles():
    for v in range(10, 18):
        graph = get_circle_graph(v)
        lp_m = get_general_mechanism(
            graph, lambda _, sup=tuple(graph.nodes): sup, anonymous=True, unanimous=True
        )
        states = list(gen_states_of_world(graph, 3))
        model_wrapper = {}
        res_m = solve_lp_mechanism(
            graph,
            states,
            lp_m,
            minimize_apx=True,
            enforce_lsp=True,
            return_model=model_wrapper,
        )
        model = model_wrapper["value"]
        print(v, model.objective.value())
        assert is_sp(graph, states, res_m, epsilon=0.0001)


def sympy_to_pulp(expr, pulp_vars):
    """
    Recursively converts a sympy expression to a pulp LpAffineExpression.

    Parameters:
        expr (sympy expression): The sympy expression to convert.
        pulp_vars (dict): Mapping from sympy symbols to pulp LpVariables.

    Returns:
        pulp-compatible expression.
    """
    if isinstance(expr, sp.Number):  # Base case: constant number
        return float(expr)  # Ensure it works with PuLP

    elif isinstance(expr, sp.Symbol):  # Variable case
        return pulp_vars(expr)

    elif isinstance(expr, sp.Add):  # Sum of terms
        return sum(sympy_to_pulp(arg, pulp_vars) for arg in expr.args)

    elif isinstance(expr, sp.Mul):  # Product of terms
        return fn.reduce(
            operator.mul, (sympy_to_pulp(arg, pulp_vars) for arg in expr.args)
        )

    else:
        raise TypeError(f"Unsupported sympy operation: {expr}")


def sympy_to_pulp_var(expr: sp.Symbol):
    return pl.LpVariable(name=str(expr), lowBound=0, upBound=1, cat=pl.LpContinuous)


def factorial(n):
    return fn.reduce(operator.mul, range(1, n + 1), 1)


def n_choose_k(n, k):
    return factorial(n) // (factorial(k) * factorial(n - k))


def dict_cache[V, **T](
    f: Callable[T, V], d: Optional[dict[tuple, V]] = None, limit: Optional[int] = None
) -> Callable[T, V]:
    if d is None:
        d = {}

    def res(*args: T.args, **kwargs: T.kwargs) -> V:
        if not kwargs:
            key = (args,)
        else:
            key = args, frozenset(kwargs.items())
        if key not in d:
            d[key] = f(*args, **kwargs)
            if limit is not None and len(d) > limit:
                d.pop(next(iter(d)))

        return d[key]

    return res


def get_lsp_check(
    agents,
    ex_vertex_m2,
    m2,
    d_ex_vertex_m2,
    cont_vertex_dis,
    v,
    n,
    ex_state,
    order,
    i,
    agent_i,
    deviation,
    eps,
):
    __agent = ex_state[agent_i]

    def dev(eps):
        return tuple_assign(ex_state, agent_i, (deviation, eps))

    ex_dev_state = dev(eps)
    _order = tuple(agent_i if o == n else o for o in order if o != agent_i)
    ex_state_e = ex_state + ((deviation, eps),)

    d = fn.partial(
        cont_vertex_dis,
        order=order,
        state=ex_state_e,
    )

    def d2(n1, n2):
        v1 = ex_state_e[n1]
        v2 = ex_state_e[n2]
        a1 = int(v1[0]) + v1[1]
        a2 = int(v2[0]) + v2[1]
        r = abs(a2 - a1)
        return min(r, v - r)

    # for i in range(n + 1):
    #     assert d(agent_i, i) == d2(agent_i, i)

    # determining the direction of deviation with respect to the agent
    # this part is specific to cycle
    a1 = int(__agent[0])
    a2 = int(deviation)
    if order.index(agent_i) < order.index(n):
        sign = 1 if (a2 + v - a1) % v < v // 2 else -1
    else:
        sign = -1 if (a1 + v - a2) % v < v // 2 else 1

    if d_ex_vertex_m2 is not None and m2 is not None:
        _res = m2(ex_dev_state, order=_order)
        d_res = d_ex_vertex_m2(ex_dev_state, order=_order, coord=agent_i)
        __c = (
            d_res[agent_i] * d2(agent_i, n)
            + _res[agent_i] * sign
            + isum([d_res[v2] * d2(agent_i, v2) for v2 in set(agents) - {agent_i}])
        ) * sign
        return __c

    ex_dev_state_e0 = dev(0)
    ex_dev_state_e1 = dev(1)
    res_e0 = ex_vertex_m2(ex_dev_state_e0, order=_order)
    res_e1 = ex_vertex_m2(ex_dev_state_e1, order=_order)
    res = res_e1 if eps == 1 else res_e0
    de_res = dict_add(res_e1, dict_mul(res_e0, -1))
    c = (
        de_res[agent_i] * d(agent_i, n)
        + res[agent_i] * sign
        + isum([de_res[v2] * d(agent_i, v2) for v2 in set(agents) - {agent_i}])
    ) * sign
    return c


def gen_lsp_eps_checks(
    agents: tuple[int, ...],
    graph: nx.Graph,
    states: Iterable[NodesTuple],
    ex_vertex_m2: ExGeneralMechanism,
    m2: Optional[ExGeneralMechanism],
    d_ex_vertex_m2: Optional[ExGeneralMechanism],
    cont_vertex_dis: Callable,
    eps: Real = 0,
    deviating_agents: Optional[Iterable[int]] = None,
    check_constructor: Callable = lambda x, e: x >= -e,
):
    v = len(graph.nodes)
    n = len(agents)
    if deviating_agents is None:
        deviating_agents = agents
    for state in states:
        for order, i in it.product(
            it.permutations(range(n + 1)), range(n + 2)
        ):  # [n + 1]):
            for agent_i in deviating_agents:
                for deviation in graph.nodes:
                    var_map = [1 if order.index(j) >= i else 0 for j in range(n)]
                    e = 1 if order.index(n) >= i else 0
                    ex_state = tuple(zip(state, var_map, strict=True))
                    c = get_lsp_check(
                        agents,
                        ex_vertex_m2,
                        m2,
                        d_ex_vertex_m2,
                        cont_vertex_dis,
                        v,
                        n,
                        ex_state,
                        order,
                        i,
                        agent_i,
                        deviation,
                        e,
                    )
                    # assert ___c.subs({v: sp.Rational(1, 3) for v in ___c.free_symbols}) >= 0
                    yield (
                        check_constructor(c, eps),
                        {
                            "state": state,
                            "order": order,
                            "i": i,
                            "agent_i": agent_i,
                            "deviation": deviation,
                            "c": c,
                            "ex_state": ex_state,
                            "eps": e,
                        },
                    )


def get_anonymous_vertex_mechanism(ex_m: ExGeneralMechanism):
    def sp_sort(state, order):
        i2, s2 = zip(
            *tuple(
                sorted(
                    enumerate(state), key=lambda x: (int(x[1][0]), order.index(x[0]))
                )
            ),
            strict=True,
        )
        return s2, i2

    def ex_vertex_m2(state, order=None, **kwargs):
        base_nodes, further_movement = zip(*state, strict=True)
        order = get_order(further_movement, order)
        s3, i3 = sp_sort(state, order)
        if "coord" in kwargs:
            kwargs["coord"] = i3.index(kwargs["coord"])
        res = ex_m(s3, order=[i3.index(i) for i in order], **kwargs)
        return map_dict_keys(res, dict(zip(range(len(order)), i3, strict=True)))

    return ex_vertex_m2


def get_anonymous_extension_of_mechanism(m: ExGeneralMechanism, successors):
    ex_m = extend_mechanism_to_continuous(m, successors)

    return get_anonymous_vertex_mechanism(ex_m)


def get_shift_normalized_mechanism(
    m: ExGeneralMechanism[T, U], pred: Callable[[U], bool]
) -> ExGeneralMechanism[T, U]:
    def res_m(state: tuple[U, ...], **kwargs) -> Mapping[T, U]:
        shift = 0
        while pred(state[-1]) and shift <= len(state):
            state = state[-1:] + state[:-1]
            shift += 1
        agents = tuple(range(len(state)))
        return map_dict_keys(
            dict(m(state)),
            dict(zip(rotate(agents, shift), agents, strict=True)),
        )

    return res_m


@app.command()
def test_extended_mechanisms_is_not_sp():
    graph = get_circle_graph(8)
    agents = tuple(range(3))
    dis = distances(graph)
    successors, *_ = get_circle_graph_automorphisms(8)
    states = list(gen_states_of_world(graph, 3, ordered=True))
    lp_m = get_general_mechanism(graph, lambda s: agents, anonymous=True, agents=agents)
    solve_lp_mechanism(
        graph,
        states,
        vertex_mechanism_to_mechanism(lp_m),
        minimize_apx=True,
        dis=dis,
    )

    extended_m = map_mechanism_domain(
        vertex_mechanism_to_mechanism(
            get_anonymous_extension_of_mechanism(
                general_mechanism_to_mechanism(lp_m),
                successors,
            )
        ),
        real_to_node,
    )

    ex_dis_dict = extend_dis_to_continuous(dis, successors)

    # check that the mechanism is anonymous
    assert extended_m((0.5, 0, 0)) == extended_m((0, 0.5, 0))
    assert extended_m((0.5, 0, 0)) == extended_m((0, 0, 0.5))

    G = nx.Graph({x / 2: [] for x in range(16)})
    assert not is_sp(
        G, it.product(G.nodes, repeat=3), extended_m, dis=ex_dis_dict, epsilon=0.1
    )


@app.command()
def test_anonymous_extension_of_mechanism_and_vertex_mechanism_match_on_edges(
    v: int = 8,
):
    graph = get_circle_graph(v)
    n = 3
    agents = tuple(range(n))
    states = list(gen_states_of_world(graph, 3, ordered=False))
    successors, *_ = get_circle_graph_automorphisms(v)
    lp_m = get_general_mechanism(
        graph,
        lambda s: agents,
        agents=agents,
        get_variable=fn.cache(get_sp_var),
    )

    def ex_vertex_to_vertex(p):
        v, a = p
        return v if a == 0 else (successors(v) if a == 1 else assert_false())

    ex_m = extend_mechanism_to_continuous(lp_m, successors)
    ex_vertex_m = get_anonymous_vertex_mechanism(ex_m)
    _lp_m = map_mechanism_domain(lp_m, ex_vertex_to_vertex)
    __lp_m = get_shift_normalized_mechanism(
        _lp_m,
        lambda v2: v2 == (str(v - 1), 1),
    )
    ex_vertex_m2 = get_anonymous_vertex_mechanism(__lp_m)

    for state in track(states):
        for order in it.permutations(range(n)):
            for i in range(n + 1):
                var_map = [1 if order.index(j) >= i else 0 for j in range(n)]
                ex_state = tuple(zip(state, var_map, strict=True))
                res1 = ex_vertex_m(ex_state, order)
                res2 = ex_vertex_m2(ex_state, order)
                assert all((res1[agent] == res2[agent]) is True for agent in agents)


def gen_critical_points_of_quad(f: sp.Poly, xs: list[sp.Symbol], j=0):
    # check if f is 0
    if not xs:
        # print("debug base")
        yield {}
        return
    # equations = [f.diff(x) for x in xs]
    # res2 = sp.solve(equations, xs)
    # # check if values of variables in xs are ordered in the same way as in xs
    # valid = bool(res2)
    # if valid:
    #     if len(res2) == len(xs):
    #         ores = list(sorted(res2.values()))
    #         for i, x in enumerate(xs):
    #             if ores[i] != res2[x]:
    #                 valid = False
    #                 break
    #         if valid:
    #             valid = res2[xs[0]] > 0 and res2[xs[-1]] < 1
    #     else:
    #         valid = False
    #         # ores = [res2.get(x, x) for x in xs]
    #         # cond = sp.solve(
    #         #     [0 < ores[0], ores[-1] < 1, *(x <= y for x, y in it.pairwise(ores))]
    #         # )
    #         # if cond:
    #         #     assert isinstance(cond, sp.And)

    # if valid:
    #     # print("debug inner", f, xs)
    #     yield res2

    equations = [f.diff(x).as_coefficients_dict() for x in xs]
    coefficients = [[float(eq.get(x, 0)) for x in xs] for eq in equations]
    constants = [float(-eq.get(1, 0)) for eq in equations]
    try:
        res = np.linalg.solve(coefficients, constants)
        if not np.all(np.isfinite(res)):
            raise ValueError("Non-finite numerical critical point")
        if np.all(res[:-1] < res[1:]) and 0 < res[0] and res[-1] < 1:
            _res = dict(zip(xs, res, strict=True))
            # assert (
            #     valid
            #     and set(_res.keys()) == set(res2.keys())
            #     and all(
            #         math.isclose(_res[key], res2[key], abs_tol=1e-6) for key in _res
            #     )
            # )
            yield _res
    except np.linalg.LinAlgError:
        # assert not valid
        pass

    def gen_extend_dict(gen, key, val):
        for d in gen:
            d[key] = val(d)
            yield d

    # recursively inspect border cases
    # print("debug", f, xs)
    for i in range(j, len(xs) + 1):
        if i == 0:
            yield from gen_extend_dict(
                gen_critical_points_of_quad(f.subs(xs[0], 0), xs[1:], j=i),
                xs[0],
                lambda d: 0,
            )
            continue
        if i == len(xs):
            yield from gen_extend_dict(
                gen_critical_points_of_quad(f.subs(xs[-1], 1), xs[:-1], j=i),
                xs[-1],
                lambda d: 1,
            )
            continue
        yield from gen_extend_dict(
            gen_critical_points_of_quad(
                f.subs(xs[i - 1], xs[i]), xs[: i - 1] + xs[i:], j=i
            ),
            xs[i - 1],
            lambda d, j=xs[i]: d[j],
        )


def get_max_of_quad(p: sp.Poly, xs: list[sp.Symbol]):
    for coefficient in sp.Poly(p, *xs).coeffs():
        finite_value(float(coefficient))
    return max(
        (
            (finite_value(float(p.subs(d))), d)
            for d in gen_critical_points_of_quad(p, xs)
        ),
        key=lambda x: x[0],
    )


def is_apx_bound(s, order, agents, alpha, gv_m, cont_vertex_dis):
    xs = sp.symbols("x_:3")
    state = tuple(zip(s, xs, strict=True))
    r = gv_m(state, order=order)
    dis = fn.partial(cont_vertex_dis, state=state, order=order)
    sc = social_cost(agents, r, dis)
    c0 = social_cost(agents, {0: 1}, dis)
    c1 = social_cost(agents, {1: 1}, dis)
    c2 = social_cost(agents, {2: 1}, dis)
    _xs = [xs[i] for i in order]
    return all(
        [
            get_max_of_quad(sc - c0 * alpha, _xs)[0] <= 0,
            get_max_of_quad(sc - c1 * alpha, _xs)[0] <= 0,
            get_max_of_quad(sc - c2 * alpha, _xs)[0] <= 0,
        ]
    )


def gen_all_chunks(states, agents):
    for s in states:
        for order in it.permutations(range(len(agents))):
            yield s, order


def filter_apx_bound_chunks(chunks, agents, gv_m, cont_vertex_dis, alpha):
    for s, order in chunks:
        if not is_apx_bound(s, order, agents, alpha, gv_m, cont_vertex_dis):
            yield s, order


def is_apx_global_bound(agents, states, gv_m, cont_vertex_dis, alpha):
    for s, order in filter_apx_bound_chunks(
        gen_all_chunks(states, agents), agents, gv_m, cont_vertex_dis, alpha
    ):
        print(s, order)
        return False
    return True


def normalize_state(state: tuple[str, ...], successors):
    res = state
    while res[0] != "0":
        res = tuple(successors(v) for v in res)
    return res


def assert_sorted(state: NodesTuple) -> NodesTuple:
    _state = tuple(int(v) for v in state)
    assert _state == tuple(sorted(_state))
    return state


def gen_symmetry_checks(m: ExGeneralMechanism, states, automorphisms, reverse=False):
    for state in states:
        for a in automorphisms:
            _state = (
                tuple(a(v) for v in reversed(state))
                if reverse
                else tuple(a(v) for v in state)
            )
            if _state != state:
                res = m(state)
                # assert _state == tuple(sorted(_state))
                _res = m(_state)
                for agent in res:
                    if reverse:
                        yield res[agent] == _res[2 - agent], (_state, state)
                    else:
                        yield res[agent] == _res[agent], (state, _state)


def get_continuos_compliant_mechanism(m: ExGeneralMechanism, successors, last_vertex):
    def ex_vertex_to_vertex(p):
        v, a = p
        return v if a == 0 else (successors(v) if a == 1 else assert_false())

    lp_m2 = map_mechanism_domain(m, ex_vertex_to_vertex)
    lp_m3 = get_shift_normalized_mechanism(
        lp_m2,
        lambda v2: v2 == (last_vertex, 1),
    )
    lp_m4 = get_anonymous_vertex_mechanism(lp_m3)
    return map_mechanism_domain(lp_m4, real_to_node)


def test_compliance_with_continuos_mechanism(v: int = 8):
    graph = get_circle_graph(v)
    n = 3
    agents = tuple(range(n))
    states = list(gen_states_of_world(graph, 3, ordered=False))
    successors, *_ = get_circle_graph_automorphisms(v)
    lp_m = get_general_mechanism(
        graph,
        lambda s: agents,
        agents=agents,
        get_variable=fn.cache(get_sp_var),
    )
    ex_vertex_m = extend_mechanism_to_continuous(lp_m, successors)
    ex_vertex_m2 = get_anonymous_vertex_mechanism(ex_vertex_m)
    lp_m2 = get_continuos_compliant_mechanism(lp_m, successors, str(v - 1))
    for state in track(states):
        for order in it.permutations(range(n)):
            for i in range(n + 1):
                var_map = [1 if order.index(j) >= i else 0 for j in range(n)]
                ex_state = tuple(zip(state, var_map, strict=True))
                res1 = lp_m2(ex_state, order)
                res2 = ex_vertex_m2(ex_state, order)
                assert all((res1[agent] == res2[agent]) is True for agent in agents)


def unique(iterable):
    seen = set()
    for x in iterable:
        if x in seen:
            continue
        seen.add(x)
        yield x


def m_setup(v: int, get_var):
    graph = get_circle_graph(v)
    n = 3
    agents = tuple(range(n))
    dis = distances(graph)
    successors, *mirrors = get_circle_graph_automorphisms(v)
    states = unique(
        normalize_state(s, successors)
        for s in gen_states_of_world(graph, 3, ordered=True)
    )
    console.rule("Mechanism definition")

    _lp_m = get_general_mechanism(
        graph,
        lambda s: agents,
        get_variable=get_var,
    )
    lp_m = lambda s, **kwargs: _lp_m(normalize_state(s, successors), **kwargs)

    cont_vertex_dis = get_continuous_vertex_dis_on_cycle(v)
    cont_dis = extend_dis_to_continuous(dis, successors)

    def get_splitted_graph(scale):
        return nx.Graph({x / scale: [] for x in range(scale * v)})

    return (
        graph,
        agents,
        dis,
        successors,
        mirrors,
        states,
        lp_m,
        cont_vertex_dis,
        cont_dis,
        get_splitted_graph,
    )


def init_timing(enabled, push_event):
    start_time = time.perf_counter()

    def get_elapsed():
        return time.perf_counter() - start_time

    def start_event_measure(event_name: str):
        if not enabled:
            return lambda: None
        start_time = get_elapsed()

        def end_event():
            end_time = get_elapsed()
            duration = end_time - start_time
            push_event(event_name, start_time, end_time, duration)

        return end_event

    return start_event_measure


def get_cbc_path():
    return os.environ.get("CBC_PATH") or shutil.which("cbc") or pl.PULP_CBC_CMD().path


def run_metadata(settings):
    source = Path(__file__).resolve()
    cbc_path = get_cbc_path()
    cbc_version = subprocess.check_output(
        [cbc_path, "-stop"], text=True, stderr=subprocess.STDOUT
    ).strip()
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=source.parent, text=True
    ).strip()
    diff = subprocess.check_output(["git", "diff", "HEAD"], cwd=source.parent)
    return {
        "settings": {
            k: str(v)
            if isinstance(v, Path) or isinstance(v, float) and not math.isfinite(v)
            else v
            for k, v in settings.items()
        },
        "source": {
            "commit": commit,
            "dirty": bool(diff),
            "diff_sha256": hashlib.sha256(diff).hexdigest(),
            "main_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        },
        "python": sys.version,
        "dependencies": {
            d.metadata["Name"]: d.version for d in importlib.metadata.distributions()
        },
        "cbc": {"path": cbc_path, "version": cbc_version},
        "native_threads": {
            name: os.environ.get(name)
            for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")
        },
    }


def finite_value(value):
    if value is None or not math.isfinite(value):
        raise ValueError(f"Missing or non-finite numerical value: {value}")
    return value


def m_load(load_path: Path):
    if load_path.suffix != ".json":
        raise ValueError("Unsupported file format")
    with open(load_path, "r") as f:
        saved = json.load(f)
    if not isinstance(saved, list) or not saved or not isinstance(saved[0], dict):
        raise ValueError("Expected a JSON mechanism, not checking results")
    preambule, *data = saved
    v = preambule["v"]
    vars_dict = {(i, tuple(s)): finite_value(value) for i, s, value in data}

    def get_var(el, agents_nodes: NodesTuple, randomized: bool = True):
        try:
            return vars_dict[(el, agents_nodes)]
        except KeyError as exc:
            raise ValueError(f"Missing coefficient for {(el, agents_nodes)}") from exc

    (
        graph,
        agents,
        dis,
        successors,
        mirrors,
        states,
        lp_m,
        cont_vertex_dis,
        cont_dis,
        get_splitted_graph,
    ) = m_setup(v, get_var)
    states = list(states)
    for state in states:
        lp_m(state)

    # define evaluation mechanism (which returns values instead of variables)
    __gv_m = get_anonymous_extension_of_mechanism(lp_m, successors)
    gv_m = map_mechanism_domain(__gv_m, real_to_node)
    gv_m = fn.cache(gv_m)
    g_m = vertex_mechanism_to_mechanism(gv_m)

    return (
        graph,
        agents,
        states,
        cont_vertex_dis,
        cont_dis,
        get_splitted_graph,
        gv_m,
        g_m,
    )


@app.command()
def check_lsp_mechanism(
    load_path: Path,
    interactive: bool = False,
    check_sp: bool = False,
    check_lsp: bool = False,
    check_anonymity: bool = False,
    calc_apx: bool = False,
    apx_threshold: Optional[float] = None,
    min_scale: int = 1,
    max_scale: int = 8,
    scale: Optional[int] = None,
    bound_apx: Optional[Real] = None,
    binsearch_apx: Optional[Real] = None,
    save_results: Optional[Path] = None,
    track_time: bool = False,
    v: int = 4,  # left for backward compatibility
    s: Optional[int] = None,  # left for backward compatibility
) -> dict[str, Any]:
    settings = locals().copy()
    if save_results is not None and save_results.resolve() == load_path.resolve():
        raise ValueError("Mechanism and checking results must use different files")
    result = {"status": "incomplete", "method": "numerical floating-point"}
    started = time.perf_counter()
    try:
        result["provenance"] = run_metadata(settings)
        result["mechanism"] = {
            "path": str(load_path),
            "sha256": hashlib.sha256(load_path.read_bytes()).hexdigest(),
        }
        _check_lsp_mechanism(result, **settings)
        result["status"] = "complete"
    except Exception as exc:
        result["status"] = "failed"
        result["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        result["duration_seconds"] = time.perf_counter() - started
        if save_results is not None:
            with save_results.open("w") as f:
                json.dump(result, f, indent=4, allow_nan=False)
    console.print(result)
    return result


def _check_lsp_mechanism(
    result: dict[str, Any],
    load_path: Path,
    interactive: bool = False,
    check_sp: bool = False,
    check_lsp: bool = False,
    check_anonymity: bool = False,
    calc_apx: bool = False,
    apx_threshold: Optional[float] = None,
    min_scale: int = 1,
    max_scale: int = 8,
    scale: Optional[int] = None,
    bound_apx: Optional[Real] = None,
    binsearch_apx: Optional[Real] = None,
    save_results: Optional[Path] = None,
    track_time: bool = False,
    v: int = 4,  # left for backward compatibility
    s: Optional[int] = None,  # left for backward compatibility
) -> dict[str, Any]:
    def push_event(event_name, start_time, end_time, duration):
        if "events" not in result:
            result["events"] = {}
        result["events"][event_name] = {
            "start": start_time,
            "end": end_time,
            "duration": duration,
        }

    def dump_results():
        if save_results is not None:
            console.log(f"Saving results to {save_results}.")
            with save_results.open("w") as f:
                json.dump(result, f, indent=4)

    start_event_measure = init_timing(track_time, push_event)
    end_measure_all = start_event_measure("total_run")

    if scale is not None:
        min_scale = max_scale = scale
    if min_scale < 1 or max_scale < min_scale:
        raise ValueError("Checking scales must satisfy 1 <= min_scale <= max_scale")
    if binsearch_apx is not None and finite_value(binsearch_apx) <= 0:
        raise ValueError("Bisection tolerance must be positive")
    if bound_apx is not None:
        finite_value(bound_apx)

    (
        graph,
        agents,
        states,
        cont_vertex_dis,
        cont_dis,
        get_splitted_graph,
        gv_m,
        g_m,
    ) = m_load(load_path)
    states = list(states)
    with load_path.open() as f:
        mechanism_metadata = json.load(f)[0]
    result["mechanism"]["candidate"] = mechanism_metadata.get("candidate")
    result["mechanism"]["search_status"] = mechanism_metadata.get("status")
    for name in ("primary_objective", "sampled_ratio"):
        value = mechanism_metadata.get(name)
        result[name] = finite_value(value) if value is not None else None

    if interactive:
        embed(colors="Linux")

    console.rule("Checking model")

    if check_lsp:
        lsp_counterexample = None
        end_measure = start_event_measure("lsp_check")
        for check, description in gen_lsp_eps_checks(
            agents,
            graph,
            track(states, description="Checking lsp constraints..."),
            gv_m,
            None,
            None,
            cont_vertex_dis,
            eps=0.00001,
        ):
            if not check:
                lsp_counterexample = description
                break
        end_measure()
        print("Not lsp:", lsp_counterexample)
        result["lsp_counterexample"] = lsp_counterexample
        if lsp_counterexample is not None:
            raise ValueError("Numerical LSP check failed")

    dump_results()
    apx_low = max(1, result["sampled_ratio"] or 1)
    result["apx_low"] = apx_low
    apx_high = 2
    scale_results = {}
    result["scale_results"] = scale_results
    end_measure = start_event_measure("scale_checks")
    for scale in range(min_scale, max_scale + 1):
        scale_result = {}
        scale_results[str(scale)] = scale_result
        G = get_splitted_graph(scale)
        print(f"scale: {scale}")
        end_measure2 = start_event_measure(f"scale_{scale}_checks")
        states2 = [s for s in gen_states_of_world(G, 3, ordered=True) if s[0] < 1]
        if check_sp:
            end_measure3 = start_event_measure(f"scale_{scale}_sp_check")
            sp_val = is_sp(
                G,
                track(states2, description="Checking sp..."),
                g_m,
                dis=cont_dis,
                epsilon=0.0001,
            )
            end_measure3()
            scale_result["sp"] = sp_val
            print(f"sp: {sp_val}")
            if not sp_val:
                for exp in gen_sp_counterexamples(
                    G,
                    states2,
                    g_m,
                    dis=cont_dis,
                    epsilon=0.0001,
                ):
                    print(exp)
                    break
                raise ValueError(f"Numerical SP check failed at scale {scale}")
        if calc_apx:
            end_measure3 = start_event_measure(f"scale_{scale}_apx_calc")
            apx_val = get_apx(
                G,
                track(states2, description="Calculating apx..."),
                g_m,
                dis=cont_dis,
                opt_candidates=lambda s: s,
            )
            end_measure3()
            apx_low = max(apx_low, finite_value(apx_val))
            result["apx_low"] = apx_low
            scale_result["apx"] = apx_val
            print(f"apx: {apx_val}")

            if apx_threshold is not None and apx_val > apx_threshold:
                table = Table("apx", "state", title="Approximation ratio")
                for state_of_world in states2:
                    real, opt = get_apx_for_state(
                        state_of_world, state_of_world, g_m, cont_dis
                    )
                    apx = real / opt if opt != 0 else 1
                    if apx > apx_threshold:
                        table.add_row(Pretty(apx), Pretty(state_of_world))
                console.print(table)

        # check that the mechanism is anonymous
        if check_anonymity:
            is_anonymous = True
            end_measure3 = start_event_measure(f"scale_{scale}_anonymity_check")
            for state in states2:
                r1 = g_m(state)
                for state2 in it.permutations(state):
                    if state == state2:
                        continue
                    r2 = g_m(state2)
                    if r1 != r2:
                        is_anonymous = False
                        break
            end_measure3()
            print(f"anonymous: {is_anonymous}")
            scale_result["anonymous"] = is_anonymous
            if not is_anonymous:
                raise ValueError(f"Anonymity check failed at scale {scale}")
        end_measure2()
        scale_results[str(scale)] = scale_result
    end_measure()

    if bound_apx is not None:
        end_measure = start_event_measure("apx_bound_check")
        is_apx_bound = is_apx_global_bound(
            agents,
            track(states, description="Checking apx bound..."),
            gv_m,
            cont_vertex_dis,
            bound_apx,
        )
        end_measure()
        if is_apx_bound:
            console.log("Apx bound is satisfied.")
        else:
            console.log("Apx bound is not satisfied.")
        result["apx_bound"] = {"value": bound_apx, "satisfied": is_apx_bound}
        if not is_apx_bound:
            raise ValueError("Numerical approximation bound check failed")

    dump_results()
    if binsearch_apx is not None:
        unbounded_chunks = list(gen_all_chunks(states, agents))
        end_measure = start_event_measure("binsearch_apx")
        if apx_low > apx_high:
            raise ValueError("Sampled ratio exceeds the safe upper bound")
        result["binsearch_apx"] = {"low": apx_low, "high": apx_high}
        console.log(
            f"Starting binsearch for apx bound between {apx_low} and {apx_high}"
        )
        console.log(f"Initial chunks count: {len(unbounded_chunks)}")

        def binsearch_step(apx_mid):
            nonlocal unbounded_chunks, apx_low, apx_high
            if apx_mid == apx_high and apx_high > apx_low:
                raise ValueError(
                    "Bisection tolerance is below floating-point resolution"
                )
            console.log(f"Trying apx bound: {apx_mid}")
            new_unbounded_chunks = list(
                filter_apx_bound_chunks(
                    track(
                        unbounded_chunks,
                        description="Filtering low bounded chunks...",
                    ),
                    agents,
                    gv_m,
                    cont_vertex_dis,
                    apx_mid,
                )
            )
            if not new_unbounded_chunks:
                console.log(f"Apx bound {apx_mid} is satisfied.")
                apx_high = apx_mid
                result["binsearch_apx"].update(low=apx_low, high=apx_high)
                return True
            else:
                console.log(f"Apx bound {apx_mid} is not satisfied.")
                for s, order in new_unbounded_chunks[:5]:
                    console.log(f"Counterexample state: {s}, order: {order}")
                apx_low = apx_mid
                result["binsearch_apx"].update(low=apx_low, high=apx_high)
                unbounded_chunks = new_unbounded_chunks
                console.log(f"Chunks count after filtering: {len(unbounded_chunks)}")
                return False

        binsearch_step(apx_low)
        while apx_high - apx_low > binsearch_apx:
            apx_mid = (apx_low * 9 + apx_high) / 10
            if not binsearch_step(apx_mid):
                break
        while apx_high - apx_low > binsearch_apx:
            apx_mid = (apx_low * 4 + apx_high) / 5
            if not binsearch_step(apx_mid):
                break
        while apx_high - apx_low > binsearch_apx:
            apx_mid = (apx_low + apx_high) / 2
            if apx_mid == apx_low:
                raise ValueError(
                    "Bisection tolerance is below floating-point resolution"
                )
            binsearch_step(apx_mid)
        end_measure()
        result["binsearch_apx"] = {"low": apx_low, "high": apx_high}

    if scale_results:
        result["scale_results"] = scale_results
    end_measure_all()
    usage = resource.getrusage(resource.RUSAGE_SELF)
    print("Peak Self RSS (KB):", usage.ru_maxrss)
    result["peak_self_rss_kb"] = usage.ru_maxrss
    dump_results()
    return result


def get_ex_vertex_pcd(num_of_v: int):
    def res_m(
        state: tuple[tuple[str, float], ...], order: tuple[int, ...], **kwargs
    ) -> Mapping[int, Real]:
        assert len(state) == 3
        v0, v1, v2 = ((int(v[0]) + v[1]) / num_of_v for v in state)
        return {
            0: v2 - v1,
            1: v0 - v2 + 1,
            2: v1 - v0,
        }

    return get_anonymous_vertex_mechanism(res_m)


def fast_constraint_id(
    con: pl.LpConstraint, equivalence_classes: Optional[nx.utils.UnionFind] = None
):
    """
    Very fast, weak normalization of a PuLP LpConstraint.

    Identifies constraints equal up to:
    - variable order
    - zero coefficients

    Does NOT normalize scaling or inequality direction.

    Parameters:
        con: PuLP LpConstraint
        equivalence_classes: Optional nx.utils.UnionFind for tracking variable equivalences.
                           If provided, will identify simple constraints (x - y = 0, -x + y = 0)
                           and add them to equivalence classes. Non-simple constraints will be
                           simplified using existing equivalences.
    """

    # Normalize sense to a small int (faster than strings)
    sense = con.sense  # LE, GE, EQ (ints)

    # Extract nonzero coefficients
    items = tuple(sorted((var.name, coef) for var, coef in con.items() if coef != 0))

    rhs = con.constant

    # Handle equivalence classes
    if equivalence_classes is not None:
        # Check if this is a simple equality constraint (x - y = 0 or -x + y = 0)
        if sense == 0 and len(items) == 2 and rhs == 0:  # 0 represents EQ sense
            (var1_name, coef1), (var2_name, coef2) = items
            # Check if coefficients are 1 and -1 (in either order)
            if abs(coef1) == 1 and abs(coef2) == 1 and coef1 + coef2 == 0:
                # This is a simple constraint: add variables to equivalence class
                equivalence_classes.union(var1_name, var2_name)
                # Return as-is, don't simplify simple constraints
                return (sense, items, rhs)

        # For non-simple constraints, simplify using equivalence classes
        if len(items) > 0:
            # Map each variable to its equivalence class representative
            simplified_items = []
            for var_name, coef in items:
                # Get the representative of this variable's equivalence class
                rep = equivalence_classes[var_name]
                simplified_items.append((rep, coef))

            # Aggregate coefficients for the same representative
            from collections import defaultdict

            coef_dict = defaultdict(float)
            for var_name, coef in simplified_items:
                coef_dict[var_name] += coef

            # Create new items, removing zeros
            items = tuple(
                sorted(
                    (var_name, coef)
                    for var_name, coef in coef_dict.items()
                    if coef != 0
                )
            )

    return (sense, items, rhs)


def print_mem_usage(message: str):
    process = psutil.Process(os.getpid())
    mem = process.memory_info().rss  # bytes
    print(message, mem / 1024 / 1024, "MB")


@app.command()
def solve_lsp_mechanism(
    v: int,
    s: int = 4,
    enforce_sp: bool = False,
    enforce_lsp: bool = True,
    warm_start: bool = True,
    minimize_avg_cost: bool = True,
    minimize_dis_from_pcd: bool = False,
    local_lsp_apx_constraints: bool = False,
    keep_files: bool = False,
    save_lp: Optional[Path] = None,
    mem_limit: Optional[float] = None,
    save_path: Optional[Path] = None,
):
    settings = locals().copy()
    if save_path is not None and save_path.suffix != ".json":
        raise ValueError("Use .json for mechanism files")
    if v < 2 or s < 1:
        raise ValueError("Require at least two vertices and a positive sampling scale")
    metadata = {
        "v": v,
        "status": "incomplete",
        "method": "numerical floating-point",
        "provenance": run_metadata(settings),
        "events": {},
        "solves": {},
        "solver_threads": 1,
    }

    def push_event(name, start, end, duration):
        metadata["events"][name] = {"start": start, "end": end, "duration": duration}

    start_event_measure = init_timing(True, push_event)
    end_total = start_event_measure("total_run")
    end_search = start_event_measure("search")
    vars_dict = {}
    _get_lp_var = (
        fn.partial(get_lp_var, initialValue=1 / 3) if warm_start else get_lp_var
    )
    __get_lp_var = dict_cache(_get_lp_var, vars_dict)
    (
        graph,
        agents,
        dis,
        successors,
        mirrors,
        states,
        lp_m,
        cont_vertex_dis,
        cont_dis,
        get_splitted_graph,
    ) = m_setup(v, __get_lp_var)
    states = list(states)

    ex_vertex_m2_cache = {}
    __ex_vertex_m2 = get_anonymous_extension_of_mechanism(lp_m, successors)
    ex_vertex_m2 = dict_cache(
        map_mechanism_domain(__ex_vertex_m2, real_to_node),
        ex_vertex_m2_cache,
        limit=None if mem_limit is None else int((mem_limit - 0.15) * 300000),
    )

    g_ex_m2 = vertex_mechanism_to_mechanism(ex_vertex_m2)

    # tracemalloc.start()
    print_mem_usage("Before LP model creation:")
    anonymous = True
    n = 3
    model = pl.LpProblem(name="lsp_mechanism", sense=pl.LpMinimize)

    bounds = set()
    bound_id = 0
    vars_eq_classes = nx.utils.UnionFind()

    def add_check(check: pl.LpConstraint, description: Any):
        nonlocal model, bounds, bound_id
        if check is False:
            raise ValueError(description)
        normalized_check_tuple = fast_constraint_id(check, vars_eq_classes)
        if normalized_check_tuple in bounds:
            return
        bounds.add(normalized_check_tuple)
        model += check, f"C_{str(bound_id).rjust(6, '0')}"
        bound_id += 1

    def add_checks(gen):
        for check, description in gen:
            add_check(check, description)

    ___lp_m = get_shift_normalized_mechanism(lp_m, lambda v2: v2 == "0")
    add_checks(
        gen_symmetry_checks(
            ___lp_m,
            gen_states_of_world(graph, 3, ordered=True),
            [successors],
        )
    )

    add_checks(
        gen_symmetry_checks(
            lp_m,
            gen_states_of_world(graph, 3, ordered=True),
            mirrors,
            reverse=True,
        )
    )
    sym_res = lp_m(("0", "0", str(v // 2)))
    add_check(sym_res[0] == sym_res[1], "Symmetry constraint")

    if enforce_lsp:
        add_checks(
            gen_lsp_eps_checks(
                agents,
                graph,
                track(states, description="Generating lsp constraints..."),
                ex_vertex_m2,
                None,
                None,
                cont_vertex_dis,
                deviating_agents=[0],
            )
        )

    for state in track(states, description="Generating probability constraints..."):
        res = lp_m(state)
        add_check(isum(res.values()) == 1, f"Probability constraint for state {state}")

    G = get_splitted_graph(s)
    states_G = list(gen_states_of_world(G, 3, ordered=anonymous))
    alpha = pl.LpVariable(name="alpha", lowBound=0)
    model.setObjective(alpha)
    for real_cost, opt_cost in gen_apx(
        G,
        track(states_G, description="Generating approximation constraints..."),
        g_ex_m2,
        dis=cont_dis,
    ):
        add_check(real_cost <= alpha * opt_cost, "Approximation constraint")

    if enforce_sp:
        add_checks(
            gen_sp_checks(
                G,
                track(states_G, description="Generating sp constraints..."),
                g_ex_m2,
                0,
                dis=cont_dis,
            )
        )

    if local_lsp_apx_constraints:
        # local apx constraints
        for vertex in graph.nodes:
            state = (vertex,) * n
            res = lp_m(state)
            add_check(
                res[1] + (res[0] + res[2]) * 3 / 2 <= alpha,
                f"Local approximation constraint for vertex {vertex}",
            )
            add_check(
                res[1] + res[0] + 2 * res[2] <= alpha,
                f"Local approximation constraint for vertex {vertex}",
            )
            add_check(
                res[1] + 2 * res[0] + res[2] <= alpha,
                f"Local approximation constraint for vertex {vertex}",
            )

    console.log("Solving the LP model.")
    usage = resource.getrusage(resource.RUSAGE_SELF)
    print("Peak Self RSS (KB):", usage.ru_maxrss)
    print_mem_usage("Before solving LP:")
    if save_lp is not None:
        model.writeLP(save_lp.as_posix())
    bounds.clear()
    ex_vertex_m2_cache.clear()
    gc.collect()
    usage = resource.getrusage(resource.RUSAGE_SELF)
    print("Peak Self RSS (KB):", usage.ru_maxrss)
    print_mem_usage("Before solving LP (after cache clear):")

    def solve_objective(name):
        end_measure = start_event_measure(name)
        try:
            status = model.solve(
                pl.COIN_CMD(
                    msg=True,
                    path=get_cbc_path(),
                    warmStart=warm_start,
                    keepFiles=keep_files,
                    threads=1,
                )
            )
            metadata["solves"][name] = pl.LpStatus[status]
            if status != pl.LpStatusOptimal:
                raise ValueError(f"{name} solve failed: {pl.LpStatus[status]}")
        except Exception as exc:
            metadata["solves"][name] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            end_measure()

    solve_objective("primary")
    end_search()
    usage = resource.getrusage(resource.RUSAGE_SELF)
    print("Peak Self RSS (KB):", usage.ru_maxrss)
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    print("Peak Child RSS (KB):", usage.ru_maxrss)
    print_mem_usage("After solving LP:")
    apx = finite_value(pl.value(alpha))
    metadata["primary_objective"] = apx
    primary_values = {
        key: finite_value(pl.value(var)) for key, var in vars_dict.items()
    }

    def save_candidate(candidate):
        coefficients = [
            [*key[0], finite_value(pl.value(var))] for key, var in vars_dict.items()
        ]
        sampled_ratio = finite_value(
            get_apx(
                G,
                states_G,
                general_mechanism_to_mechanism(g_ex_m2),
                dis=cont_dis,
                opt_candidates=lambda state: state,
            )
        )
        metadata.update(
            candidate=candidate, apx=sampled_ratio, sampled_ratio=sampled_ratio
        )
        end_total()
        if save_path is not None:
            with save_path.open("w") as f:
                json.dump([metadata, *coefficients], f, allow_nan=False)
                f.write("\n")

    save_candidate("primary")

    end_secondary = start_event_measure("secondary_optimization")
    try:
        if minimize_avg_cost:
            model += alpha <= apx + 0.000001

            beta = pl.LpVariable(name="beta", lowBound=0)
            lp_mv = vertex_mechanism_to_mechanism(lp_m)
            avg_social_cost = isum(
                social_cost(state, lp_mv(state), dis) for state in states
            )
            model += beta == avg_social_cost
            model.setObjective(beta)

            solve_objective("average_cost")
            usage = resource.getrusage(resource.RUSAGE_CHILDREN)
            print("Peak RSS (KB):", usage.ru_maxrss)
        if minimize_dis_from_pcd:
            model += alpha <= apx + 0.000001
            v_pcd = get_ex_vertex_pcd(v)

            gamma = pl.LpVariable(name="gamma", lowBound=0)
            dis_from_pcd = 0
            for state in states:
                res = lp_m(state)
                pcd_res = v_pcd(tuple((s, 0) for s in state))
                # fix comparison of probabilities in res and pcd_res
                for agent, prob_lp in res.items():
                    prob = assert_not_none(pl.value(prob_lp))
                    prob_pcd = pcd_res[agent]
                    if prob >= prob_pcd:
                        model += prob_lp >= prob_pcd
                        dis_from_pcd += prob_lp - prob_pcd
                    else:
                        model += prob_lp <= prob_pcd
                        dis_from_pcd += prob_pcd - prob_lp
                # dis_from_pcd += res[0]  # Assuming res[0] is the relevant value for dis_from_pcd
            model += dis_from_pcd == gamma
            console.log("Initial dis from pcd:", pl.value(dis_from_pcd))
            model.setObjective(gamma)

            solve_objective("distance_from_pcd")
            usage = resource.getrusage(resource.RUSAGE_CHILDREN)
            print("Peak Child RSS (KB):", usage.ru_maxrss)

        end_secondary()
        metadata["status"] = "complete"
        save_candidate(
            "secondary" if minimize_avg_cost or minimize_dis_from_pcd else "primary"
        )
    except Exception as exc:
        end_secondary()
        for key, value in primary_values.items():
            vars_dict[key].varValue = value
        metadata["status"] = "failed"
        metadata["error"] = f"{type(exc).__name__}: {exc}"
        save_candidate("primary")
        raise


def dict_to_filename(d: dict) -> str:
    # Convert the dictionary to a JSON string with sorted keys
    json_str = json.dumps(d, sort_keys=True, separators=(",", ":"))

    # Create a hash of the JSON string to ensure the filename is unique and deterministic
    hash_str = hashlib.md5(json_str.encode()).hexdigest()

    # Optionally, you can use the JSON string directly, but ensure it is sanitized
    sanitized_str = json_str.translate(
        str.maketrans(
            {" ": "_", ":": "-", ",": "_", "{": "", "}": "", '"': "", "'": ""}
        )
    )

    # Combine the hash and sanitized string for a unique and deterministic filename
    filename = f"{sanitized_str}_{hash_str}.txt"

    return filename


@app.command()
def test_lsp_reference_result(
    ask_for_overwrite: bool = False,
    overwrite: bool = False,
    ref_folder: Path = Path("lsp_ref_results"),
    rebuild_mechanisms: bool = True,
):
    """
    Check small instances of construction of lsp mechanism against previous results.
    """
    _apx = {"calc_apx": True}
    _sp = {"check_sp": True}
    _lsp = {"check_lsp": True}
    _all = {**_apx, **_sp, **_lsp}
    _sc_1 = {"s": 1, "max_scale": 1}
    _sc_2 = {"s": 2, "max_scale": 2}
    _sc_4 = {"s": 4, "max_scale": 4}
    instances = [
        {"v": 2, **_all, **_sc_1},
        {"v": 2, **_all, **_sc_2},
        {"v": 2, **_all, **_sc_4},
        {"v": 2, **_sp, "max_scale": 8},
        {"v": 4, **_all, **_sc_1},
        {"v": 4, **_all, **_sc_2},
        {"v": 4, **_all, **_sc_4},
        {"v": 4, **_sp, "max_scale": 8},
        {"v": 8, **_all, **_sc_4},
        {"v": 12, **_all, **_sc_4},
        # {"v": 16, **_all, **_sc_4},
    ]
    tmp_dir = Path.cwd() / "tmp"
    if rebuild_mechanisms:
        tmp_dir.mkdir(exist_ok=True)
        console.rule("Preparing lsp mechanisms")
        for v in [2, 4, 8, 12]:
            console.print(f"Lsp mechanism for {v} vertices")
            solve_lsp_mechanism(
                v,
                minimize_avg_cost=False,
                local_lsp_apx_constraints=True,
                save_path=tmp_dir / f"{v}.json",
            )
    # create ref folder if it doesn't exist
    ref_folder.mkdir(exist_ok=True)
    for instance in instances:
        console.rule("Testing instance")
        console.print(instance)
        v = instance["v"]
        res = check_lsp_mechanism(**instance, load_path=tmp_dir / f"{v}.json")
        filename = dict_to_filename(instance)
        # load reference result if it exists
        ref_path = ref_folder / filename
        ref_res = None
        if ref_path.exists():
            with ref_path.open("r") as f:
                ref_res = json.load(f)
        if ask_for_overwrite or overwrite:
            if ref_res != res:
                console.print("Reference result is different from the current result.")
                console.print("Reference result:")
                console.print(ref_res)
                console.print("Current result:")
                console.print(res)
                if overwrite or typer.confirm(
                    "Do you want to overwrite the reference result?"
                ):
                    console.print("Overwriting the reference result.")
                    with ref_path.open("w") as f:
                        json.dump(res, f)
        else:
            try:
                assert ref_res == res
            except AssertionError:
                print("Reference result:", ref_res)
                print("Current result:", res)
                raise


def get_avg_shifted_mechanizm(m: ExGeneralMechanism, successors, times=1):
    def res_m(s, *args, order=None, **kwargs):
        res = m(s, *args, order=order, **kwargs)
        for _ in range(times):
            s = tuple(successors(v) for v in s)
            res = dict_add(res, m(s, *args, order=order, **kwargs))
        return dict_mul(res, 1 / (times + 1))

    return res_m


@app.command()
def visualize_3_mechanism(
    load_path: Path,
    v: int = 8,
    scale: int = 2,
    average: bool = False,
    dim3: bool = False,
    display_triangle: bool = False,
    substract_pcd: bool = True,
    display_diff: bool = False,
):
    (
        graph,
        agents,
        states,
        cont_vertex_dis,
        cont_dis,
        get_splitted_graph,
        gv_m,
        g_m,
    ) = m_load(load_path)
    n = 3
    pcd = map_mechanism_domain(get_ex_vertex_pcd(v), real_to_node)

    G = get_splitted_graph(scale)
    print(f"scale: {scale}")
    # states = list((0,) + s for s in gen_states_of_world(G, 2, ordered=True))
    v2 = len(G.nodes)
    values_0 = np.full((v2, v2), np.nan)
    values_1 = np.full((v2, v2), np.nan)
    values_2 = np.full((v2, v2), np.nan)
    values_apx = np.full((v2, v2), np.nan)
    cost_0 = np.full((v2, v2), np.nan)

    def frac_successors(delta, el):
        return (el + delta) % v

    avg_gv_m = get_avg_shifted_mechanizm(
        gv_m, fn.partial(frac_successors, 1 / scale), times=scale - 1
    )
    final_m = avg_gv_m if average else gv_m

    def y_mod(y):
        return int(y * math.sqrt(3) / 2)

    def sign(x):
        return 1 if x > 0 else -1 if x < 0 else 0

    for i, x1 in enumerate(track(G.nodes)):
        for j, x2 in enumerate(G.nodes):
            if i > j:  # or i > (v2 - j):
                continue
            s = (0, x1, x2)
            _r = final_m(s)
            if substract_pcd:
                pcd_r = pcd(s)
                r = dict_add(_r, dict_mul(pcd_r, -1))
            else:
                r = _r
            x, y = (j - i // 2, y_mod(i)) if display_triangle else (j, i)

            vs = r[0], r[1], r[2]
            v1, v2, v3 = vs
            # v1, v2, v3 = map(sign, vs)
            values_0[y, x] = v1
            values_1[y, x] = v2
            values_2[y, x] = v3
            cost_0[y, x] = cont_dis(0, x1) * v2 + cont_dis(0, x2) * v3
            r2 = map_dict_keys(_r, dict(zip(range(n), s, strict=True)))
            real_cost = social_cost(s, r2, cont_dis)
            opt_cost, _ = get_opt(s, s, cont_dis)
            values_apx[i, j] = apx(real_cost, opt_cost)

    if display_diff:
        diff0y = cost_0[:-1] - cost_0[1:]
        diff0x = cost_0[:, :-1] - cost_0[:, 1:]
        # central differences on interior cells
        diff0mod = np.sqrt(diff0y[:, :-1] ** 2 + diff0x[:-1, :] ** 2)
        # diff0ang = np.arctan2(diff0y[:, :-1], diff0x[:-1, :])

        # single plot: modulus with vector field overlay
        fig, ax = plt.subplots(1, 1, figsize=(10, 7))
        ax.imshow(
            diff0mod,
            cmap="viridis",
            origin="lower",
            aspect="equal",
            interpolation="nearest",
            alpha=0.1,
        )
        ax.set_title("Modulus of diff(values_0) and vector field")
        ax.set_xlabel("x2")
        ax.set_ylabel("x1")

        # prepare quiver data (interior grid of shape (n-1, n-1))
        U = diff0x[:-1, :]
        V = diff0y[:, :-1]
        h, w = diff0mod.shape
        X, Y = np.meshgrid(np.arange(w), np.arange(h))

        # overlay quiver (adjust scale for visibility) and color arrows by length
        # mag_display = np.sign(V - U)
        mag_display = np.arctan2(V, U)
        Q = ax.quiver(
            X,
            Y,
            U * -10,
            V * -10,
            mag_display,
            angles="xy",
            scale_units="xy",
            scale=2,
            cmap="plasma",
            width=0.003,
            alpha=0.9,
        )

        # place colorbar to the right of the plot
        cbar = fig.colorbar(Q, ax=ax, orientation="vertical", fraction=0.046, pad=0.04)
        cbar.set_label("Arrow length (scaled)")
        plt.tight_layout()
        plt.show()
        return

    if dim3:
        fig = plt.figure()
        ax = fig.add_subplot(111, projection="3d")
        x, y = np.meshgrid(range(values_0.shape[0]), range(values_0.shape[1]))
        ax.plot_surface(x, y, values_apx, cmap="viridis")
        ax.set_title("3D plot of values for key 0")
        ax.set_xlabel("x1")
        ax.set_ylabel("x2")
        ax.set_zlabel("Value")
        plt.show()
        return

    n_axes = 4
    fig, axes = plt.subplots(1, n_axes, figsize=(15, 5))
    vmin = min(np.nanmin(values_0), np.nanmin(values_1), np.nanmin(values_2))
    vmax = max(np.nanmax(values_0), np.nanmax(values_1), np.nanmax(values_2))
    norm = plt.Normalize(
        vmin=-max(abs(vmin), abs(vmax)), vmax=max(abs(vmin), abs(vmax))
    )

    axes[0].imshow(values_0, cmap="coolwarm", norm=norm, origin="lower")
    axes[0].set_title("Values for key 0")
    axes[1].imshow(values_1, cmap="coolwarm", norm=norm, origin="lower")
    axes[1].set_title("Values for key 1")
    axes[2].imshow(values_2, cmap="coolwarm", norm=norm, origin="lower")
    axes[2].set_title("Values for key 2")
    axes[3].imshow(values_apx, cmap="viridis", origin="lower")
    axes[3].set_title("Approximation ratio")

    for ax in axes:
        ax.set_xlabel("x2")
        ax.set_ylabel("x1")

    plt.tight_layout()
    fig.colorbar(axes[0].images[0], ax=axes, orientation="horizontal", fraction=0.1)

    plt.show()


def get_cont_mechanism_apx_bound(
    agents: tuple[int, ...],
    states,
    gv_m,
    cont_vertex_dis,
    alpha_low,
    alpha_change,
    certainty,
    log=lambda _: None,
):
    alpha_high = alpha_low + alpha_change
    while not is_apx_global_bound(agents, states, gv_m, cont_vertex_dis, alpha_high):
        alpha_high += alpha_change
        log(f"alpha_high proposition: {alpha_high}")
    alpha_low = alpha_high - alpha_change
    while alpha_high - alpha_low > certainty:
        log(f"high: {alpha_high}, low: {alpha_low}")
        alpha = (alpha_high + alpha_low) / 2
        if is_apx_global_bound(agents, states, gv_m, cont_vertex_dis, alpha):
            alpha_high = alpha
        else:
            alpha_low = alpha
    return alpha_high


def normalize_affine(
    check: pl.LpAffineExpression,
) -> frozenset[tuple[pl.LpVariable, float]]:
    """
    Normalize the affine expression by removing the constant term and returning
    the set of variables and their coefficients.
    """
    return frozenset((v, c) for v, c in check.items() if c != 0)


def get_extended_lp_m(
    graph: nx.Graph, successors, agents, vars_dict: Optional[dict] = None
):
    if vars_dict is None:
        vars_dict = {}
    __get_lp_var = dict_cache(get_lp_var, vars_dict)
    _lp_m = get_general_mechanism(
        graph,
        lambda s: agents,
        get_variable=__get_lp_var,
    )
    lp_m = lambda s, **kwargs: _lp_m(normalize_state(s, successors), **kwargs)

    __ex_vertex_m2 = get_anonymous_extension_of_mechanism(lp_m, successors)
    ex_vertex_m2 = fn.cache(map_mechanism_domain(__ex_vertex_m2, real_to_node))
    g_ex_m2 = vertex_mechanism_to_mechanism(ex_vertex_m2)
    m = general_mechanism_to_mechanism(g_ex_m2)

    return ex_vertex_m2, m


@app.command()
def test_f_mechanism(
    v: int = 8,
    save_path: Optional[Path] = None,
    apx_threshold: float = 1.236,
    seed: int = 1_000_000_007,
    f0: float = 0.1,
):
    random.seed(seed)
    anonymous = True
    n = 3
    graph = get_circle_graph(v)
    agents = tuple(range(n))
    successors, *mirrors = get_circle_graph_automorphisms(v)
    states = list(
        unique(
            normalize_state(s, successors)
            for s in gen_states_of_world(graph, 3, ordered=anonymous)
        )
    )
    dis = distances(graph)
    cont_dis = extend_dis_to_continuous(dis, successors)
    cont_vertex_dis = get_continuous_vertex_dis_on_cycle(v)
    console.rule("Mechanism definition")
    vars_dict = {}
    ex_vertex_m2, m = get_extended_lp_m(
        graph,
        successors,
        agents,
        vars_dict,
    )

    def get_splitted_graph(scale):
        return nx.Graph({x / scale: [] for x in range(scale * v)})

    _lsp_checks = list(
        gen_lsp_eps_checks(
            agents,
            graph,
            track(states, description="Generating lsp constraints..."),
            ex_vertex_m2,
            None,
            None,
            cont_vertex_dis,
            deviating_agents=[0],
            check_constructor=lambda x, _: x,
        )
    )
    console.log("LSP checks before:", len(_lsp_checks))

    lsp_checks = [
        pl.LpAffineExpression(y)
        for y in set(normalize_affine(x) for x, _ in _lsp_checks)
    ]
    console.log("LSP checks after:", len(lsp_checks))
    # embed()

    base_f = tuple(float(x) for x in np.linspace(f0, 1, v + 1))
    scale = 4
    G = get_splitted_graph(scale)
    states_G = list(filter(lambda x: x[0] < 1, gen_states_of_world(G, 3, ordered=True)))
    fs = []

    def set_f(f: list[float]):
        for state in states:
            res = ex_vertex_m2(tuple((v, 0) for v in state))
            p0 = f[int(state[2]) - int(state[1])]
            p1 = f[v - int(state[2]) + int(state[0])]
            p2 = f[int(state[1]) - int(state[0])]
            s = sum((p0, p1, p2))
            list(res[0].keys())[0].setInitialValue(p0 / s)
            list(res[1].keys())[0].setInitialValue(p1 / s)
            list(res[2].keys())[0].setInitialValue(p2 / s)

    def score_m(m, apx_threshold):
        def _get_apx(state):
            real_cost, opt_cost = get_apx_for_state(state, state, m, dis=cont_dis)
            return real_cost / opt_cost if opt_cost != 0 else 1

        special_state = (0, 2, 4)
        max_apx = _get_apx(special_state)
        if max_apx >= apx_threshold:
            return True, max_apx

        is_lsp = True
        epsilon = 0.00001
        for check in lsp_checks:
            val = assert_not_none(pl.value(check))
            if val < -epsilon:
                # print(description, val)
                is_lsp = False
                return True, float("inf")

        # calculate approximation ratio
        for state in states_G:
            apx = _get_apx(state)
            if apx <= max_apx:
                continue
            max_apx = apx
            if max_apx >= apx_threshold:
                break
        return not is_lsp, max_apx

    # def gen_fs():
    #     for dev in it.product(*dev_config):
    #         f = [x + y * 3 for x, y in zip(base_f, dev, strict=False)]
    #         yield f

    pool: list[tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]] = [
        (base_f, (0.01,) * len(base_f), (0,) * len(base_f)),
    ] * 5

    @fn.lru_cache(maxsize=1024)
    def cached_score(fd):
        try:
            f, d, mu = fd
            set_f(f)
            return *score_m(m, 2), abs(0.1 - sum(d))
        except ZeroDivisionError:
            return True, float("inf"), 0.1

    champions = [pool[0]]
    try:
        while True:
            # gen next pool by adding deviated fs
            pool = pool[:10] + [
                (
                    tuple(
                        max(min(x + random.gauss(_mu, dev), 1), 0)
                        for x, dev, _mu in zip(el, d, mu, strict=True)
                    ),
                    tuple(max(dev + random.gauss(0, 0.001), 0) for dev in d),
                    mu,  # tuple(_mu + random.gauss(0, 0.001) for _mu in mu),
                )
                for el, d, mu in pool
            ]
            # order pool by score
            pool = sorted(pool, key=cached_score)
            # print the best score

            best_score = cached_score(pool[0])
            console.print(f"Best score: {best_score}")
            console.print(f"Best f:\n{pool[0]}\n{pool[1]}")
            console.print(
                f"Num of LSP: {len(list(filter(lambda x: not cached_score(x)[0], pool)))}"
            )

            pool = pool[:25]
            if champions[-1] != pool[0]:
                champions.append(pool[0])
    except KeyboardInterrupt:
        console.print("Stopping the process.")
    # fs, _ = zip(*list(filter(lambda x: not cached_score(x)[0], pool)), strict=False)
    fs, _, _ = zip(*champions, strict=False)
    # fs = fs[:5]
    if save_path is not None:
        set_f(fs[0])
        with save_path.open("wb") as fl:
            pickle.dump(vars_dict, fl)
    # plot the fs on one plot
    fig, ax = plt.subplots()
    for i, f in enumerate(fs):
        # score = cached_score((f, (0.01,) * len(f)))[
        #     1
        # ]
        # Get the score for the current f
        color = plt.cm.viridis(i / len(fs))  # Normalize score for colormap
        ax.plot(
            f,
            label=f"{','.join([str(round(x, ndigits=3)).ljust(5, '_') for x in f])}",
            color=color,
        )
    ax.set_xticks(range(v + 1))
    ax.set_xticklabels([f"{i}/{v}" if i != 0 else "0" for i in range(v + 1)])
    ax.set_xlabel("x2")
    ax.set_ylabel("x1")
    ax.set_title("f values")
    ax.legend()
    plt.show()


@app.command()
def debug_symmetric_constraints():
    v = 4
    graph = get_circle_graph(v)
    n = 3
    agents = tuple(range(n))
    console.rule("Mechanism definition")
    successors, *_ = get_circle_graph_automorphisms(v)
    vars_dict = {}

    _lp_m = get_general_mechanism(
        graph,
        lambda s: agents,
        get_variable=dict_cache(get_sp_var, vars_dict),
    )
    lp_m = lambda s, *args, **kwargs: _lp_m(
        normalize_state(s, successors), *args, **kwargs
    )
    _ex_vertex_m2 = get_anonymous_extension_of_mechanism(lp_m, successors)
    __ex_vertex_m2 = _ex_vertex_m2
    ex_vertex_m2 = map_mechanism_domain(__ex_vertex_m2, real_to_node)
    g_ex_m2 = vertex_mechanism_to_mechanism(ex_vertex_m2)

    vars_dict2 = {}

    def _get_sp_var(el, state, *args, **kwargs):
        _state = normalize_state(state, successors)
        if _state == state:
            return get_sp_var(el, state, *args, **kwargs)
        return _get_sp_var(el, _state, *args, **kwargs)

    lp_m2 = get_general_mechanism(
        graph,
        lambda s: agents,
        get_variable=dict_cache(_get_sp_var, vars_dict2),
    )
    _ex_vertex_m22 = get_anonymous_extension_of_mechanism(lp_m2, successors)
    __ex_vertex_m22 = _ex_vertex_m22
    ex_vertex_m22 = map_mechanism_domain(__ex_vertex_m22, real_to_node)
    g_ex_m22 = vertex_mechanism_to_mechanism(ex_vertex_m22)

    def get_splitted_graph(scale):
        return nx.Graph({x / scale: [] for x in range(scale * v)})

    G = get_splitted_graph(2)
    states_G = list(gen_states_of_world(G, 3, ordered=True))
    for state in track(states_G, description="Comparing states..."):
        r1 = g_ex_m2(state)
        r2 = g_ex_m22(state)
        if r1 != r2:
            print(state)
            print(r1)
            print(r2)
            input("Press enter to continue")


def test_extended_median_mechanism(
    v: int = 8, anonymous: bool = True, interactive: bool = False
):
    # TODO: this test does not assert anything
    graph = get_circle_graph(v)
    n = 3
    agents = tuple(range(n))
    dis = distances(graph)
    states = list(gen_states_of_world(graph, 3, ordered=anonymous))
    console.rule("Mechanism definition")
    successors, *_ = get_circle_graph_automorphisms(v)
    vars_dict = {}

    def _get_lp_var(*args, **kwargs):
        res = get_lp_var(*args, **kwargs)
        # res.setInitialValue(1 / 3)
        return res

    def get_splitted_graph(scale):
        return nx.Graph({x / scale: [] for x in range(scale * v)})

    __get_lp_var = dict_cache(_get_lp_var, vars_dict)
    lp_m = get_general_mechanism(
        graph,
        lambda s: agents,
        anonymous=False,
        agents=agents,
        get_variable=__get_lp_var,
    )

    ex_vertex_m = map_mechanism_domain(
        extend_mechanism_to_continuous(lp_m, successors), real_to_node
    )

    def sp_sort(state):
        s2 = list(sorted(state))
        i2 = list(sorted(range(n), key=state.__getitem__))
        return s2, i2

    def ex_vertex_m2(state):
        s3, i3 = sp_sort(state)
        res = ex_vertex_m(tuple(s3))
        return map_dict_keys(res, dict(zip(range(n), i3, strict=True)))

    cont_dis = extend_dis_to_continuous(dis, successors)

    for state in states:
        _state = [int(node) for node in state]
        res = ex_vertex_m2(_state)
        s2 = list(sorted(_state))
        i2 = list(sorted(range(n), key=_state.__getitem__))
        biggest_arc_i = max(
            range(n), key=lambda i: s2[(i + 1) % n] + (i + 1) // n * v - s2[i]
        )
        first_i = (biggest_arc_i + 1) % n
        i3 = rotate(i2, first_i)
        res[i3[0]].setInitialValue(0)
        res[i3[1]].setInitialValue(1)
        res[i3[2]].setInitialValue(0)

    console.rule("Checking model")
    g_m = vertex_mechanism_to_mechanism(general_mechanism_to_mechanism(ex_vertex_m2))

    if interactive:
        embed(colors="Linux")

    for scale in range(1, 5):
        G = get_splitted_graph(scale)
        print(f"scale: {scale}")
        states = list(gen_states_of_world(G, 3, ordered=True))
        # sp_val = is_sp(G, states, g_m, dis=cont_dis, epsilon=0.0001)
        # print(f"sp: {sp_val}")
        # if not sp_val:
        #     for exp in gen_sp_counterexamples(
        #         G,
        #         states,
        #         g_m,
        #         dis=cont_dis,
        #         epsilon=0.0001,
        #     ):
        #         print(exp)
        #         input("Press enter to continue")
        apx_val = get_apx(G, states, g_m, dis=cont_dis)
        print(f"apx: {apx_val}")

        table = Table("apx", "state", title="Approximation ratio")
        for state_of_world in states:
            real, opt = get_apx_for_state(G.nodes, state_of_world, g_m, cont_dis)
            apx = real / opt if opt != 0 else 1
            if apx > 1.1:
                table.add_row(Pretty(apx), Pretty(state_of_world))
        # print table if it has any rows
        if table.row_count > 0:
            console.print(table)


if __name__ == "__main__":
    app()
