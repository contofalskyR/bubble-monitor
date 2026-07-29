"""Glossary & field guide data for the site. Every definition is anchored to the
report's own numbers — terms are defined by use, not in the abstract, which is
how the vocabulary actually sticks. Rendered by build_dashboard.render_glossary()."""

INTRO = [
    ("What this site is",
     "A live appendix to one research document. The report made a falsifiable argument in July 2026 "
     "— the AI buildout is two trades priced as one — and committed in advance to the observations "
     "that would confirm or refute it. This site runs those observations: six credit dials checked "
     "against FRED every weekday, twenty-three filing tripwires read by hand on event days, a dated "
     "calendar through mid-2028, and a journal where predictions are logged before events and scored "
     "after. Nothing here recommends a trade."),
    ("How to read a dial",
     "Big number = the latest fetched value. The line under it is 30 sessions of shape. The gauge "
     "runs from the refutation threshold (blue, left) to the confirmation threshold (red, right); "
     "the dot is where we are, and both distances are printed. A card glows gold when it is 70%+ of "
     "the way to confirm, blue when it is near refute — pressure is visible before anything crosses. "
     "The tag at the bottom says where the number came from and when."),
    ("How to read the stamp",
     "ALL QUIET means nothing crossed and every dial fetched. A crossing turns it red. Dark dials "
     "(failed fetches) are announced on the stamp itself — a number's absence is a finding, never a "
     "pass. Alerts do not live here waiting to be noticed; they open GitHub issues that push to a "
     "phone."),
    ("The discipline",
     "Rule 10.7 of the report, which this site enforces structurally: read the refutation column "
     "first. Every tripwire shows what would prove the thesis wrong with the same prominence as what "
     "would prove it right, the stage engine can declare the thesis losing or dead, and every "
     "threshold change must arrive as a git commit with a reason. If a refuting condition fires and "
     "you reach for a reason it doesn't count, the thesis has become a belief."),
]

