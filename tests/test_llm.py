"""Tests for aippt.llm module."""

import base64
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from aippt.llm import (
    GatewayConfig,
    LLMClient,
    load_gateway_config,
    resolve_api_key,
)
from aippt.config import ModelConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MINIMAL_GATEWAY_YAML = """\
gateway:
  base_url: "https://gateway.example.com"
  auth_header: "X-Api-Key"
  auth_value: "test-secret"
providers:
  anthropic:
    path: "/anthropic/v1"
  openai:
    path: "/openai/v1"
  gemini:
    path: "/google/v1"
"""

GATEWAY_YAML_ENV_AUTH = """\
gateway:
  base_url: "https://gateway.example.com"
  auth_header: "X-Api-Key"
  auth_value_env: "CORP_GATEWAY_KEY"
providers:
  anthropic:
    path: "/anthropic/v1"
"""

GATEWAY_YAML_USER_HEADER = """\
gateway:
  base_url: "https://gateway.example.com"
  auth_header: "X-Api-Key"
  auth_value: "test-secret"
  user_header: "user"
  user_value_env: "AIPPT_USER_NTID"
providers:
  anthropic:
    path: "/anthropic/v1"
  openai:
    path: "/openai/v1"
"""

GATEWAY_YAML_USER_LITERAL = """\
gateway:
  base_url: "https://gateway.example.com"
  auth_header: "X-Api-Key"
  auth_value: "test-secret"
  user_header: "user"
  user_value: "literal-ntid"
providers:
  openai:
    path: "/openai/v1"
"""


def _write_tmp_yaml(content: str) -> str:
    """Write *content* to a temporary file and return its path."""
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False
    )
    tmp.write(content)
    tmp.close()
    return tmp.name


# ---------------------------------------------------------------------------
# TestGatewayConfig
# ---------------------------------------------------------------------------

class TestGatewayConfig:
    def test_load_missing_file_returns_none(self):
        result = load_gateway_config("/nonexistent/path/gateway.yaml")
        assert result is None

    def test_load_valid_config(self):
        path = _write_tmp_yaml(MINIMAL_GATEWAY_YAML)
        try:
            cfg = load_gateway_config(path)
            assert cfg is not None
            assert cfg.base_url == "https://gateway.example.com"
            assert cfg.auth_header == "X-Api-Key"
            assert cfg.auth_value == "test-secret"
            assert cfg.provider_paths["anthropic"] == "/anthropic/v1"
            assert cfg.provider_paths["openai"] == "/openai/v1"
            assert cfg.provider_paths["gemini"] == "/google/v1"
        finally:
            os.unlink(path)

    def test_load_config_reads_env_var_for_auth(self):
        path = _write_tmp_yaml(GATEWAY_YAML_ENV_AUTH)
        try:
            with patch.dict(os.environ, {"CORP_GATEWAY_KEY": "env-secret"}):
                cfg = load_gateway_config(path)
            assert cfg is not None
            assert cfg.auth_value == "env-secret"
        finally:
            os.unlink(path)

    def test_load_config_missing_env_var_gives_empty_auth(self):
        path = _write_tmp_yaml(GATEWAY_YAML_ENV_AUTH)
        try:
            env = {k: v for k, v in os.environ.items() if k != "CORP_GATEWAY_KEY"}
            with patch.dict(os.environ, env, clear=True):
                cfg = load_gateway_config(path)
            assert cfg is not None
            assert cfg.auth_value == ""
        finally:
            os.unlink(path)

    def test_load_invalid_yaml_returns_none(self):
        path = _write_tmp_yaml("{ unclosed: [bracket")
        try:
            result = load_gateway_config(path)
            assert result is None
        finally:
            os.unlink(path)

    def test_gateway_config_dataclass_fields(self):
        cfg = GatewayConfig(
            base_url="https://gw.example.com",
            auth_header="Authorization",
            auth_value="Bearer tok",
            provider_paths={"openai": "/v1"},
        )
        assert cfg.base_url == "https://gw.example.com"
        assert cfg.provider_paths["openai"] == "/v1"

    def test_load_config_with_user_header_env(self):
        path = _write_tmp_yaml(GATEWAY_YAML_USER_HEADER)
        try:
            with patch.dict(os.environ, {"AIPPT_USER_NTID": "melliott"}):
                cfg = load_gateway_config(path)
            assert cfg is not None
            assert cfg.user_header == "user"
            assert cfg.user_value == "melliott"
        finally:
            os.unlink(path)

    def test_load_config_with_user_value_literal(self):
        path = _write_tmp_yaml(GATEWAY_YAML_USER_LITERAL)
        try:
            cfg = load_gateway_config(path)
            assert cfg is not None
            assert cfg.user_header == "user"
            assert cfg.user_value == "literal-ntid"
        finally:
            os.unlink(path)

    def test_load_config_user_header_missing_env_gives_empty(self):
        path = _write_tmp_yaml(GATEWAY_YAML_USER_HEADER)
        try:
            env = {k: v for k, v in os.environ.items() if k != "AIPPT_USER_NTID"}
            with patch.dict(os.environ, env, clear=True):
                cfg = load_gateway_config(path)
            assert cfg is not None
            assert cfg.user_header == "user"
            assert cfg.user_value == ""
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# TestResolveApiKey
# ---------------------------------------------------------------------------

