# Engineering dossier: failure reports of a KNX/DALI gateway

Simulated study. No hardware and no recording from a real installation was used. All
result numbers are in `results/summary.json` and are produced by
`python scripts/run_all.py`; tables T1 to T14 are in `results/tables.md`. Source ids
(S1 to S18) refer to `docs/SOURCES.md`; S13 to S18 are the documents of three gateway
variants B, P and L of one manufacturer (`daligw/variants.py`). IEC 62386 was not read; every protocol value is a
manufacturer's restatement of it. The structure follows Wasson, *System Engineering
Analysis, Design, and Development*.

## 1. Need and operational concept

**Need.** An expert-support engineer gets cases about lighting on a KNX/DALI gateway:
"the visualisation reports driver failures that are not there", "a lamp has been dark for
a week and no alarm came", "after adding luminaires the gateway does not find them",
"the lights switch one after another". What he can collect ranges from a screenshot of the
KNX failure objects to a site visit with a DALI bus monitor and the electrical drawings. He
needs to know which causes each kind of evidence can prove, what to ask for next, and the
timing and electrical limits behind the symptoms.

**Question.** Which causes of a reported, missing or late failure can be told apart with
certainty, from which evidence, and how long can a real failure go unreported?

**Scenarios.**

| Id | Scenario | Evidence |
|---|---|---|
| OS-1 | Customer sends the KNX failure-object history from the visualisation | E1 |
| OS-2 | Customer also sends screenshots of the gateway's diagnostics page | E2 |
| OS-3 | Engineer connects a DALI bus monitor and runs a short probe | E3 |
| OS-4 | Site visit: circuit plan, emergency test plan, cable and supply data | E4 |
| OS-5 | Commissioning: polling slot, addressing mode, supply and cable sizing | studies |

**System of interest.** A diagnosis engine and the line model that feeds it. The line model
is the test bench: it produces the evidence of a virtual installation with a known injected
fault. The engine gets the evidence only, never the label.

## 2. Modes and states

**Control gear** (`daligw/line.py`): unpowered (mains off: silent although the bus is up)
-> powered, sets bit 7 "power cycle seen" -> normal (answers queries, follows commands;
any switching command clears bit 7, A10) -> lamp failed (answers, bit 1) / gear fault
(answers, bit 0) / dead (silent). A gear whose idle bus voltage is below 9.5 V (S8) does
not see a valid bus and does not answer.

**Gateway** (`daligw/scenario.py`):

```
commissioning: search -> found gear get short addresses -> known list
normal:  slot k -> QUERY STATUS to gear (k div 2) of the known list
           even slot: valid answer -> gear object = bit 0; no valid answer -> gear object = 1
           odd slot:  valid answer -> lamp object = bit 1; no valid answer -> unchanged
         KNX command -> DALI group / individual / broadcast command
bus short (output shut down after 0.6 s, S15; object sent then, A8) -> bus object = 1, polling stops
replacement request -> count faulty known gear and new unaddressed gear -> result 0, 7..11 (S9)
```

**Diagnosis session:** E1 -> hypotheses with certainty -> if not certain, the report names
what the next level would add -> E2 -> E3 -> E4.

## 3. Requirements