GLOSSARY = {
    "Using this site": [
        ("Tripwire",
         "An observation committed to in advance, with two explicit thresholds: one that would confirm "
         "the thesis and one that would refute it. This monitor tracks 29 — six auto-checked against "
         "FRED daily, twenty-three read from filings by hand on the calendar's event days."),
        ("Confirm threshold",
         "The level at which a reading counts FOR the thesis — e.g. CCC OAS above 13.00%. Strictly "
         "greater-than: a value exactly at the line stays quiet, per the report's own wording."),
        ("Refute threshold",
         "The level at which a reading counts AGAINST — e.g. CCC OAS below 8.50%. Displayed first and "
         "left-most everywhere on this site, because that is Rule 10.7."),
        ("Rule 10.7",
         "The report's operating discipline: read the refutation column first; separate the two trades "
         "in every observation; and if a refuting condition is met and you reach for a reason it "
         "doesn't count, the thesis has become a belief."),
        ("Session · 10-session rule",
         "A session is one trading day. The high-yield dial only confirms or refutes if ALL of the "
         "last ten sessions are past the line — so a one-day spike cannot trip it, and a holiday-"
         "shortened window reports a gap rather than quietly judging on fewer days."),
        ("Proximity (warm / cool glow)",
         "How far the current value sits between its two rails, 0 = at refute, 1 = at confirm. Cards "
         "glow gold at 70%+ toward confirm and blue at 30%- (near refute) — the page shows pressure "
         "building in either direction before anything crosses."),
        ("Load-bearing date",
         "One of four dates the report says carry most of the next two years' information: NVIDIA's "
         "Q2 FY2027 print (26 Aug 2026), CoreWeave's cure-window expiry (28 Oct 2026), the FY2026 "
         "10-Ks with useful-life language (Jan–Feb 2027), and DDTL 3.0's first debt-service test "
         "(31 Oct 2027). Gold-ringed on the timeline."),
        ("Stage (0–4)",
         "This monitor's own synthesis — not the report's — of where the thesis stands: 0 Priced as "
         "one · 1 Repricing begins · 2 Pressure builds · 3 Separation at the vehicle level · 4 Broad "
         "repricing. Computed from ten declared rules over the tracked evidence; every rule and its "
         "pass/fail is shown, and the engine can also declare the thesis REFUTED."),
        ("Baseline prior",
         "A declared starting floor of Stage 1, encoding evidence outside the automatable dials — the "
         "report's July 2026 read that periphery repricing was already underway (Oracle 5y CDS at "
         "203bp against an IG index at 79). It is defeasible: it yields whenever refutations "
         "preponderate, and it expires on 31 Oct 2026 unless renewed with a committed reason."),
        ("Provenance tags [V] [C] [R] [EST] [G]",
         "Every number carries its source: [V] fetched/verified from the primary source · [C] "
         "calculated from stated inputs · [R] report value (25 Jul 2026) · [EST] estimated date from "
         "prior-year pattern · [G] gap, could not be fetched. No number appears without one."),
        ("GAP / dark dial",
         "A failed fetch. Rendered as a finding — the card shows the actual error, the stamp counts "
         "the darkness — never silently skipped, because a monitor that can fail quietly will."),
        ("Journal",
         "The append-only record: a prediction logged BEFORE each event (what you expect and why), a "
         "score logged AFTER (what printed, right/wrong/mixed, the lesson). Git commits timestamp it "
         "publicly, which is the entire integrity mechanism of the track record."),
        ("run_date vs obs_date",
         "FRED posts the spread series the morning after the trading day, so the daily check records "
         "both the date it ran and the date the observation is actually from. The archive "
         "(data/history.csv) never conflates the two."),
        ("Heartbeat",
         "The daily bot commit of the history snapshot. It does double duty: it accumulates the "
         "dataset, and it keeps GitHub from disabling the schedule under its ~60-day inactive-repo "
         "rule — the system keeps itself alive."),
        ("Dead-man's switch",
         "MONITOR BROKEN alerts are a separate class from tripwire alerts: all fetches failing, a "
         "missing secret, a crashed step, or a failed deploy each open their own issue. The one thing "
         "this system is structurally forbidden to do is die silently."),
        ("Dial codes (HY · CCC · CCC−HY · BBB · IG · 10Y)",
         "Shorthand for the six FRED series: BAMLH0A0HYM2 (high-yield OAS), BAMLH0A3HYC (CCC OAS), "
         "their difference (dispersion), BAMLC0A4CBBB (BBB OAS), BAMLC0A0CM (investment-grade OAS), "
         "and DGS10 (10-year Treasury)."),
    ],

    "Spreads, rates & the credit market": [
        ("Basis point (bp)",
         "One hundredth of a percentage point. Oracle's CDS at 203bp = 2.03% per year; the IG index "
         "at 79bp = 0.79%."),
        ("Yield",
         "The annual return a bond's price implies if held to maturity. When yields on new debt rise, "
         "every future refinancing gets more expensive — the thesis's core mechanism."),
        ("Coupon",
         "The fixed interest a bond pays. Oracle's maturing notes carry 2.87% and 3.29% coupons "
         "(2027) — money borrowed in a world that no longer exists, to be replaced at ~6.7%+."),
        ("Spread",
         "The extra yield a borrower pays over the risk-free rate. Spread is the market's live "
         "opinion of credit risk, repriced every session — which is why five of the six dials here "
         "are spreads."),
        ("OAS (option-adjusted spread)",
         "The standard spread measure, adjusted for any embedded options in the bonds, so different "
         "credits compare cleanly. The FRED ICE BofA index series this site fetches are all OAS."),
        ("Investment grade (IG)",
         "BBB− and above — debt the rating agencies consider solid. The index at 0.79% sits near its "
         "tightest levels since 1998: the market, in aggregate, is priced for calm."),
        ("High-yield (HY)",
         "Below investment grade ('junk'). At 2.77% at the report date — historically tight — with a "
         "confirm line at 4.50% held for ten sessions, which would mean broad repricing."),
        ("BBB",
         "The lowest investment-grade rung — the cliff edge, because a downgrade from here ('fallen "
         "angel') forces many funds to sell. Dial at 0.98%; confirm above 1.60%."),
        ("CCC",
         "Deep speculative grade — the weakest rated credits. At 9.91% and rising every session from "
         "16–23 Jul while IG slept: stress showing up exactly where the report says it shows first."),
        ("Dispersion (CCC minus HY)",
         "The gap between the weakest credits and the junk index: 7.14 percentage points, a ratio of "
         "3.58x. The report calls this the single most informative number in credit — the market "
         "pricing a tail in the weakest names while the aggregate index radiates calm."),
        ("Credit rating",
         "A letter-grade opinion (AAA down through CCC and below) from S&P, Moody's or Fitch. Note "
         "where the periphery lives: CoreWeave's DDTL 1.0 is unrated — outside the scale entirely."),
        ("10-year Treasury",
         "The benchmark risk-free rate everything else prices off. At 4.71%; above 5.50% would mean "
         "funding stress for the entire buildout, below 4.00% meaningful relief."),
        ("Fed funds rate / FOMC",
         "The Federal Reserve's policy rate (3.63% in June 2026, down from 4.33% a year earlier) and "
         "the committee that sets it. The tripwire is the combination: cuts stopping WHILE spreads "
         "widen — easing that no longer transmits."),
        ("SOFR",
         "The overnight benchmark rate floating-rate loans price off (LIBOR's replacement). A loan at "
         "'SOFR+450' costs the benchmark plus 4.50 percentage points."),
        ("Cost-of-capital ladder",
         "One borrower's live repricing, in four months of 2026: CoreWeave borrowed at SOFR+225 in "
         "March, SOFR+450 in May, and 9.625% unsecured in June. Each new deal is the market's updated "
         "verdict; next unsecured above 11.00% confirms."),
        ("New-issue yield",
         "What the market charges a borrower TODAY, revealed each time it sells bonds. Oracle's "
         "February 2026 prints: 6.74% for 30 years, 6.89% for 40. The next 30-year above 7.50% "
         "confirms."),
        ("CDS (credit default swap)",
         "Insurance on a bond: the buyer pays an annual premium (the CDS spread) and collects if the "
         "borrower defaults. Institutional-only paper — but its price is public information about "
         "fear."),
        ("CDS spread as a signal",
         "Oracle 5-year protection at 203bp against an IG index at 79 means the market charges "
         "roughly 2.6x the index average to insure Oracle — the repricing the report's baseline "
         "prior is built on."),
        ("Refinancing",
         "Replacing maturing debt with new debt at today's prices. The thesis in one sentence: "
         "decade-length assets financed with four-year money must refinance mid-life, at rates "
         "nobody controls."),
        ("Maturity · balloon",
         "The date principal comes due; a 'balloon' is a large lump at the end. Oracle's term loan "
         "leaves a ~$4,645m balloon in August 2027 — the first hard refinancing test on the "
         "calendar."),
        ("Default",
         "Failure to pay, or an uncured covenant breach that lets lenders accelerate. The report's "
         "point about where to look: stress surfaces first at the vehicle level, not the parent."),
    ],

    "Debt, covenants & the periphery's financing": [
        ("Secured vs unsecured",
         "Secured debt has claim to specific collateral; unsecured doesn't and prices wider. "
         "CoreWeave's gap — SOFR+450 secured vs 9.625% unsecured in the same quarter — is the market "
         "pricing the difference between the GPUs and the company."),
        ("Term loan",
         "A bank/fund loan with a set maturity, usually floating-rate over SOFR, usually with "
         "covenants — the periphery's workhorse instrument."),
        ("DDTL (delayed-draw term loan)",
         "A term loan committed now but drawn later as needed. CoreWeave has five — not the three "
         "commonly reported — each inside its own ring-fenced borrower SPV. DDTL 1.0: $1,438m "
         "outstanding at ~15% effective cost, maturing March 2028. The most expensive money comes "
         "due first."),
        ("SPV (special purpose vehicle) · ring-fenced",
         "A separate legal entity holding specific assets and debt, walled off ('ring-fenced') from "
         "the parent. It is why the thesis predicts separation 'at the vehicle level, where almost "
         "nobody is looking' — the parent's face can look fine while a vehicle breaches."),
        ("VIE (variable interest entity)",
         "An entity someone controls economically without majority ownership — the consolidation "
         "rules that decide whose balance sheet an SPV's debt appears on, if anyone's."),
        ("Covenant",
         "A contractual promise inside a loan — maintain this ratio, test it monthly, breach means "
         "default unless cured or waived. Covenants are where credit stress becomes legible before "
         "it becomes public."),
        ("DSCR (debt service coverage ratio)",
         "Cash available to pay debt service, divided by the debt service due. CoreWeave's DDTL 3.0 "
         "requires ≥1.40x on a trailing three-month basis, tested monthly from 31 Oct 2027 — a test "
         "that has already been deferred once. A load-bearing date."),
        ("CRR (collateral ratio requirement)",
         "CoreWeave's monthly collateral coverage test, ≥0.85x, running since 28 Feb 2026 — the "
         "covenant its equity cures exist to fix."),
        ("Equity cure",
         "Shareholders inject cash after the fact to make a failed covenant test pass. A standard "
         "mechanism — but lenders do not negotiate UNLIMITED cures for borrowers who won't need "
         "them."),
        ("The cure window (28 Oct 2026)",
         "CoreWeave negotiated an unlimited number of equity cures through 28 Oct 2026; afterwards "
         "they cap at three of any four consecutive months. Any cure used, or any covenant "
         "shortfall, after that date is the hardest, most binary tripwire in the report."),
        ("Private credit",
         "Non-bank direct lending — the funds financing much of the periphery, typically at ~4-year "
         "tenors with far less public disclosure than bond markets. Where the '$863bn problem' gets "
         "funded."),
        ("144A",
         "A private placement sold only to large institutions, without full SEC registration — "
         "meaning thinner public disclosure on exactly the debt that matters most here."),
        ("Leverage",
         "Debt relative to earnings power. The report works Oracle to 4.33x from its own table — "
         "high for a company guiding to negative free cash flow through the buildout."),
        ("Net cash",
         "More cash than debt. Four of the six largest buyers of AI compute are still net cash — the "
         "single fact that makes the hyperscaler half of the buildout the defensible trade."),
        ("Vendor financing",
         "A supplier funding its own customers' purchases. NVIDIA's $42.3bn book of non-marketable "
         "equity stakes (+$17.9bn in one quarter, $27bn more committed) is the modern, "
         "equity-shaped version."),
        ("Circularity",
         "The same institutions acting simultaneously as investor, supplier, and customer to one "
         "another — mentioned 29 times in the report, because it is the structure that makes "
         "reported revenue quality genuinely hard to assess."),
    ],

    "Accounting & SEC filings": [
        ("EDGAR",
         "The SEC's free public filing database — the report's primary source, and this site's: the "
         "MCP server searches its full text and pulls filings directly."),
        ("10-K",
         "The audited annual report. Where useful-life language lives — the Jan–Feb 2027 10-Ks are a "
         "load-bearing date because that disclosure cannot be spun."),
        ("10-Q",
         "The quarterly report — lighter, unaudited, but where commitments, receivables, inventory "
         "and lease footnotes update four times a year. Most manual tripwires are 10-Q reads."),
        ("8-K",
         "The 'material event' filing, filed within days of the event — where financings, covenant "
         "amendments, and cures surface first. CoreWeave 8-Ks after 28 Oct 2026 are the watch."),
        ("13F",
         "Quarterly disclosure of an institution's US equity holdings, due 45 days after quarter-end "
         "(next: 14 Aug 2026). The watch: NVIDIA's 11.5% CoreWeave stake and 214.8m Intel shares — "
         "either trimmed confirms; either increased refutes."),
        ("424B (prospectus)",
         "The offering document filed when securities are actually sold — where new-issue yields "
         "print. Oracle's next one answers the 7.50% question."),
        ("RPO (remaining performance obligations)",
         "Contract value signed but not yet delivered or recognized as revenue. Oracle: $638bn, of "
         "which only ~12% (~$76.6bn) converts within a year — the gap between promise and cash the "
         "whole Oracle section turns on."),
        ("Backlog",
         "Orders on the books. CoreWeave: $99.4bn against $8.3bn of annualized revenue — about 12x — "
         "with 36% converting inside 24 months. Below 8x via revenue growth refutes."),
        ("Book-to-bill",
         "Orders received divided by orders shipped; above 1 means the backlog is growing. Vertiv "
         "last printed 2.9x — then stopped disclosing the number, which is its own tripwire."),
        ("Take-or-pay",
         "A contract that charges minimums whether or not delivery is taken. AEP's pending tariffs "
         "would hold data-centre loads to 80–90% minimums — take-or-pay applied to electricity."),
        ("Non-cancelable commitments",
         "Obligations that survive a change of mind. Meta: $237.67bn, after a $106.6bn increase in a "
         "single quarter — spending promised regardless of what AI revenue does."),
        ("Supply / purchase commitments",
         "Promises to buy from suppliers. NVIDIA: $119bn, $95bn of it due within FY2027, up 299% "
         "year over year — the demand signal NVIDIA itself has placed."),
        ("Operating vs finance lease",
         "Two accounting treatments for renting an asset; both put a liability on the balance sheet "
         "once the lease STARTS — which is exactly why the ones that haven't started matter."),
        ("ROU (right-of-use) asset",
         "The balance-sheet asset recognized when a lease commences, paired with a lease liability. "
         "An uncommenced lease has neither — yet."),
        ("Leases not yet commenced",
         "Signed lease obligations that haven't started, so they appear only in a footnote: Oracle "
         "$260bn against $30.19bn recognized — 8.6x more obligation off the balance sheet than on "
         "it. Falling >10% in a quarter without a matching ROU increase = cancellation = confirm."),
        ("Off-balance-sheet",
         "Real obligations not on the face of the financial statements. The report's headline "
         "arithmetic: roughly $863bn of signed obligations across six companies live in footnotes."),
        ("Residual value guarantee",
         "A lessee's promise that the asset will be worth a stated amount at lease-end — parking the "
         "risk of GPU values in the fine print. Twelve mentions in the report; watch for them in "
         "lease footnotes."),
        ("Useful life",
         "The years an asset is depreciated over. Today: Microsoft 2–6y, Alphabet 6y, Oracle 6y, "
         "Meta 5.5y, Amazon 5–6y (and Amazon SHORTENED in 2025). Any extension past six years "
         "confirms; the report calls it the single most informative disclosure of the next twelve "
         "months."),
        ("Depreciation (straight-line)",
         "Spreading an asset's cost evenly over its useful life. Lengthen the life, and reported "
         "expense falls with no change in cash — earnings manufactured from an estimate. That is why "
         "the useful-life line is the last remaining earnings lever."),
        ("Implied useful life",
         "Reverse-engineering the life a company is ACTUALLY using from its disclosures. The "
         "report's Section 2.7 method solves Meta's pre-change implied life at 4.61 years — the "
         "naive calculation 'fails by half.' The worked example of reading past the stated number."),
        ("Impairment",
         "A write-down when an asset's carrying value exceeds what it can recover. NVIDIA "
         "impairments above $3bn in a quarter on its equity book would confirm."),
        ("Capex",
         "Capital expenditure — cash spent on long-lived assets. The buildout, in one line item."),
        ("OCF (operating cash flow)",
         "Cash generated by the business itself, before investment. The denominator that decides "
         "whether capex is self-funded or borrowed."),
        ("FCF (free cash flow)",
         "OCF minus capex. Oracle: −$23.7bn — the buildout consuming more cash than the business "
         "produces, the definition of the levered trade."),
        ("Capex/OCF ratio",
         "The tripwire ratio: above 100% means borrowing to build. Alphabet hit 115.0% in Q2 2026, "
         "Amazon 101.7% trailing-twelve-months; the four-company aggregate above 110% for two "
         "straight quarters confirms. Epoch's estimate has the aggregate crossing OCF around Q3 "
         "2026."),
        ("DSO (days sales outstanding)",
         "How long customers take to pay: receivables ÷ quarterly revenue × 91. NVIDIA sits at 45.4 "
         "days; above 65 confirms — customers stretching payment is strain before it is news."),
        ("Receivable concentration",
         "How much of the money owed comes from few payers: NVIDIA's top three customers are 64% of "
         "receivables, with no allowance for credit losses disclosed. Above 70% with rising DSO — "
         "or a first-ever allowance — confirms."),
        ("Non-marketable equity",
         "Stakes in private companies, carried at cost with adjustments — NVIDIA's $42,336m book, "
         "up $17,899m in a single quarter. The vendor-financing flywheel, on the asset side."),
        ("Inventory · raw materials",
         "Goods and inputs on hand. NVIDIA: $25,797m (~115 days), raw materials +74.6% in a "
         "quarter — building for demand that hasn't ordered yet. Above $35bn while sequential "
         "revenue growth is under 10% confirms."),
        ("DISE (ASU 2024-03)",
         "A new accounting standard disaggregating expenses inside each income-statement line, "
         "effective 1 Jan 2027, first annual 10-Ks in Jan–Feb 2028 — the first genuinely new "
         "disclosure in a decade, which makes the report's Section 2 questions answerable."),
        ("S7-2026-15 (the meta-risk)",
         "The SEC proposal to allow semiannual instead of quarterly reporting. If adopted and "
         "elected, half of this monitor's observation points disappear — the report's own flagged "
         "threat to its framework. It goes on the calendar the day it gets an effective date."),
    ],

    "The cast & the physical build": [
        ("Hyperscaler",
         "Microsoft, Alphabet, Amazon, Meta: enormous capex out of enormous operating cash flow, "
         "against contracted, audited revenue — the defensible half of the buildout."),
        ("Neocloud / the periphery",
         "The GPU-rental and levered-builder cohort — CoreWeave the archetype — plus the SPVs and "
         "private-credit-funded developers: decade-length assets financed with roughly four-year "
         "money, against backlog rather than revenue."),
        ("Two trades priced as one",
         "The thesis in five words: the market is financing the periphery at something close to the "
         "credit quality of the hyperscalers, and the risk is that they separate — at the vehicle "
         "level."),
        ("The GPU-life debate",
         "The question under every useful-life line: do accelerators really produce competitive "
         "revenue for five or six years? Every extension bets yes with shareholders' reported "
         "earnings; Amazon's 2025 shortening bet no."),
        ("GW (gigawatt)",
         "A billion watts — the capacity currency of the buildout, for both compute and the power "
         "that feeds it."),
        ("Reservation vs firm order",
         "A reservation holds a manufacturing slot; a firm order is a contract. GE Vernova's 116 GW "
         "gas 'position' is 54% reservations — and last quarter added 18 GW of reservations against "
         "2 GW of firm orders. The conversion rate is the single most important supply-chain "
         "number."),
        ("Slot cancellation",
         "Giving back a reserved production position. Any disclosed slot cancellation at GE Vernova "
         "confirms — it would mean the buildout's committed demand is softer than its stated "
         "demand."),
        ("Renewal spread",
         "The price change when a data-centre lease renews. Digital Realty: +5.0% cash at 90.1% "
         "occupancy — solid, not shortage. Negative confirms oversupply; above +15% would refute "
         "with genuine scarcity pricing."),
        ("Occupancy",
         "The share of built capacity actually leased. Falling occupancy plus negative renewal "
         "spreads is what data-centre oversupply looks like in a REIT's disclosures."),
        ("PUC (public utility commission)",
         "The state regulator that approves electricity tariffs. Cases pending in Michigan, "
         "Oklahoma, Texas and Virginia decide whether large-load take-or-pay minimums spread — "
         "spreading confirms; rejection refutes."),
        ("PJM · $325/MW-day",
         "The largest US grid operator and the record price its capacity auction cleared for the "
         "2028/29 delivery year, beginning 1 Jun 2028 — the electricity bill the data-centre load "
         "must absorb, already scheduled."),
        ("Powered land / shell",
         "Industry shorthand for sites with electrical capacity secured but buildings unbuilt or "
         "unfitted — where much of the periphery's committed capex physically sits while its leases "
         "remain uncommenced."),
    ],
}
