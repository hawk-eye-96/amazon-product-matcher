"""Run: python3 test_sites.py  — parsers on tiny hand-made page snippets (no network), plus decide/rank and app errors."""
import asyncio
import json

import httpx

import app
import match
import sites


def amazon_page(title, crumbs, rows="", colour="", canonical="", page_title=""):
    return f"""<html><head><title>{page_title}</title><link rel="canonical" href="{canonical}"></head><body>
    <span id="productTitle"> {title} </span><div id="wayfinding-breadcrumbs_feature_div">{crumbs}</div>
    <a id="bylineInfo">Visit the Samsung Store</a>
    <div id="productOverview_feature_div"><table>{rows}</table></div>
    <span id="inline-twister-expanded-dimension-text-color_name">{colour}</span></body></html>"""


def test_amazon_phone():
    s = sites.parse_amazon(amazon_page("Samsung Galaxy S24 5G AI Smartphone (Amber Yellow, 8GB, 128GB Storage)",
                                       "Electronics › Mobiles & Accessories › Smartphones"), "u")
    assert (s["category"], s["brand"], s["tokens"], s["ram"], s["storage"]) == ("phone", "Samsung", ["galaxy", "s24"], 8, 128)
    assert s["colour"] == "Amber Yellow"  # from the title's last (...) group


def test_amazon_phone_title_beats_spec_table():
    s = sites.parse_amazon(amazon_page("vivo T5x 5G (Cyber Green, 8GB RAM, 256GB Storage) | 50MP AI Dual Camera",
                                       "Electronics › Mobiles & Accessories › Smartphones",
                                       '<tr><td>RAM Memory Installed Size</td><td>6 GB</td></tr>'
                                       '<tr><td>Memory Storage Capacity</td><td>128 GB</td></tr>'), "u")
    assert (s["ram"], s["storage"]) == (8, 256)
    s = sites.parse_amazon(amazon_page("Nothing Phone (4b) 5G (White, 8GB RAM, 128GB Storage) | Snapdragon 6 Gen 4",
                                       "Electronics › Mobiles & Accessories › Smartphones", '<tr><td>Brand</td><td>Nothing</td></tr>'), "u")
    assert s["tokens"] == ["4b"] and s["colour"] == "White"


def test_amazon_tv():
    s = sites.parse_amazon(amazon_page("Samsung 138 cm (55 inches) Crystal 4K Ultra HD Smart LED TV UA55U8400FULXL (Black)",
                                       "Electronics › Televisions › Smart Televisions"), "u")
    assert s["category"] == "tv" and s["screen"] == 55 and "ua55u8400fulxl" in s["tokens"] and s["colour"] == "Black"


def test_amazon_tv_newer_spec_table():
    html = amazon_page("Samsung 65 inch (163cm) Neo QLED 4K Vision AI 2026 Smart TV | NQ4 AI Processor", "Televisions").replace(
        "</body>", '<div id="prodDetails"><table><tr><th>Model Number</th><td>QA65QN2EHAULXL</td></tr></table></div></body>')
    s = sites.parse_amazon(html, "u")
    assert "qa65qn2ehaulxl" in s["tokens"] and s["screen"] == 65 and s["colour"] == ""  # "(163cm)" isn't a colour


def test_amazon_sneaker_uses_link_slug():
    s = sites.parse_amazon(amazon_page("Nike Men Tennis Shoe", "Shoes › Men's Shoes › Sneakers",
                                       '<tr><td>Brand</td><td>Nike</td></tr>', colour="Mid Nvy/Wte",
                                       canonical="https://www.amazon.in/Court-Royale-Shoes-Midnight-White/dp/B00VDL2CRE"), "u")
    assert (s["category"], s["brand"], s["tokens"], s["colour_family"], s["gender"]) == \
        ("sneakers", "Nike", ["court", "royale"], "blue", "men")


def test_amazon_iphone_without_breadcrumbs():
    s = sites.parse_amazon(amazon_page("iPhone 16 128 GB: 5G Mobile Phone with Camera Control, A18 Chip", "",
                                       '<tr><td>Brand</td><td>Apple</td></tr><tr><td>RAM Memory Installed Size</td><td>128 GB</td></tr>'
                                       '<tr><td>Memory Storage Capacity</td><td>128 GB</td></tr>'
                                       '<tr><td>Item model number</td><td>MYED3HN/A</td></tr>'), "u")
    assert (s["category"], s["tokens"], s["ram"], s["storage"]) == ("phone", ["iphone", "16"], None, 128)  # bogus RAM dropped