class TestResolveApiKey:
    def test_explicit_key_returned(self):
        result = resolve_api_key("openai", api_key="explicit-key")
        assert result == "explicit-key"

    def test_anthropic_env_var(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "anth-key"}):
            result = resolve_api_key("anthropic")
            assert result == "anth-key"

    def test_openai_env_var(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "oai-key"}):
            result = resolve_api_key("openai")
            assert result == "oai-key"

    def test_missing_env_var_returns_empty(self):
        env = {k: v for k, v in os.environ.items() if k not in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY")}
        with patch.dict(os.environ, env, clear=True):
            result = resolve_api_key("openai")
            assert result == ""


# ---------------------------------------------------------------------------
# TestLLMClientInit
# ---------------------------------------------------------------------------

class TestLLMClientInit:
    @patch("aippt.llm.anthropic.Client")
    def test_anthropic_client_created_for_claude_model(self, mock_client_cls, models_yaml):
        mock_client_cls.return_value = MagicMock()
        client = LLMClient(model="claude-3.5-sonnet", api_key="test-key")
        mock_client_cls.assert_called_once()
        call_kwargs = mock_client_cls.call_args.kwargs
        assert call_kwargs["api_key"] == "test-key"
        assert client.model_config.provider == "anthropic"

    @patch("aippt.llm.openai.Client")
    def test_openai_client_created_for_gpt_model(self, mock_client_cls, models_yaml):
        mock_client_cls.return_value = MagicMock()
        client = LLMClient(model="gpt-4o", api_key="test-key")
        mock_client_cls.assert_called_once()
        call_kwargs = mock_client_cls.call_args.kwargs
        assert call_kwargs["api_key"] == "test-key"
        assert client.model_config.provider == "openai"

    @patch("aippt.llm.openai.Client")
    def test_api_key_resolved_from_env(self, mock_client_cls, models_yaml):
        mock_client_cls.return_value = MagicMock()
        with patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"}):
            client = LLMClient(model="gpt-4o")  # No explicit api_key
        call_kwargs = mock_client_cls.call_args.kwargs
        assert call_kwargs["api_key"] == "env-key"

    @patch("aippt.llm.openai.Client")
    def test_api_base_passed_to_openai_client(self, mock_client_cls, models_yaml):
        mock_client_cls.return_value = MagicMock()
        LLMClient(
            model="gpt-4o",
            api_key="test-key",
            api_base="https://custom.endpoint.com/v1",
        )
        call_kwargs = mock_client_cls.call_args.kwargs
        assert call_kwargs["base_url"] == "https://custom.endpoint.com/v1"

    @patch("aippt.llm.anthropic.Client")
    def test_gateway_sets_base_url_and_headers_for_anthropic(self, mock_client_cls, models_yaml):
        mock_client_cls.return_value = MagicMock()
        gateway = GatewayConfig(
            base_url="https://gateway.example.com",
            auth_header="X-Api-Key",
            auth_value="gw-secret",
            provider_paths={"anthropic": "/anthropic/v1"},
        )
        LLMClient(model="claude-3.5-sonnet", gateway=gateway)
        call_kwargs = mock_client_cls.call_args.kwargs
        assert call_kwargs["base_url"] == "https://gateway.example.com/anthropic/v1"
        assert call_kwargs["default_headers"]["X-Api-Key"] == "gw-secret"

    @patch("aippt.llm.openai.Client")
    def test_gateway_sets_base_url_and_headers_for_openai(self, mock_client_cls, models_yaml):
        mock_client_cls.return_value = MagicMock()
        gateway = GatewayConfig(
            base_url="https://gateway.example.com",
            auth_header="X-Api-Key",
            auth_value="gw-secret",
            provider_paths={"openai": "/openai/v1"},
        )
        LLMClient(model="gpt-4o", gateway=gateway)
        call_kwargs = mock_client_cls.call_args.kwargs
        assert call_kwargs["base_url"] == "https://gateway.example.com/openai/v1"
        assert call_kwargs["default_headers"]["X-Api-Key"] == "gw-secret"

    @patch("aippt.llm.openai.Client")
    def test_gateway_overrides_explicit_api_base(self, mock_client_cls, models_yaml):
        mock_client_cls.return_value = MagicMock()
        gateway = GatewayConfig(
            base_url="https://gateway.example.com",
            auth_header="X-Api-Key",
            auth_value="gw-secret",
            provider_paths={"openai": "/openai/v1"},
        )
        LLMClient(
            model="gpt-4o",
            api_base="https://ignored.endpoint.com/v1",
            gateway=gateway,
        )
        call_kwargs = mock_client_cls.call_args.kwargs
        # Gateway takes precedence.
        assert call_kwargs["base_url"] == "https://gateway.example.com/openai/v1"

    def test_unknown_model_raises_value_error(self, models_yaml):
        """LLMClient raises ValueError for models not in the registry."""
        with pytest.raises(ValueError, match="not in the registry"):
            LLMClient(model="nonexistent-model", api_key="key")

    def test_missing_models_yaml_raises_config_error(self):
        """LLMClient raises ConfigError when models.yaml is missing (no fixture)."""
        from aippt.config import ConfigError
        # patch_default_config_path autouse fixture points to a nonexistent file
        with pytest.raises(ConfigError, match="not found"):
            LLMClient(model="gpt-4o", api_key="key")

    @patch("aippt.llm.openai.Client")
    def test_custom_image_model(self, mock_client_cls, models_yaml):
        mock_client_cls.return_value = MagicMock()
        client = LLMClient(model="gpt-4o", api_key="key", image_model="dall-e-2")
        assert client.image_model == "dall-e-2"

    @patch("aippt.llm.anthropic.Client")
    def test_gateway_sends_user_header(self, mock_client_cls, models_yaml):
        mock_client_cls.return_value = MagicMock()
        gateway = GatewayConfig(
            base_url="https://gateway.example.com",
            auth_header="X-Api-Key",
            auth_value="gw-secret",
            provider_paths={"anthropic": "/anthropic/v1"},
            user_header="user",
            user_value="melliott",
        )
        LLMClient(model="claude-3.5-sonnet", gateway=gateway)
        call_kwargs = mock_client_cls.call_args.kwargs
        assert call_kwargs["default_headers"]["user"] == "melliott"
        assert call_kwargs["default_headers"]["X-Api-Key"] == "gw-secret"

    @patch("aippt.llm.anthropic.Client")
    def test_user_ntid_overrides_gateway_value(self, mock_client_cls, models_yaml):
        mock_client_cls.return_value = MagicMock()
        gateway = GatewayConfig(
            base_url="https://gateway.example.com",
            auth_header="X-Api-Key",
            auth_value="gw-secret",
            provider_paths={"anthropic": "/anthropic/v1"},
            user_header="user",
            user_value="default-ntid",
        )
        LLMClient(model="claude-3.5-sonnet", gateway=gateway, user_ntid="override-ntid")
        call_kwargs = mock_client_cls.call_args.kwargs
        assert call_kwargs["default_headers"]["user"] == "override-ntid"

    @patch("aippt.llm.openai.Client")
    def test_no_user_header_when_not_configured(self, mock_client_cls, models_yaml):
        mock_client_cls.return_value = MagicMock()
        gateway = GatewayConfig(
            base_url="https://gateway.example.com",
            auth_header="X-Api-Key",
            auth_value="gw-secret",
            provider_paths={"openai": "/openai/v1"},
        )
        LLMClient(model="gpt-4o", gateway=gateway)
        call_kwargs = mock_client_cls.call_args.kwargs
        assert "user" not in call_kwargs.get("default_headers", {})


# ---------------------------------------------------------------------------
# TestGenerateText
# ---------------------------------------------------------------------------

class TestGenerateText:
    @patch("aippt.llm.anthropic.Client")
    def test_generate_text_anthropic(self, mock_client_cls, models_yaml):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Hello from Claude")]
        mock_client.messages.create.return_value = mock_response

        llm = LLMClient(model="claude-3.5-sonnet", api_key="key")
        result = llm.generate_text("Say hello")

        assert result == "Hello from Claude"
        mock_client.messages.create.assert_called_once()

    @patch("aippt.llm.openai.Client")
    def test_generate_text_openai(self, mock_client_cls, models_yaml):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Hello from GPT"
        mock_client.chat.completions.create.return_value = mock_response

        llm = LLMClient(model="gpt-4o", api_key="key")
        result = llm.generate_text("Say hello")

        assert result == "Hello from GPT"
        mock_client.chat.completions.create.assert_called_once()

    @patch("aippt.llm.anthropic.Client")
    def test_generate_text_passes_system_prompt(self, mock_client_cls, models_yaml):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="ok")]
        mock_client.messages.create.return_value = mock_response

        llm = LLMClient(model="claude-3.5-sonnet", api_key="key")
        llm.generate_text("prompt", system_prompt="Be concise.")

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["system"] == "Be concise."

    @patch("aippt.llm.anthropic.Client")
    def test_generate_text_raises_on_api_error(self, mock_client_cls, models_yaml):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.messages.create.side_effect = RuntimeError("API down")

        llm = LLMClient(model="claude-3.5-sonnet", api_key="key")
        with pytest.raises(RuntimeError, match="API down"):
            llm.generate_text("prompt")

    @patch("aippt.llm.openai.Client")
    def test_openai_retries_with_max_completion_tokens_on_max_tokens_rejection(
        self, mock_client_cls, models_yaml,
    ):
        """Newer OpenAI / Azure OpenAI models reject ``max_tokens`` and
        require ``max_completion_tokens`` (introduced with o1; required on
        gpt-4o-2024-12-01+). When the API returns that specific 400, the
        client must retry once with the new field name instead of bubbling
        the error up — otherwise every gateway-routed call to a current
        model fails."""
        from openai import BadRequestError
        import httpx
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "fallback worked"
        # First call fails with the canonical Azure OpenAI error; second
        # call (with max_completion_tokens) succeeds.
        request = httpx.Request("POST", "https://example.invalid/v1/chat")
        response = httpx.Response(400, request=request)
        err = BadRequestError(
            message=("Unsupported parameter: 'max_tokens' is not supported "
                     "with this model. Use 'max_completion_tokens' instead."),
            response=response,
            body={"error": {"code": "unsupported_parameter",
                            "param": "max_tokens"}},
        )
        mock_client.chat.completions.create.side_effect = [err, mock_response]

        llm = LLMClient(model="gpt-4o", api_key="key")
        result = llm.generate_text("hello", max_tokens=42)

        assert result == "fallback worked"
        assert mock_client.chat.completions.create.call_count == 2
        # First attempt used max_tokens, second used max_completion_tokens
        first = mock_client.chat.completions.create.call_args_list[0].kwargs
        second = mock_client.chat.completions.create.call_args_list[1].kwargs
        assert first.get("max_tokens") == 42
        assert "max_completion_tokens" not in first
        assert second.get("max_completion_tokens") == 42
        assert "max_tokens" not in second

    @patch("aippt.llm.openai.Client")
    def test_openai_does_not_retry_on_unrelated_400(
        self, mock_client_cls, models_yaml,
    ):
        """Only the max_tokens/max_completion_tokens swap should trigger the
        retry. Other 400s (invalid model, rate limit, etc.) must propagate
        immediately."""
        from openai import BadRequestError
        import httpx
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        request = httpx.Request("POST", "https://example.invalid/v1/chat")
        response = httpx.Response(400, request=request)
        err = BadRequestError(
            message="Model 'gpt-9000' not found",
            response=response,
            body={"error": {"code": "model_not_found"}},
        )
        mock_client.chat.completions.create.side_effect = err

        llm = LLMClient(model="gpt-4o", api_key="key")
        with pytest.raises(BadRequestError):
            llm.generate_text("hello")
        # Must NOT have retried
        assert mock_client.chat.completions.create.call_count == 1


