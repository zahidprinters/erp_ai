# ---------------------------------------------------------------------------
# LLM interface — supports multiple providers: Ollama, OpenRouter, Together AI,
# Groq, Anthropic, OpenAI, Google Gemini, Mistral, Custom API, LM Studio.
#
# Single responsibility: send a prompt to the configured LLM provider and get text back.
# No ERP logic, no doctype knowledge — just the wire.
# ---------------------------------------------------------------------------
# LLM Provider enum for type-safe provider selection
from enum import Enum

import frappe
import requests


class LLMProvider(str, Enum):
	"""Available LLM providers."""

	OLLAMA = "Ollama (Local)"
	OPENROUTER = "OpenRouter"
	TOGETHER = "Together AI"
	GROQ = "Groq"
	ANTHROPIC = "Anthropic"
	OPENAI = "OpenAI"
	GEMINI = "Google Gemini"
	MISTRAL = "Mistral"
	CUSTOM = "Custom API"
	LM_STUDIO = "LM Studio"


# Provider configurations
PROVIDERS = {
	"Ollama (Local)": {"base_url": "http://localhost:11434/api/generate", "model_format": "name"},
	"OpenRouter": {
		"base_url": "https://openrouter.ai/api/v1/chat/completions",
		"model_format": "provider/model",
	},
	"Together AI": {"base_url": "https://api.together.ai/v1/chat/completions", "model_format": "name"},
	"Groq": {"base_url": "https://api.groq.com/openai/v1/chat/completions", "model_format": "name"},
	"Anthropic": {
		"base_url": "https://api.anthropic.com/v1/messages",
		"model_format": "name",
		"type": "anthropic",
	},
	"OpenAI": {"base_url": "https://api.openai.com/v1/chat/completions", "model_format": "name"},
	"Google Gemini": {
		"base_url": "https://generativelanguage.googleapis.com/v1beta/models",
		"model_format": "models/name",
		"type": "google",
	},
	"Mistral": {"base_url": "https://api.mistral.ai/v1/chat/completions", "model_format": "name"},
	"Custom API": {"base_url": "", "model_format": "name"},
	"LM Studio": {"base_url": "http://localhost:1234/v1/chat/completions", "model_format": "name"},
}

# Default models per provider
DEFAULT_MODELS = {
	"Ollama (Local)": "qwen2.5:1.5b",
	"OpenRouter": "~openai/gpt-4o-mini",
	"Together AI": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
	"Groq": "llama-3.1-8b-instant",
	"Anthropic": "claude-3-5-haiku-20241022",
	"OpenAI": "gpt-4o-mini",
	"Google Gemini": "gemini-2.0-flash",
	"Mistral": "mistral-small-latest",
	"Custom API": "",
	"LM Studio": "lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF",
}

# Models the assistant is allowed to call directly (for Ollama local models)
AI_ALLOWED_MODELS = frozenset(("qwen2.5:1.5b", "qwen2.5:3b", "qwen2.5:7b"))

# Hard ceiling (seconds) for an Ollama generate() call. The settings form
# accepts any timeout, but a misconfigured value (or a hung model) should
# never make the chat or health endpoint hang for minutes. 30s is the
# largest value we tolerate for a single Ollama round-trip; callers that
# want longer (e.g. first-token warmup) must pass timeout explicitly.
OLLAMA_TIMEOUT_CEILING = 30

# Number of retries for transient Ollama failures (connection refused while
# the runtime is starting up, brief 503s from the generate queue, etc.).
OLLAMA_MAX_RETRIES = 2


# ---------------------------------------------------------------------------
# Helper to clean provider name from database storage format
# Database stores: "ollama|Ollama (Local - Free)"
# Code expects: "Ollama (Local)"
# ---------------------------------------------------------------------------
def clean_provider_name(stored_value):
	"""Extract clean provider name from database storage format.

	Database stores select field as "key|Label" format.
	Code needs the PROVIDERS dict key.
	"""
	if not stored_value:
		return "Ollama (Local)"

	# Split on pipe and take the second part (the label)
	if "|" in stored_value:
		label = stored_value.split("|", 1)[1]
	else:
		label = stored_value

	# Map database labels to PROVIDERS dict keys
	# Database labels may differ slightly from PROVIDERS keys
	label_to_key = {
		"Ollama (Local - Free)": "Ollama (Local)",
		"Ollama (Local)": "Ollama (Local)",
		"OpenRouter (Cloud - Pay per use)": "OpenRouter",
		"OpenRouter": "OpenRouter",
		"Together AI (Cloud - Pay per use)": "Together AI",
		"Together AI": "Together AI",
		"Groq (Cloud - Fast)": "Groq",
		"Groq": "Groq",
		"Anthropic / Claude (Cloud)": "Anthropic",
		"Anthropic": "Anthropic",
		"OpenAI / GPT (Cloud)": "OpenAI",
		"OpenAI": "OpenAI",
		"Google Gemini (Cloud)": "Google Gemini",
		"Google Gemini": "Google Gemini",
		"Mistral AI (Cloud)": "Mistral",
		"Mistral": "Mistral",
		"Custom OpenAI-compatible API": "Custom API",
		"Custom API": "Custom API",
		"LM Studio (Local - Free)": "LM Studio",
		"LM Studio": "LM Studio",
		# The doctype stores the Select's bare option keys
		# ("ollama|Ollama (Local - Free)" collapses to "ollama" before the pipe
		# split), so they must map too — "ollama" is even the field default.
		"ollama": "Ollama (Local)",
		"lm_studio": "LM Studio",
		"openrouter": "OpenRouter",
		"together": "Together AI",
		"groq": "Groq",
		"anthropic": "Anthropic",
		"openai": "OpenAI",
		"gemini": "Google Gemini",
		"mistral": "Mistral",
		"custom": "Custom API",
	}

	return label_to_key.get(label, label)


