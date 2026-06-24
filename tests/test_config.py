"""Tests for aippt.config module."""

import os
import pytest
import yaml

from aippt.config import (
    VALID_OPERATIONS,
    ConfigError,
    load_model_config,
    save_model_config,
    get_model_config,
    get_model_registry,
    get_model_default,
    init_model_config,
)


# ---------------------------------------------------------------------------
# Minimal valid models.yaml content for use across tests
# ---------------------------------------------------------------------------

MINIMAL_REGISTRY = {
    "gpt-4o": {
        "provider": "openai",
        "max_tokens": 128000,
        "max_input_tokens": 128000,
        "supports_vision": True,
        "supports_images": True,
    },
    "claude-3.5-sonnet": {
        "provider": "anthropic",
        "max_tokens": 200000,
        "max_input_tokens": 200000,
        "supports_vision": True,
        "supports_images": False,
    },
    "dall-e-3": {
        "provider": "openai",
        "max_tokens": 0,
        "max_input_tokens": 0,
        "supports_vision": False,
        "supports_images": True,
    },
}

MINIMAL_DEFAULTS = {
    "enhance": "claude-3.5-sonnet",
    "feedback": "gpt-4o",
    "notes": "gpt-4o",
    "tags": "gpt-4o",
    "image": "dall-e-3",
}


def write_minimal_config(path: str) -> None:
    """Write a minimal valid models.yaml to *path*."""
    with open(path, "w") as f:
        yaml.dump({"registry": MINIMAL_REGISTRY, "defaults": MINIMAL_DEFAULTS}, f)


# ---------------------------------------------------------------------------
# TestValidOperations
# ---------------------------------------------------------------------------

class TestValidOperations:
    def test_improve_in_valid_operations(self):
        assert "improve" in VALID_OPERATIONS

    def test_reverse_in_valid_operations(self):
        assert "reverse" in VALID_OPERATIONS

    def test_all_expected_operations_present(self):
        expected = {"enhance", "feedback", "notes", "tags", "image", "improve", "reverse"}
        assert VALID_OPERATIONS == expected


# ---------------------------------------------------------------------------
# TestLoadModelConfig
# ---------------------------------------------------------------------------

