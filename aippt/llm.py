"""LLM client module for Outline2PPT.

Provides a unified interface for multiple LLM providers (Anthropic, OpenAI,
Google/Gemini) with optional corporate gateway support.

Model registry and provider mappings are loaded from models.yaml via
``aippt.config``. There are no hardcoded model lists here.
"""

import base64
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

import anthropic
import openai

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

try:
    import tiktoken
    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Gateway configuration
# ---------------------------------------------------------------------------

@dataclass
class GatewayConfig:
    """Configuration for a corporate LLM API gateway.

    The gateway sits in front of multiple providers and requires a custom
    authentication header.  Provider-specific paths are appended to
    ``base_url`` when building the effective endpoint URL.

    The optional ``user_header`` / ``user_value`` fields support the
    mandatory ``user: <NTID>`` header required by the AMD LLM Gateway.
    """

    base_url: str
    auth_header: str
    auth_value: str
    provider_paths: Dict[str, str] = field(default_factory=dict)
    user_header: str = ""
    user_value: str = ""


def load_gateway_config(config_path: str) -> Optional[GatewayConfig]:
    """Load a :class:`GatewayConfig` from a YAML file.

    Returns ``None`` if the file does not exist or cannot be parsed.

    Expected YAML layout::

        gateway:
          base_url: "https://gateway.example.com"
          auth_header: "X-Api-Key"
          auth_value_env: "CORP_GATEWAY_KEY"   # read from env var
          # OR use a literal value instead of env var:
          # auth_value: "my-literal-key"
        providers:
          anthropic:
            path: "/anthropic/v1"
          openai:
            path: "/openai/v1"
          gemini:
            path: "/google/v1"
    """
    if not HAS_YAML:
        logger.warning("PyYAML is not installed; cannot load gateway config.")
        return None

    path = Path(config_path)
    if not path.exists():
        logger.debug("Gateway config file not found: %s", config_path)
        return None

    try:
        with path.open() as fh:
            data = yaml.safe_load(fh)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to parse gateway config %s: %s", config_path, exc)
        return None

    gw_section = data.get("gateway", {})
    base_url = gw_section.get("base_url", "")
    auth_header = gw_section.get("auth_header", "")

    # Resolve auth value — prefer env-var lookup, fall back to literal.
    auth_value = ""
    if "auth_value_env" in gw_section:
        env_var = gw_section["auth_value_env"]
        auth_value = os.environ.get(env_var, "")
        if not auth_value:
            logger.warning(
                "Gateway auth env var '%s' is not set or empty.", env_var
            )
    elif "auth_value" in gw_section:
        auth_value = gw_section["auth_value"]

    # Resolve user header (mandatory gateway "user: <NTID>" header).
    user_header = gw_section.get("user_header", "")
    user_value = ""
    if "user_value_env" in gw_section:
        env_var = gw_section["user_value_env"]
        user_value = os.environ.get(env_var, "")
    elif "user_value" in gw_section:
        user_value = gw_section["user_value"]

    # Build provider_paths mapping.
    provider_paths: Dict[str, str] = {}
    for provider, cfg in data.get("providers", {}).items():
        if isinstance(cfg, dict) and "path" in cfg:
            provider_paths[provider] = cfg["path"]

    return GatewayConfig(
        base_url=base_url,
        auth_header=auth_header,
        auth_value=auth_value,
        provider_paths=provider_paths,
        user_header=user_header,
        user_value=user_value,
    )


# ---------------------------------------------------------------------------
# Unified LLM client
# ---------------------------------------------------------------------------

def resolve_api_key(provider: str, api_key: Optional[str] = None) -> str:
    """Resolve API key from argument or environment variable.

    Args:
        provider: The LLM provider ('anthropic', 'openai', 'google')
        api_key: Explicit API key, or None to read from environment

    Returns:
        The resolved API key (may be empty string if not found)
    """
    if api_key:
        return api_key

    env_vars = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "google": "GOOGLE_API_KEY",
    }
    env_var = env_vars.get(provider, "OPENAI_API_KEY")
    return os.environ.get(env_var, "")


# ------------------------------------------------------------------
# Image preparation for API submission
# ------------------------------------------------------------------

_DEFAULT_MAX_IMAGE_BYTES = 4 * 1024 * 1024  # 4 MB


