"""Run: python3 test_sites.py  — parsers on tiny hand-made page snippets (no network), plus decide/rank and app errors."""
import asyncio
import json

import app
import match
import sites


def amazon_page(title, crumbs, rows="", colour="", canonical=""):
    return f"""<html><head><link rel="canonical" href="{canonical}"></head><body>
    <span id="productTitle"> {title} </span><div id="wayfinding-breadcrumbs_feature_div">{crumbs}</div>
    <a id="bylineInfo">Visit the Samsung Store</a>
    <div id="productOverview_feature_div"><table>{rows}</table></div>
    <span id="inline-twister-expanded-dimension-text-color_name">{colour}</span></body></html>"""


def test_amazon_phone():
    s = sites.parse_amazon(amazon_page("Samsung Galaxy S24 5G AI Smartphone (Amber Yellow, 8GB, 128GB Storage)",
                                       "Electronics › Mobiles & Accessories › Smartphones"), "u")
    assert (s["category"], s["brand"], s["tokens"], s["ram"], s["storage"]) == ("phone", "Samsung", ["galaxy", "s24"], 8, 128)
    assert s["colour"] == "Amber Yellow"  # from the title's last (...) group


def test_amazon_tv():
    s = sites.parse_amazon(amazon_page("Samsung 138 cm (55 inches) Crystal 4K Ultra HD Smart LED TV UA55U8400FULXL (Black)",
                                       "Electronics › Televisions › Smart Televisions"), "u")
    assert s["category"] == "tv" and s["screen"] == 55 and "ua55u8400fulxl" in s["tokens"] and s["colour"] == "Black"


def test_amazon_sneaker_uses_link_slug():
    s = sites.parse_amazon(amazon_page("Nike Men Tennis Shoe", "Shoes › Men's Shoes › Sneakers",
                                       '<tr><td>Brand</td><td>Nike</td></tr>', colour="Mid Nvy/Wte",
                                       canonical="https://www.amazon.in/Court-Royale-Shoes-Midnight-White/dp/B00VDL2CRE"), "u")
    assert (s["category"], s["brand"], s["tokens"], s["colour_family"], s["gender"]) == \
        ("sneakers", "Nike", ["court", "royale"], "blue", "men")


def test_amazon_unsupported():
    try:
        sites.parse_amazon(amazon_page("Dell Inspiron 15 Laptop", "Computers › Laptops"), "u")
    except sites.NotSupported:
        return
    raise AssertionError("laptop should be rejected")


def flipkart_page(*products):
    state = {"pageDataV4": {"slots": [{"productInfo": {"value": p}} for p in products]}}
    return f"<script>window.__INITIAL_STATE__ = {json.dumps(state)};</script>"


def fk_product(pid, title, specs, state="IN_STOCK", price=49999):
    return {"id": pid, "titles": {"title": title}, "keySpecs": specs, "productBrand": "SAMSUNG",
            "baseUrl": f"/x/p/{pid}", "availability": {"displayState": state},
            "pricing": {"prices": [{"value": 79999, "strikeOff": True}, {"value": price}]}}


def test_flipkart_parse():
    html = flipkart_page(fk_product("a", "Samsung Galaxy S24 5G (Amber Yellow, 128 GB)", ["8 GB RAM | 128 GB ROM"]),
                         fk_product("b", "Samsung Galaxy S24 5G (Onyx Black, 256 GB)", ["8 GB RAM | 256 GB ROM"], "OUT_OF_STOCK"),
                         fk_product("a", "duplicate", []))
    a, b = sites.parse_flipkart(html, "Samsung")
    assert (a["ram"], a["storage"], a["colour"], a["stock"], a["price"]) == (8, 128, "Amber Yellow", "in", 49999)
    assert (b["storage"], b["stock"]) == (256, "out")
    tv = sites.parse_flipkart(flipkart_page(fk_product("t", "Samsung Crystal 4K 138 cm (55 inch) Ultra HD (4K) LED TV",
                                                       ["Model ID: UA55U8400FULXL"])), "Samsung")[0]
    assert tv["screen"] == 55 and tv["colour"] == "" and "ua55u8400fulxl" in tv["tokens"]  # "4K" isn't a colour