def test_amazon_brand_codes_and_tv_model_name():
    page = amazon_page("New Balance Men BB80IN Sneaker", "Shoes › Men's Shoes › Sneakers", colour="White_4").replace(
        '<a id="bylineInfo">Visit the Samsung Store</a>', "")
    assert sites.parse_amazon(page, "u")["brand"] == "New Balance"
    s = sites.parse_amazon(amazon_page("Converse Unisex Chuck Taylor All Star Black Sneakers (UK Footwear Size System, Adult, 7)",
                                       "Shoes › Men's Shoes › Sneakers", '<tr><td>Brand</td><td>Converse</td></tr>',
                                       canonical="https://www.amazon.in/Converse-CONV-M9160C-M9160/dp/B000LFG274"), "u")
    assert "chuck" in s["tokens"] and not {"conv", "m9160c"} & set(s["tokens"])
    s = sites.parse_amazon(amazon_page("Toshiba 139 cm (55 Inches) 4K Ultra HD Smart QLED TV | Dolby Atmos", "Televisions",
                                       '<tr><td>Model name</td><td>M450 Series</td></tr>'), "u")
    assert "m450" in s["tokens"]
    assert match.colour_family("WHITE BLACK4") == "white" and match.colour_family("Sky Blue") == "blue"


def test_amazon_misfiled_tshirt():
    s = sites.parse_amazon(amazon_page("Levi's Men's Pure Cotton Slim Fit Polo T-Shirt",
                                       "Clothing & Accessories › Men › Innerwear › Thermals › Bottoms"), "u")
    assert s["category"] == "tshirt"
    for title, crumbs in [("KLOSIA Women Printed Straight Kurta", "Clothing & Accessories › Women › Kurtas"),
                          ("Symbol Men's Regular Fit Cotton Formal Shirt", "Clothing & Accessories › Men › T-shirts, Polos & Shirts › Shirts"),
                          ("U.S. Polo Assn. Men Casual Shirt", "Clothing & Accessories › Men › T-shirts, Polos & Shirts › Shirts"),
                          ("HITZ Men's Leather Formal Shoes", "Shoes › Men's Shoes › Formal Shoes"),
                          ("Dr. Ortho Men Slipper", "Shoes › Men's Shoes › Flip-Flops & Slippers"),
                          ("Spigen Back Cover Case for iPhone 16", "Electronics › Mobile Accessories › Cases & Covers")]:
        try:
            sites.parse_amazon(amazon_page(title, crumbs), "u")
            assert False, title
        except sites.NotSupported:
            pass
    assert sites.parse_amazon(amazon_page("BlissClub Polo T-Shirt for Men", "Men › T-shirts, Polos & Shirts › Polos"), "u")["category"] == "tshirt"


def test_amazon_sneaker_drops_article_code():
    s = sites.parse_amazon(amazon_page("Nike Men Tennis Shoe", "Shoes › Men's Shoes › Sneakers", '<tr><td>Brand</td><td>Nike</td></tr>', colour="WHITE/BLACK",
                                       canonical="https://www.amazon.in/Nike-Court-Royale-Running-749747-107/dp/B0B35XL88R"), "u")
    assert s["tokens"] == ["court", "royale"]
    s = sites.parse_amazon(amazon_page("Nike Men Tennis Shoe", "Shoes › Men's Shoes › Sneakers", '<tr><td>Brand</td><td>Nike</td></tr>', colour="WHITE/BLACK",
                                       canonical="https://www.amazon.in/Nike-749747-107-Court-ROYALE-749747-107-10-WHITE-BLACK/dp/B09V86VZNN"), "u")
    assert s["tokens"] == ["court", "royale"]  # size 10 after the article code dropped too


def test_amazon_phone_bad_storage_field():
    s = sites.parse_amazon(amazon_page("Motorola Edge 60 Fusion (Amazonite, 12, GB, 256)", "Smartphones",
                                       '<tr><td>Brand</td><td>Motorola</td></tr><tr><td>RAM Memory Installed Size</td><td>12 GB</td></tr>'
                                       '<tr><td>Memory Storage Capacity</td><td>12 GB</td></tr>'), "u")
    assert (s["ram"], s["storage"], s["tokens"]) == (12, 256, ["edge", "60", "fusion"])


def test_amazon_phone_title_with_colon():
    s = sites.parse_amazon(amazon_page("Apple iPhone 17e 256 GB: 15.40 cm (6.1″) Super Retina XDR Display, A19 Chip", "Smartphones",
                                       '<tr><td>Brand</td><td>Apple</td></tr>'), "u")
    assert s["tokens"] == ["iphone", "17e"]


