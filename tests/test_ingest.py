import numpy as np
import pandas as pd
import pytest

from prisma import IngestError, PrismaConfig, prepare


def test_no_imputation_missing_stays_nan():
    df = pd.DataFrame({"a": [1.0, np.nan, 3.0, 4.0], "b": [1.0, 2.0, 3.0, 5.0]})
    prep = prepare(df)
    assert prep.df["a"].isna().sum() == 1            # old code imputed the median


def test_G5_pima_zeros_are_missing(pima_df):
    prep = prepare(pima_df)
    z = prep.report["zeros_to_nan"]
    assert z["Insulin"] == 374 and z["SkinThickness"] == 227 and z["Glucose"] == 5
    assert prep.df["Insulin"].isna().sum() == 374
    assert (prep.df["Pregnancies"] == 0).sum() > 0   # zeros are LEGITIMATE here, must stay


def test_pima_outcome_is_binary_not_numeric(pima_df):
    assert prepare(pima_df).columns["Outcome"].kind == "binary"


def test_G5_id_columns_excluded_but_remembered():
    prep = prepare(pd.DataFrame({
        "patient_id": range(1, 41), "x": np.arange(40) % 7 + np.random.default_rng(0).normal(size=40),
        "y": np.random.default_rng(1).normal(size=40)}))
    assert "patient_id" in prep.excluded and "patient_id" not in prep.columns
    assert "patient_id" in prep.all_columns


def test_sequential_integer_column_detected_as_id():
    prep = prepare(pd.DataFrame({"row": range(100), "a": np.random.default_rng(0).normal(size=100),
                                 "b": np.random.default_rng(1).normal(size=100)}))
    assert "row" in prep.excluded


def test_kidney_whitespace_and_placeholders_cleaned():
    df = pd.read_csv("Datasets/kidney_disease.csv")
    prep = prepare(df)
    assert prep.columns["classification"].levels == ["ckd", "notckd"]   # raw has "ckd\t"
    assert prep.columns["pcv"].kind == "numeric"                         # raw has "\t43", "\t?"
    assert "id" in prep.excluded


def test_input_not_mutated(pima_df):
    before = pima_df.copy()
    prepare(pima_df)
    pd.testing.assert_frame_equal(pima_df, before)


def test_constant_and_text_columns_excluded():
    n = 60
    df = pd.DataFrame({"const": [1] * n, "txt": [f"s{i}" for i in range(n)],
                       "a": np.random.default_rng(0).normal(size=n),
                       "b": np.random.default_rng(1).normal(size=n)})
    prep = prepare(df)
    assert "constant" in prep.excluded["const"] and "free text" in prep.excluded["txt"]


@pytest.mark.parametrize("df", [pd.DataFrame(), pd.DataFrame({"a": [1]}),
                                pd.DataFrame({"a": [1, 2, 3], "b": [4, 4, 4]})])
def test_unusable_frames_raise_ingest_error(df):
    with pytest.raises(IngestError):
        prepare(df)


def test_zero_as_missing_is_configurable():
    df = pd.DataFrame({"Glucose": [0, 5, 6, 7, 9], "b": [1, 2, 3, 4, 6]})
    assert prepare(df, zero_as_missing=()).df["Glucose"].isna().sum() == 0
    assert prepare(df).df["Glucose"].isna().sum() == 1


def test_config_rejects_unknown_keys_and_hash_is_stable():
    with pytest.raises(ValueError):
        PrismaConfig.from_mapping({"alpah": 0.05})
    assert PrismaConfig().hash() == PrismaConfig().hash()
    assert PrismaConfig(alpha=0.01).hash() != PrismaConfig().hash()


def test_config_yaml_matches_code_defaults():
    """config/config.yaml `prisma:` must equal the code defaults: one source of truth, no drift."""
    from prisma import PrismaConfig
    assert PrismaConfig.from_yaml("config/config.yaml") == PrismaConfig()
