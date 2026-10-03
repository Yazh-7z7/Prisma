
from prisma import analyze_text, parse_insights, validate_claim, validate_claims
from prisma.models import Claim
from prisma.support import support_score


def V(text, gt):
    vs = analyze_text("1. " + text, gt).verdicts
    assert len(vs) == 1, [(v.status, v.claim.vars) for v in vs]
    return vs[0]


def S(text, gt):
    return V(text, gt).status


# ------------------------------------------------------------------ B1
def test_B1_verified_pair_is_the_mentioned_pair(pima_gt):
    vs = analyze_text("1. Pregnancies is positively correlated with Age and Glucose.", pima_gt).verdicts
    got = [{t["var1"], t["var2"]} for t in (v.truth for v in vs)]
    assert got == [{"Pregnancies", "Age"}, {"Pregnancies", "Glucose"}]
    assert vs[0].status == "VALID"                                    # r = 0.54
    assert vs[1].status == "VALID"                                    # r = 0.13, positive, weak


def test_B1_wrong_pair_cannot_validate_a_claim(pima_gt):
    # Age-BMI is null; Age-Pregnancies is strong. The claim names Age and BMI.
    assert S("Age is positively correlated with BMI.", pima_gt) == "HALLUCINATION_RELATIONSHIP"


# ------------------------------------------------------------------ B4
def test_B4_directional_claim_on_group_difference_is_not_auto_hallucination(kidney_gt):
    # unordered string binary: no sign exists, so "positive" must not be penalised
    v = V("Hemoglobin is positively associated with the CKD classification.", kidney_gt)
    assert v.status == "VALID" and v.checks["direction_checked"] is False


def test_B4_directional_claim_on_categorical_association_is_not_penalised(kidney_gt):
    v = V("Hypertension is positively associated with diabetes mellitus.", kidney_gt)
    assert v.status == "VALID"


def test_B4_direction_checked_where_it_exists(pima_gt):
    assert S("Glucose is positively associated with Outcome.", pima_gt) == "VALID"
    assert S("Glucose is negatively associated with Outcome.", pima_gt) == "HALLUCINATION_DIRECTION"


def test_B4_named_level_direction_checked_via_group_means(kidney_gt, pima_gt):
    assert S("Patients with CKD have lower hemoglobin.", kidney_gt) == "VALID"
    assert S("Patients with CKD have higher hemoglobin.", kidney_gt) == "HALLUCINATION_DIRECTION"
    assert S("Patients with diabetes have lower glucose levels.", pima_gt) == "HALLUCINATION_DIRECTION"
    assert S("Patients without diabetes have higher BMI than those with diabetes.", pima_gt) == "HALLUCINATION_DIRECTION"
    assert S("Patients with diabetes have higher BMI than those without diabetes.", pima_gt) == "VALID"


# ------------------------------------------------------------------ G5 verdict logic
def test_tested_null_is_relationship_hallucination(pima_gt):
    v = V("Age is positively correlated with BMI.", pima_gt)
    assert v.status == "HALLUCINATION_RELATIONSHIP" and "No supported relationship" in v.reason


def test_not_testable_is_unverified_never_null(synth_gt):
    v = V("Sparse is positively correlated with height.", synth_gt)
    assert v.status == "UNVERIFIED" and "could not be tested" in v.reason


def test_significant_but_negligible_is_not_valid(big_gt):
    v = V("Income is positively correlated with tenure.", big_gt)
    assert v.status == "HALLUCINATION_RELATIONSHIP" and "negligible" in v.reason


def test_excluded_identifier_column_is_unverified_not_ghost(kidney_gt):
    assert S("The id column is correlated with age.", kidney_gt) == "UNVERIFIED"


def test_ghost_variable(pima_gt):
    assert S("Salary is positively correlated with Age.", pima_gt) == "HALLUCINATION_VARIABLE"
    assert S("Glucose is negatively correlated with patientYears.", pima_gt) == "HALLUCINATION_VARIABLE"


def test_single_variable_claim_unverified(pima_gt):
    assert S("Glucose is an interesting and important variable in this data.", pima_gt) == "UNVERIFIED"


# ------------------------------------------------------------------ direction / magnitude
def test_direction_hallucination_c1(pima_gt):
    v = V("Insulin and SkinThickness are negatively correlated.", pima_gt)
    assert v.status == "HALLUCINATION_DIRECTION" and "positive" in v.reason


