# Verbatim arm texts for the 20 EXPANSION experiments (C-19..C-38).
# Same conventions as arm_texts_original.py. Expansion texts come from the
# verbatim rendered prompts in expansion/pipeline/sample_prompts/T2KX-*/
# (user prompt item text; identical system/persona wrappers excluded).
# Where the manipulation lives in preceding context (question order:
# C-21, C-27, C-36) or an added reference table (C-34/C-35) or an added
# reasoning prompt (C-32/C-33), that context is included in the arm text.

_BAUER_NARR = (
    "You are {who}. You and three other {who_s} live in and share a water supply for a "
    "particular area. Typically, you use the most amount of water with your daily activities "
    "(e.g. washing clothes and dishes, flushing the toilet, watering the lawn, bathing, etc). "
    "That is, you use about 160 gallons of water per day. {who} B uses about 140 gallons a "
    "day, {who} C uses about 120 gallons a day, and {who} D uses about 100 gallons a day."
)
_BAUER_ITEM = (
    "3) How much do you trust the other parties involved to use less water?\n"
    "A. Not at all 1\nB. 2\nC. 3\nD. 4\nE. 5\nF. 6\nG. Very much 7"
)

_BUDESCU_INSTR = (
    "You will be presented with sentences from reports published by the Inter Governmental "
    "Panel on Climate Change (IPCC). Each sentence includes phrases that represent the "
    "likelihood of occurrence of some event. The goal of this study is to see how people "
    "interpret these sentences. We ask you to give your best estimate of the probability "
    "conveyed by each sentence. In other words, we are asking for your best understanding of "
    "the probabilities that the authors intended to communicate. There is no right or wrong "
    "answer, so we encourage you to give honest estimates of the information represented by "
    "each sentence.\n"
    "Probabilities range from 0% to 100%.  The response of 0% indicates that an event is "
    "impossible. On the other hand, a response of 100% indicates that an event is certain to "
    "happen.  The response scale provides a continuum for you to provide probabilities "
    "between 0% and 100%."
)
_BUDESCU_TABLE = (
    "The IPCC has developed guidelines for the interpretation of these probability terms. "
    "They are included here for your convenience.  Consult this table as often as you wish.\n"
    "|Phrase              |Likelihood of       |\n"
    "|                    |Occurrence/Outcome  |\n"
    "|Virtually certain   |> 99%               |\n"
    "|Very likely         |> 90%               |\n"
    "|Likely              |> 66%               |\n"
    "|About as likely as  |33% to 66%          |\n"
    "|not                 |                    |\n"
    "|Unlikely            |< 33%               |\n"
    "|Very unlikely       |< 10%               |\n"
    "|Exceptionally       |< 1%                |\n"
    "|Unlikely            |                    |"
)
_BUDESCU_VERY_LIKELY = (
    "IT IS VERY LIKELY THAT HOT EXTREMES, HEAT WAVES, AND HEAVY PRECIPITATION EVENTS WILL "
    "CONTINUE TO BECOME MORE FREQUENT.\n"
    "On a scale from 0 to 100%, please indicate what is your best estimate of the probability "
    "conveyed by this statement."
)
_BUDESCU_VERY_LIKELY_VN = (
    "IT IS VERY LIKELY (GREATER THAN 90%) THAT HOT EXTREMES, HEAT WAVES, AND HEAVY "
    "PRECIPITATION EVENTS WILL CONTINUE TO BECOME MORE FREQUENT.\n"
    "On a scale from 0 to 100%, please indicate what is your best estimate of the probability "
    "conveyed by this statement."
)
_BUDESCU_VERY_UNLIKELY = (
    "IT IS VERY UNLIKELY THAT CLIMATE CHANGES OF AT LEAST THE SEVEN CENTURIES PRIOR TO 1950 "
    "WERE DUE TO VARIABILITY GENERATED WITHIN THE CLIMATE SYSTEM ALONE.\n"
    "On a scale from 0 to 100%, please indicate what is your best estimate of the probability "
    "conveyed by this statement."
)
_BUDESCU_VERY_UNLIKELY_VN = (
    "IT IS VERY UNLIKELY (LESS THAN 10%) THAT CLIMATE CHANGES OF AT LEAST THE SEVEN CENTURIES "
    "PRIOR TO 1950 WERE DUE TO VARIABILITY GENERATED WITHIN THE CLIMATE SYSTEM ALONE.\n"
    "On a scale from 0 to 100%, please indicate what is your best estimate of the probability "
    "conveyed by this statement."
)
_BUDESCU_OPTS = (
    "A. 0%\nB. 10%\nC. 20%\nD. 30%\nE. 40%\nF. 50%\nG. 60%\nH. 70%\nI. 80%\nJ. 90%\nK. 100%"
)

