# OmaSaber's partner catalogue

The catalogue behind the [OmaSaber](https://github.com/omauilabs/omasaber) Shop: sabers from CC Sabers and NeoSabers, one file, compared by the board inside.

Both partners are Shopify stores with a public `/products.json`. On a store, a saber is one product whose variants pick a board (the store's board option: `Electronics` at CC Sabers, `Type` at NeoSabers) and a blade length. `build.py` keeps the products that have that option and gives each one offer per board, at that board's lowest price. Each board is mapped to OmaSaber's platform ids in `platforms.json`. A product with no board, no photo or no price is left out: T-shirts, stands, blade tips and free gifts.

- **The file:** `https://omasaber-catalogue.pages.dev/catalogue.json` (schema `omasaber.catalogue.v1`).
- **When:** built every day at 06:00 UTC on OmaSaber's own runner, and deployed to Cloudflare Pages. It runs on a schedule or by hand only, never on a pull request.
- **When a check fails:** if a store returns fewer than 50 sabers, or a product lacks an offer or a photo, nothing is deployed and yesterday's catalogue stays up.

```
python3 -m unittest discover -s tests     the tests
python3 build.py --out site                build it here (about a minute: a second between pages)
```

## Changing it

- **A board name the build reports as unknown:** add it to `platforms.json`, with its start mapped to a platform id. Map it to `"-"` when it isn't a board, such as a blade shape or a stand.
- **A store:** add it to `stores.json`: `id`, `name`, `url`, `boardOption`, `referral`. Only Shopify stores fit as they are.
- **A referral code:** set `referral.code` in `stores.json`. OmaSaber adds `?ref=CODE` to that store's links while its user keeps "Use referral links" on.

## Referral links

OmaSaber earns a referral fee from CC Sabers and NeoSabers when someone buys through these links. It doesn't change the price. OmaSaber shows this in its Shop, and anyone can turn referral links off there.

Star Wars and related names are trademarks of Lucasfilm Ltd. / Disney. OmaSaber, CC Sabers and NeoSabers are not affiliated with them.

MIT licensed.
