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
- [ ] **P0** run `python phase0_freeze.py`, push `paper-v1` + tag `v0-pre-audit`
- [ ] **P1** core fix: GT engine v2, parser v2, validator v2, pytest with B1-B7 regressions (target 6-8 h)
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
> I'm continuing the Prisma project. Attached: HANDOFF.md and the paper PDF. Repo: github.com/Yazh-7z7/Prisma, branch `paper-v1`. Phase 0 is done. Start at the first unchecked phase in section 6. Follow the design decisions in section 3. Write code plus pytest tests, and keep every paper number traceable to a run log.
