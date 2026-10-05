#!/usr/bin/env python3
"""OmaSaber's partner catalogue: CC Sabers and NeoSabers sabers, by board, in one checked file.

Each partner is a Shopify store with a public /products.json. A saber there is one product
whose variants pick a board (the store's board option: "Electronics", "Type") and a blade
length. The catalogue keeps a product only if it has that option (so T-shirts and stands
drop out) and gives it one offer per board at that board's lowest price, mapped to
OmaSaber's platform ids (platforms.json; "-" marks a value of that option that isn't a board,
such as a blade shape or a stand, and is left out). Photos are Shopify's own https addresses, at most six.

    python3 build.py --out site      writes site/catalogue.json and site/_headers

A check refuses a thin or broken catalogue, so the workflow deploys nothing and yesterday's stays up.
"""

import argparse
import datetime
import json
import os
import sys
import time
import urllib.request

SCHEMA = "omasaber.catalogue.v1"
UA = "OmaSaber-catalogue/1 (+https://github.com/omauilabs/omasaber-catalogue)"
PHOTO_PREFIX = "https://cdn.shopify.com/"
MAX_PHOTOS = 6
MAX_PAGES = 40
MIN_PRODUCTS = 50
CURRENCY = "USD"
ATTRIBUTION = ("Star Wars and related names are trademarks of Lucasfilm Ltd. / Disney. "
               "OmaSaber, CC Sabers and NeoSabers are not affiliated with them.")
DISCLOSURE = ("OmaSaber earns a referral fee from CC Sabers and NeoSabers when you buy through these links. "
              "It doesn't change your price.")
HERE = os.path.dirname(os.path.abspath(__file__))


class BuildError(Exception):
    pass


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read(32 * 1024 * 1024))


def load_table(path):
    with open(path) as f:
        pairs = json.load(f)
    return sorted(((p.lower(), pid) for p, pid in pairs), key=lambda x: -len(x[0]))


def platform_of(board, table):
    b = board.strip().lower()
    return next((pid for prefix, pid in table if b.startswith(prefix)), None)


def pages(store, get=fetch_json, wait=time.sleep):
    out = []
    for page in range(1, MAX_PAGES + 1):
        got = get(f"{store['url']}/products.json?limit=250&page={page}").get("products") or []
        if not got:
            return out
        out += got
        wait(1.0)
    raise BuildError(f"{store['id']}: more than {MAX_PAGES} pages")


def _cents(price):
    return round(float(price) * 100)


def product(store, p, table, unknown):
    names = [o.get("name") for o in p.get("options") or []]
    if store["boardOption"] not in names:
        return None
    board_key = f"option{names.index(store['boardOption']) + 1}"
    length_key = f"option{names.index('Blade Length') + 1}" if "Blade Length" in names else None
    offers, lengths = {}, []
    for v in p.get("variants") or []:
        board = " ".join(str(v.get(board_key) or "").split())
        if not board or v.get("price") is None:
            continue
        pid = platform_of(board, table)
        if pid == "-":
            continue  # the store's option also holds things that aren't boards: a blade shape, a stand
        if pid is None:
            unknown.add(board)
            pid = "other"
        cents, avail = _cents(v["price"]), bool(v.get("available"))
        if cents <= 0:
            continue  # a free gift with an order ("100% off"): not a saber anyone buys
        o = offers.get(board)
        if o is None:
            offers[board] = {"platform": pid, "board": board, "from": f"{cents / 100:.2f}", "currency": CURRENCY,
                             "available": avail, "_c": cents}
        else:
            o["available"] = o["available"] or avail
            if cents < o["_c"]:
                o["_c"], o["from"] = cents, f"{cents / 100:.2f}"
        length = length_key and str(v.get(length_key) or "").strip()
        if length and length not in lengths:
            lengths.append(length)
    photos = [i["src"] for i in p.get("images") or []
              if isinstance(i.get("src"), str) and i["src"].startswith(PHOTO_PREFIX)][:MAX_PHOTOS]
    if not offers or not photos:
        return None  # nothing to compare, or nothing to show
    tags = p.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",")]
    return {
        "id": f"{store['id']}/{p['handle']}",
        "store": store["id"],
        "title": " ".join(str(p.get("title") or p["handle"]).split()),
        "url": f"{store['url']}/products/{p['handle']}",
        "photos": photos,
        "offers": [{k: v for k, v in o.items() if k != "_c"} for o in offers.values()],
        "lengths": lengths[:12],
        "tags": [t for t in tags if t][:20],
        "updated": str(p.get("updated_at") or "")[:10],
    }


def build(stores, table, get=fetch_json, wait=time.sleep, now=time.time):
    unknown, products = set(), []
    for store in stores:
        currency = get(f"{store['url']}/meta.json").get("currency")
        if currency != CURRENCY:
            raise BuildError(f"{store['id']}: prices in {currency}, not {CURRENCY}")
        for p in pages(store, get=get, wait=wait):
            kept = product(store, p, table, unknown)
            if kept:
                products.append(kept)
    built = datetime.datetime.fromtimestamp(now(), datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return ({"schema": SCHEMA, "built": built,
             "stores": [{"id": s["id"], "name": s["name"], "url": s["url"], "referral": s["referral"]} for s in stores],
             "attribution": ATTRIBUTION, "disclosure": DISCLOSURE, "products": products}, unknown)


def check(cat):
    for s in cat["stores"]:
        mine = [p for p in cat["products"] if p["store"] == s["id"]]
        if len(mine) < MIN_PRODUCTS:
            raise BuildError(f"{s['id']}: {len(mine)} products, fewer than {MIN_PRODUCTS}: not deployed")
    for p in cat["products"]:
        if not p["offers"] or not p["photos"]:
            raise BuildError(f"{p['id']}: no offer or no photo")


def main(argv=None, get=fetch_json, wait=time.sleep):
    a = argparse.ArgumentParser(description="Build OmaSaber's partner catalogue")
    a.add_argument("--out", default="site")
    args = a.parse_args(argv)
    with open(os.path.join(HERE, "stores.json")) as f:
        stores = json.load(f)
    cat, unknown = build(stores, load_table(os.path.join(HERE, "platforms.json")), get=get, wait=wait)
    for board in sorted(unknown):
        print(f"unknown board, counted as other: {board!r} (add it to platforms.json)")
    check(cat)
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "catalogue.json"), "w") as f:
        json.dump(cat, f, separators=(",", ":"))
    with open(os.path.join(args.out, "_headers"), "w") as f:
        f.write("/catalogue.json\n  Cache-Control: public, max-age=3600\n  X-Content-Type-Options: nosniff\n")
    print(f"{len(cat['products'])} products: " + ", ".join(
        f"{s['id']} {sum(p['store'] == s['id'] for p in cat['products'])}" for s in cat["stores"]))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BuildError as e:
        print(f"not built: {e}", file=sys.stderr)
        sys.exit(1)
