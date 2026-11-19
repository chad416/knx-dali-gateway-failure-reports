# knx-dali-gateway-failure-reports

Which lamp and driver failure reports of a KNX/DALI gateway can be trusted, from which
evidence, and how long a real failure stays unreported.

## In plain words

A gateway connects up to 64 lamp drivers on one DALI line to a KNX building system.
It asks every driver in turn whether it is fine and tells KNX when one is not.
Some of its alarms are false, some real failures come late, and some never come.
I built a simulated line, broke it in ten ways and checked which evidence tells the causes apart.
The KNX alarms alone prove only two of them; a recording of the DALI line proves seven, the site plan the rest.

**Simulated study, no hardware.** No recording from a real installation was used. The
DALI standard (IEC 62386) itself was not read, because it is not free: every protocol
fact is taken from openly readable manufacturer documentation, listed with what was taken
from it in [docs/SOURCES.md](docs/SOURCES.md). The gateway facts come from the public
documents of three KNX/DALI gateways of one manufacturer, called variants B, P and L here;
I do not name the manufacturer. Every number below comes from
`results/summary.json`, written by `scripts/run_all.py`, and is checked against it by
`scripts/check_readme_numbers.py`.

## The question

A KNX/DALI gateway tells the KNX side that a lamp or a driver has failed, or stays silent
when one really has, or cannot find a driver after commissioning. Which causes can be told
apart with certainty, from which evidence, and how long can a real failure go unreported?

## The answer

Tested on 660 randomised virtual installations (8 to 64 control gear on one DALI line, one
gateway that polls like variant B, with an integrated supply sized for the line, 30
minutes of operation each), each with one of 10 injected faults or none. The diagnosis engine sees one of four evidence levels: E1 the failure
objects on KNX, E2 plus the gateway's own diagnostics, E3 plus a DALI bus trace with a short
probe, E4 plus site facts (switched circuits, emergency test plan, wiring, supply rating).

1. **The KNX failure objects prove two causes; nothing wrong was ever called certain.** From
   E1 only a lamp failure (status bit 1) and a bus short are certain, both in 100 % of the
   runs. A gear added without a short address and an overloaded supply leave no failure
   object at all: 0 % ranked first at E1. Over all four levels the engine gave 1404
   "certain" verdicts and 0 of them were wrong. That holds at the assumed line noise of
   0.6 V; with 1.0 V the far-end rule was wrong 83 times (see Limits). While a bus short lasts, nothing else is
   reported: 0 of 28 lamp failures that happened during a short reached any level.

2. **One extra piece of evidence separates the look-alikes, and its physics is simple.** A
   wired-AND bus can only add low levels. Two gear answering one short address therefore
   leave a low where a valid frame must be high; a far gear on a long thin cable leaves a
   low that does not reach the 4.5 V receiver threshold. With the bus trace (E3) duplicate
   addresses go from 57 % ranked first to 100 % certain, and far-end wiring from 85 % to
   100 %. A driver that never answers again is still not proven defective at E3 (42 % of
   gear failures are certain, only those that answer with status bit 0); it takes the site
   facts to rule out a switched circuit or an emergency test (100 % at E4). A duplicate of
   the same product in the same group is the hard case: its answers stay identical after
   the first switching command, so the collision was never seen in 19 of 60 runs (median
   3 corrupted polls, at most 21, out of 1800). The emergency-test class needs a gateway
   that starts converter tests. Variant L documents function and duration tests; variant
   B's documents say test commands are not supported, so for B the class is outside the
   gateway and the study claims 10 classes, not 11; variant P's documents do not say.

