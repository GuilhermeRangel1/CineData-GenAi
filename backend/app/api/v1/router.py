from fastapi import APIRouter

from app.api.v1.analytics import analytics_router
from app.api.v1.auth import auth_router
from app.api.v1.communities import communities_router
from app.api.v1.conversations import conversations_router
from app.api.v1.external_movies import external_movies_router
from app.api.v1.friendships import friendships_router
from app.api.v1.lists import lists_router
from app.api.v1.movies import movies_router
from app.api.v1.profiles import profiles_router
from app.api.v1.taste_map import taste_map_router

api_router = APIRouter()
api_router.include_router(analytics_router)
api_router.include_router(auth_router)
api_router.include_router(communities_router)
api_router.include_router(conversations_router)
api_router.include_router(external_movies_router)
api_router.include_router(friendships_router)
api_router.include_router(movies_router)
api_router.include_router(lists_router)
api_router.include_router(profiles_router)
api_router.include_router(taste_map_router)
