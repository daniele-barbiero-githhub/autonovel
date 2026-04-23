"""
Shared LLM client for autonovel scripts.

Defaults preserve the original Anthropic behavior. Set
AUTONOVEL_LLM_PROVIDER=gemini plus GEMINI_API_KEY to use Gemini instead.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

ANTHROPIC_DEFAULT_BASE_URL = "https://api.anthropic.com"
GEMINI_DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
ANTHROPIC_DEFAULT_BETA = "context-1m-2025-08-07"

ROLE_MODEL_ENV = {
    "writer": "AUTONOVEL_WRITER_MODEL",
    "judge": "AUTONOVEL_JUDGE_MODEL",
    "review": "AUTONOVEL_REVIEW_MODEL",
}

DEFAULT_MODELS = {
    ("anthropic", "writer"): "claude-sonnet-4-6",
    ("anthropic", "judge"): "claude-opus-4-6",
    ("anthropic", "review"): "claude-opus-4-6",
    ("gemini", "writer"): "gemini-2.5-pro",
    ("gemini", "judge"): "gemini-2.5-pro",
    ("gemini", "review"): "gemini-2.5-pro",
}


@dataclass(frozen=True)
class LLMConfig:
    role: str
    provider: str
    model: str
    api_key: str
    api_key_env: str
    api_base_url: str


def normalize_provider(provider: str) -> str:
    value = provider.strip().lower()
    aliases = {
        "claude": "anthropic",
        "anthropic": "anthropic",
        "google": "gemini",
        "google-gemini": "gemini",
        "gemini": "gemini",
    }
    if value not in aliases:
        raise ValueError(
            f"Unsupported LLM provider {provider!r}. Use 'anthropic' or 'gemini'."
        )
    return aliases[value]


def provider_for(role: str) -> str:
    role_key = role.upper()
    provider = (
        os.environ.get(f"AUTONOVEL_{role_key}_PROVIDER")
        or os.environ.get("AUTONOVEL_LLM_PROVIDER")
        or os.environ.get("AUTONOVEL_PROVIDER")
        or "anthropic"
    )
    return normalize_provider(provider)


def model_for(role: str, anthropic_default: str | None = None) -> str:
    provider = provider_for(role)
    provider_model_env = f"AUTONOVEL_{provider.upper()}_{role.upper()}_MODEL"
    if os.environ.get(provider_model_env):
        return os.environ[provider_model_env]

    model_env = ROLE_MODEL_ENV.get(role)
    if model_env and os.environ.get(model_env):
        model = os.environ[model_env]
        if _model_matches_provider(model, provider):
            return model

    if provider == "anthropic" and anthropic_default:
        return anthropic_default
    return DEFAULT_MODELS.get((provider, role), DEFAULT_MODELS[(provider, "writer")])


def _model_matches_provider(model: str, provider: str) -> bool:
    value = model.strip().lower()
    if provider == "gemini":
        return value.startswith("gemini") or value.startswith("models/gemini")
    if provider == "anthropic":
        return "claude" in value
    return True


def config_for(role: str, model: str | None = None) -> LLMConfig:
    provider = provider_for(role)
    resolved_model = model or model_for(role)

    if provider == "anthropic":
        api_key_env = "ANTHROPIC_API_KEY"
        api_base_url = (
            os.environ.get("AUTONOVEL_ANTHROPIC_BASE_URL")
            or os.environ.get("AUTONOVEL_API_BASE_URL")
            or ANTHROPIC_DEFAULT_BASE_URL
        )
    elif provider == "gemini":
        api_key_env = "GEMINI_API_KEY"
        api_base_url = os.environ.get("AUTONOVEL_GEMINI_BASE_URL") or GEMINI_DEFAULT_BASE_URL
    else:
        raise ValueError(f"Unsupported LLM provider {provider!r}")

    return LLMConfig(
        role=role,
        provider=provider,
        model=resolved_model,
        api_key=os.environ.get(api_key_env, ""),
        api_key_env=api_key_env,
        api_base_url=api_base_url.rstrip("/"),
    )


def require_api_key(role: str, model: str | None = None) -> LLMConfig:
    cfg = config_for(role, model)
    if not cfg.api_key:
        raise RuntimeError(
            f"ERROR: Set {cfg.api_key_env} in .env first "
            f"(provider={cfg.provider}, role={role})"
        )
    return cfg


def call_llm(
    prompt: str,
    *,
    role: str,
    model: str | None = None,
    max_tokens: int = 4000,
    temperature: float = 0.7,
    system: str | None = None,
    timeout: int = 300,
    anthropic_beta: str | None = None,
) -> str:
    cfg = require_api_key(role, model)
    if cfg.provider == "anthropic":
        return _call_anthropic(
            cfg,
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            timeout=timeout,
            anthropic_beta=anthropic_beta,
        )
    if cfg.provider == "gemini":
        return _call_gemini(
            cfg,
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            timeout=timeout,
        )
    raise ValueError(f"Unsupported LLM provider {cfg.provider!r}")


def _call_anthropic(
    cfg: LLMConfig,
    prompt: str,
    *,
    max_tokens: int,
    temperature: float,
    system: str | None,
    timeout: int,
    anthropic_beta: str | None,
) -> str:
    import httpx

    headers = {
        "x-api-key": cfg.api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    beta = (
        anthropic_beta
        if anthropic_beta is not None
        else os.environ.get("AUTONOVEL_ANTHROPIC_BETA", ANTHROPIC_DEFAULT_BETA)
    )
    if beta:
        headers["anthropic-beta"] = beta

    payload = {
        "model": cfg.model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        payload["system"] = system

    resp = httpx.post(
        f"{cfg.api_base_url}/v1/messages",
        headers=headers,
        json=payload,
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    content = data.get("content", [])
    text_blocks = [
        block.get("text", "")
        for block in content
        if block.get("type") == "text" and block.get("text")
    ]
    if text_blocks:
        return "\n\n".join(text_blocks)
    if content and isinstance(content[0], dict) and content[0].get("text"):
        return content[0]["text"]
    raise KeyError(f"No text block in Anthropic response content: {content!r}")


def _call_gemini(
    cfg: LLMConfig,
    prompt: str,
    *,
    max_tokens: int,
    temperature: float,
    system: str | None,
    timeout: int,
) -> str:
    import httpx

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": temperature,
        },
    }
    if system:
        payload["system_instruction"] = {"parts": [{"text": system}]}

    resp = httpx.post(
        f"{cfg.api_base_url}/models/{cfg.model}:generateContent",
        headers={
            "x-goog-api-key": cfg.api_key,
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()

    parts = []
    for candidate in data.get("candidates", []):
        content = candidate.get("content", {})
        for part in content.get("parts", []):
            text = part.get("text")
            if text:
                parts.append(text)
    if parts:
        return "\n\n".join(parts)

    finish_reasons = [
        candidate.get("finishReason")
        for candidate in data.get("candidates", [])
        if candidate.get("finishReason")
    ]
    raise KeyError(
        "No text block in Gemini response: "
        f"finish_reasons={finish_reasons!r}, "
        f"prompt_feedback={data.get('promptFeedback')!r}"
    )
