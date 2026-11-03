# Selected certificate bounds

Sixteen configurations: thirteen paired bounds and three lower-only highlights.
These bounds concern ordinary SP in expectation and expected sum-distance cost.
Exact values and artifact paths are in [results.json](results.json); explicit unit graphs
and agent counts are in [configurations.json](configurations.json).

Upper endpoints use the complete recorded acceptances described in
[validation](../validation/README.md). Reproduction instructions are in the
[main README](../README.md). A dash means no upper certificate is included for that row.

Lower bounds are rounded downward and upper bounds upward to 12 decimal places,
using exact rational arithmetic. Each displayed gap is an upper bound on the
exact interval width, rounded upward from the exact difference.

| Graph | Agents | Lower | Upper | Gap |
| --- | ---: | ---: | ---: | ---: |
| cycle | 3 | [1.059117369100](../certificates/lower/cycle-n3.json.xz) | [1.107470000000](../certificates/upper/cycle-n3.tar.xz) | 0.048352630900 |
| c4_pendant | 3 | [1.049734282680](../certificates/lower/c4_pendant-n3.json.xz) | [1.132120000000](../certificates/upper/c4_pendant-n3.tar.xz) | 0.082385717320 |
| theta | 3 | [1.078216584909](../certificates/lower/theta-n3.json.xz) | [1.202800000000](../certificates/upper/theta-n3.tar.xz) | 0.124583415091 |
| c6_pendant | 3 | [1.050939365103](../certificates/lower/c6_pendant-n3.json.xz) | [1.190920000000](../certificates/upper/c6_pendant-n3.tar.xz) | 0.139980634897 |
| theta_244 | 3 | [1.075635097787](../certificates/lower/theta_244-n3.json.xz) | [1.217250000000](../certificates/upper/theta_244-n3.tar.xz) | 0.141614902213 |
| k2_4 | 3 | [1.077807650022](../certificates/lower/k2_4-n3.json.xz) | [1.236050000000](../certificates/upper/k2_4-n3.tar.xz) | 0.158242349978 |
| cycle | 4 | [1.089157432240](../certificates/lower/cycle-n4.json.xz) | [1.250250000000](../certificates/upper/cycle-n4.tar.xz) | 0.161092567760 |
| k3_3 | 3 | [1.078138407691](../certificates/lower/k3_3-n3.json.xz) | [1.244950000000](../certificates/upper/k3_3-n3.tar.xz) | 0.166811592309 |
| k2_5 | 3 | [1.078119703605](../certificates/lower/k2_5-n3.json.xz) | [1.248000000000](../certificates/upper/k2_5-n3.tar.xz) | 0.169880296395 |
| k2_6 | 3 | [1.077986717685](../certificates/lower/k2_6-n3.json.xz) | [1.258850000000](../certificates/upper/k2_6-n3.tar.xz) | 0.180863282315 |
| theta_224 | 3 | [1.065238837183](../certificates/lower/theta_224-n3.json.xz) | [1.250550000000](../certificates/upper/theta_224-n3.tar.xz) | 0.185311162817 |
| domino | 3 | [1.063643013134](../certificates/lower/domino-n3.json.xz) | [1.251100000000](../certificates/upper/domino-n3.tar.xz) | 0.187456986866 |
| bowtie | 3 | [1.044703688450](../certificates/lower/bowtie-n3.json.xz) | [1.250000000000](../certificates/upper/bowtie-n3.tar.xz) | 0.205296311550 |
| k2_4 | 4 | [1.118056448043](../certificates/lower/k2_4-n4.json.xz) | — | — |
| k2_5 | 5 | [1.133587351026](../certificates/lower/k2_5-n5.json.xz) | — | — |
| k2_6 | 6 | [1.140204823651](../certificates/lower/k2_6-n6.json.xz) | — | — |

The circle rows describe continuous circles up to uniform scaling, not different
finite report domains. The bowtie row consists of two equal circles joined at
one vertex. Parameterized theta and complete bipartite graphs are defined by
their explicit edge lists. Equal metric graphs with different agent counts are
different configurations. No row claims optimality among all mechanisms.