3. **A real failure can stay unreported for 2 x gear x polling slot, and a separately
   switched circuit makes the same rule produce false alarms.** Variant B documents this
   rule: one gear and one error type per slot, 1 s by default, so 64 gear take 128 s
   (simulated 127.9 s, mean 64.1 s). Its settings run from 0.5 s to 10 s, so 64 gear are
   reported within 64 s at best and 1280 s at worst; "no request" switches failure
   detection off. For variants P and L the documents read do not state the polling, so I
   give no delay for them. Switching traffic up to 50 % of the bus time changes the 128 s
   by less than 1 s (128.1 s). A short slot does not survive heavy traffic: at 0.5 s, the
   shortest setting of variant B, the p99 rises from 63.3 s to 89.7 s when commands use
   90 % of the bus (at 0.2 s, below any documented setting, from 25.3 s to 88.0 s). The
   same scan decides how often a mains-off period becomes a false gear failure:
   min(1, off time / scan). For 64 gear at 1 s, a 60 s off period raises one in 47 % of
   cases with one gear on the circuit and 93 % with four; any off period of 300 s does it
   every time. **Rule for commissioning:** to report within D seconds, set the slot to at
   most D / (2 x number of gear) but not below the gateway's shortest setting, keep it well
   above the 54.9 ms one query takes, and keep the mains of DALI gear permanent or declare
   those gear to the gateway.

4. **Individually addressed luminaires ripple visibly from 4 gear on.** One individual
   command takes 33.6 ms of bus time (16.62 ms forward frame plus a DALI-2 settling time),
   so 64 gear switch over 2.12 s (1.90 to 2.38 s over the settling-time range) and 8 gear
   over 0.24 s. Above an assumed 100 ms visibility threshold that is 4 gear; above the
   20 ms order threshold of perception research it is 2. One group or broadcast frame
   switches all of them on the same frame.

5. **Supply budget: 64 gear need 128 mA, 153.6 mA with the planning reserve. Variant B
   carries 53 gear with the reserve, variant P all 64, and an overload loses every gear at
   once.** The built-in supplies differ: variant B states 128 mA minimum and 250 mA maximum
   (one-channel device), variant P 160 mA as both its guaranteed and its maximum current,
   variant L only a maximum of 128 mA. B and L forbid an additional DALI supply; for P I
   found no such sentence. At 2 mA per gear and with the reserve, B carries 53 gear, P 64
   (66 without the cap of 64 addresses), L 53 if its maximum is used as the budget, which
   is my reading. Just above the limit the far gear do not drop out first: the gateway's
   own receiver (high above 10 V) fails before the gear (high above 9.5 V). With variant
   B's currents and a supply whose voltage sags above its guaranteed current, answers start
   to fail at 23 % overload and the gateway finds none of 64 gear at 30 %; with a hard
   current limit nothing happens until 96 % and then the bus collapses. Variant P has no
   margin between its two figures, so under either shape it loses the bus at 1 % overload.
   Both supply curves are assumptions. The cable table is one rule in disguise: every row
   gives 6.90 ohm and 1.72 V at 250 mA, which leaves 2.78 V to the receiver threshold. With
   0.6 V noise that margin holds to 133 m on 0.5 mm2 (table: 100 m), but a gear transmitter
   that leaves 1 V on the bus cuts it to 75 m.

6. **A bus short hides every other fault while it lasts, and on variant B for up to 5 s
   plus one scan after it clears.** Variant B shuts its output down 0.6 s after a short and
   tries to start again 5 s after detecting it. If it keeps trying every 5 s (assumption
   A18), the bus is back at most 5 s after the short clears (2.5 s on average), and a fault
   that began during the short is reported at most 133 s after it clears at the 1 s default
   (66.5 s on average). Variant P states that no other failure can be recognised during a
   short but gives no times; the documents of variant L state neither.

## Three gateway variants

What the documents of each variant state, used in the findings above. "Not stated" means
the documents read do not say it. Section and page for every value are in
[results/tables.md](results/tables.md) (T12), the documents in
[docs/SOURCES.md](docs/SOURCES.md).

| | variant B: basic, no display | variant P: display and web server | variant L: older, with display |
|---|---|---|---|
| DALI channels | one or two (two devices) | one | one |
| gear and groups per channel | 64 and 16 | 64 and 16 | 64 and 16 |
| scenes | 16 | 16 | not stated |
| built-in supply | min. 128 mA, max. 250 mA (one-channel device) | 160 mA guaranteed and maximum | max. 128 mA |
| additional DALI supply | not permitted | not stated | not permitted |
| multi-master | not stated | not stated | "category-1 control unit"; no sentence on multi-master |
| short circuit | output off after 0.6 s, start-up attempt 5 s after detection | no other failure recognised during a short | not stated |
| cable | 300 m per segment | not stated | not stated |
| failure polling | 1 s per gear and error type by default, 128 s for 64 gear; 0.5 to 10 s or none | not stated (claim not verified) | not stated (claim not verified) |
| emergency test commands | not supported | not stated | function and duration tests |
| mains of gear switched by a KNX object when lights are off | per group or per gear | per group or per gear | per group |
| failure reports held back while that object has the mains off | not stated | not stated | not stated |

