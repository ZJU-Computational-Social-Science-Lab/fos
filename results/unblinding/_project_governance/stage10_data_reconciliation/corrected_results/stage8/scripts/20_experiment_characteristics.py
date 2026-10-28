# 20_experiment_characteristics.py — Stage 8 Phase 1, Part 2 (step 1).
#
# What this file does:
#   Holds the experiment characteristics coded by hand from the ACTUAL
#   experimental instructions (originals: stimuli.json of the Twin-2K runs
#   and experiment_registry.json; expansion: expansion/pipeline/
#   sample_prompts verbatim prompts + expansion/pipeline/registry.py), and
#   writes EXPERIMENT_CHARACTERISTICS.csv (31 experiments). Coding was
#   completed and frozen BEFORE any accuracy numbers were joined — this
#   script writes the coded table with its evidence quotes first; the join
#   to AI-accuracy results happens only in 30_crosstabs.py.
#
#   coded_rows()  — the frozen hand-coding, one row per experiment.
#   main()        — attach contrast ids + evidence quotes, write CSV.

from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parents[1]

# Columns: experiment_id, study_group, judgment_type, response_format,
# manipulation, and the task_nature flags, then evidence quote + source.
# judgment_type: what kind of judgment the outcome measures.
#   valuation = how good/attractive/worth something is; decision = choice
#   or intended action; risk = probability/likelihood judgment; social =
#   judgment about other people or social policy; belief = own belief or
#   attitude; attribution = inferring someone's (or an event's) hidden
#   cause/state; NA = not reliably distinguishable from the instructions.
# response_format comes verbatim from the instrument.
# Flags (from instructions only): emotional_reactions = the vignette is
#   built around fear/dread/affect; incentives_at_stake = money or a
#   concrete personal payoff is explicitly at stake; social_expectations =
#   the correct/expected answer references other people's views or norms;
#   uncertainty_prominent = the outcome is explicitly probabilistic or
#   unknown; scenario_interpretation = answering requires interpreting
#   what kind of situation the vignette describes (vs applying a rule).
E = []


def row(exp, group, jtype, rfmt, manip, emot, incen, social, uncert,
        interp, quote, source, contrasts, note=""):
    E.append(dict(
        experiment_id=exp, study_group=group, judgment_type=jtype,
        response_format=rfmt, manipulation=manip,
        flag_emotional_reactions=emot, flag_incentives_at_stake=incen,
        flag_social_expectations=social, flag_uncertainty_prominent=uncert,
        flag_scenario_interpretation=interp,
        instruction_evidence=quote, instruction_source=source,
        contrast_ids=contrasts, coding_note=note))


# ---------------- originals (14) ----------------
row("disease", "original", "decision", "rating_scale",
    "Same two health programs described as saving lives (gain frame) vs as "
    "people dying (loss frame); outcome = preference for the safe program",
    0, 0, 0, 1, 1,
    "\"If Program A is adopted, 200 people will be saved. ... there is 1/3 "
    "probability that 600 people will be saved\" vs \"400 people will die\"",
    "stimuli.json QID157/QID158 (6TASKS)", "C-01")
row("less_is_more", "original", "valuation", "rating_scale",
    "A small loss (5c or 25c) is added to a gamble that otherwise wins $9 "
    "with p=7/36; rated attractiveness of the gamble",
    0, 1, 0, 1, 0,
    "\"7/36 chance of winning $9 and a 29/36 chance of winning nothing\" vs "
    "\"... 29/36 chance of losing $0.05 / losing $0.25\"",
    "stimuli.json QID171-173 (6TASKS)", "C-02,C-03")
row("fire_extinguisher", "original", "decision", "rating_scale",
    "Safety requirement saves exactly 150 lives ('all') vs 98% of 150 vs "
    "95% of 150 - same absolute number described as a proportion; support "
    "for the requirement rated",
    0, 1, 0, 1, 0,
    "\"would save the 150 people who would otherwise die\" vs \"would save "
    "98% of the 150 people\"",
    "stimuli.json QID174-176 (6TASKS)", "C-04,C-05")
