"""
DocSync — Gemma 4 AI client.
Isolated module — change request format here without touching the rest of the app.

The endpoint format is intentionally flexible:
  - If the endpoint looks like an OpenAI-compatible /v1/chat/completions, we use that format.
  - Otherwise, we POST to the URL directly with a simple {"prompt": ..., "model": ...} body.

Set GEMMA_API_URL to your actual endpoint URL.
Set GEMMA_API_KEY to your API key (sent as Authorization: Bearer <key>).
Set GEMMA_MODEL to the model identifier required by your endpoint (optional).
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

import httpx

from app.core.config import get_settings
from app.models.schemas import AIAnalysisResponse, AIFinding

logger = logging.getLogger(__name__)

# System prompt injected before every request
SYSTEM_PROMPT = """You are DocSync's documentation auditor. Your job is to identify genuine inconsistencies between software documentation and source code.

Analyze the provided documentation claims and code facts carefully:
- Only flag real inconsistencies, not superficial wording differences.
- Distinguish between confirmed contradictions and unverifiable claims.
- Pay attention to renamed parameters, removed functions, and changed configuration keys.
- Do NOT invent line numbers, file names, or code snippets not provided to you.
- Respond ONLY with a valid JSON object matching this schema:

{
  "findings": [
    {
      "title": "short descriptive title",
      "category": "outdated_signature|removed_symbol|config_drift|conflicting_docs|outdated_install|unverified_claim",
      "severity": "critical|high|medium|low|info",
      "documented_claim": "exact text from documentation",
      "evidence_excerpt": "relevant code snippet",
      "explanation": "clear explanation of the discrepancy",
      "suggested_fix": "how to fix the documentation",
      "confidence": 0.0 to 1.0,
      "is_genuine_issue": true or false
    }
  ],
  "summary": "one-sentence summary of the analysis"
}

If there are no genuine issues, return {"findings": [], "summary": "No significant inconsistencies detected."}
"""


def _is_openai_compatible(url: str) -> bool:
    return "chat/completions" in url or "openai" in url.lower()


def _build_openai_request(prompt: str, model: Optional[str]) -> dict:
    body: dict = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 4096,
    }
    if model:
        body["model"] = model
    return body


def _build_generic_request(prompt: str, model: Optional[str]) -> dict:
    """Generic format for non-OpenAI endpoints (e.g., Google AI Studio, Vertex AI)."""
    body: dict = {
        "contents": [
            {
                "parts": [
                    {"text": SYSTEM_PROMPT + "\n\n" + prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 4096,
        },
    }
    if model:
        body["model"] = model
    return body


def _extract_json_from_response(response_data: dict, is_openai: bool) -> str:
    """Extract the text/JSON string from various response shapes."""
    # OpenAI-compatible
    if is_openai:
        choices = response_data.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "")

    # Google AI / Gemini-style
    candidates = response_data.get("candidates", [])
    if candidates:
        content = candidates[0].get("content", {})
        parts = content.get("parts", [])
        if parts:
            return parts[0].get("text", "")

    # Fallback: look for common text fields
    for key in ("text", "output", "response", "result", "generated_text"):
        if key in response_data:
            return str(response_data[key])

    # Last resort: stringify
    return json.dumps(response_data)


def _parse_ai_response(raw_text: str) -> AIAnalysisResponse:
    """Parse AI JSON response, handling markdown fences and other noise."""
    # strip markdown code fences
    text = raw_text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    # extract JSON object
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        text = brace_match.group(0)

    try:
        data = json.loads(text)
        return AIAnalysisResponse(
            findings=[AIFinding(**f) for f in data.get("findings", [])],
            summary=data.get("summary"),
        )
    except Exception as e:
        logger.warning("Failed to parse AI response as JSON: %s", e)
        logger.debug("Raw AI response: %s", raw_text[:500])
        return AIAnalysisResponse(findings=[], summary="Response parse error")


async def call_gemma(prompt: str, client: httpx.AsyncClient) -> Optional[AIAnalysisResponse]:
    """
    Call the configured Gemma endpoint and return parsed findings.
    Returns None if the API is not configured or the call fails.
    """
    settings = get_settings()
    if not settings.gemma_configured:
        logger.info("Gemma API not configured — skipping AI analysis.")
        return None

    url = settings.gemma_api_url
    key = settings.gemma_api_key
    model = settings.gemma_model

    is_openai = _is_openai_compatible(url)
    body = _build_openai_request(prompt, model) if is_openai else _build_generic_request(prompt, model)

    headers: dict = {
        "Content-Type": "application/json",
    }
    if "googleapis.com" in url:
        headers["x-goog-api-key"] = key
    else:
        headers["Authorization"] = f"Bearer {key}"
        headers["x-goog-api-key"] = key

    try:
        response = await client.post(url, json=body, headers=headers, timeout=60.0)

        if response.status_code == 401:
            logger.error("Gemma API: authentication error (check GEMMA_API_KEY).")
            return None
        if response.status_code == 429:
            logger.warning("Gemma API: rate limit hit.")
            return None
        if response.status_code >= 500:
            logger.error("Gemma API: server error %d", response.status_code)
            return None

        response.raise_for_status()
        data = response.json()
        raw_text = _extract_json_from_response(data, is_openai)
        return _parse_ai_response(raw_text)

    except httpx.TimeoutException:
        logger.warning("Gemma API: request timed out.")
        return None
    except httpx.HTTPStatusError as e:
        logger.error("Gemma API HTTP error: %s", e)
        return None
    except Exception as e:
        logger.error("Gemma API unexpected error: %s", e)
        return None
