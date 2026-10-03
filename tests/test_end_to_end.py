"""Parser + validator + metrics together, on the real datasets."""
import json

import pytest

from prisma import analyze_dataframe, analyze_text

STATUS = lambda gt, t: [v.status for v in analyze_text(t, gt).verdicts]   # noqa: E731


@pytest.fixture(params=["pima_gt", "kidney_gt"])
def gt(request):
    return request.getfixturevalue(request.param)


def test_roundtrip_c1_every_pair(gt):
    """Templated claims over EVERY tested numeric pair: true -> VALID, flipped -> DIRECTION, null -> RELATIONSHIP."""
    n = 0
    for p in gt.pairs.values():
        if p.claim_type != "C1":
            continue
        a, b = p.var1, p.var2
        if p.supported:
            true, flip = ("positive", "negative") if p.direction == "positive" else ("negative", "positive")
            assert STATUS(gt, f"1. {a} is {true}ly correlated with {b}.") == ["VALID"], (a, b)
            assert STATUS(gt, f"1. {a} is {flip}ly correlated with {b}.") == ["HALLUCINATION_DIRECTION"], (a, b)
        else:
            assert STATUS(gt, f"1. {a} is positively correlated with {b}.") == ["HALLUCINATION_RELATIONSHIP"], (a, b)
        n += 1
    assert n >= 28


def test_roundtrip_c1_is_symmetric_in_mention_order(gt):
    for p in list(gt.pairs.values()):
        if p.claim_type == "C1" and p.supported:
            d = p.direction
            assert STATUS(gt, f"1. {p.var2} is {d}ly correlated with {p.var1}.") == ["VALID"]


def test_roundtrip_c2_named_level(pima_gt, kidney_gt):
    cases = [(pima_gt, "Outcome", "diabetes", "1"), (kidney_gt, "classification", "CKD", "ckd")]
    for gt_, cat, phrase, level in cases:
        n = 0
        for p in gt_.pairs.values():
            if p.claim_type != "C2" or not p.supported or p.cat_var != cat:
                continue
            key = next(k for k in p.group_means if k == level or k == level + ".0")
            other = [k for k in p.group_means if k != key][0]
            higher = p.group_means[key] > p.group_means[other]
            word, flip = ("higher", "lower") if higher else ("lower", "higher")
            assert STATUS(gt_, f"1. Patients with {phrase} have {word} {p.num_var}.") == ["VALID"], p.num_var
            assert STATUS(gt_, f"1. Patients with {phrase} have {flip} {p.num_var}.") == ["HALLUCINATION_DIRECTION"], p.num_var
            n += 1
        assert n >= 5


def test_roundtrip_c3_kidney(kidney_gt):
    n = 0
    for p in kidney_gt.pairs.values():
        if p.claim_type != "C3":
            continue
        exp = "VALID" if p.supported else "HALLUCINATION_RELATIONSHIP"
        assert STATUS(kidney_gt, f"1. {p.var1} is associated with {p.var2}.") == [exp], (p.var1, p.var2)
        n += 1
    assert n >= 20


GEMMA_PIMA = """Here are 10 insights about the diabetes dataset:

1. **Glucose and Outcome:** Higher glucose levels are strongly associated with a diabetes diagnosis.
2. Age is positively correlated with the number of pregnancies.
3. Higher age is associated with lower BMI.
4. Patients with diabetes have higher BMI than those without diabetes.
5. There is no significant relationship between BloodPressure and DiabetesPedigreeFunction.
6. Insulin and SkinThickness are strongly negatively correlated.
7. The average age in the dataset is 33 years.
8. Salary is positively correlated with Age.
9. Glucose is weakly correlated with Insulin.
10. Older patients tend to have more pregnancies, with r = 0.54.
"""
EXPECT_PIMA = ["VALID", "VALID", "HALLUCINATION_RELATIONSHIP", "VALID", "VALID",
               "HALLUCINATION_DIRECTION", "VALID", "HALLUCINATION_VARIABLE",
               "HALLUCINATION_MAGNITUDE", "VALID"]


def test_realistic_pima_document(pima_gt):
    res = analyze_text(GEMMA_PIMA, pima_gt)
    assert [v.status for v in res.verdicts] == EXPECT_PIMA
    m = res.metrics
    assert m["n_claims"] == 10 and m["n_descriptive_claims"] == 1
    assert m["counts"]["VALID"] == 5 and m["n_hallucinations"] == 4      # C4 excluded from taxonomy
    assert m["hallucination_rate"] == pytest.approx(4 / 9)


GEMMA_KIDNEY = """1. Hemoglobin is strongly positively correlated with packed cell volume.
2. Patients with CKD have lower hemoglobin levels.
3. Patients with CKD have higher serum creatinine.
4. Hypertension is strongly associated with the CKD classification.
5. Sodium is positively correlated with potassium.
6. Blood pressure increases with age.
7. Patients with chronic kidney disease show higher hemoglobin than healthy patients.
8. The id column is correlated with age.
"""


def test_realistic_kidney_document(kidney_gt):
    assert STATUS(kidney_gt, GEMMA_KIDNEY) == [
        "VALID", "VALID", "VALID", "VALID", "HALLUCINATION_RELATIONSHIP", "VALID",
        "HALLUCINATION_DIRECTION", "UNVERIFIED"]


def test_ground_truth_and_text_see_the_same_cleaned_data(pima_gt):
    """G5/G1: the prompt block is generated from the same cleaned store the validator uses."""
    assert "mean=155" in pima_gt.to_prompt_block()          # Insulin mean on non-missing rows
    assert STATUS(pima_gt, "1. The mean insulin is 155.5.") == ["VALID"]


def test_analyze_dataframe_record_is_json_serialisable_and_deterministic(pima_df):
    a = analyze_dataframe(pima_df, GEMMA_PIMA)
    b = analyze_dataframe(pima_df, GEMMA_PIMA)
    ra, rb = json.dumps(a.to_record(), default=str), json.dumps(b.to_record(), default=str)
    assert ra == rb and a.to_record()["config_hash"]


def test_legacy_verdict_shape_is_what_the_frontend_reads(pima_gt):
    res = analyze_text(GEMMA_PIMA, pima_gt)
    for v in res.verdicts:
        d = v.to_legacy()
        assert isinstance(d["claim"]["confidence_score"], float)       # frontend does .toFixed()
        assert {"original_text", "direction", "strength"} <= set(d["claim"])
        assert isinstance(d["extracted_vars"], list) and "status" in d and "reason" in d
        json.dumps(d, default=str)


def test_empty_and_nonsense_llm_output_is_safe(pima_gt):
    for t in ["", "I cannot help with that.", "1. ??? !!! ...", "\x00\x01\x02"]:
        r = analyze_text(t, pima_gt)
        assert r.metrics["hallucination_rate"] == 0.0 or r.verdicts


def test_two_datasets_do_not_share_state(pima_gt, kidney_gt):
    assert STATUS(pima_gt, "1. Glucose is positively correlated with Insulin.") == ["VALID"]
    assert STATUS(kidney_gt, "1. Glucose is positively correlated with Insulin.") == ["HALLUCINATION_VARIABLE"] or \
           STATUS(kidney_gt, "1. Glucose is positively correlated with Insulin.") == ["UNVERIFIED"]