# ---------------------------------------------------------------------------
# TestGenerateTextWithImage
# ---------------------------------------------------------------------------

class TestGenerateTextWithImage:
    def _make_png(self) -> str:
        """Write a minimal 1x1 PNG to a temp file and return its path."""
        # Minimal valid PNG bytes (1x1 white pixel).
        png_bytes = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8"
            "z8BQDwADhQGAWjR9awAAAABJRU5ErkJggg=="
        )
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.write(png_bytes)
        tmp.close()
        return tmp.name

    @patch("aippt.llm.anthropic.Client")
    def test_anthropic_vision_request_structure(self, mock_client_cls, models_yaml):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="I see an image")]
        mock_client.messages.create.return_value = mock_response

        img_path = self._make_png()
        try:
            llm = LLMClient(model="claude-3.5-sonnet", api_key="key")
            result = llm.generate_text_with_image("Describe this", img_path)

            assert result == "I see an image"
            call_kwargs = mock_client.messages.create.call_args.kwargs
            messages = call_kwargs["messages"]
            assert len(messages) == 1
            content = messages[0]["content"]
            # Expect image block then text block.
            image_block = content[0]
            assert image_block["type"] == "image"
            assert image_block["source"]["type"] == "base64"
            assert image_block["source"]["media_type"] == "image/png"
            text_block = content[1]
            assert text_block["type"] == "text"
            assert text_block["text"] == "Describe this"
        finally:
            os.unlink(img_path)

    @patch("aippt.llm.openai.Client")
    def test_openai_vision_request_structure(self, mock_client_cls, models_yaml):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "I see an image"
        mock_client.chat.completions.create.return_value = mock_response

        img_path = self._make_png()
        try:
            llm = LLMClient(model="gpt-4o", api_key="key")
            result = llm.generate_text_with_image("Describe this", img_path)

            assert result == "I see an image"
            call_kwargs = mock_client.chat.completions.create.call_args.kwargs
            user_message = call_kwargs["messages"][1]
            content = user_message["content"]
            image_block = content[0]
            assert image_block["type"] == "image_url"
            assert image_block["image_url"]["url"].startswith("data:image/png;base64,")
            text_block = content[1]
            assert text_block["type"] == "text"
        finally:
            os.unlink(img_path)

    @patch("aippt.llm.openai.Client")
    def test_raises_value_error_for_non_vision_model(self, mock_client_cls, models_yaml):
        mock_client_cls.return_value = MagicMock()
        llm = LLMClient(model="gpt-4o", api_key="key")
        # Manually override config to simulate a non-vision model.
        llm.model_config = ModelConfig("gpt-4o", "openai", 128000, 128000, supports_vision=False)

        with pytest.raises(ValueError, match="does not support vision"):
            llm.generate_text_with_image("prompt", "/some/image.png")

    @patch("aippt.llm.openai.Client")
    def test_raises_file_not_found_for_missing_image(self, mock_client_cls, models_yaml):
        mock_client_cls.return_value = MagicMock()
        llm = LLMClient(model="gpt-4o", api_key="key")

        with pytest.raises(FileNotFoundError, match="Image file not found"):
            llm.generate_text_with_image("prompt", "/nonexistent/image.png")

    @patch("aippt.llm._prepare_image_for_api")
    @patch("aippt.llm.anthropic.Client")
    def test_uses_prepare_image_for_api(self, mock_client_cls, mock_prepare, models_yaml):
        """generate_text_with_image routes through _prepare_image_for_api."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="ok")]
        mock_client.messages.create.return_value = mock_response

        # Mock _prepare_image_for_api to return fake bytes
        fake_bytes = b"\x89PNG\r\n\x1a\n"
        mock_prepare.return_value = (fake_bytes, "image/png")

        img_path = self._make_png()
        try:
            llm = LLMClient(model="claude-3.5-sonnet", api_key="key")
            llm.generate_text_with_image("Describe this", img_path)

            mock_prepare.assert_called_once_with(img_path)
            # Verify the base64 data sent to the API matches our fake bytes
            call_kwargs = mock_client.messages.create.call_args.kwargs
            content = call_kwargs["messages"][0]["content"]
            image_block = content[0]
            sent_data = base64.b64decode(image_block["source"]["data"])
            assert sent_data == fake_bytes
            assert image_block["source"]["media_type"] == "image/png"
        finally:
            os.unlink(img_path)


# ---------------------------------------------------------------------------
# TestGenerateImage
# ---------------------------------------------------------------------------

class TestGenerateImage:
    @patch("aippt.llm.openai.Client")
    def test_generate_image_returns_url(self, mock_client_cls, models_yaml):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.data[0].url = "https://example.com/image.png"
        mock_client.images.generate.return_value = mock_response

        llm = LLMClient(model="gpt-4o", api_key="key")
        url = llm.generate_image("A beautiful sunset")

        assert url == "https://example.com/image.png"
        mock_client.images.generate.assert_called_once()

    @patch("aippt.llm.openai.Client")
    def test_generate_image_uses_configured_model(self, mock_client_cls, models_yaml):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.data[0].url = "https://example.com/image.png"
        mock_client.images.generate.return_value = mock_response

        llm = LLMClient(model="gpt-4o", api_key="key", image_model="dall-e-2")
        llm.generate_image("A sunset")

        call_kwargs = mock_client.images.generate.call_args.kwargs
        assert call_kwargs["model"] == "dall-e-2"

    @patch("aippt.llm.openai.Client")
    def test_generate_image_override_model(self, mock_client_cls, models_yaml):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.data[0].url = "https://example.com/image.png"
        mock_client.images.generate.return_value = mock_response

        llm = LLMClient(model="gpt-4o", api_key="key", image_model="dall-e-3")
        llm.generate_image("A sunset", image_model="dall-e-2")

        call_kwargs = mock_client.images.generate.call_args.kwargs
        assert call_kwargs["model"] == "dall-e-2"

    @patch("aippt.llm.openai.Client")
    def test_generate_image_raises_for_non_image_model(self, mock_client_cls, models_yaml):
        mock_client_cls.return_value = MagicMock()
        llm = LLMClient(model="gpt-4o", api_key="key")
        # Patch to non-image-generating config.
        llm.model_config = ModelConfig("gpt-4o", "openai", 128000, 128000,
                                       supports_vision=True, supports_images=False)

        with pytest.raises(ValueError, match="does not support image generation"):
            llm.generate_image("A sunset")


# ---------------------------------------------------------------------------
# TestGetTokenCount
# ---------------------------------------------------------------------------

class TestGetTokenCount:
    @patch("aippt.llm.anthropic.Client")
    def test_anthropic_fallback_estimate(self, mock_client_cls, models_yaml):
        mock_client_cls.return_value = MagicMock()
        llm = LLMClient(model="claude-3.5-sonnet", api_key="key")
        text = "a" * 400  # 400 chars -> ~100 tokens estimate
        count = llm.get_token_count(text)
        assert count == 100

    @patch("aippt.llm.openai.Client")
    def test_openai_fallback_estimate(self, mock_client_cls, models_yaml):
        mock_client_cls.return_value = MagicMock()
        llm = LLMClient(model="gpt-4o", api_key="key")
        text = "b" * 800  # 800 chars -> ~200 tokens estimate
        count = llm.get_token_count(text)
        # With or without tiktoken the result should be reasonable.
        assert count > 0


# ---------------------------------------------------------------------------
# TestPrepareImageForApi
# ---------------------------------------------------------------------------

class TestPrepareImageForApi:
    """Tests for _prepare_image_for_api() which resizes oversized images."""

    def _make_large_png(self, width=2000, height=1500) -> str:
        """Create a large PNG image that exceeds a small size threshold."""
        from PIL import Image
        img = Image.new("RGB", (width, height), color=(100, 150, 200))
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        img.save(tmp.name, format="PNG")
        tmp.close()
        return tmp.name

    def _make_small_png(self) -> str:
        """Create a tiny PNG that should never need resizing."""
        from PIL import Image
        img = Image.new("RGB", (10, 10), color=(255, 0, 0))
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        img.save(tmp.name, format="PNG")
        tmp.close()
        return tmp.name

    def test_small_image_returned_unchanged(self):
        """Images under the threshold are returned as-is."""
        from aippt.llm import _prepare_image_for_api

        img_path = self._make_small_png()
        try:
            original_size = os.path.getsize(img_path)
            image_bytes, media_type = _prepare_image_for_api(img_path, max_bytes=4 * 1024 * 1024)
            assert media_type == "image/png"
            assert len(image_bytes) == original_size
        finally:
            os.unlink(img_path)

    def test_oversized_png_is_converted_to_jpeg(self):
        """A PNG exceeding max_bytes is converted to JPEG."""
        from aippt.llm import _prepare_image_for_api

        img_path = self._make_large_png(3000, 2000)
        try:
            original_size = os.path.getsize(img_path)
            # Use a threshold just under the PNG size to force conversion
            image_bytes, media_type = _prepare_image_for_api(
                img_path, max_bytes=original_size - 1
            )
            assert media_type == "image/jpeg"
            # Verify the output is valid JPEG (starts with JFIF magic bytes)
            assert image_bytes[:2] == b"\xff\xd8"
        finally:
            os.unlink(img_path)

    def test_returns_bytes_and_media_type(self):
        """Return value is (bytes, media_type_string)."""
        from aippt.llm import _prepare_image_for_api

        img_path = self._make_small_png()
        try:
            result = _prepare_image_for_api(img_path)
            assert isinstance(result, tuple)
            assert len(result) == 2
            image_bytes, media_type = result
            assert isinstance(image_bytes, bytes)
            assert isinstance(media_type, str)
            assert media_type.startswith("image/")
        finally:
            os.unlink(img_path)

    def test_original_file_not_modified(self):
        """The original file on disk must never be changed."""
        from aippt.llm import _prepare_image_for_api

        img_path = self._make_large_png(3000, 2000)
        try:
            original_size = os.path.getsize(img_path)
            with open(img_path, "rb") as f:
                original_bytes = f.read()

            _prepare_image_for_api(img_path, max_bytes=1024)

            assert os.path.getsize(img_path) == original_size
            with open(img_path, "rb") as f:
                assert f.read() == original_bytes
        finally:
            os.unlink(img_path)

    def test_jpeg_input_quality_reduced(self):
        """A JPEG over the threshold gets quality-reduced without format change."""
        from PIL import Image
        from aippt.llm import _prepare_image_for_api

        # Create a large JPEG
        img = Image.new("RGB", (3000, 2000), color=(100, 150, 200))
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        img.save(tmp.name, format="JPEG", quality=95)
        tmp.close()

        try:
            original_size = os.path.getsize(tmp.name)
            image_bytes, media_type = _prepare_image_for_api(tmp.name, max_bytes=1024)
            assert media_type == "image/jpeg"
            assert len(image_bytes) < original_size
        finally:
            os.unlink(tmp.name)
