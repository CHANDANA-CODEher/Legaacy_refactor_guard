"""Tests for agent/llm.py."""

from __future__ import annotations

import ast
from unittest.mock import MagicMock, patch

import pytest
import requests

from agent.llm import (
    LLMAPIError,
    MalformedResponseError,
    MissingCredentialsError,
    MockLLMProvider,
    NebiusLLMProvider,
    extract_code_from_llm_response,
    get_llm_provider,
)


class TestCodeExtraction:
    """Tests for extract_code_from_llm_response."""

    def test_extracts_from_python_code_block(self) -> None:
        raw = "Here is the refactored code:\n```python\ndef add(a, b):\n    return a + b\n```\nHope this helps!"
        extracted = extract_code_from_llm_response(raw)
        assert extracted == "def add(a, b):\n    return a + b"

    def test_extracts_from_generic_code_block(self) -> None:
        raw = "```\ndef multiply(a, b):\n    return a * b\n```"
        extracted = extract_code_from_llm_response(raw)
        assert extracted == "def multiply(a, b):\n    return a * b"

    def test_returns_raw_code_if_no_backticks(self) -> None:
        raw = "def subtract(a, b):\n    return a - b\n"
        extracted = extract_code_from_llm_response(raw)
        assert extracted == "def subtract(a, b):\n    return a - b"

    def test_empty_string(self) -> None:
        assert extract_code_from_llm_response("") == ""


class TestMockLLMProvider:
    """Tests for MockLLMProvider."""

    def test_mock_provider_identity_and_metadata(self) -> None:
        provider = MockLLMProvider()
        assert provider.name == "mock"

        res = provider.refactor("def foo(): pass", goal="Clean up foo")
        assert res.is_mock is True
        assert res.provider == "mock"
        assert res.model == "mock-deterministic-v1"
        assert "[MOCK MODE]" in res.explanation
        assert "Clean up foo" in res.explanation
        assert "Goal: Clean up foo" in res.code

    def test_mock_returns_syntactically_valid_code(self) -> None:
        provider = MockLLMProvider()
        source = "def calc(x: int) -> int:\n    return x * 2\n"
        res = provider.refactor(source, goal="Add documentation")

        # Must parse as valid Python syntax
        tree = ast.parse(res.code)
        assert tree is not None
        assert "MockLLMProvider" in res.code

    def test_mock_uses_scripted_responses_in_order(self) -> None:
        responses = [
            "def attempt_one():\n    return 1\n",
            "def attempt_two():\n    return 2\n",
        ]
        provider = MockLLMProvider(responses=responses)

        res1 = provider.refactor("code", goal="first")
        assert res1.code == "def attempt_one():\n    return 1\n"
        assert provider.call_count == 1

        res2 = provider.refactor("code", goal="second")
        assert res2.code == "def attempt_two():\n    return 2\n"
        assert provider.call_count == 2

    def test_mock_falls_back_to_default_code_when_queue_empty(self) -> None:
        provider = MockLLMProvider(
            responses=["def first(): pass\n"],
            default_code="def fallback(): pass\n",
        )
        assert provider.refactor("code", goal="g1").code == "def first(): pass\n"
        assert provider.refactor("code", goal="g2").code == "def fallback(): pass\n"


