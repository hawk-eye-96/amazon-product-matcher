"""Run: python3 test_match.py  — cases taken from real Amazon/Flipkart/Myntra/Croma listings."""
from match import colour_family, gb, gender, same_model, score, tokens


def phone(title, ram, storage):
    return {"brand": "Samsung", "title": title, "tokens": tokens(title, drop={"samsung"}), "ram": ram, "storage": storage}


def test_tokens():
    assert tokens("Samsung Galaxy S24 5G AI Smartphone", drop={"samsung"}) == ["galaxy", "s24"]
    assert tokens("Samsung 138 cm Crystal 4K Ultra HD Smart LED TV UA55U8400FULXL", drop={"samsung"}) == ["crystal", "ua55u8400fulxl"]
    assert tokens("samsung galaxy s24 5g 8gb ram 256gb cobalt violet", drop={"samsung"}) == ["galaxy", "s24"]
    assert tokens("Court-Royale-Shoes-Midnight-White") == ["court", "royale"]
    assert tokens("Apple iPhone 15 (128 GB) - Black", drop={"apple"}) == ["iphone", "15"]


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
    shoe = {"category": "sneakers", "brand": "Nike", "tokens": ["court", "royale"], "colour_family": "blue", "gender": "men"}
    fk = {"brand": "NIKE", "title": "NIKE Court Royale", "tokens": ["court", "royale"], "colour_family": "blue", "gender": "men"}
    assert score(shoe, fk)
    assert not score(shoe, fk | {"colour_family": "white"})
    assert not score(shoe, fk | {"gender": "women"})
    assert score(shoe, fk | {"gender": "unisex"})


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