_HOWARD_OPTS = (
    "A. $0\nB. $1 to $100\nC. $1 to $200\nD. $1 to $300\nE. $1 to $400\nF. $1 to $500\n"
    "G. $1 to $600\nH. $1 to $700\nI. $1 to $800\nJ. $1 to $900\nK. $1 to $1000\n"
    "L. more than $1000"
)
_HOWARD_QUESTION = (
    "Please enter your total estimated expenses (in dollars) for the next week. Your estimate "
    "should account for all the expenses you will incur except monthly expenses like rent that "
    "happen to be due in the next week."
)
_HOWARD_CONTROL = _HOWARD_QUESTION + "\n" + _HOWARD_OPTS
_HOWARD_ATYPICAL = (
    "Please take some time to estimate your expenses for the next week. Think about all the "
    "expenses you will incur except monthly expenses like rent that happen to be due in the "
    "next week.\n"
    "Now consider why your expenses for next week might be different from that of any other "
    "week. In the spaces provided below, please type 3 reasons why your expenses for next week "
    "might be different from that of any other week.\n" + _HOWARD_QUESTION + "\n" + _HOWARD_OPTS
)
_HOWARD_TYPICAL = (
    "Please take some time to estimate your expenses for the next week. Think about all the "
    "expenses you will incur except monthly expenses like rent that happen to be due in the "
    "next week.\n"
    "Now consider why your expenses for next week might be similar to that of any other week. "
    "In the spaces provided below, please type 3 reasons why your expenses for next week might "
    "be similar to that of any other week.\n" + _HOWARD_QUESTION + "\n" + _HOWARD_OPTS
)

# Keusch433: the six K6 items; vague response labels are identical in both
# arms, only the ORDER of the items differs (high-to-low vs low-to-high).
_K6_ITEMS = [
    "During an average week, how often do you feel so sad that nothing could cheer you up?",
    "During an average week, how often do you feel nervous?",
    "During an average week, how often do you feel restless or fidgety?",
    "During an average week, how often do you feel hopeless?",
    "During an average week, how often do you feel that everything was an effort?",
    "During an average week, how often do you feel worthless?",
]
_K6_LEAD = (
    "Now we are going to ask you some questions about feelings you may have experienced during "
    "an average week."
)
_K6_VAGUE_OPTS = "A. All of the time\nB. Most of the time\nC. Some of the time\nD. A little of the time\nE. Never"


def _k6_arm(item_order):
    """Build a Keusch433 arm text from an ordered list of K6 item indices."""
    blocks = [_K6_LEAD] + [item + "\n" + _K6_VAGUE_OPTS for item in (_K6_ITEMS[i] for i in item_order)]
    return "\n".join(blocks)