# ---------------------------------------------------------------------------
# AI Settings field resolution (audit point 14)
#
# The AI Settings *form* writes ``api_key`` / ``custom_api_base_url`` /
# ``llm_model``, while this module historically read ``llm_api_key`` /
# ``llm_base_url`` / ``default_llm_model`` for the same three settings. An
# operator-entered key or endpoint was therefore silently ignored and the
# assistant ran unauthenticated against the provider default. Both spellings are
# read now, so no stored configuration has to be migrated.
# ---------------------------------------------------------------------------
def _configured(settings, *fieldnames):
	"""First non-empty value among ``fieldnames`` on an AI Settings document."""
	for fieldname in fieldnames:
		value = settings.get(fieldname)
		if value:
			return value
	return None


def stored_model_name(stored):
	"""Model inside a stored Select value (``"ollama|qwen2.5:3b"`` -> ``"qwen2.5:3b"``).

	Frappe stores a Select as its raw option string and both spellings are in
	use: the doctype ships ``provider|model`` options while the settings form
	writes the bare model id.
	"""
	if not stored:
		return ""
	return str(stored).split("|", 1)[1] if "|" in str(stored) else str(stored)


def configured_model(settings):
	"""The model the assistant will actually call for this configuration.

	``default_llm_model`` stays authoritative (it is the field the runtime has
	always read and carries the shipped default), with the form's ``llm_model``
	as fallback when it is blank.
	"""
	return _configured(settings, "default_llm_model") or stored_model_name(_configured(settings, "llm_model"))


def validate_deployment_settings(settings):
	"""Return a blocking deployment-configuration problem, or ``None``.

	The LLM backend is site state, so a missing value used to surface as an
	unexplained failure in the middle of a chat. Callers turn a returned message
	into an error at the settings boundary instead (audit point 14: missing
	runtime configuration is a release blocker, not a silent degradation).

	Only settings the runtime cannot work around are blocking — model
	allowlisting stays in ``validate_model``, which already throws with its own
	remedy (``available_models``).
	"""
	stored_provider = settings.get("llm_provider")
	provider = clean_provider_name(stored_provider)
	if provider not in PROVIDERS:
		return "Unknown LLM provider '{}'. Set LLM Provider in AI Settings to one of: {}.".format(
			stored_provider, ", ".join(sorted(PROVIDERS))
		)

	# Hosted providers are reached over the public internet and cannot be called
	# without credentials; local endpoints (Ollama, LM Studio, a self-hosted
	# OpenAI-compatible server) legitimately run without one.
	if PROVIDERS[provider]["base_url"].startswith("https:") and provider != "Custom API":
		if not _configured(settings, "api_key", "llm_api_key"):
			return "{} requires an API key. Set API Key in AI Settings before using the assistant.".format(
				provider
			)

	if provider == "Custom API":
		if not _configured(settings, "custom_api_base_url", "llm_base_url"):
			return "Custom API requires a base URL. Set Custom API Base URL in AI Settings."
		if not configured_model(settings):
			return (
				"Custom API requires a model name: no default model can be derived for an arbitrary endpoint."
			)

	for fieldname, label in (("timeout_seconds", "Timeout (seconds)"), ("max_tokens", "Max Tokens")):
		raw = settings.get(fieldname)
		if raw in (None, ""):
			continue
		try:
			value = int(raw)
		except (TypeError, ValueError):
			return "{} must be a whole number.".format(label)
		if value < 1:
			return "{} must be at least 1.".format(label)
	return None


def get_llm_settings():
	"""Get AI Settings document."""
	return frappe.get_single("AI Settings")


