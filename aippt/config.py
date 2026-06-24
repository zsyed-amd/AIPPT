"""Model configuration management for Outline2PPT.

Loads model registry and per-operation defaults from ``models.yaml``.
If ``models.yaml`` is missing or invalid, raises ``ConfigError`` immediately.
There are no built-in fallbacks or guessed values.
"""

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

VALID_OPERATIONS = {"enhance", "feedback", "notes", "tags", "image", "improve", "reverse"}
VALID_PROVIDERS = {"anthropic", "openai", "google"}

# Default config file path (project root, alongside gateway.yaml).
DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models.yaml")
EXAMPLE_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models.yaml.example")


class ConfigError(Exception):
    """Raised when models.yaml is missing, invalid, or fails validation."""


@dataclass
class ModelConfig:
    """Capabilities and metadata for a single model."""
    name: str
    provider: str
    max_tokens: int
    max_input_tokens: int
    supports_vision: bool = False
    supports_images: bool = False


def load_model_config(config_path: Optional[str] = None) -> Dict:
    """Load model registry and defaults from models.yaml.

    Returns a dict with:
      ``registry``  -- dict of model name -> ModelConfig
      ``defaults``  -- dict of operation -> model name
      ``source``    -- path to the loaded file

    Raises:
      ConfigError  -- if file is missing, unparseable, or fails validation
    """
    if not HAS_YAML:
        raise ConfigError(
            "PyYAML is not installed. Install it with: pip install pyyaml"
        )

    path = config_path or DEFAULT_CONFIG_PATH
    p = Path(path)

    if not p.exists():
        raise ConfigError(
            f"models.yaml not found at '{path}'.\n"
            "Run 'aippt models init' to create it from models.yaml.example."
        )

    try:
        with p.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except Exception as exc:
        raise ConfigError(f"Failed to parse {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError(f"{path} is not a valid YAML mapping.")

    # --- Validate registry ---
    if "registry" not in data:
        raise ConfigError(f"{path} is missing the 'registry' key.")

    raw_registry = data["registry"]
    if not isinstance(raw_registry, dict) or not raw_registry:
        raise ConfigError(f"{path} 'registry' must be a non-empty mapping.")

    registry: Dict[str, ModelConfig] = {}
    for model_name, entry in raw_registry.items():
        if not isinstance(entry, dict):
            raise ConfigError(
                f"{path}: registry entry '{model_name}' must be a mapping."
            )
        # Required fields
        for field in ("provider", "max_tokens", "max_input_tokens"):
            if field not in entry:
                raise ConfigError(
                    f"{path}: registry entry '{model_name}' is missing required field '{field}'."
                )
        provider = entry["provider"]
        if provider not in VALID_PROVIDERS:
            raise ConfigError(
                f"{path}: registry entry '{model_name}' has invalid provider '{provider}'. "
                f"Must be one of: {', '.join(sorted(VALID_PROVIDERS))}."
            )
        if not isinstance(entry["max_tokens"], int):
            raise ConfigError(
                f"{path}: registry entry '{model_name}' field 'max_tokens' must be an integer."
            )
        if not isinstance(entry["max_input_tokens"], int):
            raise ConfigError(
                f"{path}: registry entry '{model_name}' field 'max_input_tokens' must be an integer."
            )
        registry[model_name] = ModelConfig(
            name=model_name,
            provider=provider,
            max_tokens=entry["max_tokens"],
            max_input_tokens=entry["max_input_tokens"],
            supports_vision=bool(entry.get("supports_vision", False)),
            supports_images=bool(entry.get("supports_images", False)),
        )

    # --- Validate defaults ---
    if "defaults" not in data:
        raise ConfigError(f"{path} is missing the 'defaults' key.")

    raw_defaults = data["defaults"]
    if not isinstance(raw_defaults, dict):
        raise ConfigError(f"{path} 'defaults' must be a mapping.")

    # Operations that must be present in every models.yaml
    required_ops = VALID_OPERATIONS - {"improve", "reverse"}
    for op in required_ops:
        if op not in raw_defaults:
            raise ConfigError(
                f"{path} 'defaults' is missing required operation '{op}'. "
                f"All of these must be present: {', '.join(sorted(required_ops))}."
            )
        model_name = raw_defaults[op]
        if not isinstance(model_name, str) or not model_name:
            raise ConfigError(
                f"{path} 'defaults.{op}' must be a non-empty string."
            )
        if model_name not in registry:
            raise ConfigError(
                f"{path} 'defaults.{op}' references '{model_name}' which is not in the registry. "
                "Add it to the 'registry' section first."
            )

    # Optional operations — validate if present, skip if absent
    for op in VALID_OPERATIONS - required_ops:
        if op in raw_defaults:
            model_name = raw_defaults[op]
            if not isinstance(model_name, str) or not model_name:
                raise ConfigError(
                    f"{path} 'defaults.{op}' must be a non-empty string."
                )
            if model_name not in registry:
                raise ConfigError(
                    f"{path} 'defaults.{op}' references '{model_name}' which is not in the registry. "
                    "Add it to the 'registry' section first."
                )

    defaults: Dict[str, str] = {op: raw_defaults[op] for op in VALID_OPERATIONS if op in raw_defaults}

    return {"registry": registry, "defaults": defaults, "source": str(p)}


def get_model_registry(config_path: Optional[str] = None) -> Dict[str, ModelConfig]:
    """Return the full model registry from models.yaml.

    Raises ConfigError if models.yaml is missing or invalid.
    """
    return load_model_config(config_path)["registry"]


def get_model_config(name: str, config_path: Optional[str] = None) -> ModelConfig:
    """Return the ModelConfig for a named model.

    Raises ConfigError if models.yaml is missing/invalid.
    Raises ValueError if the model name is not in the registry.
    """
    registry = get_model_registry(config_path)
    if name not in registry:
        raise ValueError(
            f"Model '{name}' is not in the registry. "
            "Add it to the 'registry' section of models.yaml first."
        )
    return registry[name]


def get_model_default(operation: str, config_path: Optional[str] = None) -> str:
    """Return the configured default model for *operation*.

    Raises ConfigError if models.yaml is missing or invalid.
    Raises ValueError if *operation* is not a valid operation name.
    """
    if operation not in VALID_OPERATIONS:
        raise ValueError(
            f"Unknown operation '{operation}'. "
            f"Valid operations: {', '.join(sorted(VALID_OPERATIONS))}"
        )
    config = load_model_config(config_path)
    return config["defaults"][operation]


def save_model_config(defaults: Dict[str, str], config_path: Optional[str] = None) -> None:
    """Write model defaults to models.yaml, preserving the existing registry.

    If models.yaml exists, the registry is preserved and only defaults are updated.
    Raises ConfigError if the file is missing (use models init to create it first).
    """
    if not HAS_YAML:
        raise RuntimeError("PyYAML is required to save model configuration.")

    path = config_path or DEFAULT_CONFIG_PATH
    p = Path(path)

    # Load existing data to preserve registry
    if p.exists():
        existing = load_model_config(config_path)
        registry = existing["registry"]
    else:
        raise ConfigError(
            f"models.yaml not found at '{path}'.\n"
            "Run 'aippt models init' to create it first."
        )

    # Validate new defaults reference the registry
    for op, model_name in defaults.items():
        if op not in VALID_OPERATIONS:
            raise ValueError(f"Unknown operation '{op}'.")
        if model_name not in registry:
            raise ValueError(
                f"Model '{model_name}' is not in the registry. "
                "Add it to the 'registry' section of models.yaml first."
            )

    # Re-read raw YAML to preserve comments and structure
    with p.open(encoding="utf-8") as fh:
        raw_data = yaml.safe_load(fh)

    raw_data["defaults"] = {k: v for k, v in defaults.items() if k in VALID_OPERATIONS}

    with open(path, "w", encoding="utf-8") as fh:
        yaml.dump(raw_data, fh, default_flow_style=False, sort_keys=False)

    logger.info("Model configuration saved to %s", path)


def init_model_config(config_path: Optional[str] = None) -> str:
    """Copy models.yaml.example to models.yaml.

    Returns the path where models.yaml was created.
    Raises ConfigError if models.yaml.example is not found.
    Raises FileExistsError if models.yaml already exists (caller handles).
    """
    import shutil

    dest = config_path or DEFAULT_CONFIG_PATH
    src = EXAMPLE_CONFIG_PATH

    if not Path(src).exists():
        raise ConfigError(
            f"models.yaml.example not found at '{src}'. "
            "Cannot initialize models.yaml."
        )

    if Path(dest).exists():
        raise FileExistsError(f"models.yaml already exists at '{dest}'.")

    shutil.copy2(src, dest)
    logger.info("Created %s from %s", dest, src)
    return dest


def reset_model_config(config_path: Optional[str] = None) -> None:
    """Delete models.yaml.

    Raises ConfigError -- models.yaml is now required; reset is not supported.
    """
    raise ConfigError(
        "Reset is no longer supported. models.yaml is required and has no built-in fallback.\n"
        "Edit models.yaml directly, or delete it and run 'aippt models init' to recreate from example."
    )


# ---------------------------------------------------------------------------
# Template configuration
# ---------------------------------------------------------------------------

DEFAULT_TEMPLATE_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates.yaml")


class TemplateConfigError(Exception):
    """Raised when templates.yaml is missing, invalid, or lacks a default_template key."""


def load_template_config(config_path: Optional[str] = None) -> Dict:
    """Load template configuration from templates.yaml.

    Returns a dict with:
      ``default_template``  -- path to the default template file
      ``source``            -- path to the loaded file

    Raises:
      TemplateConfigError  -- if file is not found, unparseable, or missing default_template
    """
    if not HAS_YAML:
        raise TemplateConfigError(
            "PyYAML is not installed. Install it with: pip install pyyaml"
        )

    path = config_path or DEFAULT_TEMPLATE_CONFIG_PATH
    p = Path(path)

    if not p.exists():
        raise TemplateConfigError(f"templates.yaml not found at '{path}'.")

    try:
        with p.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except Exception as exc:
        raise TemplateConfigError(f"Failed to parse {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise TemplateConfigError(f"{path} is not a valid YAML mapping.")

    if "default_template" not in data:
        raise TemplateConfigError(
            f"{path} is missing the 'default_template' key."
        )

    value = data["default_template"]
    if not isinstance(value, str) or not value.strip():
        raise TemplateConfigError(
            f"{path} 'default_template' must be a non-empty string."
        )

    return {"default_template": value, "source": str(p)}


def get_template_default(config_path: Optional[str] = None) -> str:
    """Return the default template path from templates.yaml.

    Raises:
      TemplateConfigError  -- if templates.yaml is missing or invalid
    """
    return load_template_config(config_path)["default_template"]


def set_template_default(template_path: str, config_path: Optional[str] = None) -> None:
    """Write or update the default_template entry in templates.yaml.

    Creates templates.yaml if it does not exist. If it already exists,
    the default_template key is updated while other keys are preserved.

    Raises:
      ValueError           -- if template_path is empty
      TemplateConfigError  -- if PyYAML is not installed
    """
    if not template_path or not template_path.strip():
        raise ValueError("template_path must be a non-empty string.")

    if not HAS_YAML:
        raise TemplateConfigError(
            "PyYAML is not installed. Install it with: pip install pyyaml"
        )

    path = config_path or DEFAULT_TEMPLATE_CONFIG_PATH
    p = Path(path)

    # Load existing data if the file exists, otherwise start fresh
    data = {}
    if p.exists():
        try:
            with p.open(encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
        except Exception:
            data = {}

    data["default_template"] = template_path

    with p.open("w", encoding="utf-8") as fh:
        yaml.dump(data, fh, default_flow_style=False, sort_keys=False)

    logger.info("Template configuration saved to %s", path)


# ---------------------------------------------------------------------------
# Directory configuration (dirs.yaml)
# ---------------------------------------------------------------------------

DEFAULT_DIRS_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dirs.yaml")

DIRS_DEFAULTS = {
    "outlines": "outlines/",
    "templates": "templates/",
    "uploads": "uploads/",
    "output": "output/",
    "backups": "backups/",
    "images": "images/",
    "db": "slides.db",
}


class DirsConfigError(Exception):
    """Raised when dirs.yaml is invalid."""


def load_dirs_config(config_path: Optional[str] = None) -> Dict:
    """Load directory configuration from dirs.yaml.

    Falls back to defaults for any missing keys. If the file does not exist,
    it is created with default values.

    Returns a dict with:
      ``directories``  -- dict of directory key -> path string
      ``base_dir``     -- absolute path to the directory containing dirs.yaml
      ``source``       -- path to the loaded file (or "defaults" if auto-created)
    """
    if not HAS_YAML:
        return {
            "directories": dict(DIRS_DEFAULTS),
            "base_dir": os.getcwd(),
            "source": "defaults (pyyaml not installed)",
        }

    path = config_path or DEFAULT_DIRS_CONFIG_PATH
    p = Path(path)

    # Auto-create dirs.yaml with defaults on first run
    if not p.exists():
        _create_default_dirs_yaml(str(p))
        return {
            "directories": dict(DIRS_DEFAULTS),
            "base_dir": str(p.parent.resolve()),
            "source": str(p),
        }

    try:
        with p.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except Exception as exc:
        raise DirsConfigError(f"Failed to parse {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise DirsConfigError(f"{path} is not a valid YAML mapping.")

    raw_dirs = data.get("directories", {})
    if not isinstance(raw_dirs, dict):
        raise DirsConfigError(f"{path} 'directories' must be a mapping.")

    # Merge with defaults — dirs.yaml values take precedence
    directories = dict(DIRS_DEFAULTS)
    directories.update({k: v for k, v in raw_dirs.items() if k in DIRS_DEFAULTS})

    return {
        "directories": directories,
        "base_dir": str(p.parent.resolve()),
        "source": str(p),
    }


def resolve_path(relative_path: str, base_dir: Optional[str] = None) -> str:
    """Resolve a relative path to absolute using a base directory.

    If *relative_path* is already absolute, it is returned as-is.
    If *base_dir* is not given, the current working directory is used.
    """
    if os.path.isabs(relative_path):
        return relative_path
    base = base_dir or os.getcwd()
    return os.path.normpath(os.path.join(base, relative_path))


# ---------------------------------------------------------------------------
# Admin tier (gateway.yaml `admin_ntids` list)
# ---------------------------------------------------------------------------


def load_admin_ntids(config_path: Optional[str] = None) -> set:
    """Return the set of NTIDs treated as admins for this deployment.

    Looks for a top-level ``admin_ntids`` list in ``gateway.yaml``::

        admin_ntids:
          - melliott
          - jdoe

    Returns an empty set when the file is missing, the key is absent, or
    the value is not a list. Each entry is stripped and lowercased before
    it joins the set; entries that don't match the same
    ``[A-Za-z0-9._-]+`` allowlist used for the ``X-AIPPT-NTID`` header are
    silently dropped (a malformed entry in config shouldn't crash the
    server).

    Membership is **case-insensitive**: entries are lowercased here and the
    gate (``aippt.web.routes._is_admin``) lowercases the incoming header
    before testing, so ``MElliott`` in config matches a ``melliott`` header
    and vice versa. Lowercasing at both sites keeps them from diverging.

    This is the v1 admin tier: an allowlist that the server trusts in
    combination with a valid Microsoft Bearer token. Audit logs record
    both the X-AIPPT-NTID and a Bearer-derived identity claim so
    impersonation attempts (claiming someone else's NTID via a
    localStorage edit) are recoverable from logs even though the gate
    itself trusts the client-supplied header. Upgrade path to AAD-groups-
    based roles is the original M2 admin-tier PRD.
    """
    import re as _re

    if not config_path or not HAS_YAML:
        return set()

    p = Path(config_path)
    if not p.exists():
        return set()

    try:
        with p.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except Exception:
        return set()

    if not isinstance(data, dict):
        return set()

    raw = data.get("admin_ntids")
    if not isinstance(raw, list):
        return set()

    pattern = _re.compile(r"^[A-Za-z0-9._-]+$")
    out: set = set()
    for entry in raw:
        if not isinstance(entry, str):
            continue
        v = entry.strip().lower()
        if pattern.match(v):
            out.add(v)
    return out


# ---------------------------------------------------------------------------
# Upload configuration (gateway.yaml `upload` block)
# ---------------------------------------------------------------------------

DEFAULT_MAX_UPLOAD_MB = 50


def load_upload_config(config_path: Optional[str] = None) -> int:
    """Return the configured upload size limit in bytes.

    Looks for an ``upload:`` block in ``gateway.yaml``:

        upload:
          max_size_mb: 50

    Returns the value times 1024**2. Defaults to ``DEFAULT_MAX_UPLOAD_MB`` if
    the file is missing, the block is absent, the key is missing, or the
    value is non-numeric. Negative or zero values are coerced to the default
    (a server that won't accept any upload is a misconfiguration, not a
    feature).
    """
    default_bytes = DEFAULT_MAX_UPLOAD_MB * 1024 * 1024

    if not config_path or not HAS_YAML:
        return default_bytes

    p = Path(config_path)
    if not p.exists():
        return default_bytes

    try:
        with p.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except Exception:
        return default_bytes

    if not isinstance(data, dict):
        return default_bytes

    block = data.get("upload")
    if not isinstance(block, dict):
        return default_bytes

    raw = block.get("max_size_mb", DEFAULT_MAX_UPLOAD_MB)
    try:
        mb = int(raw)
    except (TypeError, ValueError):
        return default_bytes
    if mb <= 0:
        return default_bytes
    return mb * 1024 * 1024


# ---------------------------------------------------------------------------
# SharePoint configuration (gateway.yaml `sharepoint` block)
# ---------------------------------------------------------------------------

DEFAULT_SHAREPOINT_ROOT_PATH = "AIPPT/render-staging"


@dataclass(frozen=True)
class SharePointConfig:
    """Resolved SharePoint coordinates for the Graph render staging area."""
    site_id: str
    drive_id: str
    root_path: str


def _resolve_sp_value(
    block: dict, key: str, env_key: str, *, source: str,
) -> Optional[str]:
    """Resolve `key` from the sharepoint block, with env-var indirection.

    Returns the literal value of `block[key]`, or `os.environ[block[env_key]]`
    if `env_key` is set instead. Raises ValueError if the env var is unset.
    Returns None if neither is provided (caller decides if that's an error).
    """
    if key in block and block[key] not in (None, ""):
        return str(block[key])
    if env_key in block and block[env_key]:
        env_var = str(block[env_key])
        value = os.environ.get(env_var, "")
        if not value:
            raise ValueError(
                f"{source}: sharepoint.{env_key} points at env var "
                f"'{env_var}' which is unset or empty."
            )
        return value
    return None


def load_sharepoint_config(config_path: str) -> Optional[SharePointConfig]:
    """Load SharePoint render staging coordinates from gateway.yaml.

    The expected YAML shape is:

        sharepoint:
          render_site_id: "..."          # or render_site_id_env: ENV_VAR
          render_drive_id: "..."         # or render_drive_id_env: ENV_VAR
          render_root_path: "AIPPT/render-staging"   # optional

    Returns:
        SharePointConfig if the block is present and complete.
        None if the file does not exist OR the file has no `sharepoint` block.

    Raises:
        ValueError: the block exists but is malformed (not a mapping, missing
            required field, or env-var indirection points at an unset env var).
    """
    p = Path(config_path)
    if not p.exists():
        return None

    if not HAS_YAML:
        raise RuntimeError(
            "PyYAML is required to load SharePoint configuration."
        )

    try:
        with p.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except Exception as exc:
        raise ValueError(f"Failed to parse {config_path}: {exc}") from exc

    if not isinstance(data, dict) or "sharepoint" not in data:
        return None

    block = data["sharepoint"]
    if not isinstance(block, dict):
        raise ValueError(
            f"{config_path}: 'sharepoint' must be a mapping, got "
            f"{type(block).__name__}."
        )

    site_id = _resolve_sp_value(
        block, "render_site_id", "render_site_id_env", source=config_path,
    )
    if not site_id:
        raise ValueError(
            f"{config_path}: sharepoint block is missing render_site_id "
            "(or render_site_id_env)."
        )

    drive_id = _resolve_sp_value(
        block, "render_drive_id", "render_drive_id_env", source=config_path,
    )
    if not drive_id:
        raise ValueError(
            f"{config_path}: sharepoint block is missing render_drive_id "
            "(or render_drive_id_env)."
        )

    root_path = block.get("render_root_path") or DEFAULT_SHAREPOINT_ROOT_PATH

    return SharePointConfig(
        site_id=site_id, drive_id=drive_id, root_path=str(root_path),
    )


# ---------------------------------------------------------------------------
# Storage backend (AIPPT_STORAGE + MINIO_* env)
# ---------------------------------------------------------------------------

DEFAULT_STORAGE_BACKEND = "fs"
DEFAULT_MINIO_PREFIX = "asic/aippt/"


@dataclass(frozen=True)
class StorageConfig:
    """Resolved storage backend selection and object-store coordinates.

    ``backend`` is ``"fs"`` (default) or ``"s3"``. The ``s3``/MinIO fields are
    only consulted when ``backend == "s3"``; they are read from the environment
    so credentials arrive via a k8s Secret (``secretKeyRef``) in production and
    never live in a repo file.
    """
    backend: str = DEFAULT_STORAGE_BACKEND
    endpoint: Optional[str] = None
    bucket: Optional[str] = None
    prefix: str = DEFAULT_MINIO_PREFIX
    access_key: Optional[str] = None
    secret_key: Optional[str] = None
    ca_bundle: Optional[str] = None
    secure: bool = True


def load_storage_config(backend: Optional[str] = None) -> StorageConfig:
    """Resolve the storage configuration from the environment.

    Reads ``AIPPT_STORAGE`` (``fs``|``s3``, default ``fs``) unless *backend* is
    given explicitly. For the ``s3`` backend the MinIO coordinates come from:

    - ``MINIO_ENDPOINT``   -- host:port of the S3 API (e.g. ``s3minio.amd.com:21000``)
    - ``MINIO_BUCKET``     -- bucket name (e.g. ``ogmatic-zoo``)
    - ``MINIO_PREFIX``     -- key prefix (default ``asic/aippt/``)
    - ``MINIO_ACCESS_KEY`` / ``MINIO_SECRET_KEY`` -- credentials
    - ``MINIO_CA_BUNDLE``  -- optional CA bundle path for TLS verification
    - ``MINIO_SECURE``     -- ``0``/``false`` to disable TLS (default on)

    No validation is performed here -- ``storage.build_storage`` reports any
    missing required s3 fields when it constructs the client.
    """
    resolved = (backend or os.environ.get("AIPPT_STORAGE") or DEFAULT_STORAGE_BACKEND).strip().lower()

    prefix = os.environ.get("MINIO_PREFIX", DEFAULT_MINIO_PREFIX)
    if prefix and not prefix.endswith("/"):
        prefix += "/"

    secure_raw = os.environ.get("MINIO_SECURE", "").strip().lower()
    secure = secure_raw not in ("0", "false", "no")

    return StorageConfig(
        backend=resolved,
        endpoint=os.environ.get("MINIO_ENDPOINT"),
        bucket=os.environ.get("MINIO_BUCKET"),
        prefix=prefix,
        access_key=os.environ.get("MINIO_ACCESS_KEY"),
        secret_key=os.environ.get("MINIO_SECRET_KEY"),
        ca_bundle=os.environ.get("MINIO_CA_BUNDLE") or None,
        secure=secure,
    )


def _create_default_dirs_yaml(path: str) -> None:
    """Write a dirs.yaml with default values."""
    content = (
        "# Outline2PPT directory configuration\n"
        "# All paths are relative to the directory containing this file.\n"
        "# Absolute paths are also supported for advanced use cases.\n"
        "directories:\n"
    )
    for key, value in DIRS_DEFAULTS.items():
        content += f"  {key}: {value}\n"

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    logger.info("Created default dirs.yaml at %s", path)