_REED_VIGNETTE = (
    "Imagine that you are choosing a doctor for a {context}. Below is a patient's review of a "
    "doctor that you are considering, Dr. Jones. Please read the review carefully and answer "
    "the questions below.\n"
    "\"Dr. Jones is {attributes} the facilities are {facilities}, the office staff is {staff}, "
    "and all of the nurses have {nurses}. Scheduling an appointment is very {scheduling}, and "
    "the costs are {costs}. I will {loyalty} go back to this doctor!\""
)
_REED_QUESTIONS = (
    "How helpful is this review?\n"
    "A. Not at all helpful 1\nB. 2\nC. 3\nD. 4\nE. 5\nF. 6\nG. Very helpful 7\n"
    "How trustworthy is the person who wrote this review?\n"
    "A. Not at all trustworthy 1\nB. 2\nC. 3\nD. 4\nE. 5\nF. 6\nG. Very trustworthy 7"
)
_REED_POS = _REED_VIGNETTE.format(
    context="risky surgery",
    attributes="polite, warm and competent.",
    facilities="clean", staff="professional", nurses="good attitudes",
    scheduling="easy", costs="low", loyalty="always",
) + "\n" + _REED_QUESTIONS
_REED_NEG = _REED_VIGNETTE.format(
    context="risky surgery",
    attributes="rude, cold, and incompetent.",
    facilities="dirty", staff="unprofessional", nurses="bad attitudes",
    scheduling="difficult", costs="high", loyalty="never",
) + "\n" + _REED_QUESTIONS