![Diagnosis by evidence level](results/diagnosis_by_evidence.png)

Left: right class and reported as certain. Right: right class ranked first at any
certainty. 60 runs per class.

Other figures:

- [results/reporting_delay.png](results/reporting_delay.png): worst reporting delay against
  the number of gear for four slot times, and the 99th percentile against command traffic.
- [results/stagger.png](results/stagger.png): first-to-last luminaire time with individual
  commands for the DALI-2 settling-time range, against one group frame.
- [results/supply_overload.png](results/supply_overload.png): gateway voltage and gear
  found at commissioning against overload, variant B with both supply models and variant P.
- [results/wiring_far_end.png](results/wiring_far_end.png): backward-frame error
  probability of the farthest gear against cable length, with the table limits.
- [results/mains_false_failure.png](results/mains_false_failure.png): share of mains-off
  periods that become a false gear failure.
- [results/confusion_matrices.png](results/confusion_matrices.png): injected fault against
  first-ranked diagnosis at E1 and E3.

All tables are in [results/tables.md](results/tables.md). A worked support case, written as
it would go back to the customer, is in [docs/SUPPORT_CASE.md](docs/SUPPORT_CASE.md).

## How to run

```
python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt   # Linux: .venv/bin/python
.venv/Scripts/python -m pytest -q                                                  # 95 tests
.venv/Scripts/python scripts/run_all.py                                            # regenerates results/ (about 1 minute)
```

`scripts/run_all.py --quick` writes a reduced run to `results/quick/` (used in CI).
`scripts/check_readme_numbers.py` fails if a number in this README is not in
`results/summary.json`.

## What is modelled

- The DALI line at frame and half-bit level: 1200 bit/s Manchester coding, 2.45 ms stop
  condition (DALI-2 framing), 16-bit forward and 8-bit backward frames, the 5.5 to 10.5 ms
  backward-frame window, DALI-2 settling times by priority, 64 short addresses, 16 groups,
  the status byte returned by QUERY STATUS bit by bit. Two answers at once are combined as
  a wired-AND of their waveforms, with each product's own reply delay.
- Electrical: loop resistance of the cable, the voltage along a daisy chain of gear, a
  supply with guaranteed and maximum current, receiver thresholds of gear (9.5 V / 6.5 V)
  and of the gateway (10 V / 4.5 V), Gaussian noise on each half-bit sample.
- Control gear: short address or none, group, lamp state, lamp failure and gear failure
  bits, power-cycle bit, silent without mains while the bus stays powered.
- The gateway: maps gear to KNX failure objects (lamp, gear, bus), polls one gear and one
  error type per slot as variant B documents, gives a bus failure object on a short and
  stops polling, searches for gear at commissioning, and runs an automatic replacement
  that aborts with the error codes the manuals give.
- Three documented gateway variants (`daligw/variants.py`): their limits, supply
  currents, short-circuit times, polling and emergency-test support, each with its source
  or marked as not stated. The supply budget, short-circuit and polling studies use them.
- Ten faults: separately switched mains, lamp failure, gear failure (silent or status bit
  0), emergency test of an undeclared pair (claimed only for a variant that supports
  emergency tests), duplicate short address, gear without short address (factory-new or
  pre-addressed), two gear exchanged at once, supply overload, bus short (with or without
  a hidden lamp failure), far end on a too long or too thin cable.
- The gateway's own energy-saving function, which switches the mains of gear off through
  a KNX object, under both answers to the open question below (`daligw/studies.py`).

## What is not modelled

- The commissioning command sequence (INITIALISE, RANDOMISE, COMPARE, WITHDRAW, PROGRAM
  and VERIFY SHORT ADDRESS). I could confirm the command codes but not the search
  procedure and its timing from an open source, so commissioning is modelled by its
  outcome: a gear is found if it is powered, hears the bus and can be read.
