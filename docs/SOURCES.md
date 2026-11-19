# Sources

The DALI standard (IEC 62386 parts 101, 102, 103) was not read: it is not free. Every
protocol fact below is a manufacturer's restatement of it, from documents that anyone can
open. Where two independent manufacturers give the same value, both are listed. The
column "taken" says exactly what was used. Each document was opened and read for this
project (the two gateway manuals as PDF text). What could not be verified is listed at the
end, with what that means for the model.

| Id | Document | Where it was read | Taken |
|---|---|---|---|
| S1 | Beckhoff Information System, TwinCAT 3 library Tc3_DALI, *Structure data frame* | https://infosys.beckhoff.com/content/1033/tcplclib_tc3_dali/12346803211.html | Manchester coding at 1200 bit/s, bit length 0.833 ms; stop condition at least 2.45 ms; settling time between forward and backward frame 5.5 / 8.0 / 10.5 ms (min / mean / max); settling time before each forward frame by priority: high 13.5 / 14.1 / 14.7, middle high 14.9 / 15.5 / 16.1, middle 16.3 / 17.0 / 17.7, middle low 17.9 / 18.6 / 19.3, low 19.5 / 20.3 / 21.2 ms; some commands are sent twice within 100 ms, the second with priority high. These are DALI-2 values; the model uses them. |
| S2 | Dynalite (Signify) System Builder 4.42 documentation, *Signal Dimmers*, DALI section | https://docs.dynalite.com/system-builder/4.42/signal_dimmers.html | 1200 bit/s, Manchester; 6-bit short address (64 drivers), 4-bit group address, 16 groups, 16 scenes per group; status bits 0 to 7 (control gear failure, lamp failure, lamp on, limit error, fade running, reset state, missing short address, power cycle seen); wire length limited to 300 m; voltage drop limited to 2 V; minimum conductor 0.5 mm2 up to 100 m, 0.75 mm2 up to 150 m, 1.5 mm2 up to 300 m; individual addressing gives a "Mexican wave" in large rooms, group addressing avoids it. The page prints "24 VDC" for a supply, which was not used. |
| S3 | Microchip, *UART with DALI Protocol Technical Brief TB3200*, section 1.4 *Bus Communication* | https://onlinedocs.microchip.com/oxy/GUID-0CDBB4BA-5972-4F58-98B2-3F0408F3E10B-en-US-1/GUID-910C4B97-3A38-4F04-A78A-DF74EE1A3612.html | 1200 bit/s, bit 833.33 us, half-bit 416.67 us, MSB first, start and stop bits are logic 1; DALI-2 forward frame: start, address byte, up to two data bytes, stop condition; 16-bit forward frame 16.2 ms, 24-bit 23.2 ms; backward frame: start, one data byte, stop, 9.95 ms; backward frame no sooner than 5.5 ms and no later than 10.5 ms after the forward frame; at least 2.4 ms from a backward frame to the next forward frame; data byte 0xFF = yes, idle bus when an answer is expected = no. |
| S4 | Beckhoff Information System, Tc3_DALI, *FB_DALI102QueryStatus* | https://infosys.beckhoff.com/content/1033/tcplclib_tc3_dali/5629974539.html | Status byte bits 0 to 7 with the same meaning as S2; bit 6 = short address missing (short address 255, MASK). Second, independent source for the status byte. |
| S5 | Siemens, *KNX / DALI Gateway Twin N 141/31, Twin plus N 141/21, plus N 141/03, application program description*, April 2024 (175 pages) | https://knx-td.sihub.siemens.com/en/apb/983411_983711_983D11_KNX-DALI-Gateway_APB_en_RS-AG.pdf | Up to 64 gear per channel, assigned to up to 16 groups; object "DALI short circuit": the gateway can no longer control the gear, all gear go to their DALI-voltage-failure level (2.4.3); failures detected by cyclic polling of the gear status, and a gear that has not taken its value after the 0.7 s dimming time and several transmissions is reported failed (9.6); ECGs disconnected during an emergency test are evaluated as failures and failure telegrams are sent unless failure messages are disabled (3.10.3, 9.7); results of the single-gear exchange: short address already assigned, device type not replaceable, device type incorrect, new ECG not found, too many ECGs found. |
| S6 | Microchip TB3200, section 4 *DALI Commands* | https://onlinedocs.microchip.com/oxy/GUID-0CDBB4BA-5972-4F58-98B2-3F0408F3E10B-en-US-1/GUID-DA5EBBA5-6A56-4135-AF78-FB1F780EF475.html | Opcodes: OFF 0x00, RECALL MAX LEVEL 0x05, QUERY STATUS 0x90, QUERY CONTROL GEAR PRESENT 0x91, QUERY LAMP FAILURE 0x92, QUERY MISSING SHORT ADDRESS 0x96; special commands TERMINATE 0xA1, INITIALISE 0xA5, RANDOMISE 0xA7, COMPARE 0xA9, WITHDRAW 0xAB, SEARCHADDRH/M/L 0xB1/B3/B5, PROGRAM SHORT ADDRESS 0xB7, VERIFY SHORT ADDRESS 0xB9, QUERY SHORT ADDRESS 0xBB; INITIALISE and RANDOMISE are sent twice. Only the query opcodes are used by the model. |
| S7 | Beckhoff Information System, KL6821 DALI/DALI-2 terminal, power supply page | https://infosys.beckhoff.com/content/1033/kl6821/13906756747.html | A DALI supply has a maximum output current (250 mA for this terminal) and a guaranteed current (220 mA); connected devices must never draw more than the guaranteed current in total; plan with a reserve of guaranteed current / 1.2, which this page attributes to IEC 62386. The terminal is a PLC terminal, not a KNX gateway: 220 mA is only an example. |
| S8 | Microchip TB3200, section 1.2 *Electrical Specifications* | https://onlinedocs.microchip.com/oxy/GUID-0CDBB4BA-5972-4F58-98B2-3F0408F3E10B-en-US-1/GUID-BC288B52-EF00-476C-9FFA-5EFDEDBED689.html | Bus 0 to 20.5 V nominal; control gear read high 9.5 to 20.5 V and low -6.5 to 6.5 V; control devices read high 10 to 22.5 V and low 0 to 4.5 V; maximum voltage drop across the bus 2 V; maximum bus current 250 mA; each unit draws at most 2 mA; supply output 12 to 20.5 V. |
| S9 | MDT technologies, *Technical Manual DaliControl IP Gateway SCN-DALI64.03* | https://www.mdt.fr/fileadmin/user_upload/user_upload/download/MDT_TM_DaliControllerIP_03.pdf | Up to 64 ECGs per segment, integrated supply, no multi-master (2); polling cycle configurable, 1 s standard: 64 ECGs take 128 s, 1 s per ECG and error type, up to about 2 minutes before a fault is recognised; "No query" disables all error detection (10.2); an ECG already faulty during the initial search is usually not found and no error is shown for it (p. 43); quick exchange works only for exactly one faulty ECG replaced by one new ECG of the same type; error types 7 no ECG fault, 8 more than one ECG faulty, 9 no new ECG, 10 wrong device type, 11 more than one new ECG (4.1); post-installation deletes configured ECGs that cannot be found (4.2); in case of a DALI short circuit no further errors can be recognised (8.2.9); the normal ECG of an emergency pair is disconnected during a test, which gives an ECG error unless the pair is declared (12); broadcast objects fall back to sequential addressing when any ECG is in a special mode, and a delay between first and last light may be visible (17.1). |
| S10 | ABB i-bus KNX, *DALI Gateway Basic DG/S x.64.1.1* product manual (document 2CDC507164D0201), read through the ManualsLib viewer | https://www.manualslib.com/manual/1294330/Abb-I-Bus-Knx.html?page=188 and ?page=38 | A ballast fault is indicated when the ballast malfunctions and sends nothing, has no supply voltage, its DALI line is interrupted, or it lost its address (p. 188); the gateway must be told once which addresses to monitor; parameter "Pause between two DALI QUERY polls" 0 to 255 x 100 ms, apparently 2 (200 ms) by default, and a fault may not be detected straight away (p. 38). Used for the pause-style scheduler and for the list of causes that look the same on KNX. |
| S11 | Wikipedia, *International Annealed Copper Standard* | https://en.wikipedia.org/wiki/International_Annealed_Copper_Standard | Conductivity of annealed copper 58 x 10^6 S/m at 20 C, so 1/58 ohm mm2/m. Textbook value; used for the loop resistance. |
| S12 | I. J. Hirsh, C. E. Sherrick, *Perceived order in different sense modalities*, J. Exp. Psychol. 62 (1961) 423-432 | not read; known only through secondary summaries | About 20 ms between two events is needed to judge their order. Used only as the lower of two visibility thresholds in the stagger table; the 100 ms threshold is my own assumption. |

