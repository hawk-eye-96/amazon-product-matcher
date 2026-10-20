"""Turn product text into comparable pieces and decide if a listing is the same product."""
import re

# Colour words -> family. Sites name colours differently ("Onyx Black", "Mid Nvy/Wte", "Navy Blue"),
# so we compare families, not names.
COLOURS = {
    "black": "black", "blk": "black", "onyx": "black", "jet": "black", "jetblack": "black", "graphite": "black",
    "white": "white", "wht": "white", "wte": "white", "snow": "white", "ivory": "white", "offwhite": "white",
    "grey": "grey", "gray": "grey", "gry": "grey", "charcoal": "grey", "ash": "grey", "titanium": "grey",
    "silver": "silver", "metallic": "silver",
    "blue": "blue", "navy": "blue", "nvy": "blue", "midnight": "blue", "obsidian": "blue", "cobalt": "blue",
    "teal": "green", "green": "green", "olive": "green", "mint": "green", "sage": "green", "khaki": "green",
    "red": "red", "maroon": "red", "burgundy": "red", "wine": "red", "crimson": "red", "rosso": "red",
    "pink": "pink", "rose": "pink", "peach": "pink", "coral": "pink",
    "purple": "purple", "violet": "purple", "lavender": "purple", "lilac": "purple", "mauve": "purple",
    "yellow": "yellow", "amber": "yellow", "mustard": "yellow", "lemon": "yellow",
    "orange": "orange", "rust": "orange",
    "brown": "brown", "tan": "brown", "chocolate": "brown", "coffee": "brown",
    "beige": "beige", "cream": "beige", "sand": "beige", "taupe": "beige",
    "gold": "gold", "golden": "gold",
    "multicolor": "multi", "multicolour": "multi", "multi": "multi",
}

# Words that make a different product when present on only one side: S24 vs S24 FE, Court Royale vs Court Royale AC SE.
VARIANTS = {"pro", "plus", "ultra", "max", "mini", "lite", "fe", "neo", "prime", "se", "ac", "edge", "fold", "flip"}

GENERIC = set("""
for with and the of in on by to new latest edition series model version
men mens man women womens woman unisex boys girls kids boy girl adult
shoe shoes sneaker sneakers casual sports sport running tennis walking lifestyle training trainers
t shirt shirts tshirt tshirts tee tees polo polos jersey jerseys top
fit regular slim relaxed oversized cotton polyester leather suede mesh synthetic knit
round crew neck collar half full short sleeve sleeves solid printed graphic logo
smart smartphone mobile phone cellphone ai dual sim camera processor battery display amoled storage ram rom
tv television led qled oled uhd hd hdr android google tizen webos smartvision vision
inch inches cm star stars built voice assistant remote
""".split())

PHRASES = re.compile(r"\b(ultra hd|full hd|hd ready|quad hd|4k uhd|hdr ?10\+?|dolby (vision|atmos)|off white)\b")
UNITS = re.compile(r"\b\d+(?:\.\d+)?\s*(?:gb|tb|mb|cm|mm|inch|inches|in|hz|mah|mp|w|k|g)\b|\b(?:19|20)\d\d\b")
ALIASES = {"lo": "low", "hi": "high"}


def tokens(text, drop=()):
    """Model-identifying words, in order: 'Samsung Galaxy S24 5G AI Smartphone' -> ['galaxy', 's24']."""
    t = PHRASES.sub(" ", text.lower())  # before '+': "HDR10+" must not leave a "plus"
    t = re.sub(r"\b(\w*[a-z]\w*)\+", r"\1 plus ", t).replace("'s", " ")  # "S24+" is a variant; "Vision + Atmos", "150+" aren't
    t = re.sub(r"\b([a-z0-9]{3,})-([a-z0-9]{3,})\b",  # model code "FTW1-ADSJ" stays one token
               lambda m: m[1] + m[2] if is_code(m[1]) or is_code(m[2]) else m[0], t)
    t = re.sub(r"[^a-z0-9.]+", " ", t)
    t = UNITS.sub(" ", t)
    out = []
    for w in t.replace(".", " ").split():
        w = ALIASES.get(w, w)
        if w in GENERIC or w in COLOURS or w in drop or w in out:
            continue
        if len(w) <= 2 and not w.isdigit() and w not in VARIANTS:
            continue
        out.append(w)
    return out


