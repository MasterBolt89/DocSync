"""DocSync — API router."""
from __future__ import annotations

import logging
import re
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import get_settings
from app.models.schemas import AnalysisResult
from app.services.analyzer import run_demo_analysis, run_full_analysis

logger = logging.getLogger(__name__)
router = APIRouter()


class AnalyzeRequest(BaseModel):
    repo_url: str
    demo_mode: bool = False


@router.get("/health")
async def health():
    settings = get_settings()
    return {
        "status": "ok",
        "gemma_configured": settings.gemma_configured,
        "github_token_set": bool(settings.github_token),
    }


@router.get("/config-status")
async def config_status():
    settings = get_settings()
    return {
        "gemma_configured": settings.gemma_configured,
        "gemma_model": settings.gemma_model,
        "github_token_set": bool(settings.github_token),
        "message": (
            "Gemma API is configured and ready."
            if settings.gemma_configured
            else "Gemma API not configured. Set GEMMA_API_URL and GEMMA_API_KEY in your .env file. Demo mode and deterministic checks are available."
        ),
    }


@router.post("/analyze", response_model=AnalysisResult)
async def analyze(request: AnalyzeRequest):
    if request.demo_mode:
        return await run_demo_analysis()

    url = request.repo_url.strip()
    if not url:
        raise HTTPException(status_code=422, detail="Repository URL is required.")
    if "github.com" not in url and not re.match(r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$", url):
        raise HTTPException(status_code=422, detail="Only GitHub repositories are supported (e.g. https://github.com/owner/repo or owner/repo).")

    result = await run_full_analysis(url)

    if result.error and result.files_fetched == 0:
        # Surface fatal errors as HTTP errors
        raise HTTPException(status_code=400, detail=result.error)

    return result