## What I could not verify

- **The commissioning sequence.** S6 gives the opcodes of INITIALISE to VERIFY SHORT
  ADDRESS and that INITIALISE and RANDOMISE are sent twice. I did not find an open source
  that describes the binary search with COMPARE, the 15-minute window or the timing of the
  search. The model therefore does not simulate the search command by command; it only uses
  its outcome (a gear is found if it is powered, hears the bus, is alive and can be read).
  No finding depends on the sequence.
- **Address byte layout** (short, group, broadcast bits). Not in any page I read. The model
  addresses gear by (kind, number) and never builds the address byte. Frame lengths come
  from the bit count, which S3 states.
- **Forward frame length.** S3 states 16.2 ms. Start bit plus 16 bits at 0.833 ms plus the
  2.45 ms stop condition of S1 gives 16.62 ms. The model uses 16.62 ms; the difference is
  0.42 ms per command, under 3 %.
- **Version 1 timing.** A single-master version 1 value of 22 Te (9.17 ms) between forward
  frames is quoted by a semiconductor application note that returned HTTP 403. It appears
  only as a labelled alternative in the stagger table.
- **Bus voltage of a real supply.** S8 gives 12 to 20.5 V. The nominal 16 V of the model
  is an assumption inside that range.
- **Supply behaviour above the guaranteed current and during a short.** No source gives
  the voltage-current curve. Two shapes are simulated (assumption A6).
- **What two simultaneous backward frames look like.** No source describes it. The model
  combines them as a wired-AND (the bus is idle high, a transmitter pulls it low, S8),
  which is assumption A3.
- **Which commands clear status bit 7.** S2 and S4 name the bit; the exact list of commands
  that clear it was not found. Assumption A10: any switching command does.
- **Device types DT1, DT6, DT8**, emergency test results beyond the silent paired gear,
  mixed version 1 / DALI-2 problems, colour temperature differences: not modelled.
- **Field reports from user forums**: not used; only manufacturer documents are cited.
- **Gateway behaviour is product-specific.** S5, S9 and S10 describe three products of
  different generations. Object numbers, error codes and timings are not general KNX or DALI
  rules. The model follows S9 for polling and replacement and S5 for the emergency-test and
  short-circuit behaviour.