class TestNebiusLLMProviderConfiguration:
    """Tests for NebiusLLMProvider initialization and environment variable reading."""

    def test_missing_api_key_raises_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
        with pytest.raises(MissingCredentialsError) as exc_info:
            NebiusLLMProvider()
        assert "NEBIUS_API_KEY environment variable" in str(exc_info.value)

    def test_empty_api_key_raises_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NEBIUS_API_KEY", "   ")
        with pytest.raises(MissingCredentialsError):
            NebiusLLMProvider()

    def test_reads_environment_variables(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NEBIUS_API_KEY", "secret-test-key-12345")
        monkeypatch.setenv("NEBIUS_BASE_URL", "https://custom.api.nebius.ai/v1/")
        monkeypatch.setenv("NEBIUS_MODEL", "meta-llama/Custom-Model-8B")

        provider = NebiusLLMProvider(timeout=45.0)
        assert provider.api_key == "secret-test-key-12345"
        assert provider.base_url == "https://custom.api.nebius.ai/v1"
        assert provider.model == "meta-llama/Custom-Model-8B"
        assert provider.timeout == 45.0
        assert provider.name == "nebius"

    def test_explicit_arguments_override_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NEBIUS_API_KEY", "env-key")
        provider = NebiusLLMProvider(
            api_key="explicit-key",
            base_url="https://explicit.url/v1",
            model="explicit-model",
            timeout=12.0,
        )
        assert provider.api_key == "explicit-key"
        assert provider.base_url == "https://explicit.url/v1"
        assert provider.model == "explicit-model"

    def test_repr_masks_api_key_for_security(self) -> None:
        provider = NebiusLLMProvider(api_key="abcdef123456789xyz")
        rep = repr(provider)
        assert "abcdef123456789xyz" not in rep
        assert "abcd...9xyz" in rep


class TestNebiusLLMProviderRequests:
    """Tests for NebiusLLMProvider request handling, HTTP errors, and response parsing."""

    @pytest.fixture
    def nebius_provider(self) -> NebiusLLMProvider:
        return NebiusLLMProvider(
            api_key="mock-test-key-1234",
            base_url="https://mock.api.nebius.ai/v1",
            model="meta-llama/Meta-Llama-3.1-70B-Instruct",
            timeout=10.0,
        )

    def test_successful_refactoring_request(self, nebius_provider: NebiusLLMProvider) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-test",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "```python\ndef calculate(a, b):\n    return a + b\n```",
                    },
                    "finish_reason": "stop",
                }
            ],
        }

        with patch("requests.post", return_value=mock_response) as mock_post:
            result = nebius_provider.refactor(
                source_code="def calc(a, b): return a + b",
                goal="Improve readability",
                test_feedback="None",
            )

            assert result.code == "def calculate(a, b):\n    return a + b"
            assert result.is_mock is False
            assert result.provider == "nebius"
            assert result.model == "meta-llama/Meta-Llama-3.1-70B-Instruct"

            # Check that request payload had correct endpoint, headers, and model
            mock_post.assert_called_once()
            call_args, call_kwargs = mock_post.call_args
            assert call_args[0] == "https://mock.api.nebius.ai/v1/chat/completions"
            assert call_kwargs["headers"]["Authorization"] == "Bearer mock-test-key-1234"
            assert call_kwargs["json"]["model"] == "meta-llama/Meta-Llama-3.1-70B-Instruct"
            assert call_kwargs["timeout"] == 10.0

    def test_http_error_handling(self, nebius_provider: NebiusLLMProvider) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 401
        http_error = requests.exceptions.HTTPError("401 Unauthorized", response=mock_response)
        mock_response.raise_for_status.side_effect = http_error

        with patch("requests.post", return_value=mock_response):
            with pytest.raises(LLMAPIError) as exc_info:
                nebius_provider.refactor("def foo(): pass", goal="Refactor")
            assert "401" in str(exc_info.value)

    def test_timeout_handling(self, nebius_provider: NebiusLLMProvider) -> None:
        with patch("requests.post", side_effect=requests.exceptions.Timeout("Connection timed out")):
            with pytest.raises(LLMAPIError) as exc_info:
                nebius_provider.refactor("def foo(): pass", goal="Refactor")
            assert "timed out after 10.0s" in str(exc_info.value)

    def test_connection_error_handling(self, nebius_provider: NebiusLLMProvider) -> None:
        with patch("requests.post", side_effect=requests.exceptions.ConnectionError("Host unreachable")):
            with pytest.raises(LLMAPIError) as exc_info:
                nebius_provider.refactor("def foo(): pass", goal="Refactor")
            assert "network request failed" in str(exc_info.value)

    def test_malformed_json_response(self, nebius_provider: NebiusLLMProvider) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON string")

        with patch("requests.post", return_value=mock_response):
            with pytest.raises(MalformedResponseError) as exc_info:
                nebius_provider.refactor("def foo(): pass", goal="Refactor")
            assert "invalid JSON" in str(exc_info.value)

    def test_malformed_response_missing_choices(self, nebius_provider: NebiusLLMProvider) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "chatcmpl-test"}

        with patch("requests.post", return_value=mock_response):
            with pytest.raises(MalformedResponseError) as exc_info:
                nebius_provider.refactor("def foo(): pass", goal="Refactor")
            assert "missing a valid 'choices' list" in str(exc_info.value)

    def test_malformed_response_empty_choices(self, nebius_provider: NebiusLLMProvider) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": []}

        with patch("requests.post", return_value=mock_response):
            with pytest.raises(MalformedResponseError):
                nebius_provider.refactor("def foo(): pass", goal="Refactor")

    def test_malformed_response_missing_content(self, nebius_provider: NebiusLLMProvider) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {}}]
        }

        with patch("requests.post", return_value=mock_response):
            with pytest.raises(MalformedResponseError) as exc_info:
                nebius_provider.refactor("def foo(): pass", goal="Refactor")
            assert "missing 'message.content'" in str(exc_info.value)

    def test_malformed_response_empty_code(self, nebius_provider: NebiusLLMProvider) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "   "}}]
        }

        with patch("requests.post", return_value=mock_response):
            with pytest.raises(MalformedResponseError) as exc_info:
                nebius_provider.refactor("def foo(): pass", goal="Refactor")
            assert "did not contain any usable Python code" in str(exc_info.value)


class TestProviderFactory:
    """Tests for get_llm_provider factory function."""

    def test_defaults_to_mock_when_env_not_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        provider = get_llm_provider()
        assert isinstance(provider, MockLLMProvider)
        assert provider.name == "mock"

    def test_explicit_mock_type(self) -> None:
        provider = get_llm_provider("mock")
        assert isinstance(provider, MockLLMProvider)

    def test_nebius_type_instantiates(self) -> None:
        provider = get_llm_provider("nebius", api_key="test-api-key")
        assert isinstance(provider, NebiusLLMProvider)
        assert provider.name == "nebius"

    def test_unsupported_provider_raises_value_error(self) -> None:
        with pytest.raises(ValueError) as exc_info:
            get_llm_provider("unknown_provider")
        assert "Unsupported LLM provider 'unknown_provider'" in str(exc_info.value)
