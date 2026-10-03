"""
prisma.aliases — text normalisation + column alias map (fixes B2).

Old behaviour: substring + fuzzy ``partial_ratio >= 75`` => the word "average"
matched column ``age``.  New behaviour: every alias must match on TOKEN
BOUNDARIES, longest alias first, spans never overlap.  Fuzzy matching is only
used as a last resort for a single residual token (typos), never for mentions.
"""
from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Optional

from .models import BINARY, CATEGORICAL, Mention

# --------------------------------------------------------------------------
# Normalisation (applied ONCE to a clause; all later offsets index this text)
# --------------------------------------------------------------------------
_MD = re.compile(r"[*`#]+")
_HYPHEN_BETWEEN_LETTERS = re.compile(r"(?<=[a-z])[-/](?=[a-z])")
_WS = re.compile(r"\s+")


def normalize_text(s: str) -> str:
    s = unicodedata.normalize("NFKC", str(s))
    s = (s.replace("\u2212", "-").replace("\u2013", "-").replace("\u2014", "-")
           .replace("\u2018", "'").replace("\u2019", "'")
           .replace("\u201c", '"').replace("\u201d", '"'))
    s = s.lower()
    s = _MD.sub("", s)
    s = s.replace("_", " ")
    s = _HYPHEN_BETWEEN_LETTERS.sub(" ", s)
    return _WS.sub(" ", s).strip()


def split_camel(name: str) -> str:
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", str(name))
    s = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", s)
    return s


# words that name a level of many columns => never auto-alias them to one column
NEUTRAL_LEVEL_WORDS = frozenset({
    "yes", "no", "true", "false", "present", "notpresent", "absent", "normal",
    "abnormal", "good", "poor", "male", "female", "none", "other", "unknown",
    "low", "high", "medium",
})


@dataclass
class AliasEntry:
    text: str                       # normalised alias
    column: str
    level: Optional[str] = None
    regex: re.Pattern = field(default=None, repr=False)  # type: ignore[assignment]


class AliasMap:
    def __init__(self, entries: list[AliasEntry], all_columns: list[str]):
        # longest alias first => "blood glucose random" wins over "glucose"
        self.entries = sorted(entries, key=lambda e: (-len(e.text), e.text))
        for e in self.entries:
            e.regex = re.compile(rf"(?<![a-z0-9]){re.escape(e.text)}(?:s|es)?(?![a-z0-9])")
        self.all_columns = list(all_columns)
        self._single_words = sorted(
            {(e.text, e.column) for e in self.entries if " " not in e.text and len(e.text) >= 5}
        )

    def find_mentions(self, norm: str) -> list[Mention]:
        taken: list[tuple[int, int]] = []
        found: list[Mention] = []
        for e in self.entries:
            for m in e.regex.finditer(norm):
                s, t = m.span()
                if any(not (t <= a or s >= b) for a, b in taken):
                    continue
                taken.append((s, t))
                found.append(Mention(column=e.column, start=s, end=t,
                                     text=norm[s:t], level=e.level))
        return sorted(found, key=lambda m: m.start)

    def fuzzy_column(self, token: str, ratio: float) -> Optional[str]:
        """Typo tolerance for ONE residual token (>=5 chars) vs single-word aliases."""
        if len(token) < 5:
            return None
        best, best_col = 0.0, None
        for alias, col in self._single_words:
            if alias[0] != token[0]:
                continue
            r = difflib.SequenceMatcher(None, token, alias).ratio()
            if r > best:
                best, best_col = r, col
        return best_col if best >= ratio else None

    def known_identifiers(self) -> set[str]:
        """Lower-cased, separator-free forms of every real column name."""
        return {re.sub(r"[^a-z0-9]", "", c.lower()) for c in self.all_columns}