class TestLoadModelConfig:
    def test_raises_on_missing_file(self, tmp_path):
        with pytest.raises(ConfigError, match="not found"):
            load_model_config(str(tmp_path / "nonexistent.yaml"))

    def test_raises_on_invalid_yaml(self, tmp_path):
        config_path = str(tmp_path / "models.yaml")
        with open(config_path, "w") as f:
            f.write(": : : invalid yaml [[[")
        with pytest.raises(ConfigError, match="Failed to parse"):
            load_model_config(config_path)

    def test_raises_when_registry_missing(self, tmp_path):
        config_path = str(tmp_path / "models.yaml")
        with open(config_path, "w") as f:
            yaml.dump({"defaults": MINIMAL_DEFAULTS}, f)
        with pytest.raises(ConfigError, match="registry"):
            load_model_config(config_path)

    def test_raises_when_registry_empty(self, tmp_path):
        config_path = str(tmp_path / "models.yaml")
        with open(config_path, "w") as f:
            yaml.dump({"registry": {}, "defaults": MINIMAL_DEFAULTS}, f)
        with pytest.raises(ConfigError, match="non-empty"):
            load_model_config(config_path)

    def test_raises_when_defaults_missing(self, tmp_path):
        config_path = str(tmp_path / "models.yaml")
        with open(config_path, "w") as f:
            yaml.dump({"registry": MINIMAL_REGISTRY}, f)
        with pytest.raises(ConfigError, match="defaults"):
            load_model_config(config_path)

    def test_raises_when_operation_missing_from_defaults(self, tmp_path):
        config_path = str(tmp_path / "models.yaml")
        incomplete_defaults = {k: v for k, v in MINIMAL_DEFAULTS.items() if k != "image"}
        with open(config_path, "w") as f:
            yaml.dump({"registry": MINIMAL_REGISTRY, "defaults": incomplete_defaults}, f)
        with pytest.raises(ConfigError, match="image"):
            load_model_config(config_path)

    def test_raises_when_default_references_unknown_model(self, tmp_path):
        config_path = str(tmp_path / "models.yaml")
        bad_defaults = dict(MINIMAL_DEFAULTS)
        bad_defaults["enhance"] = "nonexistent-model"
        with open(config_path, "w") as f:
            yaml.dump({"registry": MINIMAL_REGISTRY, "defaults": bad_defaults}, f)
        with pytest.raises(ConfigError, match="nonexistent-model"):
            load_model_config(config_path)

    def test_loads_valid_config(self, tmp_path):
        config_path = str(tmp_path / "models.yaml")
        write_minimal_config(config_path)
        config = load_model_config(config_path)

        assert "registry" in config
        assert "defaults" in config
        assert "source" in config
        assert config["source"] == config_path

    def test_registry_entries_are_model_configs(self, tmp_path):
        config_path = str(tmp_path / "models.yaml")
        write_minimal_config(config_path)
        config = load_model_config(config_path)

        from aippt.config import ModelConfig
        for name, mc in config["registry"].items():
            assert isinstance(mc, ModelConfig)
            assert mc.name == name

    def test_defaults_contain_all_required_operations(self, tmp_path):
        config_path = str(tmp_path / "models.yaml")
        write_minimal_config(config_path)
        config = load_model_config(config_path)
        required_ops = VALID_OPERATIONS - {"improve", "reverse"}
        for op in required_ops:
            assert op in config["defaults"]

    def test_loads_without_improve_default(self, tmp_path):
        """Backward compat: models.yaml without 'improve' key loads successfully."""
        config_path = str(tmp_path / "models.yaml")
        write_minimal_config(config_path)
        config = load_model_config(config_path)
        assert "improve" not in config["defaults"]
        assert "enhance" in config["defaults"]

    def test_loads_with_improve_default(self, tmp_path):
        """models.yaml with 'improve' key includes it in defaults."""
        config_path = str(tmp_path / "models.yaml")
        defaults_with_improve = dict(MINIMAL_DEFAULTS)
        defaults_with_improve["improve"] = "claude-3.5-sonnet"
        with open(config_path, "w") as f:
            yaml.dump({"registry": MINIMAL_REGISTRY, "defaults": defaults_with_improve}, f)
        config = load_model_config(config_path)
        assert config["defaults"]["improve"] == "claude-3.5-sonnet"

    def test_loads_without_reverse_default(self, tmp_path):
        """Backward compat: models.yaml without 'reverse' key loads successfully."""
        config_path = str(tmp_path / "models.yaml")
        write_minimal_config(config_path)
        config = load_model_config(config_path)
        assert "reverse" not in config["defaults"]
        assert "enhance" in config["defaults"]

    def test_loads_with_reverse_default(self, tmp_path):
        """models.yaml with 'reverse' key includes it in defaults."""
        config_path = str(tmp_path / "models.yaml")
        defaults_with_reverse = dict(MINIMAL_DEFAULTS)
        defaults_with_reverse["reverse"] = "claude-3.5-sonnet"
        with open(config_path, "w") as f:
            yaml.dump({"registry": MINIMAL_REGISTRY, "defaults": defaults_with_reverse}, f)
        config = load_model_config(config_path)
        assert config["defaults"]["reverse"] == "claude-3.5-sonnet"


# ---------------------------------------------------------------------------
# TestRegistryValidation
# ---------------------------------------------------------------------------

