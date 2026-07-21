"""Vercel Python serverless entrypoint for the single-project deployment.

The whole app deploys from the repo root: the Expo web build is served as
static files, and every ``/api/*`` request is rewritten to this function, which
serves the FastAPI backend that lives in ``backend/app``.

``backend/`` is bundled into the function via ``functions.includeFiles`` in the
root ``vercel.json``; we add it to the import path here so ``app`` resolves.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.main import app  # noqa: E402,F401  (Vercel serves this ASGI `app`)
