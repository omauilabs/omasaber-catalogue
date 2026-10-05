"""build.py against hand-made stores shaped like Shopify's /products.json."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import build as B  # noqa: E402

STORES = [{"id": "ccsabers", "name": "CC Sabers", "url": "https://www.ccsabers.com", "boardOption": "Electronics",
           "referral": {"param": "ref", "code": "OMA"}},
          {"id": "neosabers", "name": "NeoSabers", "url": "https://neosabers.com", "boardOption": "Type",
           "referral": {"param": "ref", "code": ""}}]
TABLE = B.load_table(os.path.join(os.path.dirname(__file__), "..", "platforms.json"))


def saber(handle, board_option, boards, lengths=("32\"",), photos=2, extra_opts=()):
    opts = [board_option, "Blade Length", *extra_opts]
    variants, price = [], 300
    for b in boards:
        for L in lengths:
            variants.append({"option1": b, "option2": L, "price": f"{price}.00", "available": b != "SN-Pixel V4"})
            price += 25
    return {"handle": handle, "title": handle.replace("-", " ").title(), "tags": ["cosplay", "neopixel"],
            "updated_at": "2026-10-04T10:00:00-05:00", "options": [{"name": o} for o in opts], "variants": variants,
            "images": [{"src": f"https://cdn.shopify.com/s/files/{handle}-{i}.png"} for i in range(photos)]
                      + [{"src": "https://elsewhere.example/x.png"}]}


def shop(products_by_page):
    calls = []

    def get(url):
        calls.append(url)
        if url.endswith("/meta.json"):
            return {"currency": "USD"}
        page = int(url.split("page=")[1])
        return {"products": products_by_page[page - 1] if page <= len(products_by_page) else []}
    return get, calls


class BuildTest(unittest.TestCase):
    def build(self, cc, neo):
        gets = {"ccsabers": shop(cc), "neosabers": shop(neo)}
        def get(url):
            return gets["ccsabers" if "ccsabers" in url else "neosabers"][0](url)
        return B.build(STORES, TABLE, get=get, wait=lambda s: None, now=lambda: 1791100000.0)

    def test_boards_become_offers_at_their_lowest_price(self):
        cat, unknown = self.build([[saber("nihilus", "Electronics", ["Proffieboard V2.2", "Xenopixel", "RGB S16"], lengths=("32\"", "36\""))]],
                                  [[saber("cal-replica", "Type", ["Xenopixel V3", "NeoProffie 2.2", "SN-Pixel V4", "XRGB 3.0"])]])
        self.assertEqual(unknown, set())
        p = cat["products"][0]
        self.assertEqual(p["id"], "ccsabers/nihilus")
        self.assertEqual(p["url"], "https://www.ccsabers.com/products/nihilus")
        self.assertEqual([(o["platform"], o["board"], o["from"]) for o in p["offers"]],
                         [("proffie", "Proffieboard V2.2", "300.00"), ("xenopixel", "Xenopixel", "350.00"),
                          ("baselit", "RGB S16", "400.00")])
        self.assertEqual(p["lengths"], ["32\"", "36\""])
        self.assertEqual(p["updated"], "2026-10-04")
        neo = cat["products"][1]
        self.assertEqual([o["platform"] for o in neo["offers"]], ["xenopixel", "proffie", "sn-pixel", "baselit"])
        self.assertFalse(neo["offers"][2]["available"])
        self.assertEqual(cat["schema"], "omasaber.catalogue.v1")
        self.assertEqual([s["referral"]["code"] for s in cat["stores"]], ["OMA", ""])
        self.assertIn("Lucasfilm", cat["attribution"])
        self.assertIn("referral fee", cat["disclosure"])

    def test_photos_are_shopifys_https_at_most_six(self):
        cat, _ = self.build([[saber("many", "Electronics", ["Xenopixel"], photos=9)]], [[]])
        photos = cat["products"][0]["photos"]
        self.assertEqual(len(photos), 6)
        self.assertTrue(all(u.startswith("https://cdn.shopify.com/") for u in photos))

    def test_accessories_are_left_out_and_unknown_boards_reported(self):
        shirt = {"handle": "tee", "title": "Tee", "tags": "", "updated_at": "2026-10-01T00:00:00Z",
                 "options": [{"name": "Size"}], "variants": [{"option1": "M", "price": "20.00", "available": True}], "images": []}
        cat, unknown = self.build([[shirt, saber("odd", "Electronics", ["Quantum Board"])]], [[]])
        self.assertEqual([p["id"] for p in cat["products"]], ["ccsabers/odd"])
        self.assertEqual(cat["products"][0]["offers"][0]["platform"], "other")
        self.assertEqual(unknown, {"Quantum Board"})

    def test_values_that_arent_boards_are_left_out(self):
        cat, unknown = self.build([[saber("tips", "Electronics", ["Pointed", "Rounded"]),
                                    saber("mixed", "Electronics", ["Premium", "Neo Proffie 2.2", "RBG Baselit"])]], [[]])
        self.assertEqual([p["id"] for p in cat["products"]], ["ccsabers/mixed"])
        self.assertEqual([o["platform"] for o in cat["products"][0]["offers"]], ["proffie", "baselit"])
        self.assertEqual(unknown, set())

    def test_a_free_gift_is_left_out(self):
        gift = saber("gift", "Electronics", ["RGB"])
        for v in gift["variants"]:
            v["price"] = "0.00"
        cat, _ = self.build([[gift, saber("paid", "Electronics", ["RGB"])]], [[]])
        self.assertEqual([p["id"] for p in cat["products"]], ["ccsabers/paid"])

    def test_pages_until_an_empty_one(self):
        get, calls = shop([[saber("a", "Electronics", ["Xenopixel"])], [saber("b", "Electronics", ["Xenopixel"])]])
        got = B.pages(STORES[0], get=get, wait=lambda s: None)
        self.assertEqual([p["handle"] for p in got], ["a", "b"])
        self.assertEqual([c.split("page=")[1] for c in calls], ["1", "2", "3"])

    def test_a_store_not_in_dollars_stops_the_build(self):
        def get(url):
            return {"currency": "EUR"} if url.endswith("/meta.json") else {"products": []}
        with self.assertRaises(B.BuildError):
            B.build(STORES[:1], TABLE, get=get, wait=lambda s: None, now=lambda: 0.0)

    def test_check_stops_a_thin_or_broken_catalogue(self):
        many = [saber(f"s{i}", "Electronics", ["Xenopixel"]) for i in range(B.MIN_PRODUCTS)]
        neo = [saber(f"n{i}", "Type", ["Xenopixel V3"]) for i in range(B.MIN_PRODUCTS)]
        cat, _ = self.build([many], [neo])
        B.check(cat)  # fine
        thin, _ = self.build([many[:3]], [neo])
        with self.assertRaises(B.BuildError):
            B.check(thin)
        no_photo = json.loads(json.dumps(cat))
        no_photo["products"][0]["photos"] = []
        with self.assertRaises(B.BuildError):
            B.check(no_photo)

    def test_main_writes_the_site(self):
        import tempfile
        out = tempfile.mkdtemp()
        many = [saber(f"s{i}", "Electronics", ["Xenopixel"]) for i in range(B.MIN_PRODUCTS)]
        gets = {"ccsabers": shop([many]), "neosabers": shop([[saber(f"n{i}", "Type", ["Xenopixel V3"]) for i in range(B.MIN_PRODUCTS)]])}
        B.main(["--out", out], get=lambda u: gets["ccsabers" if "ccsabers" in u else "neosabers"][0](u), wait=lambda s: None)
        with open(os.path.join(out, "catalogue.json")) as f:
            self.assertEqual(len(json.load(f)["products"]), 2 * B.MIN_PRODUCTS)
        with open(os.path.join(out, "_headers")) as f:
            self.assertIn("Cache-Control", f.read())


if __name__ == "__main__":
    unittest.main()