class TestRegistryValidation:
    def test_raises_on_missing_provider_field(self, tmp_path):
        config_path = str(tmp_path / "models.yaml")
        bad_registry = {"my-model": {"max_tokens": 100, "max_input_tokens": 100}}
        with open(config_path, "w") as f:
            yaml.dump({"registry": bad_registry, "defaults": MINIMAL_DEFAULTS}, f)
        with pytest.raises(ConfigError, match="provider"):
            load_model_config(config_path)

    def test_raises_on_invalid_provider(self, tmp_path):
        config_path = str(tmp_path / "models.yaml")
        bad_registry = dict(MINIMAL_REGISTRY)
        bad_registry["bad-model"] = {
            "provider": "unsupported-provider",
            "max_tokens": 100,
            "max_input_tokens": 100,
        }
        with open(config_path, "w") as f:
            yaml.dump({"registry": bad_registry, "defaults": MINIMAL_DEFAULTS}, f)
        with pytest.raises(ConfigError, match="unsupported-provider"):
            load_model_config(config_path)

    def test_raises_on_missing_max_tokens(self, tmp_path):
        config_path = str(tmp_path / "models.yaml")
        bad_registry = {"my-model": {"provider": "openai", "max_input_tokens": 100}}
        with open(config_path, "w") as f:
            yaml.dump({"registry": bad_registry, "defaults": MINIMAL_DEFAULTS}, f)
        with pytest.raises(ConfigError, match="max_tokens"):
            load_model_config(config_path)

    def test_capability_fields_default_to_false(self, tmp_path):
        config_path = str(tmp_path / "models.yaml")
        registry = {
            "my-model": {"provider": "openai", "max_tokens": 100, "max_input_tokens": 100},
            "dall-e-3": MINIMAL_REGISTRY["dall-e-3"],
        }
        defaults = dict(MINIMAL_DEFAULTS)
        defaults["enhance"] = "my-model"
        defaults["feedback"] = "my-model"
        defaults["notes"] = "my-model"
        defaults["tags"] = "my-model"
        with open(config_path, "w") as f:
            yaml.dump({"registry": registry, "defaults": defaults}, f)
        config = load_model_config(config_path)
        mc = config["registry"]["my-model"]
        assert mc.supports_vision is False
        assert mc.supports_images is False


# ---------------------------------------------------------------------------
# TestGetModelConfig
# ---------------------------------------------------------------------------

class TestGetModelConfig:
    def test_lookup_by_name(self, tmp_path):
        config_path = str(tmp_path / "models.yaml")
        write_minimal_config(config_path)
        mc = get_model_config("gpt-4o", config_path)
        assert mc.name == "gpt-4o"
        assert mc.provider == "openai"

    def test_raises_on_unknown_name(self, tmp_path):
        config_path = str(tmp_path / "models.yaml")
        write_minimal_config(config_path)
        with pytest.raises(ValueError, match="nonexistent"):
            get_model_config("nonexistent", config_path)

    def test_raises_config_error_on_missing_file(self, tmp_path):
        with pytest.raises(ConfigError):
            get_model_config("gpt-4o", str(tmp_path / "missing.yaml"))


# ---------------------------------------------------------------------------
# TestGetModelDefault
# ---------------------------------------------------------------------------

class TestGetModelDefault:
    def test_returns_configured_value(self, tmp_path):
        config_path = str(tmp_path / "models.yaml")
        write_minimal_config(config_path)
        result = get_model_default("enhance", config_path)
        assert result == "claude-3.5-sonnet"

    def test_raises_on_invalid_operation(self, tmp_path):
        config_path = str(tmp_path / "models.yaml")
        write_minimal_config(config_path)
        with pytest.raises(ValueError, match="Unknown operation"):
            get_model_default("invalid_op", config_path)

    def test_raises_config_error_when_file_missing(self, tmp_path):
        with pytest.raises(ConfigError):
            get_model_default("enhance", str(tmp_path / "missing.yaml"))

    def test_all_required_operations_resolve(self, tmp_path):
        config_path = str(tmp_path / "models.yaml")
        write_minimal_config(config_path)
        for op in VALID_OPERATIONS - {"improve", "reverse"}:
            result = get_model_default(op, config_path)
            assert isinstance(result, str) and result

    def test_improve_raises_key_error_when_missing(self, tmp_path):
        """get_model_default('improve') raises KeyError when not in defaults."""
        config_path = str(tmp_path / "models.yaml")
        write_minimal_config(config_path)
        with pytest.raises(KeyError):
            get_model_default("improve", config_path)

    def test_improve_resolves_when_configured(self, tmp_path):
        """get_model_default('improve') works when improve is in defaults."""
        config_path = str(tmp_path / "models.yaml")
        defaults_with_improve = dict(MINIMAL_DEFAULTS)
        defaults_with_improve["improve"] = "gpt-4o"
        with open(config_path, "w") as f:
            yaml.dump({"registry": MINIMAL_REGISTRY, "defaults": defaults_with_improve}, f)
        result = get_model_default("improve", config_path)
        assert result == "gpt-4o"

    def test_reverse_raises_key_error_when_missing(self, tmp_path):
        """get_model_default('reverse') raises KeyError when not in defaults."""
        config_path = str(tmp_path / "models.yaml")
        write_minimal_config(config_path)
        with pytest.raises(KeyError):
            get_model_default("reverse", config_path)

    def test_reverse_resolves_when_configured(self, tmp_path):
        """get_model_default('reverse') works when reverse is in defaults."""
        config_path = str(tmp_path / "models.yaml")
        defaults_with_reverse = dict(MINIMAL_DEFAULTS)
        defaults_with_reverse["reverse"] = "gpt-4o"
        with open(config_path, "w") as f:
            yaml.dump({"registry": MINIMAL_REGISTRY, "defaults": defaults_with_reverse}, f)
        result = get_model_default("reverse", config_path)
        assert result == "gpt-4o"


