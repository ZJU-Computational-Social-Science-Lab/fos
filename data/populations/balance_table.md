# Population Balance Table (Phase 3, Step 2)

Generated from 6 populations of 100 agents each (27-cell grid: age x political view x work sector).

## 1. Archetype cell counts (agents per cell, per population)

| Cell (age | political | sector) | pop_a1 | pop_a2 | pop_b1 | pop_b2 | pop_c1 | pop_c2 | max-min | flag |
|---|---|---|---|---|---|---|---|---|
| young | liberal | public | 5 | 4 | 6 | 1 | 5 | 2 | 5 | ⚠ FLAG |
| young | liberal | private | 2 | 3 | 3 | 2 | 4 | 5 | 3 | ⚠ FLAG |
| young | liberal | nonprofit | 4 | 7 | 4 | 6 | 5 | 1 | 6 | ⚠ FLAG |
| young | moderate | public | 3 | 3 | 2 | 3 | 5 | 4 | 3 | ⚠ FLAG |
| young | moderate | private | 4 | 2 | 3 | 7 | 4 | 3 | 5 | ⚠ FLAG |
| young | moderate | nonprofit | 2 | 3 | 1 | 4 | 0 | 0 | 4 | ⚠ FLAG |
| young | conservative | public | 5 | 5 | 4 | 1 | 2 | 6 | 5 | ⚠ FLAG |
| young | conservative | private | 2 | 0 | 4 | 8 | 2 | 2 | 8 | ⚠ FLAG |
| young | conservative | nonprofit | 1 | 2 | 1 | 2 | 3 | 3 | 2 |  |
| middle | liberal | public | 2 | 3 | 4 | 4 | 7 | 3 | 5 | ⚠ FLAG |
| middle | liberal | private | 6 | 2 | 6 | 7 | 5 | 2 | 5 | ⚠ FLAG |
| middle | liberal | nonprofit | 2 | 5 | 2 | 2 | 2 | 1 | 4 | ⚠ FLAG |
| middle | moderate | public | 5 | 3 | 7 | 3 | 3 | 3 | 4 | ⚠ FLAG |
| middle | moderate | private | 5 | 4 | 3 | 3 | 3 | 4 | 2 |  |
| middle | moderate | nonprofit | 4 | 3 | 3 | 1 | 4 | 5 | 4 | ⚠ FLAG |
| middle | conservative | public | 4 | 6 | 2 | 9 | 8 | 4 | 7 | ⚠ FLAG |
| middle | conservative | private | 2 | 7 | 2 | 1 | 8 | 5 | 7 | ⚠ FLAG |
| middle | conservative | nonprofit | 8 | 2 | 3 | 1 | 5 | 4 | 7 | ⚠ FLAG |
| older | liberal | public | 6 | 5 | 3 | 1 | 2 | 5 | 5 | ⚠ FLAG |
| older | liberal | private | 4 | 3 | 6 | 2 | 1 | 7 | 6 | ⚠ FLAG |
| older | liberal | nonprofit | 1 | 4 | 5 | 6 | 4 | 5 | 5 | ⚠ FLAG |
| older | moderate | public | 3 | 5 | 5 | 4 | 3 | 3 | 2 |  |
| older | moderate | private | 5 | 1 | 4 | 3 | 4 | 4 | 4 | ⚠ FLAG |
| older | moderate | nonprofit | 2 | 5 | 7 | 3 | 1 | 4 | 6 | ⚠ FLAG |
| older | conservative | public | 5 | 2 | 5 | 4 | 3 | 3 | 3 | ⚠ FLAG |
| older | conservative | private | 4 | 5 | 3 | 6 | 2 | 6 | 4 | ⚠ FLAG |
| older | conservative | nonprofit | 4 | 6 | 2 | 6 | 5 | 6 | 4 | ⚠ FLAG |

Cells whose count differs by more than 2 agents across populations are flagged with ⚠ FLAG.

## 2. Big Five trait means and standard deviations (per population)

### Openness (trait `o`)

| Population | mean | sd |
|---|---|---|
| pop_a1 | 48.44 | 18.60 |
| pop_a2 | 47.81 | 21.54 |
| pop_b1 | 45.89 | 17.13 |
| pop_b2 | 48.32 | 18.90 |
| pop_c1 | 47.55 | 20.60 |
| pop_c2 | 48.37 | 16.90 |

### Conscientiousness (trait `c`)

| Population | mean | sd |
|---|---|---|
| pop_a1 | 49.21 | 19.35 |
| pop_a2 | 51.01 | 18.46 |
| pop_b1 | 53.73 | 19.95 |
| pop_b2 | 52.54 | 19.81 |
| pop_c1 | 50.26 | 17.13 |
| pop_c2 | 50.63 | 19.01 |

### Extraversion (trait `e`)

| Population | mean | sd |
|---|---|---|
| pop_a1 | 50.10 | 20.18 |
| pop_a2 | 49.53 | 18.35 |
| pop_b1 | 50.01 | 18.91 |
| pop_b2 | 49.43 | 20.44 |
| pop_c1 | 49.27 | 20.56 |
| pop_c2 | 49.51 | 19.32 |

### Agreeableness (trait `a`)

| Population | mean | sd |
|---|---|---|
| pop_a1 | 50.82 | 17.46 |
| pop_a2 | 47.93 | 22.06 |
| pop_b1 | 50.71 | 20.25 |
| pop_b2 | 51.58 | 20.98 |
| pop_c1 | 48.44 | 19.86 |
| pop_c2 | 47.92 | 21.58 |

### Neuroticism (trait `n`)

| Population | mean | sd |
|---|---|---|
| pop_a1 | 47.57 | 20.03 |
| pop_a2 | 49.49 | 19.47 |
| pop_b1 | 49.44 | 18.15 |
| pop_b2 | 47.69 | 21.02 |
| pop_c1 | 49.28 | 21.12 |
| pop_c2 | 52.45 | 22.35 |

## 3. Voting model counts (per population)

| Population | gpt-oss-20b | qwen3.6-35b-a3b | qwen3.6-35b-a3b-uncensored-hauhaucs-aggressive | gemma-4-26b-a4b | gemma4-26b-a4b-uncensored-hauhaucs-balanced | total |
|---|---|---|---|---|---|---|
| pop_a1 | 20 | 20 | 20 | 20 | 20 | 100 |
| pop_a2 | 20 | 20 | 20 | 20 | 20 | 100 |
| pop_b1 | 20 | 20 | 20 | 20 | 20 | 100 |
| pop_b2 | 20 | 20 | 20 | 20 | 20 | 100 |
| pop_c1 | 20 | 20 | 20 | 20 | 20 | 100 |
| pop_c2 | 20 | 20 | 20 | 20 | 20 | 100 |

