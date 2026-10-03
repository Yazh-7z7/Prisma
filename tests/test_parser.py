import pytest

from prisma import parse_insights
from prisma.parser import split_clauses, split_items


def P(text, gt):
    return parse_insights(text, gt.schema, gt.cfg)


def one(text, gt):
    cs = P("1. " + text, gt)
    assert len(cs) == 1, [c.to_dict() for c in cs]
    return cs[0]


# ------------------------------------------------------------------ items
def test_items_numbered_bulleted_bold_continuation_and_preamble():
    t = """Here are the insights:
1. **Glucose and Age:** first line
   continued without terminal punctuation here.
2) Second item is long enough.
- Bullet item that is long enough.
Insight 4: Fourth item long enough.
Note: this is not a claim.
"""
    items = split_items(t)
    assert len(items) == 4
    assert "continued" in items[0] and "**" not in items[0]
    assert not any(i.lower().startswith("note") for i in items)


def test_clause_split_semicolon_and_while():
    assert len(split_clauses("A rises; B falls, while C is stable.")) == 3


def test_fallback_when_model_ignores_list_format(pima_gt):
    cs = P("Glucose is strongly correlated with Insulin. Overall this is interesting to note here.", pima_gt)
    assert [c.vars for c in cs if c.type] == [["Glucose", "Insulin"]]


def test_garbage_and_non_string_input_never_raises(pima_gt):
    for bad in ["", None, 123, "\n\n", "1.", "1. ", "🙂" * 50, "1. " + "x" * 5000, "- \n- \n"]:
        assert isinstance(parse_insights(bad, pima_gt.schema, pima_gt.cfg), list)


def test_every_item_yields_a_claim(pima_gt):
    cs = P("1. This dataset is interesting overall and worth studying.\n2. Age is correlated with BMI.", pima_gt)
    assert {c.item_index for c in cs} == {0, 1}
    assert cs[0].kind == "non_relational"


# ------------------------------------------------------------------ B2
def test_B2_average_does_not_match_age(pima_gt):
    c = one("The average value of the measurements is quite high overall.", pima_gt)
    assert "Age" not in c.vars
    assert one("The average age is 33.", pima_gt).vars == ["Age"]


def test_B2_token_boundaries_for_short_aliases(kidney_gt):
    # 'pe' / 'al' / 'su' must not fire inside words
    c = one("Patients experience several symptoms and also alternate between states.", kidney_gt)
    assert c.vars == []


# ------------------------------------------------------------------ B1
def test_B1_vars_follow_mention_order_not_dataset_order(pima_gt):
    c = one("BMI is positively correlated with Age.", pima_gt)
    assert c.vars == ["BMI", "Age"]                    # dataset order would be Age, BMI
    c = one("Outcome is associated with higher Glucose.", pima_gt)
    assert c.vars[0] == "Outcome"


def test_B1_three_variables_split_into_the_right_pairs(pima_gt):
    cs = P("1. Pregnancies is positively correlated with Age and Glucose.", pima_gt)
    assert [tuple(c.vars) for c in cs] == [("Pregnancies", "Age"), ("Pregnancies", "Glucose")]


def test_ambiguous_compound_is_flagged_not_guessed(pima_gt):
    c = one("Age, BMI, Glucose and Insulin matter for the risk profile of every patient.", pima_gt)
    assert c.ambiguous or c.type is None


def test_two_columns_without_relational_cue_is_not_a_pair_claim(pima_gt):
    c = one("Age and BMI are highly significant predictors.", pima_gt)
    assert c.ambiguous and c.type is None


# ------------------------------------------------------------------ B3
def test_B3_sentence_initial_words_are_not_ghosts(pima_gt):
    for t in ["Older patients tend to have more pregnancies.",
              "Self reported glucose is correlated with Insulin.",
              "Interestingly, patients with higher glucose tend to have higher BMI.",
              "Overall, Glucose is correlated with Insulin."]:
        assert one(t, pima_gt).ghosts == [], t


def test_B3_real_ghosts_are_detected(pima_gt):
    g = one("Salary is positively correlated with Age.", pima_gt).ghosts
    assert g and g[0].phrase == "salary" and g[0].evidence == "slot"
    g = one("Glucose is negatively correlated with patientYears.", pima_gt).ghosts
    assert g and g[0].evidence == "identifier"


def test_ghost_detection_can_be_disabled(pima_gt):
    from prisma import PrismaConfig
    cfg = PrismaConfig(ghost_slot_detection=False)
    cs = parse_insights("1. Salary is positively correlated with Age.", pima_gt.schema, cfg)
    assert cs[0].ghosts == []


def test_real_camelcase_column_is_not_a_ghost(pima_gt):
    assert one("DiabetesPedigreeFunction is correlated with Age.", pima_gt).ghosts == []
    assert one("Diabetes pedigree function is correlated with age.", pima_gt).ghosts == []


