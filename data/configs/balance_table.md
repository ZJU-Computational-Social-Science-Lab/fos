# Phase 3 Run-Matrix Balance Table

Morgan-Rubin balance evidence for the 126-run assignment. Criteria 1-5 are
hard constraints; criterion 6 (statistic means) holds at the threshold recorded
in assignment_meta.json.

## Population x generator (criterion 1, target 7 +/- 1)

|  | watts_strogatz | holme_kim | sbm |
|---|---|---|---|
| pop_a1 | 7 | 8 | 6 |
| pop_a2 | 7 | 6 | 8 |
| pop_b1 | 7 | 7 | 7 |
| pop_b2 | 7 | 6 | 8 |
| pop_c1 | 7 | 7 | 7 |
| pop_c2 | 7 | 8 | 6 |

## Population x primary level (criterion 2, target 7 +/- 1)

|  | level 0 | level 1 | level 2 |
|---|---|---|---|
| pop_a1 | 8 | 6 | 7 |
| pop_a2 | 7 | 7 | 7 |
| pop_b1 | 7 | 7 | 7 |
| pop_b2 | 6 | 7 | 8 |
| pop_c1 | 7 | 8 | 6 |
| pop_c2 | 7 | 7 | 7 |

## Population x secondary level (criterion 3, target 10 or 11)

|  | level 0 | level 1 |
|---|---|---|
| pop_a1 | 11 | 10 |
| pop_a2 | 11 | 10 |
| pop_b1 | 10 | 11 |
| pop_b2 | 10 | 11 |
| pop_c1 | 10 | 11 |
| pop_c2 | 11 | 10 |

## Population x (generator x primary level) (criterion 4, all cells >= 1)

|  | WS p0 | WS p1 | WS p2 | HK p0 | HK p1 | HK p2 | SBM p0 | SBM p1 | SBM p2 |
|---|---|---|---|---|---|---|---|---|---|
| pop_a1 | 2 | 3 | 2 | 5 | 1 | 2 | 1 | 2 | 3 |
| pop_a2 | 2 | 3 | 2 | 2 | 2 | 2 | 3 | 2 | 3 |
| pop_b1 | 2 | 3 | 2 | 3 | 1 | 3 | 2 | 3 | 2 |
| pop_b2 | 2 | 3 | 2 | 1 | 1 | 4 | 3 | 3 | 2 |
| pop_c1 | 3 | 1 | 3 | 1 | 5 | 1 | 3 | 2 | 2 |
| pop_c2 | 3 | 1 | 3 | 2 | 4 | 2 | 2 | 2 | 2 |

## Generating model x generator (criterion 5, target 14 +/- 1)

|  | watts_strogatz | holme_kim | sbm |
|---|---|---|---|
| deepseek-v4-flash | 14 | 14 | 14 |
| glm-5.2 | 14 | 13 | 15 |
| gpt-oss-20b | 14 | 15 | 13 |

## Generating model x primary level (criterion 5, target 14 +/- 1)

|  | level 0 | level 1 | level 2 |
|---|---|---|---|
| deepseek-v4-flash | 15 | 13 | 14 |
| glm-5.2 | 13 | 14 | 15 |
| gpt-oss-20b | 14 | 15 | 13 |

## Population statistic means vs grand mean (criterion 6)

| population | mean_degree | degree_gini | global_clustering | mean_path_length | modularity |
|---|---|---|---|---|---|
| pop_a1 | 6.5676 | 0.2210 | 0.2640 | 2.8538 | 0.4636 |
| pop_a2 | 6.6219 | 0.2097 | 0.2585 | 2.8557 | 0.4649 |
| pop_b1 | 6.6714 | 0.2150 | 0.2667 | 2.8159 | 0.4551 |
| pop_b2 | 6.5848 | 0.2107 | 0.2728 | 2.8100 | 0.4641 |
| pop_c1 | 6.6362 | 0.2172 | 0.2672 | 2.8268 | 0.4525 |
| pop_c2 | 6.6495 | 0.2207 | 0.2758 | 2.8465 | 0.4570 |
| grand mean | 6.6219 | 0.2157 | 0.2675 | 2.8348 | 0.4595 |
| grand SD | 0.9209 | 0.0958 | 0.1417 | 0.3704 | 0.1228 |
