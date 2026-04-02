"""Tests for LLM client module (WI-032)."""

from src.engine.llm_client import (
    LLMConfig,
    LLMResult,
    _parse_llm_response,
)


class TestLLMConfig:
    def test_defaults(self):
        cfg = LLMConfig()
        assert cfg.mode == "none"
        assert cfg.host == "http://localhost"
        assert cfg.port == 11434
        assert not cfg.is_remote

    def test_is_remote_localhost(self):
        cfg = LLMConfig(host="http://localhost")
        assert not cfg.is_remote

    def test_is_remote_127(self):
        cfg = LLMConfig(host="http://127.0.0.1")
        assert not cfg.is_remote

    def test_is_remote_true(self):
        cfg = LLMConfig(host="https://api.example.com")
        assert cfg.is_remote

    def test_roundtrip_dict(self):
        cfg = LLMConfig(mode="local_api", host="http://myhost", port=8080, model_name="llama3")
        d = cfg.to_dict()
        cfg2 = LLMConfig.from_dict(d)
        assert cfg2.mode == "local_api"
        assert cfg2.host == "http://myhost"
        assert cfg2.port == 8080
        assert cfg2.model_name == "llama3"

    def test_full_url(self):
        cfg = LLMConfig(host="http://localhost", port=11434)
        assert cfg.full_url == "http://localhost:11434/v1/chat/completions"


class TestParseLLMResponse:
    def test_valid_json_array(self):
        content = '[{"value": "Müller", "type": "name"}, {"value": "19850315", "type": "dob"}]'
        result = _parse_llm_response(content)
        assert result.ok
        assert len(result.entities) == 2
        assert result.entities[0].value == "Müller"
        assert result.entities[0].entity_type == "name"

    def test_empty_array(self):
        result = _parse_llm_response("[]")
        assert result.ok
        assert len(result.entities) == 0

    def test_markdown_code_fence(self):
        content = '```json\n[{"value": "Hans", "type": "name"}]\n```'
        result = _parse_llm_response(content)
        assert result.ok
        assert len(result.entities) == 1
        assert result.entities[0].value == "Hans"

    def test_json_with_surrounding_text(self):
        content = 'Here are the entities: [{"value": "Zürich", "type": "city"}] found.'
        result = _parse_llm_response(content)
        assert result.ok
        assert result.entities[0].value == "Zürich"

    def test_invalid_json(self):
        result = _parse_llm_response("this is not json at all")
        assert not result.ok
        assert "No JSON array" in result.error

    def test_not_array(self):
        result = _parse_llm_response('{"value": "test"}')
        assert not result.ok

    def test_skips_empty_values(self):
        content = '[{"value": "", "type": "name"}, {"value": "Hans", "type": "name"}]'
        result = _parse_llm_response(content)
        assert len(result.entities) == 1