def colour_family(text):
    """'Mid Nvy/Wte' -> 'blue', 'Cobalt Violet' -> 'purple'. Primary colour = first part, last colour word in it."""
    if not text:
        return None
    t = text.lower().replace("off white", "offwhite").replace("off-white", "offwhite")
    for part in re.split(r"[/,&+|]| and ", t):
        for w in reversed(re.findall(r"[a-z]+", part)):
            if w in COLOURS:
                return COLOURS[w]
    return None


def colour_set(text):
    """Every colour family named: 'White/Navy' -> {'white', 'blue'}."""
    t = (text or "").lower().replace("off white", "offwhite").replace("off-white", "offwhite")
    return {COLOURS[w] for w in re.findall(r"[a-z]+", t) if w in COLOURS}


def same_colour(a, b):
    """Primary colours equal, or the same two-tone in another order ('Mid Nvy/Wte' vs 'White/Navy').
    A lone 'White' against 'Navy/White' is still rejected: it may just be the all-white shoe."""
    fa, fb = colour_family(a), colour_family(b)
    return bool(fa) and (fa == fb or (len(colour_set(a)) > 1 and colour_set(a) == colour_set(b)))


def years(text):
    """Season/model year: RCB 2025 vs 2026 jersey, 2024 vs 2025 TV. tokens() drops years as noise."""
    return set(re.findall(r"\b(?:19|20)\d\d\b", text or ""))


# Same company, different names on different sites. Each maps to one name.
BRANDS = {"redmi": "xiaomi", "mi": "xiaomi", "xiaomi": "xiaomi"}


def gender(text):
    t = " " + re.sub(r"[^a-z]+", " ", (text or "").lower()) + " "
    for g, words in (("unisex", (" unisex ",)), ("women", (" women ", " womens ", " woman ", " ladies ")),
                     ("men", (" men ", " mens ", " man ")), ("kids", (" boys ", " girls ", " kids "))):
        if any(w in t for w in words):
            return g
    return None


def gb(value):
    """'8 GB' -> 8, '1 TB' -> 1024."""
    m = re.search(r"(\d+(?:\.\d+)?)\s*(gb|tb)", (value or "").lower())
    if not m:
        return None
    n = float(m.group(1))
    return int(n * 1024 if m.group(2) == "tb" else n)


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def is_code(t):
    return bool(re.search(r"\d", t)) and bool(re.search(r"[a-z]", t))


def same_code(x, y):
    """UA55U8400FULXL vs u8400f: one contains the other (sites shorten codes). But a 1-2 letter tail is a
    different variant: TCL 65Q6C vs 65Q6CS."""
    short, long_ = sorted((x, y), key=len)
    if short == long_:
        return True
    if len(short) < 4 or short not in long_:
        return False
    return not (long_.startswith(short) and len(long_) - len(short) <= 2)


def same_model(a, c, threshold):
    """Score how well candidate tokens c match Amazon tokens a. 0 = not the same model."""
    A, C = set(a), set(c)
    if any(len(x) >= 6 and is_code(x) for x in A & C):  # same full model code (UA55U8400FULXL): settled,
        return 1 + len(A & C) / len(A | C)               # whatever marketing words ("Prime Video") the titles add
    if not A or (A & VARIANTS) != (C & VARIANTS):
        return 0
    if any(t.isdigit() and t not in C for t in A):  # iPhone 15 vs 16, Air Max 90 vs SC
        return 0
    codes_a, codes_c = [t for t in A if is_code(t)], [t for t in C if is_code(t)]
    if codes_a and codes_c:
        # UA55U8400FULXL on Amazon vs u8400f in a Croma URL: one contains the other.
        hit = any(same_code(x, y) for x in codes_a for y in codes_c)
        return 1 + len(A & C) / len(A | C) if hit else 0
    recall = len(A & C) / len(A)
    return recall if recall >= threshold else 0