# --------------------------------------------------------------------------
# Presets (domain vocabulary).  Keys are normalised column names.
# --------------------------------------------------------------------------
PRESETS: dict[str, dict[str, dict[str, Any]]] = {
    "pima": {
        "pregnancies": {"aliases": ["pregnancy", "pregnancies", "number of pregnancies",
                                    "times pregnant", "pregnant"]},
        "glucose": {"aliases": ["plasma glucose", "blood glucose", "glucose concentration",
                                "glucose level", "blood sugar", "glucose"]},
        "bloodpressure": {"aliases": ["diastolic blood pressure", "diastolic", "blood pressure"]},
        "skinthickness": {"aliases": ["skin fold thickness", "triceps skin fold",
                                      "skinfold thickness", "skin thickness", "skinfold"]},
        "insulin": {"aliases": ["serum insulin", "insulin level", "insulin"]},
        "bmi": {"aliases": ["body mass index", "bmi"]},
        "diabetespedigreefunction": {"aliases": ["diabetes pedigree function", "diabetes pedigree",
                                                 "pedigree function", "pedigree", "dpf"]},
        "age": {"aliases": ["age", "older", "younger", "elderly"]},
        "outcome": {
            "aliases": ["outcome", "diabetes outcome", "diagnosis", "diabetes diagnosis",
                        "diabetes status", "diabetic status"],
            "levels": {
                "1": ["diabetic", "diabetics", "with diabetes", "has diabetes", "have diabetes",
                      "diabetes"],
                "0": ["non diabetic", "non diabetics", "nondiabetic", "not diabetic",
                      "without diabetes", "no diabetes", "healthy"],
            },
        },
    },
    "ckd": {
        "age": {"aliases": ["age", "older", "younger", "elderly"]},
        "bp": {"aliases": ["blood pressure", "bp"]},
        "sg": {"aliases": ["urine specific gravity", "specific gravity", "sg"]},
        "al": {"aliases": ["albumin", "al"]},
        "su": {"aliases": ["urine sugar", "sugar", "su"]},
        "rbc": {"aliases": ["red blood cells", "red blood cell", "rbc"]},
        "pc": {"aliases": ["pus cells", "pus cell", "pc"]},
        "pcc": {"aliases": ["pus cell clumps", "pcc"]},
        "ba": {"aliases": ["bacteria", "ba"]},
        "bgr": {"aliases": ["blood glucose random", "random blood glucose", "blood glucose",
                            "glucose", "bgr"]},
        "bu": {"aliases": ["blood urea", "urea", "bu"]},
        "sc": {"aliases": ["serum creatinine", "creatinine", "sc"]},
        "sod": {"aliases": ["sodium", "sod"]},
        "pot": {"aliases": ["potassium", "pot"]},
        "hemo": {"aliases": ["hemoglobin", "haemoglobin", "hemo", "hgb"]},
        "pcv": {"aliases": ["packed cell volume", "hematocrit", "pcv"]},
        "wc": {"aliases": ["white blood cell count", "white blood cells", "wbc", "wc"]},
        "rc": {"aliases": ["red blood cell count", "rbc count", "red cell count", "rc"]},
        "htn": {"aliases": ["hypertension", "htn"],
                "levels": {"yes": ["hypertensive", "with hypertension", "has hypertension"],
                           "no": ["normotensive", "without hypertension", "no hypertension"]}},
        "dm": {"aliases": ["diabetes mellitus", "diabetes", "dm"],
               "levels": {"yes": ["diabetic", "diabetics", "with diabetes"],
                          "no": ["non diabetic", "nondiabetic", "without diabetes", "no diabetes"]}},
        "cad": {"aliases": ["coronary artery disease", "cad"]},
        "appet": {"aliases": ["appetite", "appet"]},
        "pe": {"aliases": ["pedal edema", "edema", "pe"]},
        "ane": {"aliases": ["anemia", "anaemia", "ane"]},
        "classification": {
            "aliases": ["classification", "ckd status", "diagnosis", "kidney disease status"],
            "levels": {
                "ckd": ["chronic kidney disease", "kidney disease", "ckd"],
                "notckd": ["not ckd", "non ckd", "notckd", "no ckd", "without ckd",
                           "no kidney disease", "healthy"],
            },
        },
    },
}


def _detect_preset(columns: list[str]) -> Optional[str]:
    cols = {re.sub(r"[^a-z0-9]", "", c.lower()) for c in columns}
    best, best_frac = None, 0.0
    for name, spec in PRESETS.items():
        frac = len(set(spec) & cols) / len(spec)
        if frac > best_frac:
            best, best_frac = name, frac
    return best if best_frac >= 0.8 else None


def build_alias_map(prep: Any, extra: dict | None = None,
                    preset: str | None = "auto") -> AliasMap:
    """Alias map over EVERY original column (including excluded ones, so naming an
    identifier column is UNVERIFIED, not a ghost variable)."""
    columns: list[str] = list(prep.all_columns)
    norm_to_col = {re.sub(r"[^a-z0-9]", "", c.lower()): c for c in columns}
    entries: dict[tuple[str, Optional[str], str], AliasEntry] = {}

    def add(text: str, col: str, level: Optional[str] = None) -> None:
        t = normalize_text(text)
        if len(t) < 2:
            return
        entries.setdefault((t, level, col), AliasEntry(text=t, column=col, level=level))

    # 1. automatic aliases from the column name itself
    for c in columns:
        add(c, c)
        add(split_camel(c), c)

    # 2. automatic level aliases (string levels only, unambiguous, informative)
    seen: dict[str, set[str]] = {}
    for c, ci in prep.columns.items():
        if ci.kind in (BINARY, CATEGORICAL) and not ci.ordered:
            for lv in ci.levels:
                s = str(lv)
                if len(s) >= 3 and s.isalpha() and s.lower() not in NEUTRAL_LEVEL_WORDS:
                    seen.setdefault(s.lower(), set()).add(c)
    for s, cs in seen.items():
        if len(cs) == 1:
            c = next(iter(cs))
            lv = next(str(l) for l in prep.columns[c].levels if str(l).lower() == s)
            add(s, c, lv)

    # 3. domain preset
    chosen = _detect_preset(columns) if preset == "auto" else (preset or None)
    if chosen:
        for ncol, spec in PRESETS[chosen].items():
            col = norm_to_col.get(ncol)
            if col is None:
                continue
            for a in spec.get("aliases", []):
                add(a, col)
            for lv, names in spec.get("levels", {}).items():
                for a in names:
                    add(a, col, lv)

    # 4. caller-supplied aliases: {"ColumnName": ["alias", ...]}
    for col, names in (extra or {}).items():
        if col in columns:
            for a in names:
                add(a, col)

    # drop alias texts claimed by two different columns (ambiguous => unsafe)
    by_text: dict[str, set[str]] = {}
    for (t, _lv, _c), e in entries.items():
        by_text.setdefault(t, set()).add(e.column)
    final = [e for (t, _lv, _c), e in entries.items() if len(by_text[t]) == 1]
    return AliasMap(final, columns)
