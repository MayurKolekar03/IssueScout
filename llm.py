"""
llm.py – LLM interaction: send prompt, parse JSON response robustly.
"""

from __future__ import annotations

import json
import os
import re

from dotenv import load_dotenv
from openai import OpenAI

from prompts import SYSTEM_PROMPT, build_user_prompt

load_dotenv(override=True)

# ── Config from environment ────────────────────────────────────────────────────
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://inference.do-ai.run/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "dummy")  # Ollama accepts any non-empty key
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.3-70b-instruct")

# Approximate character budget to stay under ~12k tokens
# (1 token ≈ 4 chars → 12k tokens ≈ 48k chars)
MAX_PROMPT_CHARS = 48_000


def _get_client() -> OpenAI:
    """Create and return an OpenAI-compatible client."""
    base_url = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
    api_key = os.getenv("LLM_API_KEY", "")
    return OpenAI(api_key=api_key, base_url=base_url)


def _extract_json(text: str) -> dict:
    """
    Robustly extract the first JSON object from a string.
    Strips markdown code fences, then finds the first {...} block.
    Raises ValueError if no valid JSON found.
    """
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = text.replace("```", "")

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in response.")

    json_str = text[start : end + 1]
    return json.loads(json_str)


def _call_llm(client: OpenAI, user_prompt: str, use_json_mode: bool) -> str:
    """Single LLM API call. Returns the raw content string."""
    model = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")
    kwargs: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 2048,
    }
    if use_json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content or ""


def get_issue_plan(ctx: dict) -> dict:
    """
    Main entry point: build prompt, call LLM, return parsed JSON plan.

    Strategy:
      1. Try with json_object response format.
      2. If provider rejects it (400/422), retry without it.
      3. Parse the response; if parsing fails, retry once with a reminder.
      4. If still failing, raise with the raw text attached.
    """
    client = _get_client()

    # Build and truncate prompt
    user_prompt = build_user_prompt(ctx)
    if len(user_prompt) > MAX_PROMPT_CHARS:
        user_prompt = user_prompt[:MAX_PROMPT_CHARS] + "\n...[truncated for length]"

    # ── Attempt 1: with json_object mode ─────────────────────────────────────
    raw_text = ""
    try:
        raw_text = _call_llm(client, user_prompt, use_json_mode=True)
    except Exception as e:
        err_str = str(e).lower()
        if any(kw in err_str for kw in ["response_format", "json_object", "400", "422", "unsupported"]):
            # Provider doesn't support json_object mode → retry without it
            raw_text = _call_llm(client, user_prompt, use_json_mode=False)
        else:
            raise

    # ── Parse ─────────────────────────────────────────────────────────────────
    try:
        return _extract_json(raw_text)
    except (ValueError, json.JSONDecodeError):
        pass  # Fall through to retry

    # ── Attempt 2: retry with explicit JSON reminder ──────────────────────────
    reminder = (
        "\n\nIMPORTANT: Your previous response was not valid JSON. "
        "Return ONLY a valid JSON object — no prose, no code fences."
    )
    retry_prompt = user_prompt + reminder
    raw_text_2 = ""
    try:
        raw_text_2 = _call_llm(client, retry_prompt, use_json_mode=False)
        return _extract_json(raw_text_2)
    except (ValueError, json.JSONDecodeError) as parse_err:
        # Attach raw output for the UI to display in an expander
        raise ValueError(
            f"Could not parse LLM response as JSON.\n\n"
            f"__raw__\n{raw_text_2 or raw_text}"
        ) from parse_err