def score(spec, cand, variant=True):
    """spec = Amazon product, cand = a listing on another site. Both are dicts from sites.py.
    variant=False checks only brand + model (not RAM/storage, size, colour, gender): used to explain a miss."""
    b = BRANDS.get(norm(spec["brand"]), norm(spec["brand"]))
    cb = BRANDS.get(norm(cand.get("brand")), norm(cand.get("brand")))
    if not (cb and (cb == b or b in cb or cb in b)) and not norm(cand["title"]).startswith(norm(spec["brand"])):
        return 0
    y1, y2 = years(spec["title"]), years(cand["title"])
    if y1 and y2 and not y1 & y2:
        return 0
    cat = spec["category"]
    if cat == "tv" and not any(is_code(t) for t in spec["tokens"]):  # "Samsung Neo QLED 65" fits a range: don't guess
        return 0
    if cat in ("sneakers", "tshirt") and any(t.isdigit() and t not in spec["tokens"] for t in cand["tokens"]):
        return 0  # Court Royale 2, pack of 2
    if variant and not same_variant(spec, cand):
        return 0
    # Brand names inside the model ('Redmi Note 13' when the brand is Xiaomi) aren't model words.
    alias = {k for k, v in BRANDS.items() if v == b}
    return same_model([t for t in spec["tokens"] if t not in alias], [t for t in cand["tokens"] if t not in alias],
                      0.75 if cat in ("phone", "tv") else 0.6)


def same_variant(spec, cand):
    """The category's rule: phones RAM + storage, TVs screen size, fashion colour (+ gender)."""
    cat = spec["category"]
    if cat == "phone":
        return bool(spec["storage"]) and cand.get("storage") == spec["storage"] and \
            not (spec["ram"] and cand.get("ram") and cand["ram"] != spec["ram"])
    if cat == "tv":
        return bool(spec["screen"] and cand.get("screen")) and abs(cand["screen"] - spec["screen"]) <= 1
    g1, g2 = spec.get("gender"), cand.get("gender")
    return same_colour(spec.get("colour"), cand.get("colour")) and \
        not (g1 and g2 and g1 != g2 and "unisex" not in (g1, g2))


def size(n):
    return f"{n // 1024:g} TB" if n >= 1024 else f"{n} GB"


def miss_note(spec, cands):
    """Why 'not listed' when the site has the model in other variants:
    'Found this model, but only with 12 GB RAM / 256 GB.' None if the model itself isn't there."""
    cat, labels = spec["category"], []
    for c in cands:
        if not score(spec, c, variant=False):
            continue
        if cat == "phone" and c.get("storage"):
            label = (f"{c['ram']} GB RAM / " if c.get("ram") else "") + size(c["storage"])
        elif cat == "tv" and c.get("screen"):
            label = f'{c["screen"]:g}"'
        elif cat in ("sneakers", "tshirt") and c.get("colour"):
            g = c.get("gender")
            label = c["colour"].strip().title() + (f" ({g})" if g and g != spec.get("gender") and g != "unisex" else "")
        else:
            continue  # accessory or missing detail: says nothing about the variant
        if label.lower() not in (x.lower() for x in labels):
            labels.append(label)
    if not labels:
        return None
    labels.sort(key=lambda x: "(" in x)  # same gender first, then "(women)" etc.
    more = f" and {len(labels) - 3} more" if len(labels) > 3 else ""
    return f"Found this model, but only {'with' if cat == 'phone' else 'in'} {', '.join(labels[:3])}{more}."


def rank(spec, cands):
    """Candidates that are the same product, best first."""
    # Same colour first as a tie-break (phones/TVs don't require it, but it's the nicer link).
    scored = [(s + 0.01 * (c.get("colour_family") == spec["colour_family"]), c)
              for c in cands for s in [score(spec, c)] if s > 0]
    return [c for _, c in sorted(scored, key=lambda x: -x[0])]


def decide(hits, note=None):
    """hits = ranked matches with 'stock' set. Prefer a buyable one. note explains a 'not listed'."""
    if not hits:
        return "not_listed", ({"note": note} if note else None)
    for c in hits:
        if c.get("stock") == "in":
            return "in_stock", c
    return "out_of_stock", hits[0]
