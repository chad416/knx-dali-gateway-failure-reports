# Bench test plan

Every assumption below carries a finding of this study. Each row is the measurement on a
real DALI line and gateway that would replace it. Assumption ids are those of DOSSIER.md
section 7.1; variants B, P and L are described in `daligw/variants.py`.

Common set-up: one gateway of the variant under test with its built-in supply, four to 20
DALI drivers of two products on one line, a KNX group monitor on a PC (records every
telegram with a time stamp), a DALI bus monitor (records every frame), a two-channel
oscilloscope with a differential probe across the DALI pair, a KNX switch actuator, and
cable reels of 0.5 mm2 and 1.5 mm2.

| Assumption | What to measure | With what | Expected duration |
|---|---|---|---|
| A19 Failure reports of gear whose mains the energy-saving function switched off: held back or not (no document says) | Variant B, polling 1 s, four gear on the line (scan 8 s). Assign two gear to Energy Saving Object 1, off delay 10 s, and let that object drive the actuator that feeds their mains. Switch their group off over KNX and leave it off for 5 min, then on. Watch: the gear failure objects and failure totals of the two gear, the per-gear failure status, the energy-saving object, and whether the bus monitor shows QUERY STATUS frames to their short addresses while the mains are off. Held back: no failure telegram. Not held back: a failure telegram within 10 s plus one scan after the group goes off, cleared within one scan after it comes back. Repeat three times, then once with the off delay at 10 min and the lights off for 15 min. Repeat on P and L if available. | gateway, four drivers, KNX actuator, KNX group monitor, DALI bus monitor | 1 h per variant |
| Polling of variants P and L, and of both channels of the two-channel B (not documented) | Set the polling to its default. Record 10 min of the bus monitor without any KNX traffic. Read from the trace the time between queries, the query set per gear and the full scan time; on the two-channel B, record both channels at once. | DALI bus monitor (two on the two-channel device) | 30 min per variant |
| A18 Restart of variant B's output every 5 s during a short | Short the DALI pair through a switch for 2 s, 12 s and 60 s. Record the bus voltage on the oscilloscope (shutdown after the documented 0.6 s, each start-up attempt) and the time stamp of the DALI failure object on KNX. Then make one gear's lamp fail during a short and measure when its lamp failure arrives after the short clears. | oscilloscope, switch, KNX group monitor | 30 min |
| A8 Bus failure object sent at the shutdown | Same recordings as A18: time from the short to the DALI failure object on KNX. | oscilloscope, KNX group monitor | included above |
| A6 Supply voltage above the guaranteed current | Load the line with a programmable DC load in 2 mA steps from the documented guaranteed current to collapse; record the idle voltage at the gateway terminals, and when the gateway stops finding gear (post installation at each step). Variant P: whether anything is left above 160 mA. | programmable DC load, multimeter, ETS commissioning tool | 2 h per variant |
| L guaranteed current, two-channel B current (not stated) | Same load test; the current at which the voltage starts to fall is the usable budget. | programmable DC load, multimeter | included above |
| A5 Noise on the bus | Record the idle and low levels at the gateway terminals for 10 min with the lights switching, on a short line and on 100 m of 0.5 mm2. Standard deviation of the levels. | oscilloscope | 1 h |
| A4 Residual voltage of a gear transmitter | Low level at the terminals of a far gear and at the gateway while it answers, at 0, 50, 100 and 150 m of 0.5 mm2, for both driver products. | oscilloscope, cable reels | 1 h |
| A3 Two answers at once combine as a wired-AND | Give two drivers the same short address (one reused driver), query that address, record the backward frames at the gateway. Check for lows where a valid frame is high. | oscilloscope, DALI bus monitor | 30 min |
| A10 Which commands clear status bit 7 | Power-cycle one driver's mains, then send OFF, a group command, a broadcast and a scene; query its status after each. | DALI bus monitor (with send function) | 30 min |
| A17 A corrupted answer counts as no answer | With the duplicate address of A3, watch whether the gateway sets the gear failure object for that address. | KNX group monitor, DALI bus monitor | included in A3 |
| A15 Length of an emergency function test (variant L only; B does not support tests) | Start a function test and a duration test on one converter paired with a normal driver; record how long the normal driver is silent and what the gateway reports. | variant L gateway, emergency converter, KNX group monitor | function test 15 min; duration test up to the converter's rated time |
