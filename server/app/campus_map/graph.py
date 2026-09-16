"""Campus graph model.

Loads the campus road network (nodes / edges) from a JSON file and exposes
an undirected weighted graph used by the routing and matching engines.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DATA_FILE = Path(__file__).resolve().parent / "data" / "jinnan.json"


@dataclass(frozen=True)
class Node:
    id: str
    name: str
    x: float
    y: float
    type: str = "poi"
    aliases: Tuple[str, ...] = field(default_factory=tuple)


class CampusGraph:
    """Undirected weighted graph of a campus road network."""

    def __init__(self, nodes: Dict[str, Node], adj: Dict[str, Dict[str, float]], walk_speed: float = 80.0):
        self.nodes = nodes
        self.adj = adj  # adj[a][b] = distance in meters
        self.walk_speed = walk_speed  # meters per minute

    # ------------------------------------------------------------------ #
    # construction
    # ------------------------------------------------------------------ #
    @classmethod
    def from_json(cls, path: str | Path) -> "CampusGraph":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        nodes: Dict[str, Node] = {}
        for n in raw["nodes"]:
            nodes[n["id"]] = Node(
                id=n["id"],
                name=n["name"],
                x=float(n["x"]),
                y=float(n["y"]),
                type=n.get("type", "poi"),
                aliases=tuple(n.get("aliases", [])),
            )
        adj: Dict[str, Dict[str, float]] = {nid: {} for nid in nodes}
        for e in raw["edges"]:
            a, b, d = e["from"], e["to"], float(e["distance"])
            if a not in nodes or b not in nodes:
                raise ValueError(f"edge references unknown node: {a}-{b}")
            if d <= 0:
                raise ValueError(f"edge distance must be positive: {a}-{b}")
            adj[a][b] = d
            adj[b][a] = d
        walk_speed = float(raw.get("meta", {}).get("walk_speed_m_per_min", 80.0))
        return cls(nodes, adj, walk_speed)

    # ------------------------------------------------------------------ #
    # lookup helpers
    # ------------------------------------------------------------------ #
    def neighbors(self, node_id: str) -> Dict[str, float]:
        return self.adj.get(node_id, {})

    def resolve(self, text: str) -> Optional[str]:
        """Resolve free text (name or alias) to a node id. Exact match first,
        then substring containment (longest node name wins)."""
        text = (text or "").strip()
        if not text:
            return None
        if text in self.nodes:
            return text
        for nid, node in self.nodes.items():
            if text == node.name or text in node.aliases:
                return nid
        # substring match, prefer the longest matching name/alias
        best: Tuple[int, Optional[str]] = (0, None)
        for nid, node in self.nodes.items():
            for cand in (node.name, *node.aliases):
                if cand and (cand in text or text in cand):
                    if len(cand) > best[0]:
                        best = (len(cand), nid)
        return best[1]

    def node_name(self, node_id: str) -> str:
        node = self.nodes.get(node_id)
        return node.name if node else node_id

    def distance_to_time(self, meters: float) -> float:
        """Convert walking distance (m) to minutes."""
        return meters / self.walk_speed


@lru_cache(maxsize=1)
def get_campus_graph(path: str | Path = DATA_FILE) -> CampusGraph:
    """Process-wide cached campus graph."""
    return CampusGraph.from_json(path)
