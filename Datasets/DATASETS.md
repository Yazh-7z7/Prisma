# Datasets manifest

| file | rows | cols | sha256 (first 12) |
|---|---|---|---|
| pima_diabetes.csv | 768 | 9 | 27939f6c904b |
| kidney_disease.csv | 400 | 26 | 835c57ec100d |
| heart_disease_uci.csv | 920 | 16 | 574f2fa2b430 |
| healthcare-dataset-stroke-data.csv | 5110 | 12 | 644d473b05d2 |

## Known data-quality traps (handled in Phase 1 ingestion, NOT by silent imputation)

- **Pima**: zeros in Glucose/BloodPressure/SkinThickness/Insulin/BMI mean *missing* (Insulin ~374/768, SkinThickness ~227/768). Treat as NaN.
- **Kidney (CKD)**: has an `id` column (exclude from statistics); many missing values; string columns contain stray whitespace/tabs and `?` placeholders; target is `classification`.
- **Heart UCI**: has `id` and `dataset` (site) columns; `num` is the target; several columns heavily missing.
- **Stroke**: `id` column; `bmi` has `N/A`; class imbalance (~5% positive).

## Provenance

- Pima: Smith et al. 1988 (NIDDK); copy fetched from a public mirror, header added, 768 rows verified.
- Others: UCI / Kaggle public releases; add the exact citation + license before publishing results.