CONTRAST_ARMS_EXPANSION = {
    "C-19": {
        "experiment_id": "T2KX-ml1_gamblers_fallacy",
        "control_label": "two_sixes",
        "treatment_label": "three_sixes",
        "control": (
            "Imagine that you are in a casino and you happen to pass a man rolling dice. You "
            "observe him roll three dice and one comes up 3, and two come up 6's. Based on your "
            "imagined scenario, how many times do you think the man had rolled the dice before "
            "you walked by?\n"
            "A. 0\nB. 1\nC. 2\nD. 3\nE. 4\nF. 5\nG. 6\nH. 7\nI. 8\nJ. 9\nK. 10 or more"
        ),
        "treatment": (
            "Imagine that you are in a casino and you happen to pass a man rolling dice. You "
            "observe him roll three dice and all three come up 6's. Based on your imagined "
            "scenario, how many times do you think the man had rolled the dice before you walked "
            "by?\n"
            "A. 0\nB. 1\nC. 2\nD. 3\nE. 4\nF. 5\nG. 6\nH. 7\nI. 8\nJ. 9\nK. 10 or more"
        ),
    },
    "C-20": {
        "experiment_id": "T2KX-ml1_category_scales",
        "control_label": "low_scale",
        "treatment_label": "high_scale",
        "control": (
            "How much television do you watch per day?\n"
            "A. Up to a half hour\nB. Half an hour to an hour\nC. One to one and a half hours\n"
            "D. One and a half to two hours\nE. Two to two and a half hours\n"
            "F. More than two and a half hours"
        ),
        "treatment": (
            "How much television do you watch per day?\n"
            "A. Up to two and a half hours\nB. Two and a half to three hours\n"
            "C. Three to three and a half hours\nD. Three and a half to four hours\n"
            "E. Four to four and a half hours\nF. More than four and a half hours"
        ),
    },
    "C-21": {
        "experiment_id": "T2KX-ml1_reciprocity",
        "control_label": "us_first",
        "treatment_label": "us_second",
        "control": (
            "Do you think the UK should let newspaper reporters from North Korea come in here "
            "and send back to their papers the news as they see it?\n"
            "A. Yes\nB. No"
        ),
        "treatment": (
            "Do you think North Korea should let UK newspaper reporters come in and send back to "
            "the UK the news as they see it?\n"
            "Do you think the UK should let newspaper reporters from North Korea come in here "
            "and send back to their papers the news as they see it?\n"
            "A. Yes\nB. No"
        ),
    },
    "C-22": {
        "experiment_id": "T2KX-ml1_allowed_forbidden",
        "control_label": "allow_wording",
        "treatment_label": "forbid_wording",
        "control": (
            "Do you think the UK should allow public speeches against democracy?\n"
            "A. Yes\nB. No"
        ),
        "treatment": (
            "Do you think the UK should forbid public speeches against democracy?\n"
            "A. Yes\nB. No"
        ),
    },
    "C-23": {
        "experiment_id": "T2KX-ml1_quote_attribution",
        "control_label": "disliked_source",
        "treatment_label": "liked_source",
        "control": (
            "A quote similar to what follows was once spoken by Osama Bin Laden: \"I have sworn "
            "to only live free, even if I find bitter the taste of death.\" How much do you "
            "agree with this quote?\n"
            "A. 1 - strongly agree\nB. 2\nC. 3\nD. 4\nE. 5 - neither agree nor disagree\n"
            "F. 6\nG. 7\nH. 8\nI. 9 - strongly disagree"
        ),
        "treatment": (
            "A quote similar to what follows was once spoken by George Washington: \"I have "
            "sworn to only live free, even if I find bitter the taste of death.\" How much do "
            "you agree with this quote?\n"
            "A. 1 - strongly agree\nB. 2\nC. 3\nD. 4\nE. 5 - neither agree nor disagree\n"
            "F. 6\nG. 7\nH. 8\nI. 9 - strongly disagree"
        ),
    },
    "C-24": {
        "experiment_id": "T2KX-ml1_imagined_contact",
        "control_label": "control_walk",
        "treatment_label": "imagined_contact",
        "control": (
            "I would like you to take a minute to imagine you are walking in the outdoors. Try "
            "to imagine aspects of the scene around you (e.g., is it a beach, a forest, are "
            "there trees, hills, what's on the horizon).\n"
            "How much do you intend to interact with Muslims in the future?\n"
            "A. 1 - not at all\nB. 2\nC. 3\nD. 4\nE. 5\nF. 6\nG. 7\nH. 8\nI. 9 - very much"
        ),
        "treatment": (
            "I would like you to take a minute to imagine yourself meeting a Muslim stranger "
            "for the first time. During the conversation imagine you find out some interesting "
            "and unexpected things about the stranger.\n"
            "How much do you intend to interact with Muslims in the future?\n"
            "A. 1 - not at all\nB. 2\nC. 3\nD. 4\nE. 5\nF. 6\nG. 7\nH. 8\nI. 9 - very much"
        ),
    },
    "C-25": {
        "experiment_id": "T2KX-ml2_hauser_s1",
        "control_label": "side_effect",
        "treatment_label": "greater_good",
        "control": "Is it morally permissible for Denise to switch the train to the side track?\nA. Yes\nB. No",
        "treatment": "Is it morally permissible for Frank to shove the man?\nA. Yes\nB. No",
    },
    "C-26": {
        "experiment_id": "T2KX-ml2_risen_tempt_fate",
        "control_label": "unprepared",
        "treatment_label": "prepared",
        "control": (
            "Imagine that you are in a large lecture with a few hundred students and you are "
            "sitting in the middle section, a little more than half-way back in the room. The "
            "professor asks a question about the readings, but no one raises his or her hand to "
            "answer. You have not done the reading and feel confident that you would not be able "
            "to answer the question. The class sits in silence for two minutes before the "
            "professor explains that if no one volunteers, he will choose someone.\n"
            "How likely do you believe it is that the professor will call on you?\n"
            "A. 1 - Not at all likely\nB. 2\nC. 3\nD. 4\nE. 5\nF. 6\nG. 7\nH. 8\nI. 9\n"
            "J. 10 - Extremely likely"
        ),
        "treatment": (
            "Imagine that you are in a large lecture with a few hundred students and you are "
            "sitting in the middle section, a little more than half-way back in the room. The "
            "professor asks a question about the readings, but no one raises his or her hand to "
            "answer. You have done the reading and feel confident that the professor would like "
            "your answer, but prefer not to volunteer answers in large classes. The class sits "
            "in silence for two minutes before the professor explains that if no one volunteers, "
            "he will choose someone.\n"
            "How likely do you believe it is that the professor will call on you?\n"
            "A. 1 - Not at all likely\nB. 2\nC. 3\nD. 4\nE. 5\nF. 6\nG. 7\nH. 8\nI. 9\n"
            "J. 10 - Extremely likely"
        ),
    },
    "C-27": {
        "experiment_id": "T2KX-ml2_schwarz_order",
        "control_label": "life_first",
        "treatment_label": "life_second",
        "control": (
            "How satisfied are you currently with your life-as-a-whole?\n"
            "A. very dissatisfied 1\nB. 2\nC. 3\nD. 4\nE. 5\nF. 6\nG. 7\nH. 8\nI. 9\nJ. 10\n"
            "K. very satisfied 11"
        ),
        "treatment": (
            "Please think about your relationship to your partner (spouse or date). How "
            "satisfied are you currently with your relationship?\n"
            "How satisfied are you currently with your life-as-a-whole?\n"
            "A. very dissatisfied 1\nB. 2\nC. 3\nD. 4\nE. 5\nF. 6\nG. 7\nH. 8\nI. 9\nJ. 10\n"
            "K. very satisfied 11"
        ),
    },
    "C-28": {
        "experiment_id": "T2KX-ml2_shafir_choose_reject",
        "control_label": "award_framing",
        "treatment_label": "deny_framing",
        "control": (
            "Imagine that you serve on the jury of an only-child sole-custody case following a "
            "relatively messy divorce. The facts of the case are complicated by ambiguous "
            "economic, social, and emotional considerations, and you decide to base your "
            "decision entirely on the following few observations.\n"
            "Parent A\naverage income\naverage health\naverage working hours\nreasonable rapport "
            "with the child\nrelatively stable social life\n"
            "Parent B\nabove-average income\nvery close relationship with the child\nextremely "
            "active social life\nlots of work-related travel\nminor health problems\n"
            "To which parent would you award sole custody of the child?\nA. Parent A\nB. Parent B"
        ),
        "treatment": (
            "Imagine that you serve on the jury of an only-child sole-custody case following a "
            "relatively messy divorce. The facts of the case are complicated by ambiguous "
            "economic, social, and emotional considerations, and you decide to base your "
            "decision entirely on the following few observations.\n"
            "Parent A\naverage income\naverage health\naverage working hours\nreasonable rapport "
            "with the child\nrelatively stable social life\n"
            "Parent B\nabove-average income\nvery close relationship with the child\nextremely "
            "active social life\nlots of work-related travel\nminor health problems\n"
            "Which parent would you deny sole custody of the child?\nA. Parent A\nB. Parent B"
        ),
    },
    "C-29": {
        "experiment_id": "T2KX-ml2_miyamoto_correspondence",
        "control_label": "essay_pro_death",
        "treatment_label": "essay_pro_choice",
        "control": (
            "In this survey, you are to read an essay written by an undergraduate student, "
            "Steve. Please read the essay carefully.\n"
            "I think that capital punishment should be continued. \n"
            "When we take the viewpoint of the victim of a vicious crime, we realize that there "
            "are many cases in which justice can only be served with the criminal's death. In "
            "addition, the existence of capital punishment may deter vicious crimes.\n"
            "We should realize that capital punishment is a necessary institution for "
            "maintaining our society.\n"
            "What opinion do you think Steve really has on the issue of capital punishment? "
            "Select the point on the following rating scale that you think best represents "
            "Steve's true attitude on this issue.\n"
            "A. Against capital punishment 1\nB. 2\nC. 3\nD. 4\nE. 5\nF. 6\nG. 7\nH. Neither 8\n"
            "I. 9\nJ. 10\nK. 11\nL. 12\nM. 13\nN. 14\nO. Supports capital punishment 15"
        ),
        "treatment": (
            "In this survey, you are to read an essay written by an undergraduate student, "
            "Steve. Please read the essay carefully.\n"
            "I think that capital punishment should be abolished. \n"
            "When we take the viewpoint of the victim of a vicious crime, we realize that there "
            "are many cases in which justice can only be served with the criminal's death. In "
            "addition, the existence of capital punishment may deter vicious crimes.\n"
            "We should realize that capital punishment is a necessary institution for "
            "maintaining our society.\n"
            "What opinion do you think Steve really has on the issue of capital punishment? "
            "Select the point on the following rating scale that you think best represents "
            "Steve's true attitude on this issue.\n"
            "A. Against capital punishment 1\nB. 2\nC. 3\nD. 4\nE. 5\nF. 6\nG. 7\nH. Neither 8\n"
            "I. 9\nJ. 10\nK. 11\nL. 12\nM. 13\nN. 14\nO. Supports capital punishment 15"
        ),
    },
    "C-30": {
        "experiment_id": "T2KX-ml2_rottenstreich_affect",
        "control_label": "certainty",
        "treatment_label": "one_percent",
        "control": (
            "Imagine that you have the opportunity to either meet and kiss your favorite movie "
            "star or receive $50 in cash . \n"
            "Which would you prefer? (select one option below)\n"
            "A. Meet and kiss my favorite movie star.\nB. Receive $50 in cash."
        ),
        "treatment": (
            "Imagine that you have the opportunity to take part either in a lottery that offers "
            "a 1% chance to meet and kiss your favorite movie star or a lottery that offers a 1% "
            "chance to receive $50 in cash . \n"
            "In which lottery would you prefer to take part? (select one option below)\n"
            "A. 1% chance to meet and kiss my favorite movie star.\n"
            "B. 1% chance to receive $50 in cash."
        ),
    },
    "C-31": {
        "experiment_id": "T2KX-ml2_bauer_materialism",
        "control_label": "consumer_prime",
        "treatment_label": "individual_prime",
        "control": _BAUER_NARR.format(who="Consumer", who_s="consumers") + "\n" + _BAUER_ITEM,
        "treatment": _BAUER_NARR.format(who="Individual", who_s="individuals") + "\n" + _BAUER_ITEM,
    },
    "C-32": {
        "experiment_id": "T2KX-howard823",
        "control_label": "control",
        "treatment_label": "atypical",
        "control": _HOWARD_CONTROL,
        "treatment": _HOWARD_ATYPICAL,
    },
    "C-33": {
        "experiment_id": "T2KX-howard823",
        "control_label": "control",
        "treatment_label": "typical",
        "control": _HOWARD_CONTROL,
        "treatment": _HOWARD_TYPICAL,
    },
    "C-34": {
        "experiment_id": "T2KX-budescu779",
        "control_label": "control",
        "treatment_label": "verbal_numerical",
        "control": _BUDESCU_INSTR + "\n" + _BUDESCU_VERY_LIKELY + "\n" + _BUDESCU_OPTS,
        "treatment": (
            _BUDESCU_INSTR + "\n" + _BUDESCU_TABLE + "\n" + _BUDESCU_VERY_LIKELY_VN + "\n"
            + _BUDESCU_OPTS
        ),
    },
    "C-35": {
        "experiment_id": "T2KX-budescu779",
        "control_label": "control",
        "treatment_label": "verbal_numerical",
        "control": _BUDESCU_INSTR + "\n" + _BUDESCU_VERY_UNLIKELY + "\n" + _BUDESCU_OPTS,
        "treatment": (
            _BUDESCU_INSTR + "\n" + _BUDESCU_TABLE + "\n" + _BUDESCU_VERY_UNLIKELY_VN + "\n"
            + _BUDESCU_OPTS
        ),
    },
    "C-36": {
        "experiment_id": "T2KX-keusch433",
        "control_label": "high_to_low_vague",
        "treatment_label": "low_to_high_vague",
        "control": _k6_arm([5, 4, 3, 2, 1, 0]),
        "treatment": _k6_arm([0, 1, 2, 3, 4, 5]),
    },
    "C-37": {
        "experiment_id": "T2KX-reedBR32",
        "control_label": "risky_positive+routine_positive",
        "treatment_label": "risky_negative+routine_negative",
        "control": _REED_POS,
        "treatment": _REED_NEG,
    },
    "C-38": {
        "experiment_id": "T2KX-reedBR32",
        "control_label": "risky_positive+routine_positive",
        "treatment_label": "risky_negative+routine_negative",
        "control": _REED_POS,
        "treatment": _REED_NEG,
    },
}
