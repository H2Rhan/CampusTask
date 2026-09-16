from fastapi import APIRouter, HTTPException, Query

from ...campus_map.graph import get_campus_graph
from ...campus_map.routing import astar, dijkstra
from ...schemas import MapEdgeOut, MapNodeOut, RouteOut

router = APIRouter(prefix="/map", tags=["校园地图"])


@router.get("/nodes", response_model=list[MapNodeOut], summary="全部地图节点")
def list_nodes():
    graph = get_campus_graph()
    return [
        MapNodeOut(id=n.id, name=n.name, x=n.x, y=n.y, type=n.type, aliases=list(n.aliases))
        for n in graph.nodes.values()
    ]


@router.get("/edges", response_model=list[MapEdgeOut], summary="全部道路边")
def list_edges():
    graph = get_campus_graph()
    edges, seen = [], set()
    for a, nbrs in graph.adj.items():
        for b, d in nbrs.items():
            key = tuple(sorted((a, b)))
            if key in seen:
                continue
            seen.add(key)
            edges.append(MapEdgeOut(from_node=a, to_node=b, distance=d))
    return edges


@router.get("/resolve", summary="地点名称 → 节点 id（支持别名/模糊匹配）")
def resolve_place(q: str = Query(min_length=1)):
    graph = get_campus_graph()
    nid = graph.resolve(q)
    if nid is None:
        raise HTTPException(404, f"无法识别地点: {q}")
    node = graph.nodes[nid]
    return {"id": nid, "name": node.name}


@router.get("/route", response_model=RouteOut, summary="最短路径（dijkstra / astar）")
def route(
    start: str = Query(description="起点：节点 id / 名称 / 别名"),
    end: str = Query(description="终点：节点 id / 名称 / 别名"),
    engine: str = Query(default="dijkstra", pattern="^(dijkstra|astar)$"),
):
    graph = get_campus_graph()
    a, b = graph.resolve(start), graph.resolve(end)
    if a is None or b is None:
        raise HTTPException(404, "起点或终点无法识别")
    fn = astar if engine == "astar" else dijkstra
    result = fn(graph, a, b)
    if result is None:
        raise HTTPException(422, "两点之间不可达")
    return RouteOut(**result.__dict__)