def test_amazon_colour_code_falls_back_to_link():
    s = sites.parse_amazon(amazon_page("adidas Mens Soulzie M Sneaker", "Shoes › Men's Shoes › Sneakers", '<tr><td>Brand</td><td>adidas</td></tr>',
                                       colour="PUTBEI/LINGRN/BLACK/WARSAN",
                                       canonical="https://www.amazon.in/Adidas-Soulzie-Casual-Shoe-Beige/dp/B0FC2LK2YC"), "u")
    assert (s["colour"], s["colour_family"]) == ("Beige", "beige")
    s = sites.parse_amazon(amazon_page("adidas Mens Soulzie M Sneaker", "Shoes › Men's Shoes › Sneakers", '<tr><td>Brand</td><td>adidas</td></tr>',
                                       colour="PUTBEI/LINGRN/BLACK/WARSAN", canonical="https://www.amazon.in/adidas-Mens-Soulzie-M-Sneaker/dp/B0FFN1MZ9B",
                                       page_title="Buy Adidas Men Soulzie M, Casual Shoe, Beige, 9 at Amazon.in"), "u")
    assert s["colour"] == "Beige"  # canonical is the colourless parent: the page title has it


def test_amazon_sneaker_version_from_title():
    s = sites.parse_amazon(amazon_page("ASICS Mens Gel-Excite 10 Running Shoes", "Shoes › Men's Shoes › Sports Shoes", '<tr><td>Brand</td><td>ASICS</td></tr>',
                                       colour="BLACK/NEW LEAF", canonical="https://www.amazon.in/ASICS-Gel-Excite-Black-Running-Shoes/dp/B0D9BNCGZW"), "u")
    assert s["tokens"] == ["gel", "excite", "10"]


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
    assert (c["ram"], c["storage"], c["tokens"], c["colour_family"]) == (8, 128, ["galaxy", "s24"], "purple")
    c = sites.croma_candidate("https://www.croma.com/samsung-galaxy-s24-5g-256gb-onyx-black/p/1", "Samsung")
    assert (c["ram"], c["storage"]) == (None, 256)  # no RAM in the link: still matchable on storage
    tv = sites.croma_candidate("https://www.croma.com/samsung-u8400f-140-cm-55-inch-4k-ultra-hd-led-tv/p/315266", "Samsung")
    assert tv["screen"] == 55 and "u8400f" in tv["tokens"]
    assert sites.croma_price('..."sellingPrice":{"value":"49490.00"}...') == 49490
    ld = '{"@type": "Offer", "priceCurrency": "INR", "price": "64999.00" }'
    assert sites.croma_price('"pdpPriceData":{},"offers": ' + ld) == 64999  # app state empty: schema.org offer
    assert sites.croma_price('"mrp":{"value":"74999.00"}') is None          # MRP is not the selling price
    assert sites.croma_price("<html></html>") is None


def test_search_pages():
    assert sites.search_pages(["a", "b"]) == [("a", 1), ("a", 2), ("b", 1)]

    class Down:  # every request fails
        async def get(self, url, **k):
            return httpx.Response(500, request=httpx.Request("GET", url))
    assert asyncio.run(sites.search_page(Down(), "https://x", None, 2)) is None  # page 2 failing is skipped
    try:
        asyncio.run(sites.search_page(Down(), "https://x", None, 1))
        raise AssertionError("page 1 failing must be an error, not 'not listed'")
    except httpx.HTTPStatusError:
        pass


def test_croma_sitemap_ids():
    xml = """<url><loc>https://www.croma.com/samsung-galaxy-s24-5g-8gb-ram-128gb-cobalt-violet-/p/303832</loc></url>
    <url><loc>https://www.croma.com/samsung-qn80h-165-1-cm-65-inch-neo-qled-tv-2026-model-/p/ph120101qn80h_samsung_797</loc></url>
    <url><loc>https://www.croma.com/lg-evo-ai-292-cm-115-inch-tv/p/ph120101evo ai_lg_205</loc></url>
    <url><loc>https://www.croma.com/phones-wearables/c/1</loc></url>"""
    urls = sites.croma_product_urls(xml)
    assert len(urls) == 3 and urls[2].endswith("/p/ph120101evo%20ai_lg_205")  # category page skipped, space encoded
    tv = sites.croma_candidate(urls[1], "Samsung")
    assert tv["screen"] == 65 and "qn80h" in tv["tokens"]


