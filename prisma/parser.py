"""
prisma.parser — deterministic claim extractor v2 (fixes B1, B2, B3, B5, B6; decision 5).

Pipeline:  LLM text -> items -> clauses -> (mentions, ghosts, cues, numbers) -> typed Claims

Key differences from the legacy parser
  * Variables are resolved by TOKEN-BOUNDARY, longest-match aliases and kept in
    MENTION order (B1, B2).
  * Direction cues are ANCHORED to the variable they modify, so
    "higher age ... lower BMI" is negative, not positive (B5). Negated cues are
    dropped, and "no significant relationship" is parsed as a NULL claim.
  * "significant" is a significance claim, never a strength (B6).
  * Ghost variables come only from (a) identifier-like tokens (patientYears) and
    (b) relational slots with no resolvable column. Sentence-initial words
    ("Older") can never be ghosts (B3).
  * Compound clauses are split into atomic claims when the structure is
    unambiguous, otherwise flagged ``ambiguous`` -> UNVERIFIED.
  * Every list item yields >= 1 claim, so accounting is complete.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

from .aliases import normalize_text
from .config import DEFAULT_CONFIG, PrismaConfig
from .ground_truth import Schema
from .models import NUMERIC, Claim, Ghost, Mention

logger = logging.getLogger("Prisma.Parser")

# =========================================================================
# 1. Items and clauses
# =========================================================================
_NUMBERED = re.compile(
    r"^(?:\*\*)?\s*(?:insight|finding|observation|claim)?\s*#?(\d{1,3})\s*[.):]\s*(?:\*\*)?\s*(.*)$",
    re.IGNORECASE,
)
_BULLET = re.compile(r"^[-*•–]\s+(.*)$")
_NOT_A_CLAIM = re.compile(r"^(?:note|notes|disclaimer|caveat|caveats|summary)\b\s*[:\-]", re.IGNORECASE)
_TERMINAL = re.compile(r"[.!?)\"']\s*$")
_ABBREV = [("e.g.", "e\x00g\x00"), ("i.e.", "i\x00e\x00"), ("vs.", "vs\x00"),
           ("et al.", "et al\x00"), ("approx.", "approx\x00"), ("Fig.", "Fig\x00")]


def _strip_md(s: str) -> str:
    s = re.sub(r"[*`]+", "", s)
    return re.sub(r"\s+", " ", s).strip()


def split_items(text: str) -> list[str]:
    """Numbered / bulleted items, with continuation lines joined. Preamble is dropped."""
    items: list[str] = []
    cur: Optional[str] = None
    for raw in text.splitlines():
        line = re.sub(r"^[#>\s]+", "", raw.strip())
        if not line:
            continue
        m = _NUMBERED.match(line)
        b = _BULLET.match(line) if not m else None
        if m or b:
            if cur is not None:
                items.append(cur)
            cur = (m.group(2) if m else b.group(1)).strip()
            continue
        if cur is not None and not _TERMINAL.search(cur):
            cur += " " + line
    if cur is not None:
        items.append(cur)
    items = [_strip_md(i) for i in items]
    return [i for i in items if len(i) >= 8 and not _NOT_A_CLAIM.match(i)]


def split_sentences(text: str) -> list[str]:
    t = text
    for a, b in _ABBREV:
        t = t.replace(a, b)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"(])", t)
    return [p.replace("\x00", ".").strip() for p in parts if p.strip()]


_CLAUSE_SPLIT = re.compile(r";\s*|,?\s+(?:while|whereas|but|however)\s+", re.IGNORECASE)


def split_clauses(item: str) -> list[str]:
    out: list[str] = []
    for sent in split_sentences(item):
        out.extend(c.strip() for c in _CLAUSE_SPLIT.split(sent) if c and c.strip())
    return out or [item]


# =========================================================================
# 2. Lexicon
# =========================================================================
_UP_ADJ = r"higher|greater|larger|bigger|more|elevated|increased|raised|highest|high"
_DOWN_ADJ = r"lower|lesser|smaller|less|fewer|reduced|decreased|lowest|low|diminished"
_UP_VERB = r"increases?|rises?|rising|grows?|growing|climbs?|goes up|go up"
_DOWN_VERB = r"decreases?|falls?|falling|drops?|declines?|declining|goes down|go down|diminishes"
_REL_POS = r"positive(?:ly)?|direct(?:ly)?|proportional(?:ly)?|same direction"
_REL_NEG = r"negative(?:ly)?|inverse(?:ly)?|opposite|reverse"
_REL_NOUN = r"correlation|association|relationship|link|connection|difference|degree"

_STRONG = (r"strong(?:ly)?|robust(?:ly)?|substantial(?:ly)?|considerabl[ey]|pronounced|marked(?:ly)?|"
           r"tight(?:ly)?|highly(?=\s+(?:correlat|associat|relat|link|connect|depend))|"
           r"high(?=\s+(?:correlation|association|relationship|degree))")
_MODERATE = r"moderate(?:ly)?|medium|somewhat|intermediate"
_WEAK = (r"weak(?:ly)?|slight(?:ly)?|small|minor|marginal(?:ly)?|mild(?:ly)?|faint|modest(?:ly)?|"
         r"low(?=\s+(?:correlation|association|relationship))")

_RE_UP_ADJ = re.compile(rf"\b(?:{_UP_ADJ})\b(?!\s+(?:{_REL_NOUN}))")
_RE_DOWN_ADJ = re.compile(rf"\b(?:{_DOWN_ADJ})\b(?!\s+(?:{_REL_NOUN}))")
_RE_UP_VERB = re.compile(rf"\b(?:{_UP_VERB})\b")
_RE_DOWN_VERB = re.compile(rf"\b(?:{_DOWN_VERB})\b")
_RE_REL_POS = re.compile(rf"\b(?:{_REL_POS})\b")
_RE_REL_NEG = re.compile(rf"\b(?:{_REL_NEG})\b")
_RE_STRONG = re.compile(rf"\b(?:{_STRONG})")
_RE_MODERATE = re.compile(rf"\b(?:{_MODERATE})\b")
_RE_WEAK = re.compile(rf"\b(?:{_WEAK})")
_PREPS_AFTER_ADJ = ("in", "among", "amongst", "for", "than", "within", "with", "compared", "at", "across")

# words that are BOTH a column mention and a direction cue ("older" = Age, higher)
_IMPLIED_SIGN = {"older": +1, "elderly": +1, "younger": -1}

_NEGATORS = frozenset({
    "not", "no", "never", "without", "neither", "nor", "cannot", "lack", "lacks",
    "lacking", "absence",
})

_NULL_PATTERNS = [re.compile(p) for p in (
    r"\bno (?:statistically )?(?:(?:significant|clear|meaningful|notable|real|apparent|strong|linear|obvious|"
    r"measurable|substantial|evident) )*(?:correlation|association|relationship|link|difference|"
    r"connection|effect|dependence|trend)\b",
    r"\bnot (?:statistically |strongly |clearly |meaningfully |really )*"
    r"(?:significant|correlated|associated|related|linked|connected|different|dependent)\b",
    r"\bnot (?:statistically )?significantly (?:different|higher|lower|correlated|associated|related|linked)\b",
    r"\b(?:uncorrelated|unrelated|independent of|independent from)\b",
    r"\b(?:does|do|did) not (?:significantly |strongly |clearly )?"
    r"(?:differ|vary|correlate|affect|influence|predict|relate|change)\b",
    r"\b(?:doesn't|don't|didn't) (?:\w+ )?(?:differ|vary|correlate|affect|influence|predict|relate|change)\b",
    r"\b(?:negligible|trivial) (?:correlation|association|relationship|difference|effect)\b",
    r"\b(?:the same|similar|comparable|equal|identical|unchanged|constant|consistent) (?:\w+ ){0,2}"
    r"(?:across|between|among|regardless|for all|in all)\b",
    r"\b(?:regardless of|irrespective of|no matter)\b",
)]

_RE_SIGNIFICANT = re.compile(r"\bsignificant(?:ly)?\b")

# relational cue used for compound splitting
# strict cue: a sentence naming two columns must contain one of these to be read as a
# claim ABOUT THE PAIR ("predictors", "important features" etc. do not qualify)
_REL_CUE_STRICT = re.compile(
    r"\b(?:correlat\w*|associat\w*|link\w*|relat\w*|connect\w*|differ\w*|affect\w*|influenc\w*|"
    r"depend\w*|vs|versus|compared|between|than|higher|lower|greater|more|less|elevated|reduced|"
    r"increase\w*|decrease\w*|rise\w*|fall\w*|drop\w*|grow\w*|decline\w*|positive\w*|negative\w*|"
    r"inverse\w*|proportional\w*)\b"
)
# -- words that can never make a ghost variable ------------------------------
_FUNCTION_WORDS = frozenset("""
a an the of in on at to for with without from by and or as is are was were be been being that this these
those it its their there than then both also which who whom have has had having do does did not no tend tends
tended more less most least very quite rather much many few each every any all some per among amongst between
within across over under vs versus while whereas when where if so such only even just about around
approximately roughly generally typically usually often commonly overall interestingly notably importantly
surprisingly clearly furthermore additionally moreover however therefore thus can could may might would should
will shall seem seems appear appears exhibit exhibits show shows indicate indicates suggest suggests
reveal reveals demonstrate demonstrates tendency likely unlikely
""".split())
_GROUP_NOUNS = frozenset("""
patients patient people person persons individuals individual subjects subject participants participant cases
case women woman men man females female males male adults adult children child group groups those ones others
population populations sample samples cohort cohorts records record rows row observations observation entries
dataset datasets data table respondents members
""".split())
_MEASURE_WORDS = frozenset("""
level levels value values count counts measure measures measurement measurements rate rates score scores
amount amounts concentration concentrations number numbers reading readings result results average mean
median total trend trends variable variables feature features attribute attributes column columns metric
metrics parameter parameters factor factors indicator indicators target label response predictor predictors
outcome outcomes
""".split())
_MODIFIERS = frozenset("""
high higher highest low lower lowest elevated reduced increased decreased greater larger smaller bigger strong
strongly weak weakly moderate moderately significant significantly slight slightly positive positively
negative negatively inverse inversely direct directly clear clearly notable noticeable substantial
substantially marked markedly correlated correlation correlations association associations associated
relationship relationships linked related connection difference differences differ differs different
statistically closely highly modest modestly mild
""".split())
_LEVEL_WORDS = frozenset("yes no true false present absent normal abnormal good poor positive negative".split())
_IGNORED = _FUNCTION_WORDS | _GROUP_NOUNS | _MEASURE_WORDS | _MODIFIERS | _LEVEL_WORDS

# -- ghost slots -------------------------------------------------------------
_END = r"(?=\s+(?:is|are|was|were|shows?|has|have|appears?|suggests?|indicates?|reveals?|exists?|seems?)\b|[,;.:()]|$)"
_SLOT_PATTERNS: list[tuple[re.Pattern, tuple[str, ...]]] = [
    (re.compile(rf"\bbetween (?P<a>[^,;.:()]+?) and (?P<b>[^,;.:()]+?){_END}"), ("a", "b")),
    (re.compile(
        r"(?P<a>[^,;.:()]+?)\s+(?:(?:is|are|was|were|appears to be|seems to be|tends to be|tend to be)\s+)?"
        r"(?:(?:strongly|weakly|moderately|positively|negatively|inversely|significantly|highly|slightly|"
        r"closely|clearly|directly|statistically)\s+)*(?:correlated|associated|linked|related|connected)\s+"
        r"(?:with|to)\s+(?P<b>[^,;.:()]+?)(?=\s+(?:and|while|but|which|where|as|when|because|indicating|"
        r"suggesting|implying)\b|[,;.:()]|$)"), ("a", "b")),
    (re.compile(r"(?P<a>[^,;.:()]+?)\s+(?:vs|versus|compared (?:to|with))\s+(?P<b>[^,;.:()]+?)(?=[,;.:()]|$)"),
     ("a", "b")),
    # comparatives: only the compared QUANTITY (a) is a variable; b is a group descriptor
    (re.compile(r"\b(?:higher|lower|greater|more|less|elevated|reduced|increased|decreased|larger|smaller|fewer)"
                r"\s+(?P<a>[^,;.:()]+?)\s+(?:in|among|amongst|for|with|than)\s+[^,;.:()]+"), ("a",)),
    (re.compile(r"\b(?:average|mean|median|maximum|minimum|total)\s+(?:the\s+)?(?P<a>[^,;.:()]+?)\s+"
                r"(?:is|are|was|were|of|at|ranges?|stands?|equals?)\b"), ("a",)),
]
_IDENT_CAMEL = re.compile(r"\b[a-z]+(?:[A-Z][a-z0-9]*)+\b")
_IDENT_PASCAL = re.compile(r"\b(?:[A-Z][a-z0-9]+){2,}\b")
_IDENT_SNAKE = re.compile(r"\b[A-Za-z]+(?:_[A-Za-z0-9]+)+\b")

# -- numbers ---------------------------------------------------------------------
_NUM = r"[-+]?\d[\d,]*(?:\.\d+)?|[-+]?\.\d+"
_RE_NUM = re.compile(rf"(?<![\w.]){_NUM}")
_RE_R = re.compile(r"(?:\b(?:pearson |spearman )?r|ρ|\brho)\s*(?:=|:|≈|~|is|of)\s*([-+]?\d*\.?\d+)")
_RE_R2 = re.compile(r"correlation(?: coefficient)?\s*(?:\(r\)\s*)?(?:of|=|is|at|around|about|approximately|~)\s*"
                    r"([-+]?\d*\.\d+)")
_RE_P = re.compile(r"\bp(?:[- ]value)?\s*(<=|>=|<|>|=|≤|≥)\s*(\d*\.?\d+(?:e-?\d+)?)")
_RE_N = re.compile(r"\bn\s*=\s*([\d,]+)")
_RE_N2 = re.compile(r"\b(\d[\d,]*)\s+(?:rows|records|patients|observations|samples|entries|participants|"
                    r"individuals|cases|subjects|instances)\b")
_RE_D = re.compile(r"cohen'?s d\s*(?:=|of|is)?\s*([-+]?\d*\.?\d+)")

_DESC_KEYS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\brange[sd]?\b|\bfrom [-\d.]+ to [-\d.]+"), "range"),
    (re.compile(r"\b(?:standard deviation|std|sd)\b"), "std"),
    (re.compile(r"\bmedian\b"), "median"),
    (re.compile(r"\b(?:minimum|min|lowest|smallest)\b"), "min"),
    (re.compile(r"\b(?:maximum|max|highest|largest)\b"), "max"),
    (re.compile(r"\b(?:mean|average|avg)\b"), "mean"),
    (re.compile(r"\b(?:missing|incomplete)\b"), "missing"),
]
_RE_NROWS = re.compile(r"\b(?:rows|records|observations|entries|samples|instances|data points)\b")
_RE_DATASET_CTX = re.compile(r"\b(?:dataset|data set|data|table|contains?|has|have|consists?|comprises?|"
                             r"includes?|total|spans?|covers?)\b")
_RE_RELATIONAL_WORD = re.compile(r"\b(?:correlat\w*|associat\w*|between|compared|differ\w*|than|versus|vs)\b")


# =========================================================================
# 3. Cues
# =========================================================================
@dataclass
class _Cue:
    kind: str                  # value | rel | strength
    sign: int                  # +1 / -1 for value & rel; strength: 1/2/3
    pos: int
    anchor: Optional[str]      # column the cue modifies (None if unanchored)
    negated: bool = False


def _tokens_between(norm: str, a: int, b: int) -> int:
    return len(re.findall(r"[a-z0-9']+", norm[a:b]))


def _has_break(norm: str, a: int, b: int) -> bool:
    return bool(re.search(r"[,;:()]|\.(?!\d)", norm[a:b]))


def _next_token(norm: str, pos: int) -> str:
    m = re.match(r"\s*([a-z']+)", norm[pos:])
    return m.group(1) if m else ""


def _anchor(norm: str, cue: re.Match, mentions: list[Mention], mode: str) -> Optional[str]:
    """Which mention does this cue modify?  mode: 'adj' | 'verb' | 'rel'."""
    s, e = cue.span()
    following = [m for m in mentions if m.start >= e]
    preceding = [m for m in mentions if m.end <= s]

    def pick_following(max_tokens: int) -> Optional[str]:
        for m in following:
            if _tokens_between(norm, e, m.start) <= max_tokens and not _has_break(norm, e, m.start):
                return m.column
            break
        return None

    def pick_preceding(max_tokens: int) -> Optional[str]:
        for m in reversed(preceding):
            if _tokens_between(norm, m.end, s) <= max_tokens and not _has_break(norm, m.end, s):
                return m.column
            break
        return None

    if mode == "adj":
        if _next_token(norm, e) in _PREPS_AFTER_ADJ:          # "higher IN patients" -> modifies subject
            return pick_preceding(8) or pick_following(4)
        return pick_following(4) or pick_preceding(8)
    if mode == "verb":                                         # "glucose INCREASES"
        return pick_preceding(6) or pick_following(4)
    return pick_following(6) or pick_preceding(8)              # relationship words


def _negated(norm: str, pos: int, mentions: list[Mention]) -> bool:
    window_start = max(0, pos - 40)
    seg = norm[window_start:pos]
    cut = max(seg.rfind(","), seg.rfind(";"), seg.rfind(":"))
    base = window_start + (cut + 1 if cut >= 0 else 0)
    toks = [(m.start() + base, m.group(0)) for m in re.finditer(r"[a-z']+", norm[base:pos])]
    for tpos, tok in toks[-3:]:
        if any(mm.start <= tpos < mm.end for mm in mentions):  # "no diabetes" is a level, not a negation
            continue
        if tok in _NEGATORS or tok.endswith("n't"):
            return True
    return False


def _collect_cues(norm: str, mentions: list[Mention]) -> list[_Cue]:
    cues: list[_Cue] = []
    spec = [
        (_RE_UP_ADJ, "value", +1, "adj"), (_RE_DOWN_ADJ, "value", -1, "adj"),
        (_RE_UP_VERB, "value", +1, "verb"), (_RE_DOWN_VERB, "value", -1, "verb"),
        (_RE_REL_POS, "rel", +1, "rel"), (_RE_REL_NEG, "rel", -1, "rel"),
        (_RE_WEAK, "strength", 1, "rel"), (_RE_MODERATE, "strength", 2, "rel"),
        (_RE_STRONG, "strength", 3, "rel"),
    ]
    for rx, kind, sign, mode in spec:
        for m in rx.finditer(norm):
            if any(mm.start <= m.start() < mm.end for mm in mentions):
                continue                       # inside an alias ("low" in "low density ...")
            if kind == "strength" and sign == 3 and norm[m.end():].startswith(" significant"):
                continue                       # "highly significant" is a significance claim (B6)
            cues.append(_Cue(kind, sign, m.start(), _anchor(norm, m, mentions, mode),
                             _negated(norm, m.start(), mentions)))
    for mm in mentions:
        sign = _IMPLIED_SIGN.get(mm.text)
        if sign is not None:
            cues.append(_Cue("value", sign, mm.start, mm.column, _negated(norm, mm.start, mentions)))
    return sorted(cues, key=lambda c: c.pos)


# =========================================================================
# 4. Ghosts
# =========================================================================
def _detect_ghosts(raw: str, norm: str, mentions: list[Mention], schema: Schema,
                   cfg: PrismaConfig) -> tuple[list[Ghost], list[Mention]]:
    ghosts: list[Ghost] = []
    extra: list[Mention] = []
    amap = schema.aliases

    if cfg.ghost_identifier_detection:
        known = amap.known_identifiers()
        seen: set[str] = set()
        for rx in (_IDENT_CAMEL, _IDENT_PASCAL, _IDENT_SNAKE):
            for m in rx.finditer(raw):
                tok = m.group(0)
                key = re.sub(r"[^a-z0-9]", "", tok.lower())
                if key in known or key in seen:
                    continue
                nt = normalize_text(tok)
                if any(nt in mm.text for mm in mentions):
                    continue
                seen.add(key)
                ghosts.append(Ghost(tok, "identifier"))

    if cfg.ghost_slot_detection:
        for rx, groups in _SLOT_PATTERNS:
            for sm in rx.finditer(norm):
                for g in groups:
                    s, e = sm.span(g)
                    if any(not (mm.end <= s or mm.start >= e) for mm in mentions + extra):
                        continue
                    toks = re.findall(r"[a-z][a-z0-9']*", norm[s:e])
                    resid = [t for t in toks if t not in _IGNORED and len(t) >= 3]
                    if not resid:
                        continue
                    if len(resid) == 1:
                        col = amap.fuzzy_column(resid[0], cfg.fuzzy_token_ratio)
                        if col:
                            p = norm.find(resid[0], s)
                            extra.append(Mention(column=col, start=p, end=p + len(resid[0]),
                                                 text=resid[0], fuzzy=True))
                            continue
                    if len(resid) > 4:
                        continue                      # unparseable slot: do not guess
                    phrase = " ".join(resid)
                    if not any(g2.phrase.lower() == phrase for g2 in ghosts):
                        ghosts.append(Ghost(phrase, "slot"))
    return ghosts, extra


# =========================================================================
# 5. Numbers
# =========================================================================
def _to_float(x: str) -> Optional[float]:
    try:
        return float(x.replace(",", ""))
    except ValueError:
        return None


def _extract_values(norm: str) -> dict[str, Any]:
    v: dict[str, Any] = {}
    m = _RE_R.search(norm) or _RE_R2.search(norm)
    if m:
        v["r"] = _to_float(m.group(1))
    m = _RE_P.search(norm)
    if m:
        v["p_op"], v["p"] = m.group(1), _to_float(m.group(2))
    m = _RE_N.search(norm) or _RE_N2.search(norm)
    if m:
        v["n"] = _to_float(m.group(1))
    m = _RE_D.search(norm)
    if m:
        v["d"] = _to_float(m.group(1))
    # all free numbers EXCEPT those already explained as r / p / n / d
    explained = {x for k, x in v.items() if k in ("r", "p", "n", "d") and x is not None}
    nums = []
    for m in _RE_NUM.finditer(norm):
        f = _to_float(m.group(0))
        if f is not None and f not in explained:
            nums.append(f)
    v["numbers"] = nums
    return v


# =========================================================================
# 6. Clause -> claims
# =========================================================================
def _unique_in_mention_order(mentions: list[Mention], comparative: bool = False) -> list[Mention]:
    seen: dict[str, Mention] = {}
    levels: dict[str, list[str]] = {}
    for m in mentions:
        if m.level is not None and m.level not in levels.setdefault(m.column, []):
            levels[m.column].append(m.level)
        if m.column not in seen:
            seen[m.column] = m
    out = []
    for col, m in seen.items():
        lv = levels.get(col, [])
        if len(lv) == 1:
            level = lv[0]
        elif len(lv) > 1 and comparative:      # "A has higher X than B": first-named level is the subject
            level = lv[0]
        else:
            level = None
        out.append(Mention(column=col, start=m.start, end=m.end, text=m.text, level=level, fuzzy=m.fuzzy))
    return out


_REL_WORD_CUE = re.compile(
    r"\b(?:correlat\w*|associat\w*|link\w*|relat\w*|connect\w*|differ\w*|affect\w*|influenc\w*|"
    r"predict\w*|depend\w*|vs|versus|compared|between|than)\b"
)
_COMPARATIVE_CUE = re.compile(
    r"\b(?:higher|lower|greater|more|less|elevated|reduced|increase\w*|decrease\w*)\b"
)


def _form_pairs(um: list[Mention], norm: str) -> Optional[list[tuple[Mention, Mention]]]:
    """Split a clause with k>=3 variables into pairs, only when unambiguous:
         A <cue> B, C   -> (A,B), (A,C)        B, C and A <cue> D -> (B,D), (C,D)
    Relationship words ("associated") are tried before comparatives ("higher")."""
    if len(um) == 2:
        return [(um[0], um[1])]
    for rx in (_REL_WORD_CUE, _COMPARATIVE_CUE):
        for cue in rx.finditer(norm):
            before = [m for m in um if m.start < cue.start()]
            after = [m for m in um if m.start >= cue.start()]
            if len(before) == 1 and len(after) >= 2:
                return [(before[0], a) for a in after]
            if len(after) == 1 and len(before) >= 2:
                return [(b, after[0]) for b in before]
    return None


_COORD_GAP = re.compile(r"^[\s,]*(?:(?:and|or|as well as|plus)\s+)?(?:the\s+)?"
                        r"(?:(?:levels?|values?|count|measurements?)\s+)?$")


def _coord_groups(um: list[Mention], norm: str) -> list[set[str]]:
    groups: list[set[str]] = []
    prev_end = 0
    for m in um:
        if groups and _COORD_GAP.match(norm[prev_end:m.start]):
            groups[-1].add(m.column)
        else:
            groups.append({m.column})
        prev_end = m.end
    return groups


def _net(signs: list[int]) -> Optional[int]:
    s = set(signs)
    return s.pop() if len(s) == 1 else None


def _resolve_pair(pair: tuple[Mention, Mention], cues: list[_Cue], n_unique: int, schema: Schema,
                  norm: str, groups: list[set[str]]) -> dict[str, Any]:
    x, y = pair
    notes: list[str] = []

    def group_of(col: Optional[str]) -> set[str]:
        return next((g for g in groups if col in g), {col} if col else set())

    def on(c: _Cue, col: str) -> bool:           # does cue c modify column `col`?
        return col in group_of(c.anchor)

    def applies(c: _Cue) -> bool:
        return on(c, x.column) or on(c, y.column) or (c.kind != "value" and n_unique == 2)

    live = [c for c in cues if applies(c)]
    for c in live:
        if c.negated:
            notes.append(f"negated {c.kind} cue ignored")
    live = [c for c in live if not c.negated]

    # ---- direction -----------------------------------------------------
    direction = "unknown"
    rel = [c.sign for c in live if c.kind == "rel"]
    if rel:
        net = _net(rel)
        if net is None:
            notes.append("conflicting relationship cues")
        else:
            direction = "positive" if net > 0 else "negative"
    else:
        sx = _net([c.sign for c in live if c.kind == "value" and on(c, x.column)])
        sy = _net([c.sign for c in live if c.kind == "value" and on(c, y.column)])
        if sx is not None and sy is not None:
            direction = "positive" if sx * sy > 0 else "negative"
        elif sx is not None or sy is not None:
            s = sx if sx is not None else sy
            direction = "positive" if s > 0 else "negative"

    # ---- strength --------------------------------------------------------
    st = {c.sign for c in live if c.kind == "strength"}
    strength = {1: "weak", 2: "moderate", 3: "strong"}[next(iter(st))] if len(st) == 1 else "unknown"
    if len(st) > 1:
        notes.append("conflicting strength cues")

    # ---- type + level ----------------------------------------------------------
    kinds = {m.column: schema.columns[m.column].kind if m.column in schema.columns else None for m in pair}
    ctype: Optional[str]
    level = level_dir = None
    if None in kinds.values():
        ctype = None
        notes.append("column excluded from statistics: " +
                     ", ".join(f"{c} ({schema.excluded.get(c, 'unknown')})" for c, k in kinds.items() if k is None))
    elif all(k == NUMERIC for k in kinds.values()):
        ctype = "C1"
    elif any(k == NUMERIC for k in kinds.values()):
        ctype = "C2"
        num_m = x if kinds[x.column] == NUMERIC else y
        cat_m = y if num_m is x else x
        level = cat_m.level
        if level is not None:
            sn = _net([c.sign for c in cues
                       if c.kind == "value" and on(c, num_m.column) and not c.negated])
            level_dir = None if sn is None else ("higher" if sn > 0 else "lower")
    else:
        ctype = "C3"
    return {"direction": direction, "strength": strength, "type": ctype, "level": level,
            "level_direction": level_dir, "notes": notes}


def _parse_clause(item: str, raw: str, item_idx: int, clause_idx: int, schema: Schema,
                  cfg: PrismaConfig) -> list[Claim]:
    norm = normalize_text(raw)
    mentions = schema.aliases.find_mentions(norm)
    ghosts, extra = _detect_ghosts(raw, norm, mentions, schema, cfg)
    if extra:
        mentions = sorted(mentions + extra, key=lambda m: m.start)
    comparative = bool(re.search(r"\b(?:than|compared (?:to|with)|versus|vs)\b", norm))
    um = _unique_in_mention_order(mentions, comparative)

    is_null = any(p.search(norm) for p in _NULL_PATTERNS)
    sig = bool(_RE_SIGNIFICANT.search(norm)) and not is_null
    values = _extract_values(norm)
    if values.get("p") is not None and values.get("p_op") in ("<", "<=", "≤") and values["p"] <= 0.05:
        sig = sig or not is_null

    base = dict(text=item, clause=norm, item_index=item_idx, clause_index=clause_idx)

    # ---- descriptive (C4) -------------------------------------------------
    keys = [k for rx, k in _DESC_KEYS if rx.search(norm)]
    nums_all = values["numbers"] + ([values["n"]] if values.get("n") is not None else [])
    if len(um) <= 1 and not _RE_RELATIONAL_WORD.search(norm) and nums_all and not ghosts:
        if keys and len(um) == 1 and values["numbers"]:
            stat_keys = ["min", "max"] if "range" in keys else []
            stat_keys += [k for k in keys if k != "range"]
            values["stat_keys"] = stat_keys
            return [Claim(**base, kind="descriptive", type="C4", mentions=um, vars=[um[0].column],
                          value=values, stat_key=keys[0])]
        if not um and _RE_NROWS.search(norm) and _RE_DATASET_CTX.search(norm):
            values["stat_keys"] = ["n_rows"]
            values["numbers"] = nums_all
            return [Claim(**base, kind="descriptive", type="C4", mentions=[], vars=[],
                          value=values, stat_key="n_rows")]

    # ---- nothing to say about data -------------------------------------------
    if not um and not ghosts:
        return []

    cues = _collect_cues(norm, mentions)
    common = dict(asserts_null=is_null, claims_significance=sig, value=values, ghosts=ghosts)

    # ---- relational ---------------------------------------------------------------
    if len(um) < 2:
        c = Claim(**base, kind="non_relational", type=None, mentions=um, vars=[m.column for m in um],
                  **common)
        c.notes.append("fewer than two columns identified")
        return [c]

    if (len(um) == 2 and not is_null and not _REL_CUE_STRICT.search(norm)
            and not any(c.kind != "strength" for c in cues)):
        return [Claim(**base, kind="relational", type=None, mentions=um, vars=[m.column for m in um],
                      ambiguous="two columns are named but no relationship between them is asserted",
                      **common)]

    pairs = _form_pairs(um, norm)
    if pairs is None:
        c = Claim(**base, kind="relational", type=None, mentions=um, vars=[m.column for m in um],
                  ambiguous=f"compound clause with {len(um)} variables cannot be attributed to pairs",
                  **common)
        return [c]

    claims: list[Claim] = []
    for si, pair in enumerate(pairs):
        info = _resolve_pair(pair, cues, len(um), schema, norm, _coord_groups(um, norm))
        if is_null:
            info["direction"], info["strength"] = "unknown", "unknown"
        claims.append(Claim(
            **base, split_index=si if len(pairs) > 1 else 0, kind="relational", type=info["type"],
            mentions=list(pair), vars=[pair[0].column, pair[1].column],
            direction=info["direction"], strength=info["strength"], level=info["level"],
            level_direction=info["level_direction"], notes=info["notes"], **common,
        ))
    return claims


# =========================================================================
# 7. Public API
# =========================================================================
def parse_insights(llm_output: str, schema: Schema, cfg: PrismaConfig = DEFAULT_CONFIG) -> list[Claim]:
    """Parse LLM text into atomic typed claims. Never raises on bad input."""
    if not llm_output or not isinstance(llm_output, str):
        logger.warning("Empty or non-string LLM output supplied to parser.")
        return []

    items = split_items(llm_output)
    fallback = False
    if not items:                                   # model ignored the list format
        items = [s for s in split_sentences(_strip_md(llm_output)) if len(s) >= 15]
        fallback = True

    claims: list[Claim] = []
    for i, item in enumerate(items):
        produced: list[Claim] = []
        try:
            for ci, clause in enumerate(split_clauses(item)):
                produced.extend(_parse_clause(item, clause, i, ci, schema, cfg))
        except Exception as exc:                    # parser bugs must not kill a run
            logger.exception("Parser failed on item %d: %s", i, exc)
            c = Claim(text=item, clause=normalize_text(item), item_index=i, kind="non_relational")
            c.notes.append(f"parser error: {exc}")
            produced = [c]
        if not produced:
            if fallback:
                continue                            # preamble sentence, not a claim
            c = Claim(text=item, clause=normalize_text(item), item_index=i, kind="non_relational")
            c.notes.append("no column identified")
            produced = [c]
        claims.extend(produced)
    logger.info("Parser extracted %d claims from %d items.", len(claims), len(items))
    return claims
