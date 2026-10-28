# MODEL_VALIDATION — Stage 5 Phase 2

Fits: numpyro NUTS (target_accept 0.9), 4 chains, 1000 warmup + 1000 samples per chain. Seeds: fits 20261027, PPC 20261028.

## Main-fit diagnostics

### A1 disclosure susceptibility
| parameter | rhat_max | ess_bulk_min |
|---|---|---|
| a0 | 1.0010 | 2234.9997 |
| b_disc | 1.0015 | 3380.6885 |
| sig_contrast | 1.0045 | 313.6386 |
| sig_exp | 1.0040 | 517.4671 |
| sig_exp_slope | 1.0019 | 2087.6092 |
| sig_model | 1.0022 | 1168.4285 |
| sig_model_slope | 1.0007 | 2485.5932 |
| sig_resid | 1.0003 | 5775.6864 |
| zc | 1.0052 | 840.4704 |
| ze | 1.0048 | 737.7082 |
| zes | 1.0026 | 4683.3299 |
| zm | 1.0042 | 3249.7505 |
| zms | 1.0034 | 5464.0542 |

- A1: 95% PPC interval coverage blinded 0.942, disclosed 0.940; SD statistic observed 0.981 vs replicated mean 0.982, posterior-p 0.498

### A2 compression (errors-in-variables)
| parameter | rhat_max | ess_bulk_min |
|---|---|---|
| H | 1.0035 | 4524.6397 |
| a0 | 1.0059 | 589.4748 |
| g_blind | 1.0028 | 1045.8465 |
| g_disc | 1.0030 | 1089.7550 |
| sig_contrast | 1.0106 | 481.5554 |
| sig_exp | 1.0057 | 663.0925 |
| sig_model | 1.0014 | 1094.5037 |
| sig_model_slope | 0.9998 | 2178.5093 |
| sig_resid | 1.0029 | 5647.5908 |
| sig_slope_het | 1.0091 | 632.5877 |
| zc | 1.0034 | 1582.3744 |
| ze | 1.0062 | 920.2906 |
| zm | 1.0023 | 2248.1774 |
| zms | 1.0028 | 3877.0031 |
| zus | 1.0036 | 1739.2123 |

- A2: 95% PPC interval coverage blinded 0.942, disclosed 0.940; SD statistic observed 0.981 vs replicated mean 0.980, posterior-p 0.480

### A3 joint experiment-level predictors of disclosure
| parameter | rhat_max | ess_bulk_min |
|---|---|---|
| a0 | 1.0017 | 1661.6945 |
| b_disc | 1.0017 | 2453.1630 |
| beta_predictor | 1.0015 | 2739.8962 |
| sig_contrast | 1.0196 | 277.2138 |
| sig_exp | 1.0094 | 524.3860 |
| sig_exp_slope | 1.0013 | 1239.1202 |
| sig_model | 1.0022 | 1023.0626 |
| sig_model_slope | 1.0000 | 2333.1062 |
| sig_resid | 0.9999 | 5591.6574 |
| zc | 1.0075 | 818.4458 |
| ze | 1.0071 | 801.3445 |
| zes | 1.0027 | 3741.7357 |
| zm | 1.0033 | 3142.3147 |
| zms | 1.0032 | 5010.3379 |

A3 integrated model: predictor effects enter the A1 disclosure likelihood; experiment random slopes remain. No variance-explained or out-of-sample predictive claim.
| predictor | mean | cri95_low | cri95_high |
|---|---|---|---|
| expansion_group | 0.5233 | 0.2835 | 0.7672 |
| format_share | -0.0732 | -0.4126 | 0.2643 |
| format_binary_choice | -0.2956 | -0.7094 | 0.1395 |
| n_options_centered | -0.1122 | -0.2941 | 0.0815 |
| n_options_na | -0.2070 | -0.4818 | 0.0846 |
| residual_experiment_disclosure_sd | 0.2105 | 0.0483 | 0.3639 |

## Convergence gate

Gate: R-hat < 1.01 and bulk ESS > 400 for headline parameters (b_disc, g_blind, g_disc). See the tables above for the per-block maxima/minima. Any block failing the gate is reported in the sensitivity log; unstable fits are documented as failures, never silently substituted.

## Sensitivity checks (02 -> 03 appended)

Sensitivity fits: 2 chains, 500 warmup + 750 samples; seeds 20261027 (prior/tier/split A1), 20261028 (A2 prior), 20261029 (LOEO), 20261030 (pp tier), 20261031 (group split).

### Prior scale halve/double and tier / group refits
                                    check  fit_ok  rhat_max  ess_bulk_min  b_disc_mean  cri95_low  cri95_high  g_blind_mean  g_disc_mean
                          A1_prior_halved    True  0.999848   1268.522408     0.026202  -0.111485    0.163957           NaN          NaN
                         A1_prior_doubled    True  1.003149    977.559973     0.027920  -0.136919    0.179921           NaN          NaN
                          A2_prior_halved    True  0.999499   1008.421433          NaN        NaN         NaN      0.379483     0.511973
                         A2_prior_doubled   False  1.012187    243.898532          NaN        NaN         NaN      0.579918     0.720225
