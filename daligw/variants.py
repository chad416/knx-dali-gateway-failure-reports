"""Three documented KNX/DALI gateway variants of one manufacturer.

Every value comes from a public document read for this project and listed in
docs/SOURCES.md (S13 to S18). The manufacturer is not named on purpose. A value of None
means that the documents read do not state it; the note then says what they do say. A
value with a note was stated, but the note qualifies how it is used.

  B  variant B: basic, no display (one- and two-channel devices)
  P  variant P: display and web server
  L  variant L: older, with display

This module imports nothing from the package, so constants.py can take the polling rule
of the simulated gateway from it.
"""
from __future__ import annotations

from dataclasses import dataclass, fields


@dataclass(frozen=True)
class Fact:
    value: object
    source: str
    note: str = ""

    @property
    def documented(self) -> bool:
        return self.value is not None


NOT_STATED = "not stated in the documents read"


@dataclass(frozen=True)
class Variant:
    key: str
    name: str
    channels: Fact
    gear_per_channel: Fact
    groups_per_channel: Fact
    scenes_per_channel: Fact
    single_master: Fact
    external_supply_allowed: Fact
    i_guaranteed_a: Fact
    i_max_a: Fact
    short_shutdown_s: Fact
    short_restart_s: Fact
    short_hides_failures: Fact
    cable_max_m: Fact
    emergency_test_commands: Fact
    poll_default_s: Fact
    poll_settings_s: Fact          # (shortest, longest) cycle setting
    poll_error_types: Fact
    energy_saving: Fact
    failures_suppressed_while_mains_off: Fact

    def facts(self) -> dict[str, Fact]:
        return {f.name: getattr(self, f.name) for f in fields(self)
                if isinstance(getattr(self, f.name), Fact)}


VARIANT_B = Variant(
    key="B",
    name="variant B: basic, no display",
    channels=Fact((1, 2), "S13 section 1, p. 4",
                  "a one-channel and a two-channel device; the second channel is an "
                  "identical copy of the first"),
    gear_per_channel=Fact(64, "S13 section 2.3, p. 5-6"),
    groups_per_channel=Fact(16, "S13 section 2.3, p. 6"),
    scenes_per_channel=Fact(16, "S13 section 8.1, p. 24",
                            "the document says 16 scenes on the gateway; per channel is "
                            "inferred from the identical second channel"),
    single_master=Fact(None, "-", "no quoted sentence on multi-master operation"),
    external_supply_allowed=Fact(False, "S13 section 2.3, p. 5",
                                 "an additional DALI supply is not required and not permitted"),
    i_guaranteed_a=Fact(0.128, "S15 p. 2, technical data",
                        "stated as 'min. 128 mA' for the one-channel device; reading 'min.' "
                        "as the guaranteed current is my interpretation; the two-channel "
                        "device's current is not stated"),
    i_max_a=Fact(0.250, "S15 p. 2, technical data", "one-channel device"),
    short_shutdown_s=Fact(0.6, "S15 p. 2, technical data",
                          "shutdown 600 ms after a DALI short circuit"),
    short_restart_s=Fact(5.0, "S15 p. 2, technical data",
                         "start-up attempt 5 s after short-circuit detection; that attempts "
                         "repeat at this interval while the short lasts is assumption A18"),
    short_hides_failures=Fact(None, "-", "stated for variant P, not quoted for B"),
    cable_max_m=Fact(300.0, "S15 p. 2, technical data",
                     "whole DALI installation of a segment, 1.5 mm2 recommended"),
    emergency_test_commands=Fact(False, "S15 p. 1, notes",
                                 "single-battery converters can be read, switched and "
                                 "operated; DALI commands for starting tests and reading "
                                 "test results are not supported"),
    poll_default_s=Fact(1.0, "S13 section 7.2, p. 20; same in S14",
                        "standard setting; 64 gear take 128 s, 'up to about 2 minutes' "
                        "before a fault is recognised"),
    poll_settings_s=Fact((0.5, 10.0), "S13 section 9.1.2, p. 43; same in S14",
                         "options: no request, 0.5 s, 1 s, 2 ... 10 s; 'no request' switches "
                         "gear and lamp fault recognition off; whether the two channels of "
                         "the two-channel device are polled in parallel is not stated"),
    poll_error_types=Fact(2, "S13 section 7.2, p. 20", "1 s per gear and type of error"),
    energy_saving=Fact("16 objects, assigned per group or per gear; off delay 10 s to "
                       "10 min, on delay 0.1 to 2 s",
                       "S13 sections 8.3, p. 27, and 9.1.3, p. 46"),
    failures_suppressed_while_mains_off=Fact(None, "-", NOT_STATED + " (open question A19)"),
)

