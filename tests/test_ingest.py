"""Unit tests for the ingest_deck() pipeline function."""
import os

import pytest
from unittest.mock import patch, MagicMock

from aippt.ingest import ingest_deck


class TestIngestDeck:
    """Tests for the reusable ingest_deck function."""

    def test_file_not_found_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            ingest_deck(str(tmp_path / "missing.pptx"))

    @patch("aippt.ingest.get_deck_by_id", return_value={"slide_count": 5})
    @patch("aippt.ingest.catalog_deck", return_value=42)
    @patch("aippt.ingest.cmd_export_images", return_value=0)
    def test_ms_token_threads_to_export_args(
        self, mock_export, mock_catalog, mock_get, tmp_path
    ):
        deck = tmp_path / "test.pptx"
        deck.touch()
        ingest_deck(
            str(deck), db_path=str(tmp_path / "test.db"),
            ms_token="bearer-tok",
            gateway_config="custom-gateway.yaml",
        )
        ns = mock_export.call_args.args[0]
        assert ns.ms_token == "bearer-tok"
        assert ns.gateway_config == "custom-gateway.yaml"

    @patch("aippt.ingest.get_deck_by_id", return_value={"slide_count": 5})
    @patch("aippt.ingest.catalog_deck", return_value=42)
    @patch("aippt.ingest.cmd_export_images", return_value=0)
    def test_basic_ingest(self, mock_export, mock_catalog, mock_get, tmp_path):
        deck = tmp_path / "test.pptx"
        deck.touch()

        result = ingest_deck(str(deck), db_path=str(tmp_path / "test.db"))

        assert result["deck_id"] == 42
        assert result["deck_name"] == "test"
        assert result["slide_count"] == 5
        assert result["images_exported"] is True
        assert result["tags_generated"] is False
        mock_export.assert_called_once()
        mock_catalog.assert_called_once()

    @patch("aippt.ingest.cmd_export_images", return_value=1)
    def test_export_failure_raises_by_default(self, mock_export, tmp_path):
        """When require_images=True (default), non-zero return raises RuntimeError."""
        deck = tmp_path / "test.pptx"
        deck.touch()

        with pytest.raises(RuntimeError, match="exit code 1"):
            ingest_deck(str(deck), db_path=str(tmp_path / "test.db"))

    @patch("aippt.ingest.cmd_export_images", side_effect=Exception("PowerShell not found"))
    def test_export_exception_raises_by_default(self, mock_export, tmp_path):
        """When require_images=True (default), export exception propagates as RuntimeError."""
        deck = tmp_path / "test.pptx"
        deck.touch()

        with pytest.raises(RuntimeError, match="PowerShell not found"):
            ingest_deck(str(deck), db_path=str(tmp_path / "test.db"))

    @patch("aippt.ingest.get_deck_by_id", return_value={"slide_count": 3})
    @patch("aippt.ingest.catalog_deck", return_value=10)
    @patch("aippt.ingest.cmd_export_images", return_value=1)
    def test_export_failure_graceful_when_not_required(self, mock_export, mock_catalog, mock_get, tmp_path):
        """When require_images=False, catalog proceeds with images_dir=None."""
        deck = tmp_path / "test.pptx"
        deck.touch()

        result = ingest_deck(str(deck), db_path=str(tmp_path / "test.db"), require_images=False)

        assert result["deck_id"] == 10
        assert result["images_exported"] is False
        assert result["images_dir"] is None
        mock_catalog.assert_called_once()
        _, kwargs = mock_catalog.call_args
        assert kwargs["images_dir"] is None

    @patch("aippt.ingest.get_deck_by_id", return_value={"slide_count": 2})
    @patch("aippt.ingest.catalog_deck", return_value=7)
    @patch("aippt.ingest.cmd_export_images", side_effect=Exception("PowerShell not found"))
    def test_export_exception_graceful_when_not_required(self, mock_export, mock_catalog, mock_get, tmp_path):
        """When require_images=False, export exception is caught and catalog proceeds."""
        deck = tmp_path / "test.pptx"
        deck.touch()

        result = ingest_deck(str(deck), db_path=str(tmp_path / "test.db"), require_images=False)

        assert result["images_exported"] is False
        assert result["images_dir"] is None
        mock_catalog.assert_called_once()

    @patch("aippt.ingest.get_deck_by_id", return_value={"slide_count": 4})
    @patch("aippt.ingest.catalog_deck", return_value=5)
    @patch("aippt.ingest.cmd_export_images", return_value=0)
    def test_default_images_dir(self, mock_export, mock_catalog, mock_get, tmp_path):
        deck = tmp_path / "my-deck.pptx"
        deck.touch()

        result = ingest_deck(str(deck))

        assert result["images_dir"] == os.path.join("images", "my-deck")

    @patch("aippt.ingest.get_deck_by_id", return_value={"slide_count": 4})
    @patch("aippt.ingest.catalog_deck", return_value=5)
    @patch("aippt.ingest.cmd_export_images", return_value=0)
    def test_custom_images_dir(self, mock_export, mock_catalog, mock_get, tmp_path):
        deck = tmp_path / "test.pptx"
        deck.touch()
        custom_dir = str(tmp_path / "custom_images")

        result = ingest_deck(str(deck), images_dir=custom_dir)

        assert result["images_dir"] == custom_dir
        export_args = mock_export.call_args[0][0]
        assert export_args.out_dir == custom_dir

    @patch("aippt.ingest.cmd_analyze", return_value=0)
    @patch("aippt.ingest.get_deck_by_id", return_value={"slide_count": 2})
    @patch("aippt.ingest.catalog_deck", return_value=3)
    @patch("aippt.ingest.cmd_export_images", return_value=0)
    def test_generate_tags(self, mock_export, mock_catalog, mock_get, mock_analyze, tmp_path):
        deck = tmp_path / "test.pptx"
        deck.touch()

        result = ingest_deck(str(deck), generate_tags=True, gateway_config="gw.yaml")

        assert result["tags_generated"] is True
        mock_analyze.assert_called_once()
        analyze_args = mock_analyze.call_args[0][0]
        assert analyze_args.mode == "tags"
        assert analyze_args.gateway_config == "gw.yaml"

    @patch("aippt.ingest.get_deck_by_id", return_value={"slide_count": 2})
    @patch("aippt.ingest.catalog_deck", return_value=3)
    @patch("aippt.ingest.cmd_export_images", return_value=0)
    def test_no_tags_by_default(self, mock_export, mock_catalog, mock_get, tmp_path):
        deck = tmp_path / "test.pptx"
        deck.touch()

        with patch("aippt.ingest.cmd_analyze") as mock_analyze:
            result = ingest_deck(str(deck))
            mock_analyze.assert_not_called()

        assert result["tags_generated"] is False

    @patch("aippt.ingest.cmd_analyze", return_value=1)
    @patch("aippt.ingest.get_deck_by_id", return_value={"slide_count": 2})
    @patch("aippt.ingest.catalog_deck", return_value=3)
    @patch("aippt.ingest.cmd_export_images", return_value=0)
    def test_tag_failure_does_not_crash(self, mock_export, mock_catalog, mock_get, mock_analyze, tmp_path):
        """Tag generation returning non-zero should not raise."""
        deck = tmp_path / "test.pptx"
        deck.touch()

        result = ingest_deck(str(deck), generate_tags=True)

        assert result["tags_generated"] is False

    @patch("aippt.ingest.get_deck_by_id", return_value={"slide_count": 3})
    @patch("aippt.ingest.catalog_deck", return_value=1)
    @patch("aippt.ingest.cmd_export_images", return_value=0)
    def test_progress_callback(self, mock_export, mock_catalog, mock_get, tmp_path):
        deck = tmp_path / "test.pptx"
        deck.touch()

        stages = []
        def cb(step, detail):
            stages.append(step)

        ingest_deck(str(deck), progress_callback=cb)

        assert "export_images" in stages
        assert "catalog" in stages
        assert "complete" in stages

    @patch("aippt.ingest.get_deck_by_id", return_value={"slide_count": 3})
    @patch("aippt.ingest.catalog_deck", return_value=1)
    @patch("aippt.ingest.cmd_export_images", return_value=0)
    def test_custom_dimensions(self, mock_export, mock_catalog, mock_get, tmp_path):
        deck = tmp_path / "test.pptx"
        deck.touch()

        ingest_deck(str(deck), width=2560, height=1440)

        export_args = mock_export.call_args[0][0]
        assert export_args.width == 2560
        assert export_args.height == 1440
