"""Run: python3 test_match.py  — cases taken from real Amazon/Flipkart/Myntra/Croma listings."""
from match import colour_family, gb, gender, same_colour, same_model, score, tokens


def phone(title, ram, storage):
    return {"brand": "Samsung", "title": title, "tokens": tokens(title, drop={"samsung"}), "ram": ram, "storage": storage}


def test_tokens():
    assert tokens("Samsung Galaxy S24 5G AI Smartphone", drop={"samsung"}) == ["galaxy", "s24"]
    assert tokens("Samsung 138 cm Crystal 4K Ultra HD Smart LED TV UA55U8400FULXL", drop={"samsung"}) == ["crystal", "ua55u8400fulxl"]
    assert tokens("samsung galaxy s24 5g 8gb ram 256gb cobalt violet", drop={"samsung"}) == ["galaxy", "s24"]
    assert tokens("Court-Royale-Shoes-Midnight-White") == ["court", "royale"]
    assert tokens("Apple iPhone 15 (128 GB) - Black", drop={"apple"}) == ["iphone", "15"]
    assert "plus" not in tokens("Lumio Vision 7 TV with 4K HDR Dolby Vision + Atmos")  # '+' between words isn't a variant
    assert "plus" not in tokens("Samsung TV HDR10+ Smart")
    assert "plus" in tokens("Samsung Galaxy S24+ 5G")
    assert "plus" not in tokens("Samsung Neo QLED TV with 150+ Free Channels")
    assert tokens("Lumio Vision 7 2026 TV FTW1-ADSJ", drop={"lumio"}) == ["7", "ftw1adsj"]  # hyphenated code kept whole


def test_colours():
    assert colour_family("Mid Nvy/Wte") == "blue"
    assert colour_family("Navy Blue") == "blue"
    assert colour_family("Onyx Black") == "black"
    assert colour_family("Cobalt Violet") == "purple"
    assert colour_family("Marble Gray") == "grey"
    assert colour_family("Alpine Snow") == "white"
    assert colour_family("Off White") == "white"
    assert colour_family("Amber Yellow") == "yellow"
    assert colour_family("Sparkle") is None


def test_specs():
    assert gb("8 GB") == 8 and gb("1 TB") == 1024 and gb("none") is None
    assert gender("NIKE Court Royale Tennis Shoes For Men") == "men"
    assert gender("Puma Cotton RCB 2026 Men's Striper Polo") == "men"
    assert gender("Nike Women White COURT ROYALE") == "women"


def test_same_model():
    s24 = ["galaxy", "s24"]
    assert same_model(s24, tokens("Samsung Galaxy S24 5G Snapdragon (Amber Yellow, 128 GB)"), 0.75)
    assert not same_model(s24, tokens("Samsung Galaxy S24 FE 5G (Mint, 128 GB)"), 0.75)
    assert not same_model(s24, tokens("Samsung Galaxy S24 Ultra 5G"), 0.75)
    assert not same_model(s24, tokens("Samsung Galaxy S25 5G"), 0.75)
    assert not same_model(["iphone", "15"], tokens("Apple iPhone 16 (128 GB)"), 0.75)
    assert not same_model(["iphone", "15"], tokens("Apple iPhone 15 Pro (128 GB)"), 0.75)
    tv = ["crystal", "ua55u8400fulxl"]
    assert same_model(tv, tokens("samsung u8400f 138 cm 55 inch crystal 4k"), 0.75)  # Croma URL style
    assert not same_model(tv, tokens("Samsung Crystal 4K 138 cm (55 inch) LED TV UA55U8100FULXL"), 0.75)
    lumio = ["7", "ftw1adsj"]
    assert same_model(lumio, tokens("Lumio Vision 7 Dolby Vision + Atmos Model ID: FTW1-ADSJ"), 0.75)
    assert not same_model(lumio, tokens("Lumio Vision 7 II Gemini Model ID: FTW1-ADSK"), 0.75)  # Vision 7 II
    assert same_model(["crystal", "ua55u8400fulxl"], tokens("Samsung UA55U8400FULXL with Prime Video"), 0.75)  # code settles it
    royale = ["court", "royale"]
    assert same_model(royale, tokens("NIKE Court Royale Tennis Shoes For Men"), 0.6)
    assert not same_model(royale, tokens("NIKE Court Royale AC SE Tennis Shoes For Women"), 0.6)
    assert not same_model(royale, tokens("NIKE court vision lo nn Sneakers For Men"), 0.6)
    assert not same_model(["air", "max", "90"], tokens("Nike Air Max SC"), 0.6)