row("seatbelt", "original", "decision", "rating_scale",
    "Seatbelt saves exactly 500 drivers ('all') vs 98% vs 95% of 500; "
    "likelihood of buying the $500 option rated",
    0, 1, 0, 1, 0,
    "\"would save the lives of the 500 drivers\" vs \"would save the lives "
    "of 98% of the 500 drivers ... available as a $500 option\"",
    "stimuli.json QID177-179 (6TASKS)", "C-06,C-07")
row("sunk_cost", "original", "decision", "numeric_estimate",
    "A $50 discount card has (card arm) vs has not (no-card arm) been paid "
    "for; number of next 20 coffees bought at the cheaper store",
    0, 1, 0, 0, 1,
    "\"Imagine that you just paid $50 for a Coffee Connection discount "
    "card\" vs no payment mentioned; \"how many of your next 20 coffee "
    "purchases\"",
    "stimuli.json QID181-182 (6TASKS)", "C-08")
row("wta_wtp", "original", "valuation", "numeric_estimate",
    "Willingness to accept payment to risk a fatal virus vs willingness to "
    "pay to remove the same risk (certainty vs 4-in-1000 reduction arms); "
    "price from a $10-$5M bracket",
    1, 1, 0, 1, 0,
    "\"What is the lowest amount that you would have to be paid before you "
    "would take part in this experiment?\" vs \"What is the highest price "
    "you would be prepared to pay for such an injection?\"",
    "stimuli.json QID189-191 (6TASKS)", "C-09,C-10")
row("allais", "original", "decision", "binary_choice",
    "Common-ratio pairing: $1M for sure vs a gamble (form 1) and the same "
    "gamble pair scaled to 11%/10% chances (form 2)",
    0, 1, 0, 1, 0,
    "\"One million dollars for sure\" vs \"89% probability of one million "
    "dollars 10% probablity of five miillion dollars\"",
    "stimuli.json QID192-193 (10TASKS)", "C-11")
row("linda", "original", "risk", "rating_scale",
    "The rated statement is the conjunction ('bank teller AND feminist', "
    "conjunction arm) vs plain 'bank teller' (no-conjunction arm); "
    "probability rated 1-6",
    0, 0, 0, 1, 1,
    "\"It is ___ that Linda is a bank teller and is active in the feminist "
    "movement\" vs \"It is ___ that Linda is a bank teller\"",
    "stimuli.json QID159-160 rows (10TASKS)", "C-12")
row("anchoring_redwood", "original", "risk", "numeric_estimate",
    "Comparative question uses a high (1000 ft) vs low (85 ft) anchor "
    "before an absolute height estimate",
    0, 0, 0, 1, 0,
    "\"Is the tallest redwood tree in the world more or less than 85 feet "
    "tall?\" vs \"... more or less than 1000 feet tall?\"",
    "stimuli.json QID167-170 (10TASKS)", "C-13")
row("anchoring_african", "original", "risk", "numeric_estimate",
    "Comparative question uses a high (65) vs low (12) anchor before an "
    "absolute estimate of African UN members",
    0, 0, 0, 1, 0,
    "\"more or fewer than 12 African countries in the United Nations?\" vs "
    "\"more or fewer than 65\"",
    "stimuli.json QID163-166 (10TASKS)", "C-14")
row("outcome_bias", "original", "social", "rating_scale",
    "Identical 8%-mortality operation decision evaluated after a "
    "successful vs fatal outcome; decision quality rated 1-7",
    1, 1, 0, 1, 0,
    "\"His physician decided to go ahead with the operation. The operation "
    "succeeded.\" vs \"... did not succeed and the patient died.\"",
    "stimuli.json QID161-162 (10TASKS)", "C-15")