def test_flipkart_blocked_and_page_stock():
    try:
        sites.parse_flipkart("<html>captcha</html>", "Samsung")
        raise AssertionError("no data must raise, not look like 'not listed'")
    except RuntimeError:
        pass
    assert sites.flipkart_page_stock("<button>Add to cart</button>") == "in"
    assert sites.flipkart_page_stock("<button>Add to cart</button> Size 9: Sold Out") == "out"  # sold-out text wins
    assert sites.flipkart_page_stock("<button>Buy now</button> Coming soon") == "out"


def test_myntra_parse():
    data = {"searchData": {"results": {"products": [
        {"productName": "Nike Men Court Royale Sneakers", "brand": "Nike", "landingPageUrl": "shoes/1", "primaryColour": "Navy Blue",
         "gender": "Men", "inventoryInfo": [{"available": False}, {"available": True}], "price": 3995},
        {"productName": "Nike Men Court Royale Sneakers", "brand": "Nike", "landingPageUrl": "shoes/2", "primaryColour": "White",
         "gender": "Men", "inventoryInfo": [{"available": False}], "price": 3995}]}}}
    navy, white = sites.parse_myntra(f"<script>window.__myx = {json.dumps(data)}</script>", "Nike")
    assert (navy["colour_family"], navy["gender"], navy["stock"], navy["url"]) == ("blue", "men", "in", "https://www.myntra.com/shoes/1")
    assert white["stock"] == "out"  # every size sold out
    try:
        sites.parse_myntra("<html>Access denied</html>", "Nike")
        raise AssertionError("blocked page must raise")
    except RuntimeError:
        pass


def test_croma_url_parsing():
    c = sites.croma_candidate("https://www.croma.com/samsung-galaxy-s24-5g-8gb-ram-128gb-cobalt-violet-/p/303832", "Samsung")
    assert (c["ram"], c["storage"], c["tokens"]) == (8, 128, ["galaxy", "s24"])
    c = sites.croma_candidate("https://www.croma.com/samsung-galaxy-s24-5g-256gb-onyx-black/p/1", "Samsung")
    assert (c["ram"], c["storage"]) == (None, 256)  # no RAM in the link: still matchable on storage
    tv = sites.croma_candidate("https://www.croma.com/samsung-u8400f-140-cm-55-inch-4k-ultra-hd-led-tv/p/315266", "Samsung")
    assert tv["screen"] == 55 and "u8400f" in tv["tokens"]
    assert sites.croma_price('..."sellingPrice":{"value":"49490.00"}...') == 49490
    assert sites.croma_price("<html></html>") is None


def test_tv_and_phone_rules():
    tv = {"category": "tv", "brand": "Samsung", "title": "Samsung TV", "tokens": ["crystal", "ua55u8400fulxl"], "screen": 55}
    c = {"brand": "Samsung", "title": "samsung u8400f", "tokens": ["u8400f"], "screen": 55}
    assert match.score(tv, c) and match.score(tv, c | {"screen": 55.5})
    assert not match.score(tv, c | {"screen": 43}) and not match.score(tv, c | {"screen": None})
    ph = {"category": "phone", "brand": "Samsung", "title": "S24", "tokens": ["galaxy", "s24"], "ram": 8, "storage": 128}
    assert match.score(ph, {"brand": "Samsung", "title": "S24", "tokens": ["galaxy", "s24"], "ram": None, "storage": 128})


def test_decide_and_rank():
    assert match.decide([]) == ("not_listed", None)
    out, oin = {"stock": "out"}, {"stock": "in"}
    assert match.decide([out, oin]) == ("in_stock", oin)  # a buyable match beats a better-scored sold-out one
    assert match.decide([out]) == ("out_of_stock", out)
    spec = {"category": "phone", "brand": "Samsung", "title": "S24", "tokens": ["galaxy", "s24"], "ram": 8,
            "storage": 128, "colour_family": "yellow"}
    base = {"brand": "Samsung", "title": "S24", "tokens": ["galaxy", "s24"], "ram": 8, "storage": 128}
    violet, yellow, fe = base | {"colour_family": "purple"}, base | {"colour_family": "yellow"}, base | {"tokens": ["galaxy", "s24", "fe"]}
    assert match.rank(spec, [violet, fe, yellow]) == [yellow, violet]  # same colour first, FE dropped


def test_app_error_hides_details():
    async def broken(client, spec):
        raise RuntimeError("https://api.scraperapi.com/?api_key=SECRET")
    sites.ADAPTERS["broken"] = broken
    r = asyncio.run(app.check(None, "broken", {}))
    del sites.ADAPTERS["broken"]
    assert r["status"] == "error" and "SECRET" not in json.dumps(r)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