# ---------------------------------------------------------------------------
# TestInitModelConfig
# ---------------------------------------------------------------------------

class TestInitModelConfig:
    def test_creates_models_yaml_from_example(self, tmp_path, monkeypatch):
        import shutil
        import aippt.config as cfg_module
        # Point example path at our test fixture
        example = str(tmp_path / "models.yaml.example")
        dest = str(tmp_path / "models.yaml")
        # Write a minimal example file
        with open(example, "w") as f:
            yaml.dump({"registry": MINIMAL_REGISTRY, "defaults": MINIMAL_DEFAULTS}, f)
        monkeypatch.setattr(cfg_module, "EXAMPLE_CONFIG_PATH", example)

        result = init_model_config(dest)
        assert result == dest
        assert os.path.exists(dest)
        # Verify the copy is valid
        config = load_model_config(dest)
        assert "registry" in config

    def test_raises_config_error_when_example_missing(self, tmp_path, monkeypatch):
        import aippt.config as cfg_module
        monkeypatch.setattr(cfg_module, "EXAMPLE_CONFIG_PATH", str(tmp_path / "missing_example.yaml"))
        with pytest.raises(ConfigError, match="models.yaml.example not found"):
            init_model_config(str(tmp_path / "models.yaml"))


# ---------------------------------------------------------------------------
# TestSaveModelConfig
# ---------------------------------------------------------------------------

class TestSaveModelConfig:
    def test_saves_defaults_to_existing_file(self, tmp_path):
        config_path = str(tmp_path / "models.yaml")
        write_minimal_config(config_path)
        new_defaults = dict(MINIMAL_DEFAULTS)
        new_defaults["enhance"] = "gpt-4o"
        save_model_config(new_defaults, config_path)

        config = load_model_config(config_path)
        assert config["defaults"]["enhance"] == "gpt-4o"

    def test_raises_config_error_when_file_missing(self, tmp_path):
        with pytest.raises(ConfigError):
            save_model_config(MINIMAL_DEFAULTS, str(tmp_path / "missing.yaml"))

    def test_raises_value_error_for_model_not_in_registry(self, tmp_path):
        config_path = str(tmp_path / "models.yaml")
        write_minimal_config(config_path)
        bad_defaults = dict(MINIMAL_DEFAULTS)
        bad_defaults["enhance"] = "nonexistent-model"
        with pytest.raises(ValueError, match="nonexistent-model"):
            save_model_config(bad_defaults, config_path)

    def test_registry_preserved_after_save(self, tmp_path):
        config_path = str(tmp_path / "models.yaml")
        write_minimal_config(config_path)
        new_defaults = dict(MINIMAL_DEFAULTS)
        save_model_config(new_defaults, config_path)

        config = load_model_config(config_path)
        assert "gpt-4o" in config["registry"]
        assert "claude-3.5-sonnet" in config["registry"]


# ---------------------------------------------------------------------------
# TestLoadTemplateConfig
# ---------------------------------------------------------------------------

from aippt.config import (
    load_template_config,
    get_template_default,
    set_template_default,
    TemplateConfigError,
)


