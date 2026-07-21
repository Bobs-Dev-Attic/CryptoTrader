"""Vercel Python serverless entrypoint.

Vercel's Python runtime serves an ASGI ``app`` exported from this module. All
routes are handled by the FastAPI application; ``vercel.json`` rewrites every
path to this function.
"""
from app.main import app  # noqa: F401  (Vercel looks for `app`)
