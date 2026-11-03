# Complete verifier fixtures

| Directory | Meaning | Expected CLI outcome |
| --- | --- | --- |
| single-edge-dictator | Two agents, dictator on a single unit edge | exit 0, `1` |
| four-cycle-dictator | Two agents, dictator on a continuous four-cycle | exit 0, `1` |
| single-edge-non-sp | A supplied mechanism with a profitable unilateral deviation | exit 1, exact counterexample |
| single-edge-false-factor | An SP mechanism with an insufficient claimed approximation factor | exit 1, exact counterexample |

Each directory contains all five canonical certificate files. The test suite
also generates corruptions and independent mathematical controls. These examples
check installation and failure handling; they do not establish scoreboard endpoints.
