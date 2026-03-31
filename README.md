# resource vs gdp

what happens to a country's economy after it strikes oil, diamonds, or copper? does it get rich? does it stay rich? does it get worse?

this is an interactive chart of 28 countries, tracking gdp per person from 20 years *before* extraction started to 60 years *after*. every line starts at 100 so you can compare trajectories instead of absolute wealth — norway in 1971 and nigeria in 1958 plotted on the same scale.

**→ [open the chart](https://03shraddha.github.io/resource-vs-gdp/)**

---

## what you can do with it

- **drag the slider** to move the "after" endpoint from t+10 to t+60 — watch how rankings change completely over time
- **click a country in the legend** to hide/show it; **double-click** to isolate it
- **click any row in the table** to read the country's story
- **contrast mode** shows just the sharpest divergence pairs (norway vs nigeria, botswana vs sierra leone, etc.)
- **t−5 / t+5 buttons** shift the extraction start date ±5 years — useful for checking whether a finding survives if the t=0 date is slightly wrong

---

## data sources

| source | what it covers | indicator |
|--------|---------------|-----------|
| [world bank wdi](https://data.worldbank.org/indicator/NY.GDP.PCAP.PP.KD) | gdp per capita, 1990–2023 | ny.gdp.pcap.pp.kd (constant 2021 ppp $) |
| [maddison project 2023](https://www.rug.nl/ggdc/historicaldevelopment/maddison/releases/maddison-project-database-2023) | historical gdp per capita, pre-1990 | cgdppc (2011 int'l $) |

the two sources are spliced together: world bank values are used directly from 1990 onward; maddison growth rates are used to backfill earlier years by chaining them to the 1990 anchor. this means absolute levels are in world bank's 2021 ppp dollars throughout.

---

## how the chart works

**event-study indexing** — each country's gdp/pc is set to 100 in its t=0 year. this removes the "norway started rich" problem and lets you compare growth *trajectories* across countries that started at wildly different income levels.

**t=0** — the first year of *commercially significant* extraction, not discovery. discovery and first revenue can be decades apart (chad's oil was discovered in the 1970s, commercial extraction started 2003).

**dashed vs solid lines** — solid lines are world bank data (post-1990). dashed lines are maddison-backfilled estimates (pre-1990). the dashed sections are directionally reliable but not precise — treat them as "roughly this shape."

**the ⚠ flag** — countries where gdp per capita is a poor welfare proxy because oil revenues were so concentrated at the top. the average can look great while most people see nothing.

---

## running it locally

just open `index.html` in a browser — no server, no build step, no dependencies. the chart data is embedded directly in the html.

to regenerate the data from scratch:
```bash
pip install requests openpyxl
python analyze.py
```

note: `analyze.py` requires the maddison 2023 excel file (the dataverse download is sometimes blocked). if you get a 403, download it manually from the maddison project page and place it at `cache/maddison.xlsx`.

---

## countries included

**oil:** norway, nigeria, equatorial guinea, saudi arabia, venezuela, angola, indonesia, malaysia, uae, kazakhstan, ghana, chad, libya, algeria, ecuador, iran, iraq, oman, trinidad & tobago, azerbaijan, colombia, bolivia

**minerals:** botswana (diamonds), zambia (copper), drc (cobalt/coltan), chile (copper), sierra leone (diamonds), nauru (phosphate)

---

## 10 counterintuitive findings

| # | finding | the "wait, that makes no sense" moment | countries | index at t+30 |
|---|---------|---------------------------------------|-----------|--------------|
| 1 | **uae beat norway by 2.6x** despite having no democratic institutions | theory says you need rule of law to turn oil into growth. uae has neither elections nor transparency — and still won | UAE vs Norway | 752 vs 284 |
| 2 | **venezuela is poorer now than before oil** | a century of extraction left the average venezuelan worse off in real terms than when the first well was drilled | Venezuela | 68 at t+60 (started at 100) |
| 3 | **nauru went from richest to nearly nothing** in 30 years — no war, no sanctions | they spent every cent on a national airline that flew empty routes, a west end musical that bombed, and advisors who stole the rest | Nauru | 756 → 38 by t+60 |
| 4 | **libya had the steepest 10-year rise in the dataset** — starting as the poorest country in africa | in 1960 libya was poorer than most of sub-saharan africa. by 1970 it had one of the highest per-capita incomes on earth | Libya | 590 at t+10 |
| 5 | **the world bank built chad a special pipeline with international monitors** — it failed completely | chad changed the law, spent the money on weapons, and the world bank pulled out. t+30 index: 112 | Chad | 112 |
| 6 | **botswana (552) vs drc (92, falling)** — same resource type, same continent, same starting poverty | the drc sits on ~$24 trillion in minerals and is still one of the world's poorest countries. botswana negotiated fair terms with de beers and built institutions | Botswana vs DRC | 552 vs 92 |
| 7 | **angola's gdp fell to 54 at t+10 while oil was flowing the whole time** | oil money funded both sides of a 27-year civil war. extraction + active conflict = worse than no extraction | Angola | drops to 54, recovers to 162 |
| 8 | **indonesia: 100+ years of oil, barely moved** | after 30 years past t=0, indonesia's index is 126 — less than bolivia, which is landlocked and had its industry nationalized | Indonesia vs Bolivia | 126 vs 132 |
| 9 | **equatorial guinea's index hit 650 — most citizens still live on under $2/day** | gdp per capita is an average. when one family takes almost all the oil money, the average looks great while nothing reaches ordinary people | Equatorial Guinea | 650 (⚠ welfare proxy) |
| 10 | **oman banned glasses and books until 1970, then built a functional modern state in one generation** | sultan qaboos took power in 1970 in one of the most isolated countries on earth and used oil revenue to build schools, roads, and hospitals from scratch. index 682 at t+30 — same tier as uae, never mentioned in textbooks | Oman | 682 |

**the single most theoretically interesting comparison: botswana vs drc.** same resource type (minerals), same continent, both starting from extreme poverty with a colonial extractive history. the only meaningful difference is what the government chose to do with the money. outcome gap: 6x. no other pair in the dataset has such similar starting conditions and such a clean divergence.

---

made with world bank api + maddison project data. no frameworks, no build tools.
