"""Deterministic synthetic manufacturing/IoT data for the workshop.

Reference module (readable, importable). The execution path attendees actually run is the
self-contained notebook data_gen/load_to_uc.py, which inlines this logic so it works even
when the repo is not importable as workspace files.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

MODELS = ["TruLaser 3030", "TruBend 5130", "TruPunch 5000", "TruMatic 6000"]
LINES = ["Line-A", "Line-B", "Line-C"]
LOCATIONS = ["Ditzingen", "Neukirch", "Hettingen", "Grüsch"]
PRODUCTS = ["bracket", "panel", "housing", "flange", "rail"]
FAULTS = ["coolant low", "vibration alarm", "laser calibration", "belt wear", "sensor fault"]


def _machines(rng: np.random.Generator, n: int = 50) -> pd.DataFrame:
    df = pd.DataFrame({
        "machine_id": np.arange(1, n + 1),
        "model": rng.choice(MODELS, n),
        "line": rng.choice(LINES, n),
        "install_date": pd.to_datetime("2018-01-01") + pd.to_timedelta(rng.integers(0, 2500, n), unit="D"),
        "location": rng.choice(LOCATIONS, n),
    })
    df["install_date"] = df["install_date"].dt.date
    return df


def _sensor_readings(rng: np.random.Generator, machine_ids: np.ndarray, n: int = 10_000) -> pd.DataFrame:
    start = pd.Timestamp("2026-06-01")
    return pd.DataFrame({
        "reading_id": np.arange(1, n + 1),
        "machine_id": rng.choice(machine_ids, n),
        "ts": start + pd.to_timedelta(rng.integers(0, 30 * 24 * 60, n), unit="m"),
        "temperature_c": np.round(rng.normal(65, 8, n), 2),
        "vibration_mm_s": np.round(np.abs(rng.normal(2.5, 1.0, n)), 3),
        "load_pct": np.round(rng.uniform(20, 100, n), 1),
    })


def _production_orders(rng: np.random.Generator, machine_ids: np.ndarray, n: int = 200) -> pd.DataFrame:
    due = pd.Timestamp("2026-07-01") + pd.to_timedelta(rng.integers(0, 60, n), unit="D")
    return pd.DataFrame({
        "order_id": np.arange(1, n + 1),
        "machine_id": rng.choice(machine_ids, n),
        "product": rng.choice(PRODUCTS, n),
        "qty": rng.integers(10, 500, n),
        "status": rng.choice(["open", "running", "done"], n, p=[0.3, 0.4, 0.3]),
        "due_date": [d.date() for d in due],
    })


def _maintenance_tickets(rng: np.random.Generator, machine_ids: np.ndarray, n: int = 120) -> pd.DataFrame:
    opened = pd.Timestamp("2026-06-01") + pd.to_timedelta(rng.integers(0, 40 * 24 * 60, n), unit="m")
    return pd.DataFrame({
        "ticket_id": np.arange(1, n + 1),
        "machine_id": rng.choice(machine_ids, n),
        "opened_at": opened,
        "priority": rng.choice(["low", "medium", "high"], n, p=[0.5, 0.35, 0.15]),
        "status": rng.choice(["open", "closed"], n, p=[0.4, 0.6]),
        "description": rng.choice(FAULTS, n),
    })


def generate_all(seed: int = 42) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    machines = _machines(rng)
    ids = machines["machine_id"].to_numpy()
    return {
        "machines": machines,
        "sensor_readings": _sensor_readings(rng, ids),
        "production_orders": _production_orders(rng, ids),
        "maintenance_tickets": _maintenance_tickets(rng, ids),
    }
