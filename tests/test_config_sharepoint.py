"""Unit tests for aippt.config.load_sharepoint_config."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from aippt import config


class TestLoadSharePointConfigMissingFile:
    def test_missing_file_returns_none(self, tmp_path):
        # gateway.yaml does not exist on disk
        result = config.load_sharepoint_config(str(tmp_path / "no-such.yaml"))
        assert result is None


class TestLoadSharePointConfigMissingBlock:
    def test_no_sharepoint_block_returns_none(self, tmp_path):
        cfg = tmp_path / "gateway.yaml"
        cfg.write_text(textwrap.dedent("""
            gateway:
              base_url: "https://llm-api.amd.com"
            providers:
              openai:
                path: "/OpenAI"
        """).strip())
        result = config.load_sharepoint_config(str(cfg))
        assert result is None

    def test_empty_file_returns_none(self, tmp_path):
        cfg = tmp_path / "gateway.yaml"
        cfg.write_text("")
        result = config.load_sharepoint_config(str(cfg))
        assert result is None


class TestLoadSharePointConfigValid:
    def test_full_inline_config(self, tmp_path):
        cfg = tmp_path / "gateway.yaml"
        cfg.write_text(textwrap.dedent("""
            sharepoint:
              render_site_id: "contoso.sharepoint.com,abc-123,def-456"
              render_drive_id: "b!XYZ"
              render_root_path: "AIPPT/render-staging"
        """).strip())
        result = config.load_sharepoint_config(str(cfg))
        assert result is not None
        assert result.site_id == "contoso.sharepoint.com,abc-123,def-456"
        assert result.drive_id == "b!XYZ"
        assert result.root_path == "AIPPT/render-staging"

    def test_default_root_path_when_omitted(self, tmp_path):
        cfg = tmp_path / "gateway.yaml"
        cfg.write_text(textwrap.dedent("""
            sharepoint:
              render_site_id: "S"
              render_drive_id: "D"
        """).strip())
        result = config.load_sharepoint_config(str(cfg))
        assert result is not None
        assert result.root_path == "AIPPT/render-staging"

    def test_dataclass_is_frozen(self, tmp_path):
        cfg = tmp_path / "gateway.yaml"
        cfg.write_text(textwrap.dedent("""
            sharepoint:
              render_site_id: "S"
              render_drive_id: "D"
        """).strip())
        result = config.load_sharepoint_config(str(cfg))
        with pytest.raises(Exception):
            result.site_id = "mutated"


class TestLoadSharePointConfigEnvIndirection:
    def test_site_id_from_env_var(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MY_SITE_ID", "site-from-env")
        cfg = tmp_path / "gateway.yaml"
        cfg.write_text(textwrap.dedent("""
            sharepoint:
              render_site_id_env: "MY_SITE_ID"
              render_drive_id: "D"
        """).strip())
        result = config.load_sharepoint_config(str(cfg))
        assert result is not None
        assert result.site_id == "site-from-env"
        assert result.drive_id == "D"

    def test_drive_id_from_env_var(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MY_DRIVE_ID", "drive-from-env")
        cfg = tmp_path / "gateway.yaml"
        cfg.write_text(textwrap.dedent("""
            sharepoint:
              render_site_id: "S"
              render_drive_id_env: "MY_DRIVE_ID"
        """).strip())
        result = config.load_sharepoint_config(str(cfg))
        assert result.drive_id == "drive-from-env"

    def test_env_var_unset_raises(self, tmp_path, monkeypatch):
        monkeypatch.delenv("MISSING_VAR", raising=False)
        cfg = tmp_path / "gateway.yaml"
        cfg.write_text(textwrap.dedent("""
            sharepoint:
              render_site_id_env: "MISSING_VAR"
              render_drive_id: "D"
        """).strip())
        with pytest.raises(ValueError, match="MISSING_VAR"):
            config.load_sharepoint_config(str(cfg))


class TestLoadSharePointConfigPartial:
    def test_missing_site_id_raises(self, tmp_path):
        cfg = tmp_path / "gateway.yaml"
        cfg.write_text(textwrap.dedent("""
            sharepoint:
              render_drive_id: "D"
        """).strip())
        with pytest.raises(ValueError, match="render_site_id"):
            config.load_sharepoint_config(str(cfg))

    def test_missing_drive_id_raises(self, tmp_path):
        cfg = tmp_path / "gateway.yaml"
        cfg.write_text(textwrap.dedent("""
            sharepoint:
              render_site_id: "S"
        """).strip())
        with pytest.raises(ValueError, match="render_drive_id"):
            config.load_sharepoint_config(str(cfg))

    def test_empty_site_id_raises(self, tmp_path):
        cfg = tmp_path / "gateway.yaml"
        cfg.write_text(textwrap.dedent("""
            sharepoint:
              render_site_id: ""
              render_drive_id: "D"
        """).strip())
        with pytest.raises(ValueError, match="render_site_id"):
            config.load_sharepoint_config(str(cfg))

    def test_sharepoint_not_a_mapping_raises(self, tmp_path):
        cfg = tmp_path / "gateway.yaml"
        cfg.write_text(textwrap.dedent("""
            sharepoint: "not-a-dict"
        """).strip())
        with pytest.raises(ValueError, match="sharepoint"):
            config.load_sharepoint_config(str(cfg))