def _prepare_image_for_api(
    image_path: str,
    max_bytes: int = _DEFAULT_MAX_IMAGE_BYTES,
) -> tuple:
    """Return *(image_bytes, media_type)* ready for base64 encoding.

    If the raw file is larger than *max_bytes* the image is progressively
    compressed in-memory (never modifying the original file):

    1. Convert PNG → JPEG at quality 85
    2. Scale dimensions down by 50 %
    3. Reduce JPEG quality to 60
    """
    img_path = Path(image_path)
    raw_bytes = img_path.read_bytes()

    ext = img_path.suffix.lower().lstrip(".")
    media_type_map = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
    }
    media_type = media_type_map.get(ext, "image/png")

    if len(raw_bytes) <= max_bytes:
        return raw_bytes, media_type

    # --- need to shrink ---
    from io import BytesIO

    from PIL import Image

    original_mb = len(raw_bytes) / (1024 * 1024)
    img = Image.open(BytesIO(raw_bytes)).convert("RGB")

    # Step 1: save as JPEG quality=85
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85)
    if buf.tell() <= max_bytes:
        logger.info(
            "Resized image for API: %.1fMB → %.1fMB (JPEG quality=85) %s",
            original_mb, buf.tell() / (1024 * 1024), img_path.name,
        )
        return buf.getvalue(), "image/jpeg"

    # Step 2: scale down 50 % + JPEG quality=85
    w, h = img.size
    img_half = img.resize((w // 2, h // 2), Image.LANCZOS)
    buf = BytesIO()
    img_half.save(buf, format="JPEG", quality=85)
    if buf.tell() <= max_bytes:
        logger.info(
            "Resized image for API: %.1fMB → %.1fMB (50%% scale, JPEG quality=85) %s",
            original_mb, buf.tell() / (1024 * 1024), img_path.name,
        )
        return buf.getvalue(), "image/jpeg"

    # Step 3: same 50 % scale + JPEG quality=60
    buf = BytesIO()
    img_half.save(buf, format="JPEG", quality=60)
    logger.info(
        "Resized image for API: %.1fMB → %.1fMB (50%% scale, JPEG quality=60) %s",
        original_mb, buf.tell() / (1024 * 1024), img_path.name,
    )
    return buf.getvalue(), "image/jpeg"


class LLMClient:
    """Unified client interface for different LLM providers.

    Supports direct API access (using environment-variable API keys) as well
    as routing through a corporate gateway via an optional
    :class:`GatewayConfig`.
    """

    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        gateway: Optional[GatewayConfig] = None,
        image_model: str = "dall-e-3",
        user_ntid: Optional[str] = None,
    ) -> None:
        self.model = model
        self.api_base = api_base
        self.image_model = image_model

        # Look up model config from registry; raises ValueError/ConfigError if not found.
        from aippt.config import get_model_config
        self.model_config = get_model_config(model)

        # Build the effective base URL and extra headers from the gateway (if
        # provided), overriding any explicitly supplied api_base.
        extra_headers: Dict[str, str] = {}
        effective_base: Optional[str] = api_base

        if gateway is not None:
            provider_key = self.model_config.provider
            provider_path = gateway.provider_paths.get(provider_key, "")
            effective_base = gateway.base_url.rstrip("/") + provider_path
            if gateway.auth_header and gateway.auth_value:
                extra_headers[gateway.auth_header] = gateway.auth_value
            if gateway.user_header:
                ntid = user_ntid or gateway.user_value
                if ntid:
                    extra_headers[gateway.user_header] = ntid

        # Resolve API key: explicit > gateway auth > environment variable
        resolved_key = api_key
        if not resolved_key and gateway is not None:
            resolved_key = gateway.auth_value or "dummy"
        if not resolved_key:
            resolved_key = resolve_api_key(self.model_config.provider)
        self.api_key = resolved_key or ""

        # Instantiate the underlying SDK client.
        if self.model_config.provider == "anthropic":
            client_kwargs: Dict = {"api_key": self.api_key}
            if effective_base:
                client_kwargs["base_url"] = effective_base
            if extra_headers:
                client_kwargs["default_headers"] = extra_headers
            self.client = anthropic.Client(**client_kwargs)
        else:
            # OpenAI and all OpenAI-compatible providers (Google via gateway, etc.)
            client_kwargs = {"api_key": self.api_key}
            if effective_base:
                client_kwargs["base_url"] = effective_base
            if extra_headers:
                client_kwargs["default_headers"] = extra_headers
            self.client = openai.Client(**client_kwargs)

    # ------------------------------------------------------------------
    # Token counting
    # ------------------------------------------------------------------

    def get_token_count(self, text: str) -> int:
        """Return an approximate token count for *text*."""
        if self.model_config.provider == "anthropic":
            if hasattr(anthropic, "count_tokens"):
                return anthropic.count_tokens(text)
            # Rough estimate: ~4 chars per token.
            return len(text) // 4
        else:
            if HAS_TIKTOKEN:
                try:
                    if "gpt-4" in self.model:
                        enc = tiktoken.encoding_for_model("gpt-4")
                    else:
                        enc = tiktoken.encoding_for_model("gpt-3.5-turbo")
                    return len(enc.encode(text))
                except Exception:  # noqa: BLE001
                    pass
            return len(text) // 4

    # ------------------------------------------------------------------
    # Text generation
    # ------------------------------------------------------------------

    def generate_text(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful assistant.",
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> str:
        """Generate text using the configured provider."""
        try:
            if self.model_config.provider == "anthropic":
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system_prompt,
                    messages=[{"role": "user", "content": prompt}],
                )
                return response.content[0].text
            else:
                response = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                )
                return response.choices[0].message.content
        except Exception as exc:
            logger.error("Error generating text: %s", exc)
            raise

    # ------------------------------------------------------------------
    # Multimodal (vision) text generation
    # ------------------------------------------------------------------

    def generate_text_with_image(
        self,
        prompt: str,
        image_path: str,
        system_prompt: str = "You are a helpful assistant.",
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> str:
        """Generate text from a prompt combined with an image file.

        The image at *image_path* is base64-encoded and included in the
        request payload.  The media type is inferred from the file extension.

        Raises :class:`ValueError` if the configured model does not declare
        ``supports_vision = True``.
        """
        if not self.model_config.supports_vision:
            raise ValueError(
                f"Model '{self.model}' does not support vision/multimodal input."
            )

        # Read, optionally resize, and encode the image.
        if not Path(image_path).exists():
            raise FileNotFoundError(
                f"Image file not found: {image_path}"
            )

        try:
            image_bytes, media_type = _prepare_image_for_api(image_path)
            image_data = base64.b64encode(image_bytes).decode("utf-8")
        except OSError as exc:
            raise FileNotFoundError(
                f"Failed to read image file '{image_path}': {exc}"
            ) from exc

        try:
            if self.model_config.provider == "anthropic":
                content = [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data,
                        },
                    },
                    {"type": "text", "text": prompt},
                ]
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system_prompt,
                    messages=[{"role": "user", "content": content}],
                )
                return response.content[0].text
            else:
                # OpenAI / compatible
                data_url = f"data:{media_type};base64,{image_data}"
                content = [
                    {
                        "type": "image_url",
                        "image_url": {"url": data_url},
                    },
                    {"type": "text", "text": prompt},
                ]
                response = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": content},
                    ],
                )
                return response.choices[0].message.content
        except Exception as exc:
            logger.error("Error generating text with image: %s", exc)
            raise

    # ------------------------------------------------------------------
    # Image generation
    # ------------------------------------------------------------------

    def generate_image(
        self,
        prompt: str,
        size: str = "1024x1024",
        image_model: Optional[str] = None,
    ) -> str:
        """Generate an image via DALL-E or a compatible endpoint.

        Args:
            prompt: Text description of the image to generate
            size: Image dimensions (e.g., "1024x1024")
            image_model: Override the image model (defaults to self.image_model)

        Returns the URL of the generated image.

        Raises :class:`ValueError` if the model does not support image
        generation (``supports_images = True``).
        """
        if not self.model_config.supports_images:
            raise ValueError(
                f"Model '{self.model}' does not support image generation."
            )

        model_to_use = image_model or self.image_model

        try:
            response = self.client.images.generate(
                model=model_to_use,
                prompt=prompt,
                size=size,
                quality="hd",
                style="natural",
                n=1,
            )
            return response.data[0].url
        except Exception as exc:
            logger.error("Error generating image: %s", exc)
            raise
