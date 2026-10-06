# Buying Window

Pick what you sell. See the Minneapolis-area businesses that just started needing it.

**Live:** https://buying-window.vercel.app

A business is easiest to win in the weeks it is changing: building out a space,
getting a liquor license, opening its doors. It has no bookkeeper, linen route, sign
shop or trash hauler yet, so there is nobody to switch away from. Those changes leave
public records. This site reads them, sorts them by trade, and hands you the list.

It started with one bookkeeper. He got a list of restaurant build-outs, saw a café he
knew at final inspection, and had a meeting set up the next day. This is the same
list for every B2B trade.

## What counts as a change

| Event | Source | Means |
|---|---|---|
| Building out a space | Minneapolis building permits (CCS_Permits) | a new tenant, or a big remodel, is under way |
| New liquor license | Minneapolis on-sale liquor licenses | a new bar or restaurant, or new owners (license numbers are sequential) |
| Just opened | Minneapolis food inspections | a kitchen got its first-ever health inspection |
| Building coming down | Minneapolis wrecking permits (commercial and apartment) | a teardown |
| Layoffs or closing | Minnesota DEED WARN notices | a site will shed jobs or close |

Every row links to the city or state record it came from. Every count on the page is
computed from the data.

## Trades

`pipeline/trades.py` maps 6-digit NAICS trades (from Census County Business Patterns)
to the events that open their buying window, with a one-line reason for each. A trade
with no plausible event is left out.

## Run it

```
python3 pipeline/build.py      # pulls the public sources, writes site/data/
python3 -m pytest -q tests     # the data agrees with itself
VERCEL_TOKEN=... python3 scripts/deploy.py
```

No keys needed to build. The WARN rows are read from the Brick & Mortar layer
(`bricks/website/api/_data/twincities_layoff_notices.json`), which caches DEED's PDFs.

## License

MIT. The data is public record from the City of Minneapolis and the State of Minnesota.