def test_B5_end_to_end_audit_example(pima_gt):
    # "higher age ... lower BMI" used to be parsed positive.  Age-BMI is null in Pima, so it is a
    # RELATIONSHIP hallucination; on a pair with a real positive effect it must be a DIRECTION one.
    assert S("Higher glucose is associated with lower pregnancies.", pima_gt) == "HALLUCINATION_DIRECTION"
    assert S("Higher age is associated with higher pregnancies.", pima_gt) == "VALID"


def test_magnitude_weak_vs_strong_is_flagged(pima_gt):
    assert S("Glucose is weakly correlated with Insulin.", pima_gt) == "HALLUCINATION_MAGNITUDE"   # r=.58
    assert S("SkinThickness is strongly correlated with BMI.", pima_gt) == "VALID"                  # r=.65


def test_magnitude_adjacent_tiers_not_flagged(pima_gt):
    # moderate claim vs strong truth differs by ONE tier -> borderline, not penalised (paper: only serious)
    assert S("Glucose is moderately correlated with Insulin.", pima_gt) == "VALID"
    assert S("Age is strongly correlated with BloodPressure.", pima_gt) == "VALID"   # r=.33 moderate; gap 1


def test_quoted_r_must_be_close(pima_gt):
    assert S("Glucose and Insulin are correlated (r = 0.58).", pima_gt) == "VALID"
    v = V("Glucose and Insulin are correlated (r = 0.20).", pima_gt)
    assert v.status == "HALLUCINATION_MAGNITUDE" and "Quoted r" in v.reason


def test_null_claims(pima_gt):
    assert S("There is no significant correlation between Age and BMI.", pima_gt) == "VALID"
    v = V("There is no significant correlation between Glucose and Insulin.", pima_gt)
    assert v.status == "HALLUCINATION_RELATIONSHIP" and v.checks["null_claim"]


# ------------------------------------------------------------------ descriptive
def test_descriptive_claims_are_validated_separately(pima_gt):
    assert S("The average age is 33 years.", pima_gt) == "VALID"
    assert S("The average age is 50 years.", pima_gt) == "DESCRIPTIVE_INCORRECT"
    assert S("Insulin has 374 missing values.", pima_gt) == "VALID"
    assert S("The dataset contains 768 rows.", pima_gt) == "VALID"
    assert S("The dataset contains 1000 rows.", pima_gt) == "DESCRIPTIVE_INCORRECT"
    assert S("Insulin ranges from 14 to 846.", pima_gt) == "VALID"
    assert S("The mean glucose is 121.7 and the standard deviation is 30.5.", pima_gt) == "VALID"
    assert S("The mean glucose is 99 and the standard deviation is 30.5.", pima_gt) == "DESCRIPTIVE_INCORRECT"


def test_G5_descriptive_uses_cleaned_data_not_zero_polluted(pima_gt):
    # raw Insulin mean (zeros included) is 79.8; the cleaned mean is 155.5
    assert S("The mean insulin is 155.5.", pima_gt) == "VALID"
    assert S("The mean insulin is 79.8.", pima_gt) == "DESCRIPTIVE_INCORRECT"


# ------------------------------------------------------------------ robustness / support
def test_validator_never_raises_and_records_error(pima_gt, monkeypatch):
    import prisma.validator as vmod
    monkeypatch.setattr(vmod, "_check_direction", lambda *a, **k: 1 / 0)
    c = parse_insights("1. Glucose is positively correlated with Insulin.", pima_gt.schema)[0]
    v = validate_claim(c, pima_gt)
    assert v.status == "UNVERIFIED" and v.error and "division" in v.error


def test_validate_claims_handles_empty_and_handbuilt_claims(pima_gt):
    assert validate_claims([], pima_gt) == []
    v = validate_claim(Claim(text="x", clause="x", item_index=0), pima_gt)
    assert v.status == "UNVERIFIED"


def test_support_score_formula_and_ordering(pima_gt):
    strong = pima_gt.lookup("SkinThickness", "BMI")
    null = pima_gt.lookup("Age", "BMI")
    s_strong, s_null = support_score(strong), support_score(null)
    assert 0.01 <= s_null < s_strong <= 0.99
    expected = round(min(max(0.6 * (1 - strong.q) + 0.4 * strong.effect_r, 0.01), 0.99), 3)
    assert s_strong == expected


def test_support_is_none_when_no_ground_truth_entry(pima_gt):
    assert V("Salary is positively correlated with Age.", pima_gt).support is None
    assert V("Glucose is an important variable in this dataset.", pima_gt).support is None