row("myside", "original", "social", "rating_scale",
    "The 8x-fatality ban targets an out-group-referenced car ('the German "
    "car', German respondents ban it) vs an in-group one (Ford Explorer); "
    "ban support rated 1-6",
    0, 0, 1, 0, 1,
    "\"Ford Explorers are 8 times more likely ... Germany should ban\" vs "
    "\"a particular German car is 8 times more likely ... the U.S. should "
    "ban\"",
    "stimuli.json QID194-195 (10TASKS)", "C-16")
row("prob_matching", "original", "risk", "numeric_estimate",
    "Two decline-rate prediction problems (7-3 cards, 4-2 die); "
    "manipulation is the position in the sequence at which prediction is "
    "elicited",
    0, 1, 0, 1, 1,
    "\"What would you predict after ...\" (sequence of rolls/draws); "
    "\"7 cards with the number '1' ... and 3 cards with the number '2'\"",
    "stimuli.json QID198/QID203 (10TASKS)", "C-17",
    note="sequence-position manipulation; instrument text does not name "
         "the elicited positions, so the manipulation is coded at "
         "experiment level only")
row("abs_relative", "original", "decision", "binary_choice",
    "The same $10 saving is embedded in a cheap ($30 calculator) vs "
    "expensive ($250 jacket) purchase; drive to the other store? yes/no",
    0, 1, 0, 0, 0,
    "\"purchase a calculator for $30 ... on sale for $20\" vs \"purchase a "
    "jacket for $250 ... on sale for $240\"",
    "stimuli.json QID183-184 (10TASKS)", "C-18")

# ---------------- expansion: ML1 (6) ----------------
row("T2KX-ml1_gamblers_fallacy", "ML1", "risk", "numeric_estimate",
    "Dice-roller has thrown two 6s vs three 6s (vs one 3); number of prior "
    "rolls estimated on a 0-10+ bracket",
    0, 0, 0, 1, 1,
    "\"one comes up 3, and two come up 6's\" vs \"all three come up 6's\"; "
    "\"how many times do you think the man had rolled the dice before you "
    "walked by?\"",
    "sample_prompts/T2KX-ml1_gamblers_fallacy unblinded item", "C-19")
row("T2KX-ml1_category_scales", "ML1", "belief", "numeric_estimate",
    "Answer categories for daily TV watching start low (up to half an "
    "hour) vs high (up to 2.5 hours); share above 2.5h is the outcome",
    0, 0, 0, 0, 1,
    "\"A. Up to a half hour ... F. More than two and a half hours\" vs "
    "\"A. Up to two and a half hours ... F. More than four and a half "
    "hours\"",
    "sample_prompts/T2KX-ml1_category_scales unblinded item", "C-20")
row("T2KX-ml1_reciprocity", "ML1", "social", "binary_choice",
    "Order of two reciprocity questions: the US-reporters question comes "
    "first vs after the North-Korea-reporters question; share letting "
    "reporters in",
    0, 0, 1, 0, 0,
    "\"let newspaper reporters from North Korea come in here\" / (order "
    "manipulation) \"Do you think the UK should let newspaper reporters "
    "from the US ...\" - identical wording, position varies",
    "sample_prompts/T2KX-ml1_reciprocity unblinded item + registry.py "
    "human_effect note (us_first vs us_second)", "C-21")
row("T2KX-ml1_allowed_forbidden", "ML1", "social", "binary_choice",
    "Same anti-democracy speech policy phrased as 'allow' vs 'forbid'; "
    "share opposing the speeches",
    0, 0, 1, 0, 1,
    "\"Do you think the UK should allow public speeches against "
    "democracy?\" vs \"... should forbid public speeches against "
    "democracy?\"",
    "sample_prompts/T2KX-ml1_allowed_forbidden unblinded item", "C-22")