def test_croma_adapter_page_errors(monkeypatch=None):
    spec = {"category": "tv", "brand": "LG", "title": "LG 43NU870BPLA 2026", "tokens": ["43nu870bpla"], "screen": 43,
            "colour_family": None}
    urls = ["https://www.croma.com/lg-nu870b-109-cm-43-inch-tv-2026-model-/p/ph120101nu870b_lg_999",
            "https://www.croma.com/lg-nu870b-109-cm-43-inch-tv-2026-model-/p/323496"]
    async def fake_urls(client, category):
        return urls
    def run(status):
        tried = []
        async def fake_get(client, url, proxy=None):
            tried.append(url)
            req = httpx.Request("GET", url)
            if status != 200:
                raise httpx.HTTPStatusError("x", request=req, response=httpx.Response(status, request=req))
            return httpx.Response(200, request=req, text='"sellingPrice":{"value":"30990.00"}')
        orig = sites.croma_urls, sites.get
        sites.croma_urls, sites.get = fake_urls, fake_get
        try:
            return asyncio.run(sites.croma(None, spec)), tried
        finally:
            sites.croma_urls, sites.get = orig
    (st, hit), tried = run(200)
    assert st == "in_stock" and hit["price"] == 30990 and tried[0].endswith("/p/323496")  # numeric ID page first
    (st, hit), _ = run(500)
    assert st == "in_stock" and hit["price"] is None   # page error: still listed in Croma's catalogue
    (st, hit), _ = run(404)
    assert st == "not_listed"                            # both pages gone: delisted


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


def test_miss_note():
    op = {"category": "phone", "brand": "OnePlus", "title": "OnePlus 13s 16GB+512GB", "tokens": ["13s"], "ram": 16, "storage": 512}
    c = {"brand": "OnePlus", "title": "OnePlus 13s 5G", "tokens": ["13s"], "ram": 12}
    cands = [c | {"storage": 512}, c | {"storage": 256}, c | {"storage": 512},  # duplicate variant listed once
             {"brand": "OnePlus", "title": "OnePlus 13", "tokens": ["13"], "ram": 16, "storage": 512},  # other model
             {"title": "oneplus 13s back cover", "tokens": ["13s", "back", "cover"]}]  # accessory: no storage
    cands = [x | {"url": f"https://fk/{i}"} for i, x in enumerate(cands)]
    miss = match.miss_note(op, cands)
    assert miss["note"] == "Found this model, but only with 12 GB RAM / 512 GB, 12 GB RAM / 256 GB."
    assert miss["near"] == [{"label": "12 GB RAM / 512 GB", "url": "https://fk/0"}, {"label": "12 GB RAM / 256 GB", "url": "https://fk/1"}]
    assert miss["lead"] == "Found this model, but only with" and miss["more"] == 0
    green = match.miss_note(op | {"colour_family": "green"}, cands + [c | {"storage": 512, "colour_family": "green", "url": "https://fk/green"}])
    assert green["near"][0]["url"] == "https://fk/green"  # same variant, Amazon's colour preferred
    assert match.miss_note(op, cands[3:]) is None  # model not there at all: plain "not listed"
    shoe = {"category": "sneakers", "brand": "Nike", "title": "Nike Court Royale", "tokens": ["court", "royale"],
            "colour": "Mid Nvy/Wte", "gender": "men"}
    my = {"brand": "Nike", "title": "Nike Court Royale", "tokens": ["court", "royale"], "colour": "white", "gender": "men", "url": "u"}
    assert match.miss_note(shoe, [my | {"colour": "Black", "gender": "women"}, my])["note"] == \
        "Found this model, but only in White, Black (women)."
    many = [my | {"colour": c} for c in ("White", "Black", "Red", "Green", "Grey")]
    assert match.miss_note(shoe, many)["note"].endswith("White, Black, Red and 2 more.")
    tv = {"category": "tv", "brand": "Samsung", "title": "Samsung TV", "tokens": ["ua55u8400fulxl"], "screen": 55}
    assert match.miss_note(tv, [{"brand": "Samsung", "title": "x", "tokens": ["ua55u8400fulxl"], "screen": 43, "url": "u"}])["note"] == \
        'Found this model, but only in 43".'
    assert match.decide([], miss) == ("not_listed", miss) and match.decide([]) == ("not_listed", None)


def test_miss_note_without_model():
    polo = {"category": "tshirt", "brand": "U.S. POLO ASSN.", "title": "U.S. Polo ASSN. Men Polo Shirt", "tokens": [], "colour": "Olive"}
    assert "doesn't name a model" in match.miss_note(polo, [])["note"]


def test_app_passes_miss_note():
    async def near(client, spec):
        return match.decide([], {"note": "Found this model, but only with 12 GB RAM / 512 GB.", "lead": "Found this model, but only with",
                                 "near": [{"label": "12 GB RAM / 512 GB", "url": "https://fk/1"}], "more": 0})
    sites.ADAPTERS["near"] = near
    r = asyncio.run(app.check(None, "near", {}))
    del sites.ADAPTERS["near"]
    assert r == {"platform": "near", "status": "not_listed", "note": "Found this model, but only with 12 GB RAM / 512 GB.",
                 "lead": "Found this model, but only with", "near": [{"label": "12 GB RAM / 512 GB", "url": "https://fk/1"}], "more": 0}


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
