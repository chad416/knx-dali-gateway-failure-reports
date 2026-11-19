# Support case: six drivers reported failed every evening, all fine the next morning

Simulated case (installation seed 4006, fault class MAINS_SWITCHED). The engine output,
the KNX object log and trace lines are in `results/support_case.txt`, written by
`scripts/run_all.py`. Times are seconds from the start of the recording.

## 1. Symptom as reported

"The visualisation shows a control gear failure for six luminaires on the first floor,
gear 12, 16, 28, 33, 35 and 38, almost every evening. Next morning the alarms are gone. The
electrician swapped the driver of luminaire 28 last week; no change. We have 40 luminaires
on this gateway line. Are the drivers bad?"

## 2. What was reproduced

The case was reproduced on the virtual line: 40 gear, all 40 known to the gateway, 89 m of
0.5 mm2 cable, polling at 1 s per gear and error type (a full scan takes 80 s). During a
30-minute recording the KNX side showed:

```
t=  376.0 s  gear failure  gear 28  -> 1
t=  386.0 s  gear failure  gear 33  -> 1
...
t=  432.0 s  gear failure  gear 16  -> 1
t=  776.0 s  gear failure  gear 28  -> 0
...
t=  832.0 s  gear failure  gear 16  -> 0
```

Six objects go to 1 within 56 s of each other and back to 0 within 56 s of each other,
400 s later. No lamp failure object and no bus failure object.

## 3. What each evidence level could and could not say

**E1, KNX failure objects only.** The engine ranks "mains switched" first, but only as
*likely*: six gear failing and recovering inside one polling scan is what a common power
loss looks like. It cannot be certain. Six real driver failures that all recover by
themselves are not a credible alternative, but a long emergency test or six intermittent
collisions would also set and clear the objects. The swap of driver 28 shows that the
object alone did not tell the electrician anything about the driver.

**E2, plus the gateway diagnostics.** Nothing new: the gateway knows 40 gear, the bus is
fine, no replacement was attempted. Its page shows the six gear as "ECG error" while they
are silent. It does not say why.

**E3, plus a DALI bus trace and a probe.** The trace shows *no answer at all* to QUERY
STATUS from the six gear during the alarm, not a corrupted answer and not an answer with
the failure bit set:

```
t=  376.0 s  QUERY STATUS gear 28: none
t=  386.0 s  QUERY STATUS gear 33: none
...
t=  776.0 s  QUERY STATUS gear 28: ok status=0x84 power_cycle_seen=1
t=  786.0 s  QUERY STATUS gear 33: ok status=0x00 power_cycle_seen=0
```

So the bus to them is fine and nothing else answers in their place: no low level where a
valid frame is high (that would be a duplicate address) and no weak low level (that would
be the wiring). Driver 28 then comes back with status 0x84: lamp on and bit 7, "power cycle
seen". It was switched off, not broken. The other five came back without bit 7, because a
group switching command reached them before their next poll and cleared it. The engine
still says *likely*, not certain: from the trace alone, six gear on a common mains feed and
an emergency test of a single pair cannot be fully ruled out without knowing the site.

**E4, plus the site facts.** The electrical drawing shows the six luminaires on a
separately switched circuit (a contactor for the corridor and stair lighting, switched by
the building time program). The contactor log shows the circuit off from 369.8 s to
755.6 s. Every poll without an answer from the six gear falls inside that interval, and no
other gear was silent. The engine now says *certain*: "every silent gear sits on the
separately switched circuit and was silent only while that circuit was off".

## 4. Root cause

The drivers are fine. Their mains is switched by a contactor while the DALI line stays
powered. A driver without mains cannot answer, and the gateway reads a missing answer as a
control gear failure. The four causes the gateway cannot tell apart on KNX are listed in
one gateway manual (S10): driver defective, no mains, DALI line interrupted, address lost.

In this study a mains-off period produces a false failure for one gear with probability
min(1, off time / scan time). Here the scan takes 80 s, so every off period longer than
80 s raises a failure object for every gear on the circuit, as it did here (386 s off,
six objects).

## 5. Fix

In order of preference:

1. Feed the six drivers from permanent mains and switch the light over DALI (group
   command from the time program). This removes the false alarms and keeps real driver
   failures reported. It needs an electrician and one change in the KNX project.
2. If the contactor must stay (for example for energy reasons at night): declare those gear
   to the gateway as separately switched, where the product allows it, or give their
   failure objects to a logic that ignores them while the contactor is off. Disabling
   failure messages altogether (a gateway option in S5) is not recommended: it also hides
   real driver failures on the whole line.
3. Do not swap drivers on the strength of a gear failure object alone.

## 6. How it was confirmed

On the virtual line the contactor was bridged (permanent mains) and the evening program
switched the group by DALI instead; same installation, same 30 minutes of traffic
(`make_run(..., bridge_circuit=True)` in `scripts/run_all.py`). Result: 0 gear failure
objects, 268 of 268 QUERY STATUS polls to the six gear answered, and the engine at E4
reports the installation healthy and certain ("count matches the site, every gear answers
cleanly, no switching, test, wiring or supply issue"). In the evaluation the engine was
certain and right for 60 of 60 healthy installations at E4.

## 7. Note for the knowledge base

- A group of gear failures that set and clear together within one polling scan is a power
  question before it is a driver question. Ask for the circuit plan before sending anyone
  to swap drivers.
- Look for status bit 7 in the first answer after the alarm clears. It proves a power
  cycle, but a switching command clears it quickly (A10 in the dossier), so its absence
  proves nothing.
- The same pattern with exactly one gear and a known emergency test plan is the emergency
  pair case (S9, S5): declare the pair in the gateway.