| Id | Requirement | Source | Verification |
|---|---|---|---|
| R-01 | 1200 bit/s Manchester, bit 0.833 ms, MSB first | S1, S2, S3 | test `test_bit_time_and_half_bit`, round trip of all bit patterns |
| R-02 | Stop condition at least 2.45 ms (DALI-2 framing) | S1 | test `test_backward_waveform_length` |
| R-03 | Backward frame 9.95 ms; forward frame 16 bits | S3 | test against the stated 9.95 ms; 16.62 ms derived against 16.2 ms stated (under 3 %) |
| R-04 | Backward frame starts 5.5 to 10.5 ms after the forward frame | S1, S3 | reply delays drawn in that window; `query_time_no_answer` |
| R-05 | Settling time before a forward frame by priority (13.5 to 21.2 ms) | S1 | test `test_settling_times_increase_with_lower_priority` |
| R-06 | 64 short addresses, 16 groups, gear without address answers only broadcast | S2, S4, S5 | installation generator, probe |
| R-07 | Status byte bits 0 to 7 as in S2 and S4 | S2, S4 | tests `test_status_byte_bits`, round trip of all 256 values |
| R-08 | Answer 0xFF = yes, no answer = no | S3 | probe of QUERY MISSING SHORT ADDRESS |
| R-09 | Supply never above 250 mA; consumption at most the guaranteed current; plan with / 1.2 | S7, S8 | test `test_supply_budget` |
| R-09a | Built-in supply per variant: B min. 128 / max. 250 mA, P 160 / 160 mA, L max. 128 mA; no additional supply (B, L) | S13, S15, S16, S18 | test `test_budget_per_variant` |
| R-10 | Each unit draws at most 2 mA | S8 | gear draw 1 to 2 mA |
| R-11 | Gear read high above 9.5 V, low below 6.5 V; a control device high above 10 V, low below 4.5 V | S8 | reception model, overload sweep |
| R-12 | Voltage drop 2 V; conductor table 0.5 / 0.75 / 1.5 mm2 for 100 / 150 / 300 m | S2, S8 | test `test_conductor_table_is_a_constant_resistance_rule` |
| R-13 | Polling: 1 s per gear and error type, 64 gear = 128 s; settings 0.5 to 10 s or none (variant B); not documented for P and L | S9, S13 | tests `test_polling_delay_no_traffic_matches_formula`, `test_polling_rule_only_where_documented` |
| R-14 | Bus short: bus object, no further errors recognised | S5, S9, S16 | test `test_bus_short_masks_everything` |
| R-14a | Variant B: output off 0.6 s after a short, start-up attempt 5 s after detection | S15 | test `test_short_circuit_timing_variant_b` |
| R-15 | Automatic replacement only for one faulty and one new gear of the same type; error codes 7 to 11 | S9 | test `test_replace_two_aborts_with_error_8` |
| R-16 | The normal gear of an emergency pair is disconnected during a test and reported failed unless declared | S5, S9 | EMERG_TEST class |
| R-16a | The EMERG_TEST class is claimed only for a variant that supports emergency tests (L); outside B (test commands not supported), not stated for P | S15, S16, S17 | test `test_emergency_class_only_where_tests_are_supported` |
| R-17 | A verdict marked "certain" must not be wrong | need | evaluation: wrong certain verdicts = 0 |
| R-18 | A healthy installation must not be accused | need | HEALTHY row of the confusion matrices |
| R-19 | Every hypothesis states the evidence it rests on | need | report text, `results/support_case.txt` |

## 4. Architecture and interfaces

```
daligw/constants.py   values with source ids                         (R-01..R-16)
daligw/frames.py      timing, Manchester, wired-AND, receiver, status (R-01..R-08)
daligw/electrical.py  cable, supply, voltages, error model            (R-09..R-12)
daligw/line.py        gear, reception of one or several answers
daligw/scenario.py    installation, faults, commissioning, gateway    (R-13..R-16)
daligw/diagnose.py    engine                                          (R-17..R-19)
daligw/evaluate.py    confusion matrices
daligw/studies.py     delay, stagger, budget, wiring, mains
```

**Interface line model -> engine.** An `Evidence` record with five parts. E1: list of (time,
object, short address, value) as sent to KNX. E2: known short addresses, bus state, last
replacement result, current error flags. E3: one record per gateway poll (time, address,
reception none / ok / corrupt, value, mark) plus a probe after the window (QUERY STATUS to
all 64 addresses, QUERY MISSING SHORT ADDRESS) and the idle voltage at the gateway. E4:
luminaire list with the address documented at commissioning, switched-circuit members and
their on/off log, emergency pairs and test times, exchanged gear, cable length and size,
supply ratings, total draw from datasheets. The engine never sees the fault label, the
positions of addresses on the cable or the noise level.

