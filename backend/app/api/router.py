"""Aggregates all API route modules. Everything here is mounted under /api."""

from fastapi import APIRouter

from app.api.routes import health, openai, uploads

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(uploads.router)
api_router.include_router(openai.router)
