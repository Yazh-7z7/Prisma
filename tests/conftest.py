"""Shared fixtures. The synthetic dataset has KNOWN structure so tests assert exact behaviour."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from prisma import PrismaConfig, build_ground_truth

DATA = Path(__file__).resolve().parent.parent / "Datasets"


def make_synth(n: int = 400, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    height = rng.normal(0, 1, n)
    weight = 0.8 * height + 0.6 * rng.normal(0, 1, n)            # strong positive
    sleep = -0.5 * height + 0.87 * rng.normal(0, 1, n)           # moderate negative
    noise = rng.normal(0, 1, n)                                  # independent
    arm = np.where(rng.random(n) < 0.5, "treated", "control")    # height higher when treated
    height = height + np.where(arm == "treated", 0.6, 0.0)
    colour = rng.choice(["red", "green", "blue"], n)             # unordered, independent
    flag = (rng.random(n) < 0.4).astype(int)                     # ordered binary, independent
    sparse = np.full(n, np.nan)
    sparse[:6] = rng.normal(size=6)                              # too few pairs -> untestable
    return pd.DataFrame({
        "patient_id": np.arange(1, n + 1), "height": height, "weight": weight, "sleep": sleep,
        "noise": noise, "arm": arm, "colour": colour, "flag": flag, "sparse": sparse,
    })


@pytest.fixture(scope="session")
def synth_df():
    return make_synth()


@pytest.fixture(scope="session")
def synth_gt(synth_df):
    return build_ground_truth(synth_df)


@pytest.fixture(scope="session")
def big_gt():
    """n=6000, income~tenure r~0.06: statistically detectable but negligible."""
    rng = np.random.default_rng(1)
    n = 6000
    income = rng.normal(0, 1, n)
    tenure = 0.06 * income + rng.normal(0, 1, n)
    other = rng.normal(0, 1, n)
    return build_ground_truth(pd.DataFrame({"income": income, "tenure": tenure, "other": other}))


@pytest.fixture(scope="session")
def pima_df():
    return pd.read_csv(DATA / "pima_diabetes.csv")


@pytest.fixture(scope="session")
def pima_gt(pima_df):
    return build_ground_truth(pima_df)


@pytest.fixture(scope="session")
def kidney_gt():
    return build_ground_truth(pd.read_csv(DATA / "kidney_disease.csv"))


@pytest.fixture
def cfg():
    return PrismaConfig()