**Receiver marks.** A corrupt answer carries a mark. *extra_low*: a half-bit is low where
any valid frame is high (both halves of a bit low, or low in the stop condition).
*weak*: a level did not reach its threshold (an undefined level, or both halves high).

**Premises behind "certain".** P1: the bus is a wired-AND, a transmitter can only pull it
low (A3); so *extra_low* needs a second transmitter. P2: with a supply in its 12 to 20.5 V
range and wiring inside the table, noise does not move a level across a threshold more than
twice in 1800 polls (A5); so three *weak* answers mean wiring resistance. P3: only a gear
with a lamp failure answers with bit 1, only a gear fault with bit 0. P4: the gateway sets
the bus object only on a short or supply failure. P5: site facts are true. Section 8 shows
what happens when P2 fails.

## 5. Performance budgets and margins

**Bus time** (T1, R-03 to R-05):

| Item | Time |
|---|---|
| forward frame, 16 bits | 16.62 ms |
| backward frame | 9.95 ms |
| one command, middle priority, mean settling | 33.6 ms |
| one query with answer, low priority | 54.9 ms, so at most 18 queries per second |
| one query without answer | 47.4 ms |
| 64 individual commands, first to last | 2.12 s (1.90 to 2.38 s over the settling range) |

**Reporting delay** (T7). Slot scheduler, no traffic: worst = 2 x N x slot, mean half of
it; 64 gear at 1 s: 128 s, simulated 127.9 s. Command traffic up to 50 % of the bus adds
less than 1 s. At 90 % the free bus limits the poll rate to (1 - 0.9) / 54.9 ms = 1.8 per
second: a 0.2 s slot can no longer be kept and the p99 rises from 25.3 s to 88.0 s. The pause
scheduler of S10 (one query per gear, a pause after each) gives 67.5 s for 64 gear at 1 s
pause without traffic and stretches more under traffic (p99 160 s at 90 %, T7).

**Supply** (T9, T13). 64 gear x 2 mA = 128 mA. With the / 1.2 planning reserve of S7 a
full line needs 153.6 mA guaranteed. Variant B (min. 128 mA) carries 53 gear with the
reserve, 64 without; variant P (160 mA) carries 64 either way (66 with the reserve if the
64 addresses did not cap it); variant L states only a maximum of 128 mA, which gives 53 if
used as the budget. Other bus devices (sensors, push-button interfaces) come out of the
same budget. B has 95 % between its two figures; P and L have none, so any overload there
removes the bus at once whatever the curve shape.

**Short circuit** (T13, variant B). Output off 0.6 s after a short; start-up attempt
5 s after detection, repeated at that interval while the short lasts (A18). The bus is
back at most 5 s after the short clears; a fault that began during the short is reported
at most 5 s + 128 s = 133 s after it clears at the default polling.

**Wiring** (T10). The conductor table is a constant-resistance rule: 100 m of 0.5 mm2,
150 m of 0.75 mm2 and 300 m of 1.5 mm2 all give 6.90 ohm loop resistance and 1.72 V at
250 mA, inside the 2 V limit. A far gear pulling the bus low is then seen at 1.72 V plus
its transmitter's residual voltage; the gateway needs below 4.5 V. Margin 2.78 V. Whether
that margin is enough depends on two values no source gives: the transmitter residual (A4)
and the noise (A5).

## 6. Trade studies

### 6.1 Which evidence to ask for

| Alt. | Evidence | Cost |
|---|---|---|
| E1 | KNX failure-object history | none, the customer has it |
| E2 | + gateway diagnostics page | a screenshot, remote |
| E3 | + DALI bus monitor recording and probe | a bus monitor on site or a remote DALI interface, 30 minutes |
| E4 | + site facts | electrical drawings, test plan, cable and supply data; often a visit |