def get_provider_config(provider=None):
	"""Get configuration for a specific provider.

	``provider`` may be the stored Select value (``"openrouter|OpenRouter (…)"``)
	or a clean key. An unknown provider throws instead of silently falling back
	to the local Ollama default, which turned a misconfigured backend into
	confusing connection errors (audit point 14).
	"""
	if not provider:
		settings = get_llm_settings()
		provider = settings.llm_provider or "Ollama (Local)"
	provider = clean_provider_name(provider)
	if provider not in PROVIDERS:
		frappe.throw(f"Unknown LLM provider: {provider}. Set LLM Provider in AI Settings.")
	return PROVIDERS[provider]


def get_default_model(provider=None):
	"""Get default model for a provider (or the site's configured default)."""
	# `settings` is needed on every path: with no explicit provider it supplies
	# the provider, and the site-configured default model only applies to the
	# configured provider — an explicitly named provider falls back to its own
	# known default.
	settings = get_llm_settings()
	if not provider:
		raw_provider = settings.llm_provider or "Ollama (Local)"
		provider = clean_provider_name(raw_provider)
		return settings.default_llm_model or DEFAULT_MODELS.get(provider, "")
	# Explicit callers may pass the stored bare key ("ollama") rather than the
	# PROVIDERS key — normalize before the lookup.
	return DEFAULT_MODELS.get(clean_provider_name(provider), "")


def validate_model(provider, model):
	"""Validate model name for the given provider."""
	if not model:
		return get_default_model(provider)

	# Clean provider name if it comes from database storage
	provider = clean_provider_name(provider)

	# For Ollama local models, check allowlist
	if provider == "Ollama (Local)":
		if model in AI_ALLOWED_MODELS:
			return model
		# Allow if set in settings
		settings = get_llm_settings()
		if model in (settings.available_models or ""):
			return model
		frappe.throw(f"Model not allowed: {model}. Please configure in AI Settings.")

	return model


def ask_llm(prompt, provider=None, model=None, temperature=None, max_tokens=None, api_key=None, timeout=None):
	"""
	Send a prompt to the configured LLM provider and return the response text.

	Args:
	    prompt: The prompt to send
	    provider: Provider name (default: from AI Settings)
	    model: Model name (default: from AI Settings)
	    temperature: Temperature (default: from AI Settings)
	    max_tokens: Max tokens (default: from AI Settings)
	    api_key: API key (default: from AI Settings)
	    timeout: Request timeout in seconds (default: from AI Settings)

	Returns:
	    Response text string
	"""
	settings = get_llm_settings()

	# Use settings if not provided
	if not provider:
		raw_provider = settings.llm_provider or "Ollama (Local)"
		provider = clean_provider_name(raw_provider)
	if not model:
		model = configured_model(settings) or get_default_model(provider)
	if temperature is None:
		temperature = settings.default_temperature or 0.7
	if max_tokens is None:
		max_tokens = settings.max_tokens or 2048
	if api_key is None:
		api_key = _configured(settings, "api_key", "llm_api_key") or ""
	if timeout is None:
		timeout = settings.timeout_seconds or 120

	# Validate model
	model = validate_model(provider, model)

	# Get provider config
	config = get_provider_config(provider)
	base_url = config.get("base_url", "")

	# A custom endpoint, and a relocated LM Studio/Ollama, override the shipped
	# URL. The settings form writes `custom_api_base_url`; the runtime read only
	# `llm_base_url`, so a configured endpoint was ignored (audit point 14).
	configured_base_url = _configured(settings, "custom_api_base_url", "llm_base_url")
	if provider in ("Custom API", "LM Studio") and configured_base_url:
		base_url = configured_base_url

	# Build request based on provider type
	if config.get("type") == "anthropic":
		return _ask_anthropic(prompt, model, api_key, temperature, max_tokens, timeout, base_url)
	elif config.get("type") == "google":
		return _ask_google(prompt, model, api_key, temperature, max_tokens, timeout, base_url)
	elif provider == "Ollama (Local)" or config.get("base_url", "").endswith("/api/generate"):
		return _ask_ollama_with_retry(prompt, model, api_key, temperature, max_tokens, timeout, base_url)
	else:
		return _ask_chat_completions(
			prompt, provider, model, api_key, temperature, max_tokens, timeout, base_url, config
		)


