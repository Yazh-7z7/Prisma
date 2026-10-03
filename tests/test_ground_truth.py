
import numpy as np
import pandas as pd
from scipy import stats

from prisma import PrismaConfig, build_ground_truth
from prisma.ground_truth import tier_of


def test_G4_cohen_tiers_single_config():
    r = PrismaConfig().r_thresholds
    assert r == (0.1, 0.3, 0.5)
    assert [tier_of(v, r) for v in (0.05, 0.1, 0.29, 0.3, 0.49, 0.5, -0.7)] == [0, 1, 1, 2, 2, 3, 3]
    assert PrismaConfig().d_thresholds == (0.2, 0.5, 0.8)
    assert PrismaConfig().eta2_thresholds == (0.01, 0.06, 0.14)


def test_G4_pima_glucose_age_is_weak_under_cohen(pima_gt):
    p = pima_gt.lookup("Glucose", "Age")           # r = 0.267: old 0.2/0.5 scheme said "weak" only by luck
    assert p.tier_name == "weak" and 0.25 < p.effect < 0.29


def test_G5_every_tested_pair_is_stored_including_null(pima_gt):
    assert pima_gt.n_tests == 36                    # C(8,2) + 8 numeric x Outcome
    null = pima_gt.lookup("Age", "BMI")
    assert null is not None and not null.supported and null.q > 0.05
    assert any(not p.supported for p in pima_gt.pairs.values())


def test_G5_untestable_is_recorded_not_null(synth_gt):
    assert synth_gt.lookup("sparse", "height") is None
    reason = synth_gt.untestable_reason("sparse", "height")
    assert reason and "pairwise-complete" in reason


def test_pairwise_complete_n_reported(pima_gt):
    assert pima_gt.lookup("Insulin", "Glucose").n < 768   # NaN-zeros dropped pairwise


def test_bh_fdr_matches_scipy_and_never_decreases_p(pima_gt):
    ps = np.array([p.p for p in pima_gt.pairs.values()])
    qs = np.array([p.q for p in pima_gt.pairs.values()])
    np.testing.assert_allclose(qs, stats.false_discovery_control(ps, method="bh"))
    assert (qs >= ps - 1e-15).all()


def test_significant_but_negligible_effect_not_supported(big_gt):
    p = big_gt.lookup("income", "tenure")
    assert p.q < 0.05 and p.tier == 0 and not p.supported


def test_known_structure_recovered(synth_gt):
    assert synth_gt.lookup("height", "weight").supported
    assert synth_gt.lookup("height", "weight").tier_name == "strong"
    s = synth_gt.lookup("height", "sleep")
    assert s.direction == "negative" and s.supported
    assert not synth_gt.lookup("height", "noise").supported
    assert not synth_gt.lookup("colour", "flag").supported


def test_c2_group_test_direction_and_higher_group(synth_gt, pima_gt):
    a = synth_gt.lookup("height", "arm")
    assert a.claim_type == "C2" and a.higher_group == "treated"
    assert a.direction is None                      # unordered string binary: no sign defined
    g = pima_gt.lookup("Glucose", "Outcome")
    assert g.direction == "positive" and g.higher_group in ("1", "1.0") and g.effect_kind == "d"


def test_multilevel_group_uses_eta2_and_has_no_direction(synth_gt):
    p = synth_gt.lookup("height", "colour")
    assert p.test == "anova" and p.effect_kind == "eta2" and p.direction is None


def test_c3_association_and_ordered_phi_sign(kidney_gt):
    p = kidney_gt.lookup("htn", "classification")
    assert p.claim_type == "C3" and p.supported and p.cramers_v > 0.5
    assert p.direction is None                       # string levels: unordered


def test_deterministic(synth_df):
    a, b = build_ground_truth(synth_df), build_ground_truth(synth_df)
    assert {k: (v.p, v.q) for k, v in a.pairs.items()} == {k: (v.p, v.q) for k, v in b.pairs.items()}


def test_support_pairs_ranked_by_tier_then_effect(pima_gt):
    sp = pima_gt.supported_pairs()
    assert sp[0].tier == 3 and all(sp[i].tier >= sp[i + 1].tier for i in range(len(sp) - 1))


def test_G1_prompt_block_is_ranked_complete_and_has_nulls(pima_gt):
    block = pima_gt.to_prompt_block()
    assert "SUPPORTED RELATIONSHIPS" in block and "TESTED BUT NOT SUPPORTED" in block
    section = block.split("SUPPORTED RELATIONSHIPS")[1].splitlines()[1]
    top = pima_gt.supported_pairs()[0]
    assert top.var1 in section and top.var2 in section       # strongest first, not store order
    assert "Insulin" in block and "missing=374" in block     # same cleaned data the validator uses


def test_legacy_dict_shape(pima_gt):
    d = pima_gt.to_legacy_dict()
    assert {"summary", "correlations", "group_differences", "categorical_associations", "pairs"} <= set(d)
    assert d["correlations"] and "pearson" in d["correlations"][0] and "confidence" in d["correlations"][0]
    import json
    json.dumps(d, default=str)                       # must be serialisable


def test_tiny_n_pairs_not_tested():
    df = pd.DataFrame({"a": [1, 2, 3, 4, 5, 6.0], "b": [2, 1, 4, 3, 6, 5.0], "c": [1, 3, 2, 5, 4, 6.0]})
    gt = build_ground_truth(df, PrismaConfig(min_pair_n=10))
    assert gt.n_tests == 0 and len(gt.untestable) == 3
