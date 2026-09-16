from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...campus_map.graph import get_campus_graph
from ...core.deps import get_current_user
from ...db.session import get_db
from ...models.user import User, UserRoute
from ...schemas import UserOut, UserRouteIn, UserRouteOut

router = APIRouter(prefix="/users", tags=["用户"])


@router.get("/me", response_model=UserOut, summary="我的资料与信用信息")
def get_me(me: User = Depends(get_current_user)):
    return me


@router.get("/{user_id}", response_model=UserOut, summary="查看用户公开资料")
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "用户不存在")
    return user


def _route_out(route: UserRoute) -> UserRouteOut:
    graph = get_campus_graph()
    return UserRouteOut(
        id=route.id,
        name=route.name,
        waypoints=route.waypoints,
        waypoint_names=[graph.node_name(n) for n in route.waypoints],
        active=route.active,
    )


@router.get("/me/routes", response_model=list[UserRouteOut], summary="我的日常路线")
def list_my_routes(me: User = Depends(get_current_user), db: Session = Depends(get_db)):
    routes = db.query(UserRoute).filter(UserRoute.user_id == me.id, UserRoute.active.is_(True)).all()
    return [_route_out(r) for r in routes]


@router.post("/me/routes", response_model=UserRouteOut, summary="登记日常路线（智能匹配的输入）")
def create_my_route(payload: UserRouteIn, me: User = Depends(get_current_user), db: Session = Depends(get_db)):
    graph = get_campus_graph()
    resolved: list[str] = []
    for wp in payload.waypoints:
        nid = graph.resolve(wp)
        if nid is None:
            raise HTTPException(400, f"无法识别地点: {wp}")
        resolved.append(nid)
    if len(set(resolved)) < 2:
        raise HTTPException(400, "路线至少需要两个不同的地点")
    route = UserRoute(user_id=me.id, name=payload.name, waypoints=resolved)
    db.add(route)
    db.commit()
    db.refresh(route)
    return _route_out(route)


@router.delete("/me/routes/{route_id}", summary="删除日常路线")
def delete_my_route(route_id: int, me: User = Depends(get_current_user), db: Session = Depends(get_db)):
    route = db.get(UserRoute, route_id)
    if route is None or route.user_id != me.id:
        raise HTTPException(404, "路线不存在")
    route.active = False
    db.commit()
    return {"ok": True}