def _ask_chat_completions(
	prompt, provider, model, api_key, temperature, max_tokens, timeout, base_url, config
):
	"""Send request to chat completions API (OpenAI format)."""
	# Build model name based on provider format
	model_format = config.get("model_format", "name")
	if model_format == "provider/model":
		# For OpenRouter, format as provider/model
		provider_map = {
			"OpenRouter": "openai",
		}
		provider_name = provider_map.get(provider, provider.lower().replace(" ", "-"))
		full_model = f"{provider_name}/{model}" if "/" not in model else model
	elif model_format == "models/name":
		full_model = f"{model}" if model.startswith("models/") else f"models/{model}"
	else:
		full_model = model

	# Prepare headers
	headers = {
		"Content-Type": "application/json",
	}

	# Add API key based on provider
	if provider == "Anthropic":
		headers["x-api-key"] = api_key
		headers["anthropic-version"] = "2023-06-01"
	elif provider == "OpenAI":
		if api_key:
			headers["Authorization"] = f"Bearer {api_key}"
		if frappe.get_single("AI Settings").openai_org_id:
			headers["OpenAI-Organization"] = frappe.get_single("AI Settings").openai_org_id
	elif provider == "Google Gemini":
		if api_key:
			headers["Authorization"] = f"Bearer {api_key}"
	else:
		if api_key:
			headers["Authorization"] = f"Bearer {api_key}"

	# Prepare payload
	payload = {
		"model": full_model,
		"messages": [{"role": "user", "content": prompt}],
		"temperature": temperature,
		"max_tokens": max_tokens,
	}

	# Make request
	response = requests.post(base_url, json=payload, headers=headers, timeout=timeout)
	response.raise_for_status()

	result = response.json()

	# Extract response text based on provider format
	if "choices" in result:
		return result["choices"][0]["message"]["content"]
	elif "content" in result:
		return result["content"][0]["text"]
	else:
		frappe.throw(f"Unexpected response format from {provider}: {result}")


def _ask_anthropic(prompt, model, api_key, temperature, max_tokens, timeout, base_url):
	"""Send request to Anthropic API."""
	headers = {
		"Content-Type": "application/json",
		"x-api-key": api_key,
		"anthropic-version": "2023-06-01",
	}

	payload = {
		"model": model,
		"messages": [{"role": "user", "content": prompt}],
		"temperature": temperature,
		"max_tokens": max_tokens,
	}

	response = requests.post(base_url, json=payload, headers=headers, timeout=timeout)
	response.raise_for_status()

	result = response.json()
	return result["content"][0]["text"]


def _ask_google(prompt, model, api_key, temperature, max_tokens, timeout, base_url):
	"""Send request to Google Gemini API."""
	# Gemini uses a different URL format
	full_url = f"{base_url}/{model}:generateContent?key={api_key}"

	payload = {
		"contents": [{"parts": [{"text": prompt}]}],
		"generationConfig": {
			"temperature": temperature,
			"maxOutputTokens": max_tokens,
		},
	}

	response = requests.post(full_url, json=payload, timeout=timeout)
	response.raise_for_status()

	result = response.json()
	return result["candidates"][0]["content"]["parts"][0]["text"]


# ---------------------------------------------------------------------------
# Ollama wrapper with retry (Phase 1.1)
# Retries on transient failures (connection refused during runtime startup,
# brief 503s from the generate queue). Caps the timeout at
# OLLAMA_TIMEOUT_CEILING so a misconfigured setting can't hang the caller.
# ---------------------------------------------------------------------------
def _ask_ollama_with_retry(prompt, model, api_key, temperature, max_tokens, timeout, base_url):
	"""Call Ollama with retry on transient failures and a timeout ceiling."""
	import time

	from requests.exceptions import ConnectionError as RequestsConnectionError

	# Clamp caller timeout to the safety ceiling.
	timeout = min(timeout, OLLAMA_TIMEOUT_CEILING)

	last_exc = None
	for attempt in range(OLLAMA_MAX_RETRIES + 1):
		try:
			return _ask_ollama(prompt, model, api_key, temperature, max_tokens, timeout, base_url)
		except (RequestsConnectionError, requests.exceptions.HTTPError) as exc:
			last_exc = exc
			if attempt < OLLAMA_MAX_RETRIES:
				time.sleep(0.5 * (attempt + 1))
			continue
	# All retries exhausted; re-raise the last error.
	if last_exc:
		raise last_exc
	# Should be unreachable, but guard anyway.
	return _ask_ollama(prompt, model, api_key, temperature, max_tokens, timeout, base_url)


def _ask_ollama(prompt, model, api_key, temperature, max_tokens, timeout, base_url):
	"""Send request to Ollama API (uses /api/generate endpoint)."""
	# Ollama uses a different format than OpenAI chat completions
	payload = {
		"model": model,
		"prompt": prompt,
		"stream": False,
	}

	# Ollama doesn't use temperature in the same way, but we can pass it
	if temperature is not None:
		payload["temperature"] = temperature

	response = requests.post(base_url, json=payload, timeout=timeout)
	response.raise_for_status()
	result = response.json()

	# Ollama returns 'response' field directly
	if "response" in result:
		return result["response"]
	else:
		frappe.throw(f"Unexpected response format from Ollama: {result}")


def ask_ollama(prompt, model=None, timeout=180, num_predict=220):
	"""Legacy function for backward compatibility - uses Ollama only."""
	return ask_llm(prompt, provider="Ollama (Local)", model=model, timeout=timeout)