**Decision rule.** No wrong "certain" verdict is acceptable. Among the levels that meet
this, choose the cheapest that makes the suspected class certain in at least 95 % of runs.

**Result** (60 runs per class, T2 to T4):

| Level | mean right at first rank, 11 classes | certain verdicts right : wrong | classes certain in >= 95 % |
|---|---|---|---|
| E1 | 68.2 % | 120 : 0 | 2 (lamp failure, bus short) |
| E2 | 81.5 % | 180 : 0 | 3 (+ replacement of two) |
| E3 | 96.2 % | 445 : 0 | 7 (+ duplicate address, no address, supply low, far end) |
| E4 | 99.8 % | 659 : 0 | 11 |

**Decision.** For every case that is not a lamp failure or a bus short, ask for a bus
recording with the probe before a site visit. It makes seven classes certain and adds the
power-cycle bit, which turns "driver failed" into "driver lost mains". The site facts are
needed for exactly the classes whose cause is outside the DALI line: switched circuits,
emergency tests, and a driver that is silent for good.

### 6.2 How to build the engine

(a) Rules with stated physical premises, (b) a classifier trained on simulated evidence,
(c) re-simulating the installation and comparing. Chosen: (a). A support answer must name
the evidence and the rule. (b) cannot say why and would learn this simulator's traffic;
(c) needs E4 in every case.

### 6.3 Polling slot for the gateway (commissioning)

Alternatives: 2 s, 1 s (default of S9 and of variant B, S13), 0.5 s (shortest setting of
variant B), 0.2 s per gear and error type (below any documented setting; kept to show the
scheduler), for 64 gear.
Decision rule: the smallest worst-case reporting delay whose p99 does not more than double
when commands use 90 % of the bus. Results (T7): 2 s gives 256 s and stays at 254 s p99;
1 s gives 128 s and 129 s; 0.5 s gives 64 s and 90 s; 0.2 s gives 25.6 s and 88 s. Decision:
0.5 s for 64 gear (worst 64 s, p99 under heavy traffic 90 s); 1 s if the line carries long
individual dimming sequences. The rule behind it: slot <= D / (2 N) for a target D, and
slot well above the 54.9 ms a query takes, more the busier the bus.

## 7. Model and validation

### 7.1 Assumptions

| Id | Assumption | Why | Effect if wrong / sensitivity |
|---|---|---|---|
| A1 | Supply 16 V nominal | inside 12 to 20.5 V of S8 | shifts the overload thresholds of T9 |
| A2 | Gear draw 1 to 2 mA, other bus devices 0 to 12 mA | S8 caps at 2 mA; real draws from datasheets | budget only |
| A3 | Two answers combine as a wired-AND of their waveforms | bus idle high, transmitters pull low (S8); no source describes a collision | carries the duplicate-address certainty |
| A4 | Gear transmitter pulls the bus to 0 V at its terminals (residual 0 V) | no source | residual 1 V cuts the reliable length on 0.5 mm2 from 133 m to 75 m (T10) |
| A5 | Gaussian noise 0.6 V on each half-bit sample | no source | at 1.0 V the far-end rule gives 83 wrong certain verdicts at E3 (T6) |
| A6 | Supply voltage sags linearly from the guaranteed to the maximum current ("linear"), or holds until the maximum ("hard") | no source gives the curve | with variant B's 128 / 250 mA, first errors at 23 % or 96 % overload; both lose all gear at once (T9); for P and L the two figures coincide, so the shape does not matter |
| A7 | Each product answers after a fixed delay drawn in 5.5 to 10.5 ms | window from S1 and S3 | two products with different delays always collide; same product collides only when the bytes differ |
| A8 | Gateway sets the bus failure object when it shuts its output down, 0.6 s after a short (variant B, S15) | the shutdown time is stated, the time of the object is not | timing of the bus object only |
| A9 | Commissioning finds a gear if it is powered, hears the bus, is alive and its frame error probability is below 0.5 | search sequence not verified | decides which gear are unknown in SUPPLY_LOW and FAR_END |
| A10 | Any switching command clears status bit 7 | the clearing commands could not be checked | decides how briefly a twin-like duplicate and a mains return are visible |
| A11 | The gateway's receiver locks to the bit grid of the earliest answer | simplest receiver | offsets below half a half-bit (208 us) are not seen |
| A12 | After mains return a gear switches its lamp on | power-on level not checked | lamp-on bit only |
| A13 | 30 minutes per run; a KNX command every 20 s on average (group 85 %, individual 10 %, broadcast 5 %) | a support engineer records while operating the lights | a fault that is never exercised leaves no trace |
| A14 | Extra consumption of SUPPLY_LOW sits at the far end | added sensors or non-compliant devices | where the voltage drops |
| A15 | Emergency function test 30 to 300 s; 20 % of tests are long (duration tests) | test lengths not in the sources read | short tests are missed by polling (1 of 60 at E4) |
| A16 | Pause scheduler: one QUERY STATUS per gear | S10 gives the pause, not the query set | the pause rows of T7 |
| A17 | The gateway treats a corrupted answer like no answer | not described in the manuals | a duplicate or a far gear sets the gear failure object |
| A18 | Variant B repeats its start-up attempt every 5 s while a short lasts, counted from the shutdown | S15 states one attempt 5 s after detection | the bus is back at most 5 s after a short clears (T13) |
| A19 | Open question, both answers simulated: failure reports of gear whose mains the gateway's energy-saving function switched off are held back, or not | no document of B, P or L says (S13, S14, S16, S17) | not held back: every gear on such an object is reported failed after a long enough off period (T14); held back: nothing on the failure objects |

