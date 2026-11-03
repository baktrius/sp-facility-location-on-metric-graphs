# Initial lower replay status

The initial preparation check recorded 12 complete acceptances and 4 incomplete
replays with a 60-second limit per certificate. The later
[XZ migration replays](README.md#xz-migration-checks) completed and accepted all
16 lower certificates. The table below preserves the initial outcomes; its
timeouts are not the current replay status.

Timeouts supply no fresh verdict. All 16 copies retain the decoded mathematical
payload of their recorded accepted inputs.

| Configuration | Replay outcome | Seconds |
| --- | --- | ---: |
| cycle-n3 | incomplete | 60.07 |
| c4_pendant-n3 | accepted | 4.73 |
| theta-n3 | accepted | 32.91 |
| c6_pendant-n3 | accepted | 5.55 |
| theta_244-n3 | accepted | 0.62 |
| k2_4-n3 | accepted | 35.74 |
| cycle-n4 | incomplete | 60.06 |
| k3_3-n3 | accepted | 47.85 |
| k2_5-n3 | accepted | 46.10 |
| k2_6-n3 | accepted | 56.02 |
| theta_224-n3 | accepted | 1.18 |
| domino-n3 | accepted | 0.38 |
| bowtie-n3 | accepted | 0.08 |
| k2_4-n4 | accepted | 9.76 |
| k2_5-n5 | incomplete | 60.07 |
| k2_6-n6 | incomplete | 60.07 |

Exact stdout, certificate hashes and process outcomes are in [lower-recheck.json](lower-recheck.json).
The [validation guide](README.md) gives the full replay commands and evidence distinctions.