VARIANT_P = Variant(
    key="P",
    name="variant P: display and web server",
    channels=Fact(1, "S16 section 3.4, p. 14", "one DALI output"),
    gear_per_channel=Fact(64, "S16 section 3.4, p. 14"),
    groups_per_channel=Fact(16, "S16 section 3.4, p. 14", "plus individual control of 64 gear"),
    scenes_per_channel=Fact(16, "S16 section 3.4, p. 15"),
    single_master=Fact(None, "-", "no quoted sentence on multi-master operation"),
    external_supply_allowed=Fact(None, "-", "no quoted sentence for this variant"),
    i_guaranteed_a=Fact(0.160, "S16 section 3.4, p. 14", "'guaranteed value of 160mA'"),
    i_max_a=Fact(0.160, "S16 chapter 14, p. 85", "'maximum total current of 160mA'; the "
                 "hardware leaflet was not read, so a higher short-circuit current is not "
                 "ruled out"),
    short_shutdown_s=Fact(None, "-", NOT_STATED),
    short_restart_s=Fact(None, "-", NOT_STATED),
    short_hides_failures=Fact(True, "S16 section 20.2.9, p. 148",
                              "no further failures can be recognised during a short"),
    cable_max_m=Fact(None, "-", NOT_STATED),
    emergency_test_commands=Fact(None, "-",
                                 "the feature list names single-battery converters and a "
                                 "test mode for central-battery systems (S16 p. 15); test "
                                 "commands and result objects were not verified"),
    poll_default_s=Fact(None, "-", "a 1 s / 128 s statement for this variant did not "
                        "survive verification"),
    poll_settings_s=Fact(None, "-", NOT_STATED),
    poll_error_types=Fact(None, "-", NOT_STATED),
    energy_saving=Fact("16 objects, assigned per group or per gear; off delay 10 s to "
                       "10 min, on delay 0.1 to 2 s",
                       "S16 sections 21.1.3.1, p. 155, and 22.1.4, p. 208"),
    failures_suppressed_while_mains_off=Fact(None, "-", NOT_STATED + " (open question A19)"),
)

VARIANT_L = Variant(
    key="L",
    name="variant L: older, with display",
    channels=Fact(1, "S18 p. 1-2", "64 gear and 16 groups per gateway"),
    gear_per_channel=Fact(64, "S18 p. 2, technical data"),
    groups_per_channel=Fact(16, "S18 p. 1",
                            "a gear can belong to one group only, and a grouped gear can no "
                            "longer be controlled individually"),
    scenes_per_channel=Fact(None, "-", "a claim of 16 scenes did not survive verification"),
    single_master=Fact("category-1 control unit", "S18 p. 2, technical data",
                       "the quoted text gives the category, not the word single-master"),
    external_supply_allowed=Fact(False, "S18 p. 1",
                                 "an additional DALI supply is not required and not permitted"),
    i_guaranteed_a=Fact(None, "-", "only 'max. 128 mA' is stated"),
    i_max_a=Fact(0.128, "S18 p. 2, technical data", "output DC 16 to 20 V"),
    short_shutdown_s=Fact(None, "-", NOT_STATED),
    short_restart_s=Fact(None, "-", NOT_STATED),
    short_hides_failures=Fact(None, "-", NOT_STATED),
    cable_max_m=Fact(None, "-", NOT_STATED),
    emergency_test_commands=Fact(True, "S17 sections 11.4, p. 59, and 8.6, p. 51",
                                 "function and duration tests per converter, started by a "
                                 "KNX object or the website; central-battery test mode of "
                                 "15 min to 4 h"),
    poll_default_s=Fact(None, "-", "a 1 s / 128 s statement for this variant did not "
                        "survive verification"),
    poll_settings_s=Fact(None, "-", NOT_STATED),
    poll_error_types=Fact(None, "-", NOT_STATED),
    energy_saving=Fact("one object per group, group level only; DALI switch-on commands "
                       "300 ms after the object goes to 1; off delay 10 s to 10 min",
                       "S17 sections 16.4, p. 109, and 17.2.1, p. 128-129"),
    failures_suppressed_while_mains_off=Fact(None, "-", NOT_STATED + " (open question A19)"),
)

VARIANTS = {v.key: v for v in (VARIANT_B, VARIANT_P, VARIANT_L)}


def emergency_scope(v: Variant) -> str:
    """Whether the EMERG_TEST fault class (a test started for a converter disconnects the
    normal gear of an undeclared pair) belongs to this variant."""
    f = v.emergency_test_commands
    if f.value is True:
        return "in scope"
    if f.value is False:
        return "outside this variant"
    return "not stated"
