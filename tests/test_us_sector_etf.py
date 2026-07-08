# -*- coding: utf-8 -*-
"""Tests for US sector rotation data fetching."""

import unittest
from unittest.mock import MagicMock, patch

from data_provider.us_sector_etf import (
    US_SECTOR_ETFS,
    _build_sector_item,
    format_sector_ranking_summary,
    get_us_sector_performance,
)


class TestUSSectorETFMapping(unittest.TestCase):
    """Test the sector ETF mapping definitions."""

    def test_mapping_has_expected_tickers(self) -> None:
        """Verify US_SECTOR_ETFS contains all expected tickers."""
        self.assertIn("XLK", US_SECTOR_ETFS)
        self.assertIn("XLF", US_SECTOR_ETFS)
        self.assertIn("XLV", US_SECTOR_ETFS)
        self.assertIn("XLE", US_SECTOR_ETFS)
        self.assertIn("XLY", US_SECTOR_ETFS)
        self.assertIn("XLP", US_SECTOR_ETFS)
        self.assertIn("XLU", US_SECTOR_ETFS)
        self.assertIn("XLI", US_SECTOR_ETFS)
        self.assertIn("XLB", US_SECTOR_ETFS)
        self.assertIn("XLRE", US_SECTOR_ETFS)
        self.assertIn("XLC", US_SECTOR_ETFS)
        self.assertIn("SMH", US_SECTOR_ETFS)
        self.assertIn("XSD", US_SECTOR_ETFS)
        self.assertIn("XAR", US_SECTOR_ETFS)

    def test_mapping_has_correct_structure(self) -> None:
        """Verify each entry has name and category fields."""
        for ticker, info in US_SECTOR_ETFS.items():
            with self.subTest(ticker=ticker):
                self.assertIn("name", info)
                self.assertIn("category", info)
                self.assertIsInstance(info["name"], str)
                self.assertIn(info["category"], ("core", "sub"))

    def test_total_etf_count(self) -> None:
        """Verify there are exactly 14 sector ETFs tracked."""
        self.assertEqual(len(US_SECTOR_ETFS), 14)

    def test_related_stock_sectors_are_present(self) -> None:
        """Verify sectors related to user's holdings are mapped."""
        # SMH for MU (semiconductor)
        self.assertEqual(US_SECTOR_ETFS["SMH"]["name"], "半导体")
        # XSD for SNDK (electronic semiconductor)
        self.assertEqual(US_SECTOR_ETFS["XSD"]["name"], "电子半导体(等权)")
        # XAR for RKLB (aerospace & defense)
        self.assertEqual(US_SECTOR_ETFS["XAR"]["name"], "航天与国防")


class TestBuildSectorItem(unittest.TestCase):
    """Test the _build_sector_item helper function."""

    def test_build_item_with_all_data(self) -> None:
        """Verify item structure with complete data."""
        info = {"name": "科技", "category": "core"}
        item = _build_sector_item(
            "XLK",
            info,
            close=220.50,
            prev_close=218.30,
            close_5d=210.00,
        )
        self.assertEqual(item["ticker"], "XLK")
        self.assertIn("XLK", item["name"])
        self.assertIn("科技", item["name"])
        self.assertEqual(item["category"], "core")
        self.assertEqual(item["close"], 220.50)
        # (220.50 - 218.30) / 218.30 * 100 ≈ 1.01%
        self.assertAlmostEqual(item["change_pct"], 1.01, places=1)
        # (220.50 - 210.00) / 210.00 * 100 ≈ 5.0%
        self.assertAlmostEqual(item["change_pct_5d"], 5.0, places=1)

    def test_build_item_no_close_5d(self) -> None:
        """Verify item works without 5-day data."""
        info = {"name": "金融", "category": "core"}
        item = _build_sector_item(
            "XLF",
            info,
            close=100.0,
            prev_close=99.0,
            close_5d=None,
        )
        self.assertNotIn("change_pct_5d", item)
        self.assertAlmostEqual(item["change_pct"], 1.01, places=1)

    def test_build_item_with_zero_prev_close(self) -> None:
        """Verify handling of zero prev_close (should not crash)."""
        info = {"name": "能源", "category": "core"}
        item = _build_sector_item(
            "XLE",
            info,
            close=100.0,
            prev_close=0.0,
        )
        self.assertEqual(item["change_pct"], 0.0)


class TestFormatSectorRankingSummary(unittest.TestCase):
    """Test the format_sector_ranking_summary helper."""

    def test_format_with_valid_data(self) -> None:
        """Verify formatting with valid sector items."""
        ranking = [
            {"ticker": "XLK", "change_pct": 2.5},
            {"ticker": "SMH", "change_pct": 1.8},
        ]
        result = format_sector_ranking_summary(ranking)
        self.assertIn("XLK", result)
        self.assertIn("+2.50%", result)
        self.assertIn("SMH", result)
        self.assertIn("+1.80%", result)

    def test_format_with_negative_changes(self) -> None:
        """Verify negative changes format correctly."""
        ranking = [
            {"ticker": "XLE", "change_pct": -2.3},
        ]
        result = format_sector_ranking_summary(ranking)
        self.assertIn("XLE", result)
        self.assertIn("-2.30%", result)

    def test_format_empty_list(self) -> None:
        """Verify empty list returns N/A."""
        self.assertEqual(format_sector_ranking_summary([]), "N/A")
        self.assertEqual(format_sector_ranking_summary(None), "N/A")

    def test_format_respects_limit(self) -> None:
        """Verify limit parameter truncates correctly."""
        ranking = [
            {"ticker": "A", "change_pct": 1.0},
            {"ticker": "B", "change_pct": 2.0},
            {"ticker": "C", "change_pct": 3.0},
            {"ticker": "D", "change_pct": 4.0},
        ]
        result = format_sector_ranking_summary(ranking, limit=2)
        self.assertNotIn("D", result)