- The address byte layout, device types DT1, DT6 and DT8, colour control, emergency test
  results beyond the silent paired gear, mixed version 1 and DALI-2 devices.
- Bit-timing tolerances, cable capacitance, wave shape, multi-master operation.
- More than one fault at a time, except the lamp failure hidden behind a bus short.

## Limits and what I would do next with real hardware

- The certainty of the far-end rule rests on the noise level (assumption A5). With 1.0 V
  of noise instead of 0.6 V, lines that meet the cable table produce occasional weak
  answers and the engine called the far end "certain" wrongly 83 times at E3. The physics
  says the table leaves 2.78 V of margin; how much of it noise and the gear transmitter
  use is not in any source I could read.
- The supply curve above the guaranteed current (A6) decides finding 5's numbers. Both
  shapes agree on the main point (all gear lost together), not on where.
- That any switching command clears status bit 7 (A10) decides how briefly a twin-like
  duplicate is visible.
- **Open question (A19): are failure reports held back while the gateway's own
  energy-saving function has switched the gear's mains off?** All three variants can
  switch the mains of gear off through a KNX object once their lights have been off for
  an off delay of 10 s to 10 min. No document read says whether the gateway then still
  reports those gear as failed, or what it reports when gear lose mains while the DALI
  line stays powered. I simulated both answers (T14). *Not held back:* a gear on such an
  object is reported failed once its mains have been off over its polling slot. With the
  shortest delay, 60 s of darkness raises at least one false failure in 39 % of cases
  with one gear on the object and 99 % with eight; from 300 s on, every time, and the
  failure totals count every gear on the object (8 of 8 in the example). With the longest
  delay a 5-minute break never does and a longer evening always does. On KNX this looks
  like a separately switched circuit (finding 3), except that the energy-saving object's
  own telegram comes first; the diagnostics count the gear as gear failures. *Held back:*
  KNX shows only the energy-saving object, the failure objects and counters stay at 0.
  The bench test that settles it, about an hour on one gateway with four gear, is in
  [docs/BENCH_TEST_PLAN.md](docs/BENCH_TEST_PLAN.md).
- The delay findings are for variant B only. For P and L the polling is not documented,
  and for the two-channel B it is not stated whether both channels are polled in parallel,
  so I give no delay for 128 gear. The supply current of the two-channel B is not stated.
- The emergency-test class rests on S5 and S9, gateways of other manufacturers. Of the
  three variants only L documents test commands, and L's polling is not documented. No
  single documented variant both polls as modelled and starts tests.
- Gateway behaviour follows variant B where its documents state it, and S9 and S5
  elsewhere. The treatment of a corrupted answer as "no answer" (A17) and what the
  diagnostics page shows are not documented for any variant.
- E4 assumes the site facts are true. A wrong circuit list makes "certain" wrong.
- Next with hardware: the measurements that would replace each assumption that carries a
  finding, with equipment and duration, are listed in
  [docs/BENCH_TEST_PLAN.md](docs/BENCH_TEST_PLAN.md).

## Repo map

```
daligw/constants.py    every protocol and electrical value with its source id
daligw/frames.py       frame timing, Manchester coding, wired-AND, receiver, status byte
daligw/electrical.py   cable, supply, voltages along the line, reception error model
daligw/line.py         control gear and the reception of one or several answers
daligw/scenario.py     random installation, fault injection, commissioning, gateway polling
daligw/diagnose.py     diagnosis engine: evidence levels, rules, certainty, report
daligw/evaluate.py     confusion matrices over randomised installations
daligw/studies.py      reporting delay, stagger, supply budget, wiring, switched mains,
                       variant studies, short-circuit timing, energy-saving hypotheses
daligw/variants.py     the three documented gateway variants, each value with its source
scripts/run_all.py     one command that regenerates results/
scripts/check_readme_numbers.py   README numbers against results/summary.json
tests/                 95 tests
results/               summary.json, tables.md, seven figures, support-case evidence
DOSSIER.md             systems-engineering dossier (need, requirements, trade study, FMEA, V&V)
docs/SOURCES.md        every source with what was taken from it, and what could not be verified
docs/SUPPORT_CASE.md   worked support case
docs/BENCH_TEST_PLAN.md  the measurement that would replace each assumption
```
