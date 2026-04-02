"""WI-032: LLM client for OpenAI-compatible API endpoints.

Supports Local API mode (Ollama, LM Studio, llama.cpp) via
/v1/chat/completions. All calls run in a background thread —
this module provides the synchronous HTTP logic only.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

DEFAULT_PROMPT = (
    "Identify ALL person-related and sensitive data in the following HL7 field value. "
    "Look for: first names, last names (surnames), full names, "
    "addresses (street, city, zip code, country), "
    "phone numbers, fax numbers, email addresses, "
    "dates of birth, dates of death, "
    "patient IDs, insurance numbers, social security numbers (SSN/AHV), "
    "doctor names, employer names, "
    "and any other personally identifiable information (PII). "
    'Return ONLY a JSON array of found entities, each with "value" and "type" keys. '
    "If nothing is found, return an empty array []. "
    "Examples: "
    '[{"value": "Müller", "type": "last_name"}, '
    '{"value": "Hans", "type": "first_name"}, '
    '{"value": "test@gmail.com", "type": "email"}, '
    '{"value": "19850315", "type": "date_of_birth"}, '
    '{"value": "Hauptstr. 1", "type": "address"}]'
)


@dataclass
class LLMConfig:
    """LLM connection settings."""
    mode: str = "none"  # "none", "local_api", "embedded"
    host: str = "http://localhost"
    port: int = 11434
    endpoint: str = "/v1/chat/completions"
    model_name: str = ""
    api_key: str = ""
    prompt_template: str = DEFAULT_PROMPT

    @property
    def base_url(self) -> str:
        return f"{self.host}:{self.port}"

    @property
    def full_url(self) -> str:
        return f"{self.base_url}{self.endpoint}"

    @property
    def is_remote(self) -> bool:
        """True if host is not localhost."""
        h = self.host.lower().replace("http://", "").replace("https://", "")
        return h not in ("localhost", "127.0.0.1", "::1")

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "host": self.host,
            "port": self.port,
            "endpoint": self.endpoint,
            "model_name": self.model_name,
            "api_key": self.api_key,
            "prompt_template": self.prompt_template,
        }

    @classmethod
    def from_dict(cls, data: dict) -> LLMConfig:
        return cls(
            mode=data.get("mode", "none"),
            host=data.get("host", "http://localhost"),
            port=data.get("port", 11434),
            endpoint=data.get("endpoint", "/v1/chat/completions"),
            model_name=data.get("model_name", ""),
            api_key=data.get("api_key", ""),
            prompt_template=data.get("prompt_template", DEFAULT_PROMPT),
        )


@dataclass
class LLMEntity:
    """A single entity found by the LLM."""
    value: str
    entity_type: str


@dataclass
class LLMResult:
    """Result of an LLM analysis call."""
    entities: list[LLMEntity]
    raw_response: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error


def test_connection(config: LLMConfig, timeout: float = 5.0) -> tuple[bool, str]:
    """Test if the LLM API is reachable.

    Returns (success, message).
    """
    if config.mode == "none":
        return False, "LLM mode is set to 'None'"

    try:
        # Try to list models (works for Ollama and OpenAI-compatible APIs)
        url = f"{config.base_url}/v1/models"
        req = urllib.request.Request(url, method="GET")
        if config.api_key:
            req.add_header("Authorization", f"Bearer {config.api_key}")

        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
            models = data.get("data", [])
            model_names = [m.get("id", "?") for m in models]

            # Validate selected model exists
            if config.model_name:
                if config.model_name in model_names:
                    return True, f"Connected. Model '{config.model_name}' available."
                # Also check with :latest suffix (Ollama convention)
                if f"{config.model_name}:latest" in model_names:
                    return True, f"Connected. Model '{config.model_name}' available."
                avail = ", ".join(model_names[:5])
                return False, f"Model '{config.model_name}' not found. Available: {avail}"

            avail = ", ".join(model_names[:5])
            return True, f"Connected. Available models: {avail}"
    except urllib.error.URLError as e:
        return False, f"Connection failed: {e.reason}"
    except Exception as e:
        return False, f"Error: {e}"


def analyze_field(config: LLMConfig, field_text: str, timeout: float = 30.0) -> LLMResult:
    """Send a single field value to the LLM for PII analysis.

    Returns an LLMResult with found entities.
    """
    if not field_text.strip():
        return LLMResult(entities=[])

    if not config.model_name:
        return LLMResult(entities=[], error="No model name configured. Set a model in Settings → LLM.")

    prompt = config.prompt_template + f"\n\nField value: {field_text}"

    body = json.dumps({
        "model": config.model_name,
        "messages": [
            {"role": "system", "content": "You are a data privacy expert analyzing HL7 healthcare messages for personal data. Respond only with valid JSON."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
        "max_tokens": 512,
    }).encode("utf-8")

    req = urllib.request.Request(
        config.full_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    if config.api_key:
        req.add_header("Authorization", f"Bearer {config.api_key}")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except urllib.error.URLError as e:
        return LLMResult(entities=[], error=f"Connection failed: {e.reason}")
    except Exception as e:
        return LLMResult(entities=[], error=str(e))

    # Extract content from OpenAI-compatible response
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        return LLMResult(entities=[], raw_response=str(data), error="Unexpected response format")

    return _parse_llm_response(content)


def _parse_llm_response(content: str) -> LLMResult:
    """Parse the LLM response JSON into entities."""
    # Strip markdown code fences if present
    text = content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        items = json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON array in the response
        start = text.find("[")
        end = text.rfind("]")
        if start >= 0 and end > start:
            try:
                items = json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                return LLMResult(entities=[], raw_response=content, error="Could not parse JSON from response")
        else:
            return LLMResult(entities=[], raw_response=content, error="No JSON array in response")

    if not isinstance(items, list):
        return LLMResult(entities=[], raw_response=content, error="Response is not a JSON array")

    entities = []
    for item in items:
        if isinstance(item, dict):
            value = item.get("value", "")
            etype = item.get("type", "unknown")
            if value:
                entities.append(LLMEntity(value=str(value), entity_type=str(etype)))

    return LLMResult(entities=entities, raw_response=content)
