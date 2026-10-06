"""Which change events mean "this business needs you now", per B2B trade.

Each trade is one 6-digit NAICS code from the Census County Business Patterns layer
(bricks/data/cbp_trades_twincities.json, 318 Twin Cities trades). A trade is listed
only when a public event plausibly opens its buying window; trades with no trigger
are left out, not padded. `triggers` is a list of (event, segments): an empty
segment list means every build-out, otherwise only build-outs of those kinds
(food, retail, care, office, other — see SEGMENTS in build.py).

The buyer logic comes from Joel Oine (Blue Vector, 2026-10-05): a business under
construction or near final inspection "is likely making decisions right now about
accounting, POS, payroll, banking, vendors and other operational infrastructure".
"""

TRIGGERS = {
    "buildout": {"label": "Building out a space", "short": "Build-out"},
    "liquor": {"label": "New liquor license", "short": "Liquor license"},
    "first_inspection": {"label": "Just opened", "short": "Just opened"},
    "wrecking": {"label": "Building coming down", "short": "Wrecking"},
    "warn": {"label": "Layoffs or closing", "short": "Layoffs"},
}

FOODISH = ["food"]
STOREFRONT = ["food", "retail", "care"]
ALL = []

NEW_BIZ_WHY = {
    "buildout": "A new tenant is building out. They have no vendor yet to switch away from.",
    "liquor": "A new liquor license usually means a new place, or new owners.",
    "first_inspection": "The city just inspected this kitchen for the first time. It just opened.",
}