class TestLoadTemplateConfig:
    def test_raises_on_missing_file(self, tmp_path):
        with pytest.raises(TemplateConfigError, match="not found"):
            load_template_config(str(tmp_path / "nope.yaml"))

    def test_raises_on_invalid_yaml(self, tmp_path):
        p = tmp_path / "templates.yaml"
        p.write_text("{{bad")
        with pytest.raises(TemplateConfigError, match="parse"):
            load_template_config(str(p))

    def test_raises_when_default_template_missing(self, tmp_path):
        p = tmp_path / "templates.yaml"
        p.write_text("foo: bar\n")
        with pytest.raises(TemplateConfigError, match="default_template"):
            load_template_config(str(p))

    def test_raises_on_non_mapping_yaml(self, tmp_path):
        p = tmp_path / "templates.yaml"
        p.write_text("- item1\n- item2\n")
        with pytest.raises(TemplateConfigError, match="mapping"):
            load_template_config(str(p))

    def test_raises_when_default_template_is_null(self, tmp_path):
        p = tmp_path / "templates.yaml"
        p.write_text("default_template:\n")
        with pytest.raises(TemplateConfigError, match="non-empty"):
            load_template_config(str(p))

    def test_loads_valid_config(self, tmp_path):
        p = tmp_path / "templates.yaml"
        p.write_text("default_template: templates/corp.pptx\n")
        result = load_template_config(str(p))
        assert result["default_template"] == "templates/corp.pptx"
        assert result["source"] == str(p)


# ---------------------------------------------------------------------------
# TestGetTemplateDefault
# ---------------------------------------------------------------------------

class TestGetTemplateDefault:
    def test_returns_configured_value(self, tmp_path):
        p = tmp_path / "templates.yaml"
        p.write_text("default_template: my/template.pptx\n")
        assert get_template_default(str(p)) == "my/template.pptx"

    def test_raises_on_missing_file(self, tmp_path):
        with pytest.raises(TemplateConfigError):
            get_template_default(str(tmp_path / "nope.yaml"))


# ---------------------------------------------------------------------------
# TestSetTemplateDefault
# ---------------------------------------------------------------------------

class TestSetTemplateDefault:
    def test_creates_file_if_missing(self, tmp_path):
        p = tmp_path / "templates.yaml"
        set_template_default("new/path.pptx", str(p))
        assert p.exists()
        result = load_template_config(str(p))
        assert result["default_template"] == "new/path.pptx"

    def test_updates_existing_file(self, tmp_path):
        p = tmp_path / "templates.yaml"
        p.write_text("default_template: old.pptx\n")
        set_template_default("new.pptx", str(p))
        result = load_template_config(str(p))
        assert result["default_template"] == "new.pptx"

    def test_raises_on_empty_path(self, tmp_path):
        with pytest.raises(ValueError, match="non-empty"):
            set_template_default("", str(tmp_path / "templates.yaml"))

    def test_raises_on_whitespace_only_path(self, tmp_path):
        with pytest.raises(ValueError, match="non-empty"):
            set_template_default("   ", str(tmp_path / "templates.yaml"))


# ---------------------------------------------------------------------------
# TestLoadDirsConfig
# ---------------------------------------------------------------------------

from aippt.config import (
    load_dirs_config,
    resolve_path,
    DIRS_DEFAULTS,
    DirsConfigError,
)