def test_typo_is_fuzzy_matched_not_ghosted(pima_gt):
    c = one("Glucse is positively correlated with Insulin.", pima_gt)
    assert c.ghosts == [] and "Glucose" in c.vars


# ------------------------------------------------------------------ B5
@pytest.mark.parametrize("text,expected", [
    ("Higher age is associated with lower BMI.", "negative"),          # the audit's exact example
    ("Higher glucose is associated with higher BMI.", "positive"),
    ("Lower age is associated with lower BMI.", "positive"),
    ("As glucose increases, insulin decreases.", "negative"),
    ("Glucose increases as insulin increases.", "positive"),
    ("Individuals with higher age have lower BMI.", "negative"),
    ("Glucose and insulin are inversely related.", "negative"),
    ("Glucose is positively correlated with insulin.", "positive"),
    ("Younger patients tend to have more pregnancies.", "negative"),
    ("Older patients tend to have more pregnancies.", "positive"),
    ("Glucose is correlated with insulin.", "unknown"),
])
def test_B5_direction_is_anchored_to_variables(text, expected, pima_gt):
    assert one(text, pima_gt).direction == expected


def test_B5_negated_cue_is_not_read_as_positive(pima_gt):
    c = one("Glucose is not positively correlated with BMI.", pima_gt)
    assert c.direction == "unknown"


def test_B5_no_diabetes_level_is_not_a_negation(pima_gt):
    c = one("Patients with no diabetes have lower glucose levels.", pima_gt)
    assert c.level == "0" and c.level_direction == "lower"


def test_B5_cues_distribute_over_coordinated_lists(pima_gt):
    cs = P("1. Age is positively correlated with BloodPressure and Pregnancies.", pima_gt)
    assert [c.direction for c in cs] == ["positive", "positive"]
    cs = P("1. Higher age is associated with lower BMI and glucose.", pima_gt)
    assert [c.direction for c in cs] == ["negative", "negative"]


@pytest.mark.parametrize("text", [
    "There is no significant relationship between Age and BMI.",
    "Age is not correlated with BMI.",
    "Age and BMI are unrelated.",
    "BMI does not differ by outcome.",
    "Average blood pressure is the same across all outcomes.",
])
def test_null_claims_detected(text, pima_gt):
    c = one(text, pima_gt)
    assert c.asserts_null and c.direction == "unknown" and c.strength == "unknown"


# ------------------------------------------------------------------ B6
def test_B6_significant_is_not_strength(pima_gt):
    c = one("Glucose is significantly correlated with Insulin.", pima_gt)
    assert c.strength == "unknown" and c.claims_significance
    c = one("Glucose and Insulin are highly significant correlated.", pima_gt)
    assert c.strength == "unknown"


@pytest.mark.parametrize("text,expected", [
    ("Glucose is strongly correlated with Insulin.", "strong"),
    ("Glucose is weakly correlated with Insulin.", "weak"),
    ("Glucose is moderately correlated with Insulin.", "moderate"),
    ("There is a weak positive correlation between Glucose and Insulin.", "weak"),
    ("Glucose is highly correlated with Insulin.", "strong"),
    ("Glucose is not strongly correlated with Insulin.", "unknown"),
])
def test_strength_cues(text, expected, pima_gt):
    assert one(text, pima_gt).strength == expected


# ------------------------------------------------------------------ numbers / levels / types
def test_numbers_extracted(pima_gt):
    c = one("Glucose and Insulin are correlated (r = 0.58, p < 0.001, n = 394).", pima_gt)
    assert c.value["r"] == 0.58 and c.value["p"] == 0.001 and c.value["n"] == 394 and c.claims_significance


def test_claim_types_from_column_kinds(pima_gt, kidney_gt):
    assert one("Glucose is correlated with Insulin.", pima_gt).type == "C1"
    assert one("Glucose is higher in diabetic patients.", pima_gt).type == "C2"
    assert one("Hypertension is associated with diabetes mellitus.", kidney_gt).type == "C3"


def test_level_resolution_and_comparison_order(pima_gt):
    c = one("Patients without diabetes have higher BMI than those with diabetes.", pima_gt)
    assert c.level == "0" and c.level_direction == "higher"        # first-named level is the subject
    c = one("Glucose is higher in diabetic than non-diabetic patients.", pima_gt)
    assert c.level == "1" and c.level_direction == "higher"


def test_excluded_column_flagged(kidney_gt):
    c = one("The id column is correlated with age.", kidney_gt)
    assert c.type is None and any("excluded" in n for n in c.notes)


def test_descriptive_claims(pima_gt):
    c = one("The average age is 33 years.", pima_gt)
    assert c.type == "C4" and c.stat_key == "mean"
    c = one("Insulin ranges from 14 to 846.", pima_gt)
    assert c.type == "C4" and set(c.value["stat_keys"]) >= {"min", "max"}
    assert one("The dataset contains 768 rows.", pima_gt).stat_key == "n_rows"
