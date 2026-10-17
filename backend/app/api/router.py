"""API 路由聚合。"""
from fastapi import APIRouter

from app.api.v1 import (
    auth,
    dashboard,
    downloads,
    main_tasks,
    market,
    meta,
    metrics,
    orgs,
    projects,
    roles,
    system,
    tasks,
    users,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(meta.router)
api_router.include_router(orgs.router)
api_router.include_router(projects.router)
api_router.include_router(market.router)
api_router.include_router(roles.router)
api_router.include_router(users.router)
api_router.include_router(metrics.router)
api_router.include_router(tasks.router)
api_router.include_router(main_tasks.router)
api_router.include_router(dashboard.router)
api_router.include_router(system.router)
api_router.include_router(downloads.router)