class TestLoadDirsConfig:
    def test_defaults_when_file_missing(self, tmp_path):
        """Missing dirs.yaml is auto-created and returns all defaults."""
        config_path = str(tmp_path / "dirs.yaml")
        result = load_dirs_config(config_path)
        assert result["directories"] == DIRS_DEFAULTS
        assert result["base_dir"] == str(tmp_path.resolve())
        # File should have been auto-created
        assert os.path.exists(config_path)

    def test_partial_config_fills_defaults(self, tmp_path):
        """Partial dirs.yaml fills in missing keys with defaults."""
        config_path = tmp_path / "dirs.yaml"
        config_path.write_text(
            "directories:\n  images: custom_images/\n  db: custom.db\n"
        )
        result = load_dirs_config(str(config_path))
        assert result["directories"]["images"] == "custom_images/"
        assert result["directories"]["db"] == "custom.db"
        # defaults for missing keys
        assert result["directories"]["outlines"] == "outlines/"
        assert result["directories"]["uploads"] == "uploads/"

    def test_full_config(self, tmp_path):
        """Full dirs.yaml is loaded without modification."""
        config_path = tmp_path / "dirs.yaml"
        custom = {
            "outlines": "my_outlines/",
            "templates": "my_templates/",
            "uploads": "my_uploads/",
            "output": "my_output/",
            "backups": "my_backups/",
            "images": "my_images/",
            "db": "my.db",
        }
        config_path.write_text(
            "directories:\n"
            + "".join(f"  {k}: {v}\n" for k, v in custom.items())
        )
        result = load_dirs_config(str(config_path))
        assert result["directories"] == custom

    def test_invalid_yaml_raises(self, tmp_path):
        """Invalid YAML raises DirsConfigError."""
        config_path = tmp_path / "dirs.yaml"
        config_path.write_text("{{bad yaml")
        with pytest.raises(DirsConfigError, match="parse"):
            load_dirs_config(str(config_path))

    def test_non_mapping_raises(self, tmp_path):
        """Non-mapping YAML raises DirsConfigError."""
        config_path = tmp_path / "dirs.yaml"
        config_path.write_text("- item1\n- item2\n")
        with pytest.raises(DirsConfigError, match="mapping"):
            load_dirs_config(str(config_path))

    def test_directories_not_mapping_raises(self, tmp_path):
        """directories key that is not a mapping raises DirsConfigError."""
        config_path = tmp_path / "dirs.yaml"
        config_path.write_text("directories: not-a-mapping\n")
        with pytest.raises(DirsConfigError, match="mapping"):
            load_dirs_config(str(config_path))

    def test_ignores_unknown_keys(self, tmp_path):
        """Unknown keys in directories section are ignored."""
        config_path = tmp_path / "dirs.yaml"
        config_path.write_text(
            "directories:\n  images: img/\n  unknown_key: val/\n"
        )
        result = load_dirs_config(str(config_path))
        assert "unknown_key" not in result["directories"]
        assert result["directories"]["images"] == "img/"

    def test_base_dir_from_config_location(self, tmp_path):
        """base_dir comes from the parent directory of dirs.yaml."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        config_path = subdir / "dirs.yaml"
        config_path.write_text("directories:\n  db: slides.db\n")
        result = load_dirs_config(str(config_path))
        assert result["base_dir"] == str(subdir.resolve())


# ---------------------------------------------------------------------------
# TestResolvePath
# ---------------------------------------------------------------------------


class TestResolvePath:
    def test_relative_path_resolved(self, tmp_path):
        """Relative path is resolved against base_dir."""
        result = resolve_path("images/deck/", str(tmp_path))
        assert result == os.path.normpath(os.path.join(str(tmp_path), "images/deck/"))

    def test_absolute_path_returned_as_is(self):
        """Absolute path is returned unchanged."""
        abs_path = "/home/user/data/slides.db"
        result = resolve_path(abs_path, "/some/base")
        assert result == abs_path

    def test_default_base_is_cwd(self):
        """Without base_dir, resolve_path uses cwd."""
        result = resolve_path("relative/path")
        expected = os.path.normpath(os.path.join(os.getcwd(), "relative/path"))
        assert result == expected

    def test_nested_relative_path(self, tmp_path):
        """Nested relative paths are normalized."""
        result = resolve_path("a/../b/./c", str(tmp_path))
        assert result == os.path.normpath(os.path.join(str(tmp_path), "b/c"))


from aippt.config import load_admin_ntids


class TestLoadAdminNtidsCaseInsensitive:
    """The admin allowlist loader lowercases entries so membership matching
    is case-insensitive (see also tests/test_admin_tier.py)."""

    def test_lowercases_entries(self, tmp_path):
        cfg = tmp_path / "gw.yaml"
        cfg.write_text(
            "admin_ntids:\n  - MElliott\n  - ZSYED\n", encoding="utf-8",
        )
        assert load_admin_ntids(str(cfg)) == {"melliott", "zsyed"}

    def test_mixed_case_dedupes_to_one(self, tmp_path):
        cfg = tmp_path / "gw.yaml"
        cfg.write_text(
            "admin_ntids:\n  - melliott\n  - MELLIOTT\n  - MElliott\n",
            encoding="utf-8",
        )
        assert load_admin_ntids(str(cfg)) == {"melliott"}

    def test_regex_still_applies_to_lowercased_value(self, tmp_path):
        # A space survives lowercasing and is still rejected by the allowlist.
        cfg = tmp_path / "gw.yaml"
        cfg.write_text(
            "admin_ntids:\n  - 'Has Space'\n  - Good.Name\n", encoding="utf-8",
        )
        assert load_admin_ntids(str(cfg)) == {"good.name"}