### 7.2 How we know the model is right

| Check | Reference | Result |
|---|---|---|
| backward frame length | 9.95 ms stated in S3 | 9.95 ms (test) |
| forward frame length | 16.2 ms stated in S3 | 16.62 ms derived from S1; difference 2.6 %, documented |
| status byte | two independent manufacturers (S2, S4) | identical layout; all 256 values round-trip (test) |
| Manchester and collision | limiting cases: equal frames at the same time read as one; different frames always leave an extra low; a collision never leaves a weak mark | all hold for both polarities (tests) |
| polling delay | 2 x N x slot (S9: 128 s for 64 gear at 1 s) | simulated worst 127.9 s; largest relative error over all no-traffic rows 0.13 % |
| false failures from switched mains | min(1, off / scan) for one gear | largest absolute error 0.0084 over 12 rows (T11) |
| cable table | Ohm's law with copper at 1/58 ohm mm2/m (S11) | every row 6.90 ohm, 1.72 V at 250 mA, under the 2 V of S2 and S8 |
| stagger | (N - 1) x per-command time | event loop gives 2.1178 s for 64 gear, equal to the formula |

What the validation does not cover: the virtual installations and traffic are not
validated against a real building, and A3 to A7 have no source. The fault signatures rest
on the status byte, the frame structure and the electrical thresholds, which are sourced,
and on A3, A5 and A10, which are not.

## 8. FMEA of the design

Failure modes of the diagnosis method, not of the installation.

| # | Failure mode | Effect | Sev. | How it is caught or limited |
|---|---|---|---|---|
| 1 | Noise on site higher than assumed (A5) | lines that meet the cable table give weak answers; far end called certain wrongly (83 times at E3 with 1.0 V) | high | measure the noise or the far-end low level with an oscilloscope before trusting the far-end rule; rule needs at least 3 weak answers |
| 2 | Twin-like duplicate (same product, same group) | collision visible only until the first switching command; never seen in 19 of 60 runs | high | run the probe right after power-up of new gear; at E4 the count gap ranks it first (60 of 60), but only as likely |
| 3 | Site facts out of date (wrong circuit list) | a real driver failure on a gear listed as switched is called mains | high | certainty requires every silent poll to fall inside a logged off period, not only membership |
| 4 | Bus short during the window | every other fault hidden (0 of 28 lamp failures seen) | medium | report says so; repeat the probe after the short is cleared |
| 5 | Fault not exercised in the window (short mains-off, short emergency test) | nothing to see | medium | at E4 the logged off period keeps "healthy" from being certain; the report names it as possible |
| 6 | Gateway treats corrupted answers differently (A17) | E1 patterns of duplicate and far end change | medium | E3 rules work on the trace, not on the objects |
| 7 | Supply curve differs (A6) | SUPPLY_LOW appears at another overload | low | the E3 rule uses the idle voltage below 12 V, not the curve |
| 8 | Two faults at once | ranking favours the louder one | medium | not evaluated, except the hidden lamp failure |

