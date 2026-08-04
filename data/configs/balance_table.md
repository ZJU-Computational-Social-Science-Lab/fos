# Phase 3 Run-Matrix Balance Table

Morgan-Rubin balance evidence for the 126-run assignment. Criteria 1-5 are
hard constraints; criterion 6 (statistic means) holds at the threshold recorded
in assignment_meta.json.

## Population x generator (criterion 1, target 7 +/- 1)

|  | watts_strogatz | holme_kim | sbm |
|---|---|---|---|
| pop_a1 | 8 | 7 | 6 |
| pop_a2 | 6 | 7 | 8 |
| pop_b1 | 7 | 7 | 7 |
| pop_b2 | 7 | 7 | 7 |
| pop_c1 | 6 | 7 | 8 |
| pop_c2 | 8 | 7 | 6 |

## Population x primary level (criterion 2, target 7 +/- 1)

|  | level 0 | level 1 | level 2 |
|---|---|---|---|
| pop_a1 | 7 | 6 | 8 |
| pop_a2 | 6 | 8 | 7 |
| pop_b1 | 8 | 6 | 7 |
| pop_b2 | 7 | 8 | 6 |
| pop_c1 | 7 | 7 | 7 |
| pop_c2 | 7 | 7 | 7 |

## Population x secondary level (criterion 3, target 10 or 11)

|  | level 0 | level 1 |
|---|---|---|
| pop_a1 | 10 | 11 |
| pop_a2 | 10 | 11 |
| pop_b1 | 11 | 10 |
| pop_b2 | 10 | 11 |
| pop_c1 | 11 | 10 |
| pop_c2 | 11 | 10 |

## Population x (generator x primary level) (criterion 4, all cells >= 1)

|  | WS p0 | WS p1 | WS p2 | HK p0 | HK p1 | HK p2 | SBM p0 | SBM p1 | SBM p2 |
|---|---|---|---|---|---|---|---|---|---|
| pop_a1 | 2 | 2 | 4 | 3 | 3 | 1 | 2 | 1 | 3 |
| pop_a2 | 1 | 3 | 2 | 2 | 3 | 2 | 3 | 2 | 3 |
| pop_b1 | 3 | 3 | 1 | 2 | 1 | 4 | 3 | 2 | 2 |
| pop_b2 | 4 | 1 | 2 | 1 | 3 | 3 | 2 | 4 | 1 |
| pop_c1 | 2 | 2 | 2 | 2 | 3 | 2 | 3 | 2 | 3 |
| pop_c2 | 2 | 3 | 3 | 4 | 1 | 2 | 1 | 3 | 2 |

## Generating model x generator (criterion 5, target 14 +/- 1)

|  | watts_strogatz | holme_kim | sbm |
|---|---|---|---|
| deepseek-v4-flash | 14 | 14 | 14 |
| glm-5.2 | 14 | 14 | 14 |
| gpt-oss-20b | 14 | 14 | 14 |

## Generating model x primary level (criterion 5, target 14 +/- 1)

|  | level 0 | level 1 | level 2 |
|---|---|---|---|
| deepseek-v4-flash | 13 | 14 | 15 |
| glm-5.2 | 15 | 14 | 13 |
| gpt-oss-20b | 14 | 14 | 14 |

## Population statistic means vs grand mean (criterion 6)

| population | mean_degree | degree_gini | global_clustering | mean_path_length | modularity |
|---|---|---|---|---|---|
| pop_a1 | 6.6390 | 0.2157 | 0.2086 | 2.8445 | 0.4612 |
| pop_a2 | 6.6038 | 0.2201 | 0.2080 | 2.8170 | 0.4649 |
| pop_b1 | 6.6076 | 0.2120 | 0.2181 | 2.8574 | 0.4609 |
| pop_b2 | 6.5724 | 0.2143 | 0.2180 | 2.8313 | 0.4532 |
| pop_c1 | 6.6248 | 0.2182 | 0.2122 | 2.8357 | 0.4607 |
| pop_c2 | 6.6838 | 0.2141 | 0.2134 | 2.8227 | 0.4562 |
| grand mean | 6.6219 | 0.2157 | 0.2130 | 2.8348 | 0.4595 |
| grand SD | 0.9209 | 0.0958 | 0.1161 | 0.3704 | 0.1228 |