def test_score_filters():
    spec = phone("Samsung Galaxy S24", 8, 128) | {"category": "phone"}
    good = {"brand": "Samsung", "title": "Samsung Galaxy S24 5G", "tokens": ["galaxy", "s24"], "ram": 8, "storage": 128}
    assert score(spec, good)
    assert not score(spec, good | {"storage": 256})
    assert not score(spec, good | {"ram": 12})
    assert not score(spec, good | {"brand": "Apple", "title": "Apple Galaxy S24"})
    case = {"title": "samsung silicone back cover for galaxy s24", "tokens": ["silicone", "back", "cover", "galaxy", "s24"]}
    assert not score(spec, case)  # Croma accessory: no storage -> rejected
    tv = {"category": "tv", "brand": "Samsung", "title": "Samsung 65 inch Neo QLED", "tokens": ["neo"], "screen": 65}
    assert not score(tv, {"brand": "Samsung", "title": "Samsung QN70H Neo QLED", "tokens": ["qn70h", "neo"], "screen": 65})  # no code: don't guess
    shoe = {"category": "sneakers", "brand": "Nike", "title": "Nike Court Royale", "tokens": ["court", "royale"],
            "colour": "Mid Nvy/Wte", "gender": "men"}
    fk = {"brand": "NIKE", "title": "NIKE Court Royale", "tokens": ["court", "royale"], "colour": "Navy Blue", "gender": "men"}
    assert score(shoe, fk)
    assert not score(shoe, fk | {"colour": "White"})
    assert not score(shoe, fk | {"gender": "women"})
    assert score(shoe, fk | {"gender": "unisex"})
    assert not score(shoe, fk | {"title": "NIKE court royale 2 next nature", "tokens": ["court", "royale", "2", "next", "nature"]})

    polo = {"category": "tshirt", "brand": "Puma", "title": "Puma Cotton RCB 2026 Men's Striper Polo",
            "tokens": ["rcb", "striper"], "colour": "Black", "gender": "men"}
    my = {"brand": "Puma", "title": "Puma x RCB 2026 Men's Striper Polo", "tokens": ["rcb", "striper"],
          "colour": "Black", "gender": "men"}
    assert score(polo, my)
    assert not score(polo, my | {"title": "Puma x RCB 2025 Men's Striper Polo"})
    assert score(polo, my | {"title": "Puma x RCB Men's Striper Polo"})  # no year on one side: fine


def test_two_tone():
    assert same_colour("Mid Nvy/Wte", "White/Navy")      # same shoe, colours listed the other way round
    assert same_colour("Navy", "Navy Blue")
    assert not same_colour("Mid Nvy/Wte", "White")       # could be the all-white shoe
    assert same_colour("Black/Red", "Black/White")         # primary colour decides, as before
    assert not same_colour("Red/Black", "Black/White")
    assert not same_colour(None, "Black")


def test_brand_alias():
    redmi = {"category": "phone", "brand": "Xiaomi", "title": "Redmi Note 13 5G", "tokens": ["redmi", "note", "13"],
             "ram": 6, "storage": 128}
    fk = {"brand": "REDMI", "title": "REDMI Note 13 5G", "tokens": ["note", "13"], "ram": 6, "storage": 128}
    assert score(redmi, fk)
    assert not score(redmi, fk | {"brand": "Realme", "title": "realme Note 13"})


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
