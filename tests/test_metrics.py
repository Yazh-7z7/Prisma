from prisma import analyze_text, compute_metrics, to_legacy_metrics
from prisma.models import Claim, Verdict


def mk(status, ctype="C1", support=0.5, item=0):
    c = Claim(text="t", clause="t", item_index=item, type=ctype)
    return Verdict(claim=c, status=status, reason="", support=support)


def test_B7_fraction_and_percent_are_explicit():
    vs = [mk("VALID")] * 9 + [mk("HALLUCINATION_DIRECTION")]
    m = compute_metrics(vs)
    assert m["hallucination_rate"] == 0.1                           # core: fraction
    leg = to_legacy_metrics(m)
    assert leg["hallucination_rate"] == 10.0                        # legacy dashboard: percent
    assert leg["hallucination_rate_pct"] == 10.0 and leg["hallucination_rate_frac"] == 0.1
    assert leg["units"]["hallucination_rate"] == "percent"


def test_B7_rate_granularity_with_ten_claims():
    # With N=10 claims a rate can only be a multiple of 10%.  The paper reports 0.2% and 0.9%,
    # which is impossible for N=10 — this test documents why units must be explicit.
    for k in range(11):
        vs = [mk("HALLUCINATION_DIRECTION")] * k + [mk("VALID")] * (10 - k)
        assert abs(compute_metrics(vs)["hallucination_rate"] * 10 - k) < 1e-9
    assert 0.002 not in {k / 10 for k in range(11)} and 0.009 not in {k / 10 for k in range(11)}


def test_descriptive_claims_excluded_from_taxonomy():
    vs = [mk("VALID"), mk("HALLUCINATION_MAGNITUDE"), mk("VALID", "C4"), mk("DESCRIPTIVE_INCORRECT", "C4")]
    m = compute_metrics(vs)
    assert m["n_taxonomy_claims"] == 2 and m["hallucination_rate"] == 0.5
    assert m["descriptive"] == {"n": 2, "valid": 1, "incorrect": 1, "unverified": 0, "incorrect_rate": 0.5}
    assert sum(m["counts"].values()) == 2


def test_verifiable_rate_excludes_unverified_and_support_ignores_none():
    vs = [mk("VALID", support=0.8), mk("HALLUCINATION_RELATIONSHIP", support=0.4),
          mk("UNVERIFIED", support=None), mk("UNVERIFIED", support=None)]
    m = compute_metrics(vs)
    assert m["hallucination_rate"] == 0.25 and m["hallucination_rate_verifiable"] == 0.5
    assert m["unverified_rate"] == 0.5 and abs(m["avg_support"] - 0.6) < 1e-9 and m["n_with_support"] == 2


def test_empty_input_and_legacy_shape():
    m = compute_metrics([])
    assert m["n_claims"] == 0 and m["hallucination_rate"] == 0.0 and m["avg_support"] is None
    leg = to_legacy_metrics(m)
    for k in ("total_claims", "valid_claims", "hallucination_rate", "validity_score",
              "taxonomy_distribution", "avg_confidence", "confidence_by_label"):
        assert k in leg


def test_ghost_rate_and_category_rates():
    vs = [mk("HALLUCINATION_VARIABLE", None), mk("VALID"), mk("VALID"), mk("VALID")]
    m = compute_metrics(vs)
    assert m["ghost_rate"] == 0.25 and m["category_rates"]["HALLUCINATION_VARIABLE"] == 0.25


def test_metrics_accept_legacy_dict_records(pima_gt):
    res = analyze_text("1. Glucose is positively correlated with Insulin.\n2. The average age is 33.", pima_gt)
    legacy = [v.to_legacy() for v in res.verdicts]
    a, b = compute_metrics(legacy), compute_metrics(res.verdicts)
    assert a["n_valid"] == b["n_valid"] == 1                     # taxonomy VALID only (C1)
    assert a["descriptive"]["valid"] == b["descriptive"]["valid"] == 1   # C4 reported separately
