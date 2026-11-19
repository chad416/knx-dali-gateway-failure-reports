# Changelog

## 0.2.0 - 2026-11-19

The gateway now follows the documents of three real KNX/DALI gateways of one manufacturer
(variants B, P and L, sources S13 to S18) instead of one generic parameter set. The
manufacturer is not named on purpose; the documents are public.

- New `daligw/variants.py`: channels, gear, groups and scenes per channel, supply
  currents, short-circuit times, cable limit, polling rule, emergency-test support and
  energy-saving function for each variant, every value with section and page, or marked
  "not stated". Why: the earlier overload sweep used a guaranteed current of 150 mA that
  no source gives, and the polling rule came from one product only; the findings should
  hold for real gateways, and say where their documents are silent.
- The simulated gateway takes its polling rule (1 s per gear and error type) from variant
  B, the only variant that documents it. It is the same rule as before (S9), so the
  diagnosis results did not change. For P and L the reporting delay is now stated as not
  documented instead of being implied.
- The bus failure object is sent 0.6 s after a short (variant B's shutdown time) instead
  of 0.5 s (A8). No result changed.
- Supply: budget per variant (B 53 gear with the planning reserve, P 64, L 53 on its
  maximum). The overload sweep now uses B's 128 / 250 mA instead of an undocumented
  150 / 250 mA: answers fail from 23 % (was 16 %) and all gear are lost at 30 % (was 21 %)
  with the sagging supply; with the hard limit at 96 % (was 67 %). The curve above the
  guaranteed current is still assumption A6. P has no margin between its two figures.
- Short circuit (variant B): the bus is back at most 5 s after a short clears; a fault
  that began during the short is reported at most 133 s after it clears. The repetition of
  the start-up attempt is a new assumption, A18.
- New open question A19: no document says whether failure reports are held back while the
  gateway's energy-saving function has switched a gear's mains off. Both answers are
  simulated (T14) and a bench test is given.
- The emergency-test class is claimed only for variant L. B's documents say test commands
  are not supported; P's do not say.
- New `docs/BENCH_TEST_PLAN.md`: for each assumption that carries a finding, the
  measurement on a real line and gateway that would replace it.
- Tables T12 to T14, 12 new tests (95 in total).

## 0.1.0 - 2026-11-19

First complete version.

- DALI line at frame and half-bit level: Manchester coding, DALI-2 stop condition and
  settling times, backward-frame window, status byte, wired-AND superposition of answers
  with per-product reply delays, receiver with gear and control-device thresholds.
- Electrical model: loop resistance, daisy-chain voltages, supply with guaranteed and
  maximum current (two curve shapes), noise on each half-bit sample.
- Gateway: commissioning outcome, slot polling per gear and error type, KNX failure
  objects for lamp, gear and bus, automatic replacement with the error codes of S9.
- Ten faults and healthy; diagnosis engine at four evidence levels; evaluation over 660
  randomised installations; studies of reporting delay, stagger, supply budget, wiring and
  separately switched mains.
- One worked support case in `docs/SUPPORT_CASE.md`.

Changes made during development that altered results:

- SUPPLY_LOW was first injected as "the far gear drop below 9.5 V while the near ones stay".
  The run showed that this cannot happen on a cable inside the table: the gateway reads
  high only above 10 V, so its own receiver fails before any gear does. The class is now
  "gateway voltage just above the gear threshold", which loses most or all gear at once.
- "Gear without short address" was first certain whenever the missing-address probe got a
  clean yes and nothing else was abnormal. In one SUPPLY_LOW run an unfound gear gave that
  yes. The rule now also needs the idle voltage inside the 12 to 20.5 V supply range.
- The E4 rules for switched mains and emergency tests first compared the span from the
  first to the last silent poll with the logged off period. Two off periods with a gap in
  between failed that test. Now every silent poll must fall inside a logged off period.
- At E3 one gear that came back with the power-cycle bit first made "emergency test" rank
  above a six-gear common mains loss. The number of gear that went silent and came back
  now decides, the bit only strengthens it (a switching command clears it quickly).
- The far-end rule first fired on a single weak answer. It now needs three; with the
  assumed 0.6 V noise a line inside the cable table gives a weak answer with probability
  of about 2 x 10^-5 per poll.
