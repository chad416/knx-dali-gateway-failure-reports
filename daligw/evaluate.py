"""Confusion matrices of the diagnosis engine over randomised installations."""
from __future__ import annotations

from collections import Counter, defaultdict

from .diagnose import LEVELS, diagnose
from .scenario import FAULTS, make_run


def evaluate(runs_per_class: int, seed0: int = 1, **kw) -> dict:
    conf = {lv: {f: Counter() for f in FAULTS} for lv in LEVELS}
    right_first = {lv: Counter() for lv in LEVELS}
    certain_right = {lv: Counter() for lv in LEVELS}
    certain_verdicts = {lv: {"right": 0, "wrong": 0, "wrong_cases": []} for lv in LEVELS}
    by_variant: dict = defaultdict(lambda: defaultdict(Counter))
    hidden = Counter()
    runs = []
    for fi, fault in enumerate(FAULTS):
        for r in range(runs_per_class):
            seed = seed0 + 10_000 * fi + r
            run = make_run(fault, seed, **kw)
            runs.append(run)
            for lv in LEVELS:
                rep = diagnose(run.evidence, lv)
                first = rep.first.cls if rep.first else "NONE"
                conf[lv][fault][first] += 1
                ok = first == fault
                right_first[lv][fault] += ok
                cert_ok = ok and rep.first.certainty == "certain"
                certain_right[lv][fault] += cert_ok
                by_variant[lv][fault][f"{run.variant}|{'ok' if ok else 'miss'}"] += 1
                for h in rep.hypotheses:
                    if h.certainty != "certain":
                        continue
                    if h.cls == fault:
                        certain_verdicts[lv]["right"] += 1
                    else:
                        certain_verdicts[lv]["wrong"] += 1
                        certain_verdicts[lv]["wrong_cases"].append(
                            {"fault": fault, "seed": run.truth["seed"], "said": h.cls,
                             "reason": h.reason})
            if fault == "BUS_SHORT" and run.truth.get("hidden_lamp") is not None:
                rep = diagnose(run.evidence, "E4")
                hidden["with_hidden_lamp"] += 1
                hidden["hidden_lamp_reported"] += any(h.cls == "LAMP_FAIL" for h in rep.hypotheses)
    n = runs_per_class
    return {
        "runs_per_class": n,
        "faults": list(FAULTS),
        "levels": list(LEVELS),
        "confusion": {lv: {f: dict(conf[lv][f]) for f in FAULTS} for lv in LEVELS},
        "right_first": {lv: {f: right_first[lv][f] / n for f in FAULTS} for lv in LEVELS},
        "certain_and_right": {lv: {f: certain_right[lv][f] / n for f in FAULTS} for lv in LEVELS},
        "certain_verdicts": certain_verdicts,
        "by_variant": {lv: {f: dict(v) for f, v in d.items()} for lv, d in by_variant.items()},
        "bus_short_hidden_lamp": dict(hidden),
    }, runs
