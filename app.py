import asyncio

import httpx
from fastapi import FastAPI

app = FastAPI()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "Accept-Language": "en-IN,en;q=0.9",
}

PROBES = {
    "amazon": "https://www.amazon.in/s?k=samsung+galaxy+s24",
    "flipkart": "https://www.flipkart.com/search?q=samsung+galaxy+s24",
    "croma": "https://www.croma.com/searchB?q=samsung%20galaxy%20s24",
    "myntra": "https://www.myntra.com/nike-shoes",
}

BLOCK_SIGNS = ("captcha", "robot check", "access denied", "are you a human")


async def probe(client, name, url):
    try:
        r = await client.get(url)
        body = r.text.lower()
        blocked = r.status_code >= 400 or any(s in body for s in BLOCK_SIGNS)
        return name, {"status": r.status_code, "bytes": len(r.text), "blocked": blocked}
    except Exception as e:
        return name, {"error": repr(e)}


@app.get("/probe")
async def probe_all():
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=15) as c:
        return dict(await asyncio.gather(*(probe(c, n, u) for n, u in PROBES.items())))


@app.get("/")
def root():
    return {"ok": True, "try": "/probe"}