## 9. Verification and validation: plan and results

**Plan.** Unit tests for every requirement that is a protocol or electrical rule. Analytic
checks of the line model (7.2). For the engine: 60 randomised installations per class (10
faults and healthy, 660 runs), each diagnosed at four evidence levels; fault position,
gear, timing and variants random. Sensitivity runs for A3/A10 (twin-like duplicate) and A5
(noise 1.0 V), and for A4, A6 in the studies.

**Results.**

| Item | Result | Status |
|---|---|---|
| Tests | 95 passed (`python -m pytest -q`) | pass |
| R-01 to R-16 | covered by tests in `tests/` and the checks of 7.2 | pass |
| R-17 no wrong certain verdict | 0 of 1404 at base assumptions | pass |
| R-17 under noise 1.0 V | 83 wrong at E3 and at E4 (all "far end") | fail, documented as limit |
| R-18 healthy not accused | healthy ranked first in 60 of 60 at every level, certain at E4 in 60 of 60 | pass |
| R-19 evidence in each hypothesis | every hypothesis carries its reason; trace lines in the support case | pass |

**What each evidence level proves** (T2, T3, T5):

| Fault | E1 | Separating evidence | Certain from |
|---|---|---|---|
| lamp failure | certain (bit 1 answered) | none needed | E1 |
| bus short | certain (bus object) | hides all others | E1 |
| replacement of two | two failures, likely | replacement error 8 | E2 |
| duplicate address | toggling or one failure, 57 % first | extra low in an answer | E3 |
| far end | several toggling, 85 % first | weak low in answers, idle voltage normal | E3 |
| supply low | nothing on KNX | idle voltage below 12 V | E3 |
| no short address | nothing on KNX, 0 % first | probe: unaddressed gear answers, or an unknown address answers | E3 |
| gear failure | one failure, likely | bit 0 answered (42 %); silent for good needs site facts | E3 / E4 |
| mains switched | correlated failures, 75 % first | silent then back; circuit log | E4 |
| emergency test | one failure and back, 80 % first | test schedule | E4 |
| healthy | nothing on KNX, likely | count matches, no off period, no test | E4 |

## 10. Limits and next steps

- Everything is simulated. First step with hardware: one gateway, 10 to 20 drivers of two
  products, a DALI bus monitor; measure the noise and the low level of a far driver on 0.5
  and 1.5 mm2 at increasing length; create each fault on purpose and run the engine on the
  recordings.
- A3, A4, A5 and A10 have no source and carry findings. They are the first things to
  measure. `docs/BENCH_TEST_PLAN.md` lists the measurement for every assumption.
- Gateway behaviour follows variant B (S13 to S15) for polling and short-circuit times,
  S9 and S5 elsewhere. Variants P and L do not document their polling. Another product may
  poll differently, report a corrupted answer differently, or show more on its diagnostics
  page.
- Whether a gateway reports gear whose mains its own energy-saving function switched off
  is not documented for any variant (A19). Both answers are simulated; one bench test
  settles it.
- The EMERG_TEST class is claimed for variant L only; B does not support test commands,
  P does not say.
- One fault per run (except the lamp failure hidden by a bus short).
- The commissioning search, device types DT1 / DT6 / DT8 and mixed version 1 / DALI-2
  devices are not modelled.
