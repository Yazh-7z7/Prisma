# Prisma - Handoff & Project State
_Paste this whole file (plus the paper PDF) into any new chat/tool to resume. Update the checkboxes as you go._

## 0. Goal and deadlines
Make the **implementation** actually validate the **paper** ("Prisma: statistical grounding + CSVL for hallucination detection in LLM tabular insights", GICITE'26).
- **Camera-ready due: 5 Oct 2026** (no changes after). Talk: 6-7 Nov (online).
- Rule: **the paper's numbers must come from logged runs of the fixed code.** Never edit a number without the run log behind it.

## 1. Repo facts (https://github.com/Yazh-7z7/Prisma)
- Live backend path = `backend/` (FastAPI): `api_server.py`, `stat_engine.py`, `csvl_engine.py`, `validator.py`, `parser.py`, `llm_client.py`, `reporting.py`. Frontend = Next.js in `frontend/` (Vercel). Backend on Railway.
- `src/` + `app.py` + `main.py` = older Streamlit/CLI tree (duplicate logic; consolidate in Phase 1).
- Branches: `main` = deployed, untouched. `paper-v1` = all fix work. Tag `v0-pre-audit` = snapshot before fixes.
- Datasets in `Datasets/`: kidney (400x26), heart_uci (920x16), stroke (5110x12), **pima_diabetes.csv added in Phase 0** (768x9). See `Datasets/DATASETS.md`.
- Old runs (10-row toy table, mislabelled "stroke") are in `archive/legacy_runs/` - **do not cite**.
- No API keys were found in git history (scanned in Phase 0).

## 2. Audit findings (bugs reproduced, each needs a regression test)
| # | File | Bug | Effect |
|---|---|---|---|
| B1 | `validator.py::_validate_one` | `var1, var2 = matched_vars[0], [1]` where matches follow **dataset column order**, not mention order | wrong pair verified -> false VALID / false HALLUCINATION_RELATIONSHIP |
| B2 | `validator.py::_extract_vars` | substring + fuzzy `partial_ratio>=75` | "average" matches column `age` |
| B3 | `validator.py::_detect_ghosts` | any Capitalised non-stopword not in columns = ghost | sentence-initial words ("Older") flagged; likely the paper's "Self" example is a parser artifact |
| B4 | `stat_engine.py` vs `parser.py` | group-diff direction stored `"A > B"`, categorical `"associated"`; parser emits positive/negative | any directional group/categorical claim -> HALLUCINATION_DIRECTION |
| B5 | `parser.py::_build_claim` | positive words checked before negative; token set, no negation/scope | "higher age ... lower BMI" -> positive |
| B6 | `parser.py` | "significant" in the STRONG keyword set | false MAGNITUDE errors |
| B7 | `reporting.py` vs old `src/` | hallucination_rate is % in backend, fraction in old code | paper's 0.2% / 0.9% unit confusion possible |
| G1 | `api_server._build_summary` | Step-1 generation sees only top-5 correlations, not the full GT store | contradicts paper Sec III-C |
| G2 | `csvl_engine._compact_stats` | critique/refine see first 8 correlations (unranked), 5 group diffs w/o direction, no categorical | critic can't verify most claims |
| G3 | `csvl_engine` | critique output is never parsed; single pass; README says "loop until threshold" | not a closed loop |
| G4 | `stat_engine` | thresholds 0.2/0.5/0.8 vs validator/paper 0.3/0.6; neither is Cohen's r (0.1/0.3/0.5) | inconsistent magnitude labels |
| G5 | `stat_engine` | only significant pairs stored; no FDR; no ID-column exclusion; imputation before stats; Pima zeros not treated as missing; `\|t\|/sqrt(n)` called effect size | "tested & null" == "never tested"; spurious/biased truth |
| G6 | `llm_client` | no temperature/seed control; model IDs in README likely retired | non-reproducible runs |

## 3. Design decisions (do not relitigate)
1. One web-free core package `prisma/`; FastAPI, CLI runner, UI all import it.
2. Typed claims: `{type: C1 corr | C2 group | C3 categorical | C4 descriptive, vars_in_mention_order, direction, strength, value}`. Taxonomy applies to C1-C3; C4 reported separately.
3. GT store holds **every tested pair**: n (pairwise-complete), test, effect size, raw p, BH-FDR q, signed direction. Verdict logic: tested&null -> RELATIONSHIP; not testable -> UNVERIFIED.
4. Direction checked only where it exists (C1 sign of r; C2 higher group; none for C3/multi-level).
5. Parser v2 deterministic: token-boundary, longest-match alias map, negation handling, compound claims split or UNVERIFIED. **Evaluate the parser** (error injection).
6. Thresholds = Cohen (r .1/.3/.5; d .2/.5/.8; eta2 .01/.06/.14), single config; VALID = q<0.05 + min effect size. Fix paper text accordingly.
7. CSVL variants: **C2** paper's LLM-critic; **C3** validator-verdict feedback, k<=2 iterations.
8. Rename "confidence" -> **statistical support score**; evaluate with AUROC/calibration, state it is uncalibrated.

## 4. Architecture
```
CSV -> Ingest/Clean (zeros->NaN, drop IDs, no imputation for truth) -> GT Engine (Pearson/Spearman, Welch/ANOVA, chi2, BH-FDR)
    -> GT Store -> Generation strategy [C0 raw | C1 grounded | C2 CSVL-LLM | C3 CSVL-verifier]
    -> Claim extractor (Parser v2) -> Validator (typed lookup) -> Metrics + support score
    -> JSONL run logs (experiments/runs/) -> API / Next.js UI / paper tables
```

## 5. Experiment protocol (this produces the paper's tables)
- Conditions C0-C3; **>=20-30 seeded runs** per dataset x condition (pima, kidney first). Log: prompt, raw output, parsed claims, verdicts, model tag+digest, temperature, seed, latency. Runner must be **resumable** (append JSONL, skip finished seeds).
- Metrics: hallucination rate per category, valid, unverified, yield (#valid claims), coverage of top-k true relationships, ghost rate, latency. Report mean +/- std, bootstrap 95% CI, paired Wilcoxon (C1 vs C2).
- Instrument validation: error-injection benchmark (flip direction / inflate magnitude / ghost var / null pair), human audit of ~100 claims (2 annotators, kappa), counterfactual (sign-flipped) datasets.

## 6. Phase checklist
- [x] **P0** run `python phase0_freeze.py`, push `paper-v1` + tag `v0-pre-audit`
- [x] **P1** core fix: GT engine v2, parser v2, validator v2, pytest with B1-B7 regressions (DONE 3 Oct 2026; 128 tests; see section 9)
- [ ] **P2** CLI runner C0-C2 + Pima/CKD loaders (2-3 h)
- [ ] **P3** overnight runs (20-30 per cell)
- [ ] **P4** paper: real numbers, baseline row, mean+/-std, pipeline figure, worked example, limitations, reference fixes
- [ ] **P5** C3 variant, error injection, human audit
- [ ] **P6** counterfactual data, support-score calibration, FDR sensitivity
- [ ] **P7** more models/datasets, repo consolidation, CI, README

## 7. If time/tokens run out - priority ladder (stop at the highest rung you reach)
1. **Text-only paper fixes** (no experiments): p-value definition, Cohen thresholds, 5-vs-6 categories, remove "production-ready / any LLM / real-time / first", fix refs [1][6][9][10][13], rename confidence score, expand limitations. (~3 h)
2. **B1+B3+B4+B7 fixed + tests**, then run **C1 vs C2 on Pima and kidney, N>=10 seeds**. Report exact counts and mean+/-std. Even this beats the current evidence.
3. Add pipeline figure + one worked example claim.
4. If you cannot rerun anything: reframe the results section as a **"preliminary case study"** with only numbers you can show logs for, and say so.

## 8. Resume prompt for a new chat
> I'm continuing the Prisma project. Attached: HANDOFF.md and the paper PDF. Repo: github.com/Yazh-7z7/Prisma, branch `paper-v1`. Phases 0 and 1 are done (core package `prisma/`, 128 passing tests). Start at the first unchecked phase in section 6. Follow the design decisions in section 3. Write code plus pytest tests, and keep every paper number traceable to a run log.


## 9. Phase 1 result (done 3 Oct 2026)

**Layout.** `prisma/` is the web-free core (decision 1): `config.py` (single frozen config, `cfg.hash()` goes in every run log),
`models.py`, `ingest.py`, `ground_truth.py`, `aliases.py`, `parser.py`, `validator.py`, `support.py`, `metrics.py`, `pipeline.py`.
Entry points: `build_ground_truth(df, cfg)`, `analyze_text(llm_text, gt)`, `analyze_dataframe(df, llm_text, cfg)`; `AnalysisResult.to_record()` is the JSONL record for P2.
`backend/{parser,validator,stat_engine}.py` are now thin shims; `api_server.py`, `csvl_engine.py`, `reporting.py` call the core. `config/config.yaml` has a `prisma:` section (the only threshold source); the old `statistics:` block is marked LEGACY (src/ tree only).
Run tests: `pip install -r requirements-dev.txt && python -m pytest` (128 tests, ~3 s, no network/LLM needed).

**Bug -> fix -> test**
| # | Status | Where tested |
|---|---|---|
| B1 pair in dataset order | FIXED: vars in mention order; k>=3 clauses split into the pairs actually claimed | test_parser `test_B1_*`, test_validator `test_B1_*` |
| B2 substring/fuzzy ("average"->age) | FIXED: token-boundary longest-match aliases | `test_B2_*` |
| B3 capitalised word = ghost | FIXED: ghosts only from identifier tokens or relational slots with no column | `test_B3_*` |
| B4 direction key mismatch | FIXED: direction only where defined (C1 sign r; C2 ordered-binary sign / named level via group means; none for C3/multilevel) | `test_B4_*` |
| B5 positive-before-negative, no negation | FIXED: cues anchored to variables, negation, null claims | `test_B5_*`, `test_null_claims_detected` |
| B6 "significant" = strong | FIXED: significance flag, never strength | `test_B6_*` |
| B7 % vs fraction | FIXED: core = fractions; legacy keys percent + explicit `*_frac`/`*_pct` | test_metrics `test_B7_*` |
| G1 gen sees top-5 | FIXED: prompt = full ranked store (+ tested-null sample) | test_api `test_G1_*` |
| G2 critic sees 8 corr | FIXED: same store block | test_api `test_G2_*` |
| G3 critique never parsed / single pass | **OPEN -> P5 (C3 variant)** | - |
| G4 inconsistent thresholds | FIXED: Cohen via one config | `test_G4_*` |
| G5 only-significant store, no FDR, imputation, zeros | FIXED: all tested pairs, BH-FDR, no imputation, zeros->NaN, IDs excluded, untestable != null | test_ingest, `test_G5_*` |
| G6 no temperature/seed | **OPEN -> P2 (llm_client)** | - |

**Decisions/clarifications made inside P1 (extend section 3, same spirit)**
- Verdict logic: tested&not supported -> RELATIONSHIP; not testable -> UNVERIFIED; supported but |tier gap|>=2 vs verbal strength, or quoted r off by >0.15 -> MAGNITUDE. `supported = q<0.05 AND effect >= Cohen small`.
- One BH-FDR family = all tested pairs in the dataset. Pearson is the primary C1 test (Spearman stored, informational).
- Numeric 0/1 columns (Pima `Outcome`) are BINARY: group test (Welch d), not Pearson. Direction for "A higher with Outcome" is the sign of d.
- Null claims ("no significant relationship") are parsed (`asserts_null`): VALID if pair unsupported, else RELATIONSHIP. A two-column sentence with no relational cue ("age and BMI are predictors") is UNVERIFIED, not a pair claim.
- C4 descriptive claims (mean/min/max/range/std/missing/n_rows, 5% tolerance) are validated against the CLEANED data and reported separately (`descriptive` block; status `DESCRIPTIVE_INCORRECT`). They never enter hallucination rate. Frontend got the additive status.
- Metrics denominators: hallucination_rate = H / all non-C4 atomic claims; also `hallucination_rate_verifiable` = H/(H+VALID). Atomic claims = after splitting compound clauses; `item_index` links back to the LLM's numbered item.
- Support score = 0.6(1-q)+0.4*effect_r, effect_r = |r| | |d|/sqrt(d^2+4) | sqrt(eta2) | V; None if the pair has no store entry (old code defaulted to 0.5 and polluted averages). Uncalibrated.
- Ghost detection is heuristic and switchable (`ghost_slot_detection`, `ghost_identifier_detection`); P5 error-injection must report its precision/recall.

**Verification done.** 128 pytest tests; exhaustive templated round-trip over every pair of Pima+CKD (true->VALID, flipped->DIRECTION, null->RELATIONSHIP: 198/198 correct); 2000 fuzzed documents (7.5k claims) with zero internal errors; heart & stroke build without error; API smoke tests with stub LLM; before/after comparison against tag `v0-pre-audit` confirmed B1, B2, B3 manifest in the old code.
**Not verified (be aware).** Parser has NEVER seen real Gemma output yet - its coverage on real text is unknown (first job of P2). Frontend edits are additive TS but not compiled here (no node_modules). `git push` not done from the sandbox.

**Paper edits this phase makes mandatory (Priority-ladder rung 1; do with the run logs, not before)**
1. Sec III-A: delete "imputing missing values (median/mode)"; describe: no imputation, pairwise-complete, zeros->NaN for Pima, ID columns excluded.
2. Sec III-B: p-value definition is wrong ("probability the result occurred by chance"); thresholds attributed to Cohen (0.3/0.6) are not Cohen's: use r .1/.3/.5, d .2/.5/.8, eta2 .01/.06/.14, w .1/.3/.5; add BH-FDR; VALID = q<0.05 and >= small effect. Pima `Outcome` is binary -> group test.
3. Rename "confidence" -> statistical support score; new formula (q, effect_r); say uncalibrated; Table II "Avg Conf." column renamed/recomputed.
4. Taxonomy: six labels incl. UNVERIFIED (abstract says five); descriptive claims reported separately; null claims.
5. Sec IV-E: the "yes/no direction flagged by chi-square" finding and the "Self" ghost example come from B4/B3 and no longer occur; re-derive qualitative analysis from NEW logs only.
6. **Table II units: 0.2% and 0.9% are impossible with 10 claims (granularity is 10%); the text also says 90% valid for kidney. Treat as a unit/aggregation error (B7); recompute from logs, report `*_frac` with N.**
7. Sec III-C: CSVL critique output is parsed only in the C3 variant (P5); describe C2 honestly. Remove "production-ready / any LLM / real-time / first".

**Known limitations to state in the paper**: parser is rule-based (anchored cues, alias vocabulary: presets exist for Pima & CKD, generic camelCase/underscore aliases otherwise); compound clauses with >=3 variables are split only when structurally unambiguous, else UNVERIFIED; heart UCI `chol`/`trestbps` zeros are missing codes - add to `zero_as_missing` before using that dataset (P7).

**Next (P2)**: CLI runner (C0 raw, C1 grounded, C2 CSVL-LLM) using `analyze_text`/`to_record`; seeded, resumable JSONL; llm_client temperature/seed/model digest (G6); first run 5 real Gemma generations per dataset and inspect `ambiguous`/`non_relational`/`UNVERIFIED` rates + ghost flags by hand BEFORE launching P3.