row("T2KX-ml1_quote_attribution", "ML1", "social", "rating_scale",
    "An identical quote is attributed to Osama Bin Laden vs George "
    "Washington; agreement rated 1-9",
    0, 0, 1, 0, 0,
    "\"A quote similar to what follows was once spoken by Osama Bin "
    "Laden\" vs \"... by George Washington\"",
    "sample_prompts/T2KX-ml1_quote_attribution unblinded item", "C-23")
row("T2KX-ml1_imagined_contact", "ML1", "decision", "rating_scale",
    "Control: imagine walking outdoors vs imagined contact: imagine "
    "meeting a Muslim stranger; four 1-9 intention items (interaction, "
    "learning, importance, willingness)",
    0, 0, 1, 0, 1,
    "\"take a minute to imagine you are walking in the outdoors\" vs "
    "\"imagine yourself meeting a Muslim stranger for the first time\"",
    "sample_prompts/T2KX-ml1_imagined_contact unblinded item", "C-24")

# ---------------- expansion: ML2 (7) ----------------
row("T2KX-ml2_hauser_s1", "ML2", "social", "binary_choice",
    "Trolley dilemma: harm as a side effect (switch the train) vs harm as "
    "a means (shove the man); permissibility yes/no",
    1, 0, 0, 1, 1,
    "\"Is it morally permissible for Denise to switch the train to the "
    "side track?\" vs \"Is it morally permissible for Frank to shove the "
    "man?\"",
    "sample_prompts/T2KX-ml2_hauser_s1 unblinded item", "C-25")
row("T2KX-ml2_risen_tempt_fate", "ML2", "risk", "rating_scale",
    "You have NOT done the reading (tempting-fate arm) vs HAVE done the "
    "reading and could answer (prepared arm); likelihood the professor "
    "calls on you, 1-10",
    1, 0, 0, 1, 1,
    "\"You have not done the reading and feel confident that you would not "
    "be able to answer\" vs \"You have done the reading and feel confident "
    "that the professor would like your answer\"",
    "sample_prompts/T2KX-ml2_risen_tempt_fate unblinded item", "C-26")
row("T2KX-ml2_schwarz_order", "ML2", "belief", "rating_scale",
    "Position of the general life-satisfaction question in the "
    "questionnaire (before vs after a marriage-satisfaction block); 1-11 "
    "rating", 0, 0, 0, 0, 0,
    "\"How satisfied are you currently with your life-as-a-whole?\" "
    "(identical wording in both versions; manipulation is question ORDER "
    "within the instrument, not item content)",
    "sample_prompts/T2KX-ml2_schwarz_order unblinded item", "C-27",
    note="manipulation invisible in any single item text; coded as "
         "question-order per Schwarz et al. design and registry note")
row("T2KX-ml2_shafir_choose_reject", "ML2", "decision", "binary_choice",
    "Custody case framed as which parent to award custody vs which to "
    "deny custody (same two parent profiles)",
    0, 0, 1, 0, 1,
    "\"To which parent would you award sole custody\" vs \"Which parent "
    "would you deny sole custody\"",
    "sample_prompts/T2KX-ml2_shafir_choose_reject unblinded item", "C-28")
row("T2KX-ml2_miyamoto_correspondence", "ML2", "attribution", "rating_scale",
    "A student's essay argues for vs against capital punishment; the "
    "reader infers the student's TRUE attitude on a 1-15 scale "
    "(correspondence bias: inference tracks the essay despite the "
    "assigned position)",
    0, 0, 1, 0, 1,
    "\"I think that capital punishment should be continued.\" vs \"... "
    "should be abolished.\" ... \"What opinion do you think Steve really "
    "has on the issue\"",
    "sample_prompts/T2KX-ml2_miyamoto_correspondence unblinded item", "C-29")
row("T2KX-ml2_rottenstreich_affect", "ML2", "decision", "binary_choice",
    "Choice between an affect-rich (kiss from movie star) and affect-poor "
    "($50) option at certainty vs at 1% probability",
    1, 1, 0, 1, 0,
    "\"either meet and kiss your favorite movie star or receive $50 in "
    "cash\" vs \"a lottery that offers a 1% chance to meet and kiss ... or "
    "a lottery that offers a 1% chance to receive $50\"",
    "sample_prompts/T2KX-ml2_rottenstreich_affect unblinded item", "C-30")
