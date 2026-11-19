# Changelog

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
