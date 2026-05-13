# tests/test_csv_loader.py
"""Tests for utils/csv_loader.py"""
from __future__ import annotations
import os
import tempfile
import time
import pandas as pd
import pytest
from utils.csv_loader import load_latest_backtest_csv, BacktestData, parse_strategy_allocation


def _write_fake_csv(folder: str, filename: str = "rolling_msci_strategies_results.csv") -> str:
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, filename)
    df = pd.DataFrame({
        "Window_End": ["1999-12-31", "2000-01-07"],
        "Hybrid SPY (70/15/15) CAGR": [0.169, 0.166],
        "Hybrid SPY (70/15/15) MDD":  [-0.362, -0.362],
        "Dull S&P 500 CAGR":          [0.178, 0.175],
        "Dull S&P 500 MDD":           [-0.328, -0.328],
    })
    df.to_csv(path, index=False)
    return path


def test_load_returns_none_when_no_csv_exists(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = load_latest_backtest_csv()
    assert result is None


def test_load_returns_backtest_data_from_latest_bt_folder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    folder = os.path.join(tmp_path, "data", "BT_20y_1980-01-01_to_2026-01-01_20260101_120000")
    _write_fake_csv(folder)
    result = load_latest_backtest_csv()
    assert result is not None
    data, path = result
    assert isinstance(data, BacktestData)
    assert "Hybrid SPY (70/15/15)" in data.strategies
    assert "Dull S&P 500" in data.strategies


def test_load_picks_most_recently_modified_folder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    old_folder = os.path.join(tmp_path, "data", "BT_20y_1980-01-01_to_2025-01-01_20250101_000000")
    new_folder = os.path.join(tmp_path, "data", "BT_20y_1980-01-01_to_2026-01-01_20260101_120000")
    _write_fake_csv(old_folder)
    time.sleep(0.05)
    _write_fake_csv(new_folder)
    result = load_latest_backtest_csv()
    assert result is not None
    _, path = result
    assert "20260101" in path


def test_backtest_data_separates_cagr_and_mdd_columns(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    folder = os.path.join(tmp_path, "data", "BT_20y_test_20260101_120000")
    _write_fake_csv(folder)
    result = load_latest_backtest_csv()
    assert result is not None
    data, _ = result
    assert "Hybrid SPY (70/15/15)" in data.cagr_df.columns
    assert "Hybrid SPY (70/15/15)" in data.mdd_df.columns
    assert data.cagr_df["Hybrid SPY (70/15/15)"].iloc[0] == pytest.approx(0.169)
    assert data.mdd_df["Hybrid SPY (70/15/15)"].iloc[0] == pytest.approx(-0.362)


def test_parse_strategy_allocation_hybrid_spy():
    alloc = parse_strategy_allocation("Hybrid SPY (70/15/15)")
    assert abs(alloc.get("SPY", 0) - 0.70) < 0.001
    assert abs(alloc.get("UPRO", 0) - 0.15) < 0.001
    assert abs(alloc.get("Gold", 0) - 0.15) < 0.001


def test_parse_strategy_allocation_hybrid_msci():
    alloc = parse_strategy_allocation("Hybrid MSCI (40/35/25)")
    assert abs(alloc.get("MSCI", 0) - 0.40) < 0.001
    assert abs(alloc.get("UPRO", 0) - 0.35) < 0.001
    assert abs(alloc.get("Gold", 0) - 0.25) < 0.001


def test_parse_strategy_allocation_dull_sp500():
    alloc = parse_strategy_allocation("Dull S&P 500")
    assert abs(alloc.get("SPY", 0) - 1.0) < 0.001


def test_parse_strategy_allocation_dull_msci():
    alloc = parse_strategy_allocation("Dull MSCI World")
    assert abs(alloc.get("MSCI", 0) - 1.0) < 0.001


def test_backtest_data_includes_allocations(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    folder = os.path.join(tmp_path, "data", "BT_20y_test_alloc_20260101_120000")
    _write_fake_csv(folder)
    result = load_latest_backtest_csv()
    assert result is not None
    data, _ = result
    assert hasattr(data, "allocations")
    assert isinstance(data.allocations, dict)
    assert "Hybrid SPY (70/15/15)" in data.allocations