row("T2KX-ml2_bauer_materialism", "ML2", "social", "rating_scale",
    "A consumer-identity prime (you are Consumer, top water user, in a "
    "shared drought-stricken supply) vs neutral control; trust in the "
    "other parties rated 1-7",
    0, 1, 1, 1, 0,
    "\"You are Consumer. You and three other consumers live in and share "
    "a water supply ... you use about 160 gallons of water per day\" vs "
    "(control version without the consumer prime); \"How much do you "
    "trust the other parties involved to use less water?\"",
    "sample_prompts/T2KX-ml2_bauer_materialism unblinded item", "C-31")

# ---------------- expansion: TESS (4) ----------------
row("T2KX-howard823", "TESS", "attribution", "numeric_estimate",
    "Explaining an outcome: generates reasons why next week's expenses "
    "might be DIFFERENT (atypical/disfluency arm) vs SIMILAR (typical arm) "
    "vs no reasons (control); weekly expense estimate from a $0-$1000+ "
    "bracket", 0, 1, 0, 1, 1,
    "\"type 3 reasons why your expenses for next week might be different "
    "from that of any other week\" vs \"... might be similar to that of "
    "any other week\"; \"Please enter your total estimated expenses (in "
    "dollars) for the next week\"",
    "sample_prompts/T2KX-howard823 unblinded items", "C-32,C-33")
row("T2KX-budescu779", "TESS", "risk", "probability_judgment",
    "IPCC likelihood phrases ('very likely', 'likely', ...) are presented "
    "verbal-only vs alongside their numerical range (translation arm); "
    "best-estimate probability 0-100% in 10-point bins", 0, 0, 0, 1, 1,
    "\"IT IS VERY LIKELY THAT HOT EXTREMES ... WILL CONTINUE TO BECOME "
    "MORE FREQUENT. On a scale from 0 to 100%, please indicate what is "
    "your best estimate of the probability conveyed by this statement.\"",
    "sample_prompts/T2KX-budescu779 unblinded items", "C-34,C-35")
row("T2KX-keusch433", "TESS", "belief", "rating_scale",
    "K-6 distress items answered on an evaluative frequency scale ('All "
    "of the time' ... 'Never') vs a literal day-count scale ('7 days' ... "
    "'0 days'), plus scale order variants", 1, 0, 0, 1, 0,
    "\"how often do you feel nervous? A. All of the time ... E. Never\" vs "
    "\"A. 7 days B. 5 or 6 days ... E. 0 days\"",
    "sample_prompts/T2KX-keusch433 unblinded items", "C-36")
row("T2KX-reedBR32", "TESS", "social", "rating_scale",
    "Doctor review valence (positive vs negative) crossed with decision "
    "risk (risky surgery vs routine checkup); helpfulness and "
    "trustworthiness rated 1-7", 1, 0, 1, 1, 0,
    "\"choosing a doctor for a risky surgery\" vs \"for a routine "
    "checkup\"; \"Dr. Jones is polite, warm and competent.\" vs \"Dr. "
    "Jones is rude, cold, and incompetent.\"",
    "sample_prompts/T2KX-reedBR32 unblinded items", "C-37,C-38")


def coded_rows() -> pd.DataFrame:
    df = pd.DataFrame(E)
    assert len(df) == 31, f"expected 31 experiments, got {len(df)}"
    assert (df.judgment_type != "").all()
    return df


def main() -> None:
    df = coded_rows()
    out = OUT / "EXPERIMENT_CHARACTERISTICS.csv"
    df.to_csv(out, index=False)
    print(f"wrote {out} ({len(df)} rows) - coding frozen BEFORE accuracy join")


if __name__ == "__main__":
    main()