class TestGetUsSectorPerformance(unittest.TestCase):
    """Test the get_us_sector_performance function."""

    @patch("yfinance.download")
    def test_successful_fetch_multiindex_format(self, mock_download: MagicMock) -> None:
        """Verify return structure with MultiIndex format (yfinance sometimes returns this)."""
        import pandas as pd

        mock_df = pd.DataFrame(
            {
                ("Close", "XLK"): [218.0, 220.0],
                ("Volume", "XLK"): [1_000_000, 2_000_000],
                ("Close", "SMH"): [150.0, 155.0],
                ("Volume", "SMH"): [500_000, 800_000],
            },
            index=pd.date_range("2026-07-03", periods=2),
        )
        mock_df.columns = pd.MultiIndex.from_tuples(
            [("Close", "XLK"), ("Volume", "XLK"), ("Close", "SMH"), ("Volume", "SMH")]
        )

        mock_download.return_value = mock_df

        result = get_us_sector_performance()
        self.assertIsNotNone(result)
        self.assertIn("top", result)
        self.assertIn("bottom", result)
        self.assertIn("all", result)
        self.assertIn("timestamp", result)
        # XLK change = (220-218)/218*100 = 0.92%, SMH = (155-150)/150*100 = 3.33%
        # So SMH should be top, XLK bottom
        self.assertEqual(result["top"][0]["ticker"], "SMH")
        self.assertEqual(result["bottom"][0]["ticker"], "XLK")

    @patch("yfinance.download")
    def test_successful_fetch_flat_format(self, mock_download: MagicMock) -> None:
        """Verify return structure with flat column format (Close_XLK style).

        This is the ACTUAL format yfinance returns in production as of 2024-2025.
        """
        import pandas as pd

        # 扁平格式：列名为 "Close_XLK", "Volume_XLK" 等
        mock_df = pd.DataFrame(
            {
                "Close_XLK": [218.0, 220.0],
                "Volume_XLK": [1_000_000, 2_000_000],
                "Close_SMH": [150.0, 155.0],
                "Volume_SMH": [500_000, 800_000],
            },
            index=pd.date_range("2026-07-03", periods=2),
        )

        mock_download.return_value = mock_df

        result = get_us_sector_performance()
        self.assertIsNotNone(result)
        self.assertIn("top", result)
        self.assertIn("bottom", result)
        self.assertIn("all", result)
        self.assertIn("timestamp", result)
        # XLK change = (220-218)/218*100 = 0.92%, SMH = (155-150)/150*100 = 3.33%
        # So SMH should be top, XLK bottom
        self.assertEqual(result["top"][0]["ticker"], "SMH")
        self.assertEqual(result["bottom"][0]["ticker"], "XLK")

    @patch("yfinance.download")
    def test_real_world_flat_format_14_tickers(self, mock_download: MagicMock) -> None:
        """Test with real-world flat format data for all 14 tickers.

        This simulates the actual yfinance response that caused the production bug.
        """
        import pandas as pd

        # 模拟真实 yfinance 返回的扁平格式（14个 ticker × 5列 OHLCV）
        data = {}
        tickers = ["XLK", "XLF", "XLV", "XLE", "XLY", "XLP", "XLU", "XLI", "XLB", "XLRE", "XLC", "SMH", "XSD", "XAR"]

        for ticker in tickers:
            data[f"Close_{ticker}"] = [100.0, 101.0]
            data[f"Volume_{ticker}"] = [1_000_000, 1_500_000]

        mock_df = pd.DataFrame(data, index=pd.date_range("2026-07-03", periods=2))
        mock_download.return_value = mock_df

        result = get_us_sector_performance()
        self.assertIsNotNone(result)
        self.assertEqual(len(result["all"]), 14)
        self.assertEqual(len(result["top"]), 5)
        self.assertEqual(len(result["bottom"]), 5)

    @patch("yfinance.download")
    def test_empty_dataframe(self, mock_download: MagicMock) -> None:
        """Verify None is returned for empty response."""
        import pandas as pd

        mock_download.return_value = pd.DataFrame()
        result = get_us_sector_performance()
        self.assertIsNone(result)

    @patch("yfinance.download")
    def test_partial_data_some_tickers_missing(self, mock_download: MagicMock) -> None:
        """Verify handling when some tickers have missing data."""
        import pandas as pd

        # 只有 2 个 ticker 有数据
        mock_df = pd.DataFrame(
            {
                "Close_XLK": [218.0, 220.0],
                "Volume_XLK": [1_000_000, 2_000_000],
                "Close_SMH": [150.0, 155.0],
                "Volume_SMH": [500_000, 800_000],
                # 其他 12 个 ticker 没有数据
            },
            index=pd.date_range("2026-07-03", periods=2),
        )

        mock_download.return_value = mock_df

        result = get_us_sector_performance()
        self.assertIsNotNone(result)
        # 只有 2 个有效 ticker
        self.assertEqual(len(result["all"]), 2)


if __name__ == "__main__":
    unittest.main()