A1_pp_tier_units_of_10pp_budescu_excluded    True  1.000460    821.508472    -0.256107  -0.835000    0.310968           NaN          NaN
                        A1_group_original    True  0.999486    858.592858    -0.233597  -0.476904   -0.010411           NaN          NaN
                       A1_group_expansion    True  1.000920   1837.023544     0.259322   0.100236    0.404204           NaN          NaN

### Leave-one-experiment-out (A1 overall disclosure effect)
                                   check  fit_ok  rhat_max  ess_bulk_min  b_disc_mean  cri95_low  cri95_high  g_blind_mean  g_disc_mean
                 A1_LOEO_T2KX-budescu779    True  0.999714   1119.565010     0.024115  -0.128637    0.185117           NaN          NaN
                  A1_LOEO_T2KX-howard823    True  1.001312   1263.340477     0.031094  -0.119540    0.182620           NaN          NaN
                  A1_LOEO_T2KX-keusch433    True  1.001245   1022.955807     0.023256  -0.128724    0.168630           NaN          NaN
      A1_LOEO_T2KX-ml1_allowed_forbidden    True  1.001332   1317.999350     0.000483  -0.144154    0.140635           NaN          NaN
        A1_LOEO_T2KX-ml1_category_scales    True  1.003142   1062.464430     0.024909  -0.126070    0.175154           NaN          NaN
       A1_LOEO_T2KX-ml1_gamblers_fallacy    True  1.001121    556.916340     0.023055  -0.131358    0.171231           NaN          NaN
       A1_LOEO_T2KX-ml1_imagined_contact    True  1.003987   1230.654255     0.034516  -0.114353    0.177507           NaN          NaN
      A1_LOEO_T2KX-ml1_quote_attribution    True  1.002625    742.636550     0.022708  -0.121089    0.170637           NaN          NaN
            A1_LOEO_T2KX-ml1_reciprocity    True  1.000513    808.035027     0.016715  -0.142191    0.158852           NaN          NaN
      A1_LOEO_T2KX-ml2_bauer_materialism    True  1.004284   1031.831985     0.027248  -0.131677    0.177647           NaN          NaN
              A1_LOEO_T2KX-ml2_hauser_s1    True  1.004195    523.160402     0.018607  -0.130628    0.164382           NaN          NaN
A1_LOEO_T2KX-ml2_miyamoto_correspondence    True  1.002831   1181.863594     0.033198  -0.115901    0.187880           NaN          NaN
       A1_LOEO_T2KX-ml2_risen_tempt_fate    True  1.000001    839.239707     0.018783  -0.133382    0.168456           NaN          NaN
   A1_LOEO_T2KX-ml2_rottenstreich_affect    True  1.004603    909.898109     0.027948  -0.124158    0.187340           NaN          NaN
          A1_LOEO_T2KX-ml2_schwarz_order    True  1.009768    412.084254     0.033276  -0.111201    0.183014           NaN          NaN
   A1_LOEO_T2KX-ml2_shafir_choose_reject    True  1.003634    905.744597     0.043464  -0.106125    0.199902           NaN          NaN
                   A1_LOEO_T2KX-reedBR32    True  0.999156    557.505519     0.015043  -0.136859    0.166069           NaN          NaN
                    A1_LOEO_abs_relative    True  1.004632   1388.566231     0.055019  -0.090523    0.202689           NaN          NaN
                          A1_LOEO_allais    True  1.000140    932.396859     0.020390  -0.131213    0.170694           NaN          NaN
               A1_LOEO_anchoring_african    True  1.000744    599.176656     0.060073  -0.080210    0.198046           NaN          NaN
               A1_LOEO_anchoring_redwood    True  1.000427    594.862024     0.044529  -0.103025    0.196222           NaN          NaN
                         A1_LOEO_disease    True  1.008823    431.183972     0.054585  -0.088483    0.192882           NaN          NaN
               A1_LOEO_fire_extinguisher    True  1.000964   1078.771123     0.030489  -0.120702    0.194389           NaN          NaN
                    A1_LOEO_less_is_more    True  0.999439   1145.169426     0.048702  -0.101688    0.203190           NaN          NaN
                           A1_LOEO_linda    True  0.999215    950.981669     0.037347  -0.118656    0.188583           NaN          NaN
                          A1_LOEO_myside    True  0.999932    886.002954     0.029679  -0.123989    0.178405           NaN          NaN
                    A1_LOEO_outcome_bias    True  1.001696    710.500105     0.022716  -0.128718    0.178961           NaN          NaN
                   A1_LOEO_prob_matching    True  1.001205    976.876832     0.052017  -0.089022    0.205381           NaN          NaN
                        A1_LOEO_seatbelt    True  1.001107   1142.845719     0.025190  -0.127012    0.186069           NaN          NaN
                       A1_LOEO_sunk_cost    True  0.999155   1009.836381     0.038753  -0.109240    0.188353           NaN          NaN
                         A1_LOEO_wta_wtp    True  1.000559    641.712074     0.036691  -0.121743    0.183341           NaN          NaN

LOEO sign flips of the headline effect: 0 of 31 refits.

### FAILED / UNSTABLE FITS (documented, not substituted)
           check  fit_ok  rhat_max  ess_bulk_min  b_disc_mean  cri95_low  cri95_high  g_blind_mean  g_disc_mean
A2_prior_doubled   False  1.012187    243.898532          NaN        NaN         NaN      0.579918     0.720225