TRADES = [
    # --- money and paperwork: every new business needs one
    dict(slug="bookkeeping", name="Bookkeeping and accounting", naics="541219", group="Money and paperwork",
         triggers=[("buildout", STOREFRONT), ("liquor", ALL), ("first_inspection", ALL)], why=NEW_BIZ_WHY),
    dict(slug="cpa", name="CPA firms", naics="541211", group="Money and paperwork",
         triggers=[("buildout", STOREFRONT), ("liquor", ALL), ("first_inspection", ALL)], why=NEW_BIZ_WHY),
    dict(slug="payroll", name="Payroll services", naics="541214", group="Money and paperwork",
         triggers=[("buildout", STOREFRONT), ("liquor", ALL), ("first_inspection", ALL)],
         why={**NEW_BIZ_WHY, "buildout": "They will hire before they open. Payroll gets picked now."}),
    dict(slug="insurance", name="Insurance agents", naics="524210", group="Money and paperwork",
         triggers=[("buildout", ALL), ("liquor", ALL), ("first_inspection", ALL)],
         why={**NEW_BIZ_WHY, "liquor": "A liquor license needs liquor liability coverage before it can serve.",
              "buildout": "A new space needs a new policy before the doors open."}),
    dict(slug="banks", name="Banks", naics="522110", group="Money and paperwork",
         triggers=[("buildout", STOREFRONT), ("liquor", ALL), ("first_inspection", ALL)], why=NEW_BIZ_WHY),
    dict(slug="credit-unions", name="Credit unions", naics="522130", group="Money and paperwork",
         triggers=[("buildout", STOREFRONT), ("liquor", ALL), ("first_inspection", ALL)], why=NEW_BIZ_WHY),

    # --- selling to restaurants and bars
    dict(slug="restaurant-equipment", name="Restaurant equipment and POS", naics="423440", group="Restaurants and bars",
         triggers=[("buildout", FOODISH), ("liquor", ALL)],
         why={"buildout": "A kitchen is being built. The equipment list is being written now.",
              "liquor": "A new bar or restaurant needs a register and a bar setup."}),
    dict(slug="restaurant-supply", name="Restaurant supply", naics="423850", group="Restaurants and bars",
         triggers=[("buildout", FOODISH), ("liquor", ALL), ("first_inspection", ALL)],
         why={"buildout": "A kitchen is being built and has no supplier yet.",
              "liquor": "A new place is stocking up for the first time.",
              "first_inspection": "Just opened. They are still picking who they order from."}),
    dict(slug="food-distributors", name="Food distributors", naics="424490", group="Restaurants and bars",
         triggers=[("buildout", FOODISH), ("liquor", ALL), ("first_inspection", ALL)],
         why={"buildout": "A new kitchen will need a food order before it opens.",
              "liquor": "A new place is setting up its first orders.",
              "first_inspection": "Just opened. Their first supplier is not locked in."}),
    dict(slug="breweries", name="Breweries (selling to bars)", naics="312120", group="Restaurants and bars",
         triggers=[("liquor", ALL)],
         why={"liquor": "A new license means a new tap list is being picked."}),
    dict(slug="linen", name="Linen and laundry service", naics="812320", group="Restaurants and bars",
         triggers=[("buildout", FOODISH), ("liquor", ALL), ("first_inspection", ALL)],
         why={"buildout": "A new kitchen needs aprons, towels and table linen.",
              "liquor": "A new bar or restaurant needs a linen route.",
              "first_inspection": "Just opened. Linen is often set up after the doors open."}),
    dict(slug="pest-control", name="Pest control", naics="561710", group="Restaurants and bars",
         triggers=[("buildout", FOODISH), ("first_inspection", ALL)],
         why={"buildout": "A new kitchen needs a pest contract before its health inspection.",
              "first_inspection": "The health inspector just came. Pest control is on their checklist."}),
    dict(slug="printing", name="Printers (menus, signs, cards)", naics="323111", group="Restaurants and bars",
         triggers=[("liquor", ALL), ("first_inspection", ALL)],
         why={"liquor": "A new place needs menus and cards.",
              "first_inspection": "Just opened. Menus and cards get reprinted in the first months."}),

    # --- selling to a new space
    dict(slug="signs", name="Sign shops", naics="339950", group="New storefronts",
         triggers=[("buildout", STOREFRONT), ("liquor", ALL)],
         why={"buildout": "A new tenant needs a sign before opening day.",
              "liquor": "A new name over the door needs a new sign."}),
    dict(slug="cleaning", name="Commercial cleaning", naics="561720", group="New storefronts",
         triggers=[("buildout", ALL), ("first_inspection", ALL)],
         why={"buildout": "Construction ends with a turnover clean, then a cleaning contract.",
              "first_inspection": "Just opened. Nightly cleaning gets set up now."}),
    dict(slug="security-systems", name="Security systems and alarms", naics="561621", group="New storefronts",
         triggers=[("buildout", ALL), ("liquor", ALL)],
         why={"buildout": "Cameras and alarms go in during the build-out.",
              "liquor": "Bars need cameras and alarms before they open."}),
    dict(slug="internet", name="Business internet and phone", naics="517311", group="New storefronts",
         triggers=[("buildout", ALL), ("first_inspection", ALL)],
         why={"buildout": "A new space needs internet and phones on day one.",
              "first_inspection": "Just opened. Many start on a stopgap plan."}),
    dict(slug="it-services", name="IT services", naics="541512", group="New storefronts",
         triggers=[("buildout", ["office", "care"])],
         why={"buildout": "A new office or clinic needs its network and computers set up."}),
    dict(slug="waste", name="Trash and recycling haulers", naics="562111", group="New storefronts",
         triggers=[("buildout", ALL), ("first_inspection", ALL), ("wrecking", ALL)],
         why={"buildout": "A new tenant needs a trash contract, and the job site needs a dumpster.",
              "first_inspection": "Just opened. Trash pickup gets set up now.",
              "wrecking": "A teardown fills roll-off dumpsters."}),
    dict(slug="movers", name="Office and business movers", naics="484210", group="New storefronts",
         triggers=[("buildout", ["office", "care", "retail"]), ("warn", ALL)],
         why={"buildout": "Someone is moving into this space soon.",
              "warn": "A site is closing. Someone has to move what is inside."}),
    dict(slug="marketing", name="Marketing consultants", naics="541613", group="New storefronts",
         triggers=[("liquor", ALL), ("first_inspection", ALL)],
         why={"liquor": "A new place needs to get the word out before opening.",
              "first_inspection": "Just opened. The first months decide if they make it."}),

    # --- teardowns
    dict(slug="scrap", name="Scrap metal buyers", naics="423930", group="Teardowns",
         triggers=[("wrecking", ALL)],
         why={"wrecking": "A commercial building is coming down. Its metal goes somewhere."}),
    dict(slug="salvage", name="Salvage and used goods", naics="453310", group="Teardowns",
         triggers=[("wrecking", ALL), ("warn", ALL)],
         why={"wrecking": "Fixtures and materials can be pulled before the wreck.",
              "warn": "A closing site often sells off what is inside."}),
    dict(slug="remediation", name="Asbestos and remediation", naics="562910", group="Teardowns",
         triggers=[("wrecking", ALL)],
         why={"wrecking": "Old buildings get checked for asbestos before they come down."}),
    dict(slug="site-prep", name="Site prep and excavation", naics="238910", group="Teardowns",
         triggers=[("wrecking", ALL)],
         why={"wrecking": "After the wreck, the lot gets graded for what comes next."}),
    dict(slug="security-guards", name="Security guards", naics="561612", group="Teardowns",
         triggers=[("wrecking", ALL), ("warn", ALL), ("liquor", ALL)],
         why={"wrecking": "Empty buildings waiting to come down need watching.",
              "warn": "A closing site needs guarding after the last shift.",
              "liquor": "New bars hire door staff."}),

    # --- layoffs and closings
    dict(slug="staffing", name="Staffing agencies", naics="561320", group="Layoffs and closings",
         triggers=[("warn", ALL), ("first_inspection", ALL), ("liquor", ALL)],
         why={"warn": "Workers here are about to need jobs. Good people, ready now.",
              "first_inspection": "Just opened, and new places are short-staffed.",
              "liquor": "A new bar or restaurant is hiring."}),
    dict(slug="placement", name="Job placement agencies", naics="561311", group="Layoffs and closings",
         triggers=[("warn", ALL)],
         why={"warn": "Workers here are about to need jobs."}),
    dict(slug="hr-consulting", name="HR and outplacement", naics="541612", group="Layoffs and closings",
         triggers=[("warn", ALL)],
         why={"warn": "A layoff needs outplacement help and HR support."}),
    dict(slug="used-equipment", name="Used machinery dealers", naics="423830", group="Layoffs and closings",
         triggers=[("warn", ALL)],
         why={"warn": "A closing plant sells off its machines."}),
    dict(slug="cre-brokers", name="Commercial real estate brokers", naics="531210", group="Layoffs and closings",
         triggers=[("warn", ALL), ("wrecking", ALL)],
         why={"warn": "A closing site will be empty space soon.",
              "wrecking": "A teardown means a lot is about to be rebuilt or sold."}),
]
