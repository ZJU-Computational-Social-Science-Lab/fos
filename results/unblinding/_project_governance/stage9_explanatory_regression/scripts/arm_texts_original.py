# Verbatim arm texts for the 18 ORIGINAL experiments (C-01..C-18).
# Each contrast maps to the two compared arm texts exactly as the survey
# instrument presented them (item text + response options). Identical
# generic instructions shared by both arms are kept (they are part of the
# stimulus); the model-only wrapper ("Answer with only the corresponding
# uppercase letter.") is excluded because it is identical across arms.
# Sources: 6TASK/10TASK stimuli.json as quoted in
# _project_governance/stage8_shared_failures/SCENARIO_TEXT.md.

CONTRAST_ARMS_ORIGINAL = {
    "C-01": {
        "experiment_id": "disease",
        "control_label": "gain",
        "treatment_label": "loss",
        "control": (
            "Imagine that the U.S. is preparing for the outbreak of an unusual disease, "
            "which is expected to kill 600 people. Two alternative programs to combat the "
            "disease have been proposed. Assume that the exact scientific estimate of the "
            "consequences of the programs are as follows: If Program A is adopted, 200 people "
            "will be saved. If Program B is adopted, there is 1/3 probability that 600 people "
            "will be saved, and 2/3 probability that no people will be saved. Which of the two "
            "programs would you favor?\n"
            "A. I strongly favor program A\nB. I favor program A\nC. I slightly favor program A\n"
            "D. I slightly favor program B\nE. I favor program B\nF. I strongly favor program B"
        ),
        "treatment": (
            "Imagine that the U.S. is preparing for the outbreak of an unusual disease, "
            "which is expected to kill 600 people. Two alternative programs to combat the "
            "disease have been proposed. Assume that the exact scientific estimate of the "
            "consequences of the programs are as follows: If Program A is adopted, 400 people "
            "will die. If Program B is adopted, there is 1/3 probability that nobody people "
            "will die, and 2/3 probability that 600 people be die. Which of the two "
            "programs would you favor?\n"
            "A. I strongly favor program A\nB. I favor program A\nC. I slightly favor program A\n"
            "D. I slightly favor program B\nE. I favor program B\nF. I strongly favor program B"
        ),
    },
    "C-02": {
        "experiment_id": "less_is_more",
        "control_label": "A",
        "treatment_label": "B",
        "control": (
            "Please rate your level of disagreement or agreement with the following statement: "
            "\"I would find a game that had a 7/36 chance of winning $9 and a 29/36 chance of "
            "winning nothing extremely attractive.\"\n"
            "A. Disagree strongly\nB. Disagree a little\nC. Neither agree nor disagree\n"
            "D. Agree a little\nE. Agree strongly"
        ),
        "treatment": (
            "Please rate your level of disagreement or agreement with the following statement: "
            "\"I would find a game that had a 7/36 chance of winning $9 and a 29/36 chance of "
            "losing $0.05 extremely attractive.\"\n"
            "A. Disagree strongly\nB. Disagree a little\nC. Neither agree nor disagree\n"
            "D. Agree a little\nE. Agree strongly"
        ),
    },
    "C-03": {
        "experiment_id": "less_is_more",
        "control_label": "A",
        "treatment_label": "C",
        "control": (
            "Please rate your level of disagreement or agreement with the following statement: "
            "\"I would find a game that had a 7/36 chance of winning $9 and a 29/36 chance of "
            "winning nothing extremely attractive.\"\n"
            "A. Disagree strongly\nB. Disagree a little\nC. Neither agree nor disagree\n"
            "D. Agree a little\nE. Agree strongly"
        ),
        "treatment": (
            "Please rate your level of disagreement or agreement with the following statement: "
            "\"I would find a game that had a 7/36 chance of winning $9 and a 29/36 chance of "
            "losing $0.25 extremely attractive.\"\n"
            "A. Disagree strongly\nB. Disagree a little\nC. Neither agree nor disagree\n"
            "D. Agree a little\nE. Agree strongly"
        ),
    },
    "C-04": {
        "experiment_id": "fire_extinguisher",
        "control_label": "all",
        "treatment_label": "98pct",
        "control": (
            "Imagine that highway safety experts have determined that a substantial number of "
            "people are at risk of dying in a type of automobile fire. A requirement that every "
            "car have a built-in fire extinguisher (estimated cost, $300) would save the 150 "
            "people who would otherwise die every year in this type of automobile fire. Rate the "
            "following statement about yourself: I would be supportive of this requirement.\n"
            "A. Disagree strongly\nB. Disagree a little\nC. Neither agree nor disagree\n"
            "D. Agree a little\nE. Agree strongly"
        ),
        "treatment": (
            "Imagine that highway safety experts have determined that a substantial number of "
            "people are at risk of dying in a type of automobile fire. A requirement that every "
            "car have a built-in fire extinguisher (estimated cost, $300) would save 98% of the "
            "150 people who would otherwise die every year in this type of automobile fire. Rate "
            "the following statement about yourself: I would be supportive of this requirement.\n"
            "A. Disagree strongly\nB. Disagree a little\nC. Neither agree nor disagree\n"
            "D. Agree a little\nE. Agree strongly"
        ),
    },
    "C-05": {
        "experiment_id": "fire_extinguisher",
        "control_label": "all",
        "treatment_label": "95pct",
        "control": (
            "Imagine that highway safety experts have determined that a substantial number of "
            "people are at risk of dying in a type of automobile fire. A requirement that every "
            "car have a built-in fire extinguisher (estimated cost, $300) would save the 150 "
            "people who would otherwise die every year in this type of automobile fire. Rate the "
            "following statement about yourself: I would be supportive of this requirement.\n"
            "A. Disagree strongly\nB. Disagree a little\nC. Neither agree nor disagree\n"
            "D. Agree a little\nE. Agree strongly"
        ),
        "treatment": (
            "Imagine that highway safety experts have determined that a substantial number of "
            "people are at risk of dying in a type of automobile fire. A requirement that every "
            "car have a built-in fire extinguisher (estimated cost, $300) would save 95% of the "
            "150 people who would otherwise die every year in this type of automobile fire. Rate "
            "the following statement about yourself: I would be supportive of this requirement.\n"
            "A. Disagree strongly\nB. Disagree a little\nC. Neither agree nor disagree\n"
            "D. Agree a little\nE. Agree strongly"
        ),
    },
    "C-06": {
        "experiment_id": "seatbelt",
        "control_label": "all",
        "treatment_label": "98pct",
        "control": (
            "You have recently graduated from university, obtained a good job, and are buying a "
            "new car. A newly designed seatbelt has just become available that would save the "
            "lives of the 500 drivers a year who are involved in a type of head-on-collision. "
            "(Approximately half of these fatalities involve drivers who were not at fault.) The "
            "newly designed seatbelt is not yet standard on most car models. However, it is "
            "available as a $500 option for the car model that you are ordering. How likely is it "
            "that you would order your new car with this optional seatbelt?\n"
            "A. very unlikely\nB. unlikely\nC. somewhat unlikely\nD. somewhat likely\n"
            "E. likely\nF. very likely"
        ),
        "treatment": (
            "You have recently graduated from university, obtained a good job, and are buying a "
            "new car. A newly designed seatbelt has just become available that would save the "
            "lives of 98% of the 500 drivers a year who are involved in a type of "
            "head-on-collision. (Approximately half of these fatalities involve drivers who were "
            "not at fault.) The newly designed seatbelt is not yet standard on most car models. "
            "However, it is available as a $500 option for the car model that you are ordering. "
            "How likely is it that you would order your new car with this optional seatbelt?\n"
            "A. very unlikely\nB. unlikely\nC. somewhat unlikely\nD. somewhat likely\n"
            "E. likely\nF. very likely"
        ),
    },
    "C-07": {
        "experiment_id": "seatbelt",
        "control_label": "all",
        "treatment_label": "95pct",
        "control": (
            "You have recently graduated from university, obtained a good job, and are buying a "
            "new car. A newly designed seatbelt has just become available that would save the "
            "lives of the 500 drivers a year who are involved in a type of head-on-collision. "
            "(Approximately half of these fatalities involve drivers who were not at fault.) The "
            "newly designed seatbelt is not yet standard on most car models. However, it is "
            "available as a $500 option for the car model that you are ordering. How likely is it "
            "that you would order your new car with this optional seatbelt?\n"
            "A. very unlikely\nB. unlikely\nC. somewhat unlikely\nD. somewhat likely\n"
            "E. likely\nF. very likely"
        ),
        "treatment": (
            "You have recently graduated from university, obtained a good job, and are buying a "
            "new car. A newly designed seatbelt has just become available that would save the "
            "lives of 95% of the 500 drivers a year who are involved in a type of "
            "head-on-collision. (Approximately half of these fatalities involve drivers who were "
            "not at fault.) The newly designed seatbelt is not yet standard on most car models. "
            "However, it is available as a $500 option for the car model that you are ordering. "
            "How likely is it that you would order your new car with this optional seatbelt?\n"
            "A. very unlikely\nB. unlikely\nC. somewhat unlikely\nD. somewhat likely\n"
            "E. likely\nF. very likely"
        ),
    },
    "C-08": {
        "experiment_id": "sunk_cost",
        "control_label": "no_card",
        "treatment_label": "card",
        "control": (
            "Imagine that Coffee Connection sells coffee for $1.50 per cup. Java Coffee, a "
            "competitor, sells coffee for just $2.00 per cup. Although the Coffee Connection "
            "store is ten minutes away by car, Java Coffee is only about 1/2 block from your "
            "apartment. Assuming that you only buy coffee from these two places and that you like "
            "the coffee sold in both places the same, how many of your next 20 coffee purchases "
            "would be from Java Coffee? Enter a number between 0 and 20."
        ),
        "treatment": (
            "Imagine that you just paid $50 for a Coffee Connection discount card that allows you "
            "to buy coffee for 50% off the regular price of $3.00 (i.e., you pay $1.50). Soon "
            "after you purchased the Coffee Connection discount card, Java Coffee, a competitor, "
            "opened a new store that sells coffee for just $2.00 per cup. Although the Coffee "
            "Connection store is ten minutes away by car, Java Coffee is only about 1/2 block "
            "from your apartment. Assuming that you only buy coffee from these two places and "
            "that you like the coffee sold in both places the same, how many of your next 20 "
            "coffee purchases would be from Java Coffee? Enter a number between 0 and 20."
        ),
    },
    "C-09": {
        "experiment_id": "wta_wtp",
        "control_label": "wtp_certainty",
        "treatment_label": "wta_certainty",
        "control": (
            "Imagine that when you went to the movies last week, you were inadvertently exposed "
            "to a rare and fatal virus. The possibility of actually contracting the disease is 1 "
            "in 1,000, but once you have the illness there is no known cure. On the other hand, "
            "you can, readily and now, be given an injection that stops the development of the "
            "illness. Unfortunately, these injections are only available in very small quantities "
            "and are sold to the highest bidder. What is the highest price you would be prepared "
            "to pay for such an injection? [You can get a long-term, low-interest loan if needed.]\n"
            "A. $10\nB. $100\nC. $1,000\nD. $10,000\nE. $50,000\nF. $100,000\nG. $250,000\n"
            "H. $500,000\nI. $1,000,000\nJ. $5,000,000 or more"
        ),
        "treatment": (
            "Imagine that a group of research scientists in the School of Medicine are running a "
            "laboratory experiment on a vaccine for a rare and fatal virus. The possibility of "
            "actually contracting the disease from the vaccine is 1 in 1,000, but once you have "
            "the disease there is no known cure. The scientists are seeking volunteers to test "
            "the vaccine on. What is the lowest amount that you would have to be paid before you "
            "would take part in this experiment?\n"
            "A. $10\nB. $100\nC. $1,000\nD. $10,000\nE. $50,000\nF. $100,000\nG. $250,000\n"
            "H. $500,000\nI. $1,000,000\nJ. $5,000,000 or more"
        ),
    },
    "C-10": {
        "experiment_id": "wta_wtp",
        "control_label": "wtp_certainty",
        "treatment_label": "wtp_noncertainty",
        "control": (
            "Imagine that when you went to the movies last week, you were inadvertently exposed "
            "to a rare and fatal virus. The possibility of actually contracting the disease is 1 "
            "in 1,000, but once you have the illness there is no known cure. On the other hand, "
            "you can, readily and now, be given an injection that stops the development of the "
            "illness. Unfortunately, these injections are only available in very small quantities "
            "and are sold to the highest bidder. What is the highest price you would be prepared "
            "to pay for such an injection? [You can get a long-term, low-interest loan if needed.]\n"
            "A. $10\nB. $100\nC. $1,000\nD. $10,000\nE. $50,000\nF. $100,000\nG. $250,000\n"
            "H. $500,000\nI. $1,000,000\nJ. $5,000,000 or more"
        ),
        "treatment": (
            "Imagine that when you went to the movies last week, you were inadvertently exposed "
            "to a rare and fatal virus. The possibility of actually contracting the disease is 4 "
            "in 1,000, but once you have the illness there is no known cure. On the other hand, "
            "you can, readily and now, be given an injection that reduces the possibility of "
            "contracting the disease to 3 in 1,000. Unfortunately, these injections are only "
            "available in very small quantities and are sold to the highest bidder. What is the "
            "highest price you would be prepared to pay for such an injection?\n"
            "A. $10\nB. $100\nC. $1,000\nD. $10,000\nE. $50,000\nF. $100,000\nG. $250,000\n"
            "H. $500,000\nI. $1,000,000\nJ. $5,000,000 or more"
        ),
    },
    "C-11": {
        "experiment_id": "allais",
        "control_label": "form1",
        "treatment_label": "form2",
        "control": (
            "Choose between:\n"
            "A. One million dollars for sure\n"
            "B. 89% probability of one million dollars 10% probablity of five miillion dollars "
            "1% probability of nothing"
        ),
        "treatment": (
            "Choose between:\n"
            "A. 11% probability of one million dollars 89% probability of nothing\n"
            "B. 10% probablity of five miillion dollars 90% probability of nothing"
        ),
    },
    "C-12": {
        "experiment_id": "linda",
        "control_label": "no_conjunction",
        "treatment_label": "conjunction",
        "control": (
            "Linda is 31 years old, single, outspoken, and very bright. She majored in "
            "philosophy. As a student, she was deeply concerned with issues of discrimination "
            "and social justice, and also participated in anti-nuclear demonstrations. Please "
            "complete the statements below.\n"
            "It is ___ that Linda is a teacher in an elementary school\n"
            "It is ___ that Linda works in a bookstore and takes Yoga classes\n"
            "It is ___ that Linda is a bank teller\n"
            "Scale: Extremely improbable / Very improbable / Somewhat probable / Moderately "
            "probable / Very probable / Extremely probable"
        ),
        "treatment": (
            "Linda is 31 years old, single, outspoken, and very bright. She majored in "
            "philosophy. As a student, she was deeply concerned with issues of discrimination "
            "and social justice, and also participated in anti-nuclear demonstrations. Please "
            "complete the statements below.\n"
            "It is ___ that Linda is a teacher in an elementary school\n"
            "It is ___ that Linda works in a bookstore and takes Yoga classes\n"
            "It is ___ that Linda is a bank teller and is active in the feminist movement\n"
            "Scale: Extremely improbable / Very improbable / Somewhat probable / Moderately "
            "probable / Very probable / Extremely probable"
        ),
    },
    "C-13": {
        "experiment_id": "anchoring_redwood",
        "control_label": "low",
        "treatment_label": "high",
        "control": (
            "Is the tallest redwood tree in the world more or less than 85 feet tall?\n"
            "A. more\nB. less\n"
            "How tall do you think the tallest redwood tree in the world is? Enter a number of feet."
        ),
        "treatment": (
            "Is the tallest redwood tree in the world more or less than 1000 feet tall?\n"
            "A. more\nB. less\n"
            "How tall do you think the tallest redwood tree in the world is? Enter a number of feet."
        ),
    },
    "C-14": {
        "experiment_id": "anchoring_african",
        "control_label": "low",
        "treatment_label": "high",
        "control": (
            "Do you think there are more or fewer than 12 African countries in the United "
            "Nations?\nA. more\nB. fewer\n"
            "How many African countries do you think are in the United Nations?"
        ),
        "treatment": (
            "Do you think there are more or fewer than 65 African countries in the United "
            "Nations?\nA. more\nB. fewer\n"
            "How many African countries do you think are in the United Nations?"
        ),
    },
    "C-15": {
        "experiment_id": "outcome_bias",
        "control_label": "failure",
        "treatment_label": "success",
        "control": (
            "A 55-year-old man had a heart condition. He had to stop working because of chest "
            "pain. He enjoyed his work and did not want to stop. His pain also interfered with "
            "other things, such as travel and recreation. A type of bypass operation would "
            "relieve his pain and increase his life expectancy from age 65 to age 75. However, "
            "2% of the people who have this operation die from the operation itself. His "
            "physician decided to go ahead with the operation. The operation did not succeed and "
            "the patient died. Evaluate the physician's decision to go ahead with the operation.\n"
            "A. Incorrect, a very bad decision\nB. Incorrect, all things considered\n"
            "C. Incorrect, but not unreasonable\nD. The decision and its opposite are equally good\n"
            "E. Correct, but the opposite would be reasonable too\n"
            "F. Correct, all things considered\nG. Clearly correct, an excellent decision"
        ),
        "treatment": (
            "A 55-year-old man had a heart condition. He had to stop working because of chest "
            "pain. He enjoyed his work and did not want to stop. His pain also interfered with "
            "other things, such as travel and recreation. A type of bypass operation would "
            "relieve his pain and increase his life expectancy from age 65 to age 70. However, "
            "8% of the people who have this operation die from the operation itself. His "
            "physician decided to go ahead with the operation. The operation succeeded. Evaluate "
            "the physician's decision to go ahead with the operation.\n"
            "A. Incorrect, a very bad decision\nB. Incorrect, all things considered\n"
            "C. Incorrect, but not unreasonable\nD. The decision and its opposite are equally good\n"
            "E. Correct, but the opposite would be reasonable too\n"
            "F. Correct, all things considered\nG. Clearly correct, an excellent decision"
        ),
    },
    "C-16": {
        "experiment_id": "myside",
        "control_label": "ford",
        "treatment_label": "german",
        "control": (
            "According to a comprehensive study by the U.S. Department of Transportation, Ford "
            "Explorers are 8 times more likely than a typical family car to kill occupants of "
            "another car in a crash. The Department of Transportation in Germany is considering "
            "recommending a ban on the sale of the Ford Explorer in Germany. Do you think that "
            "Germany should ban the sale of the Ford Explorer?\n"
            "A. definitely no\nB. no\nC. probably no\nD. probably yes\nE. yes\nF. definitely yes"
        ),
        "treatment": (
            "According to a comprehensive study by the U.S. Department of Transportation, a "
            "particular German car is 8 times more likely than a typical family car to kill "
            "occupants of another car in a crash. The U.S. Department of Transportation is "
            "considering recommending a ban on the sale of this German car. Do you think that the "
            "U.S. should ban the sale of the German car?\n"
            "A. definitely no\nB. no\nC. probably no\nD. probably yes\nE. yes\nF. definitely yes"
        ),
    },
    "C-17": {
        "experiment_id": "prob_matching",
        "control_label": "problem1",
        "treatment_label": "problem2",
        "control": (
            "Consider the following hypothetical situation: A deck with 10 cards is randomly "
            "shuffled 10 separate times. The 10 cards are composed of 7 cards with the number "
            "\u201c1\u201d on the down side and 3 cards with the number \u201c2\u201d on the down "
            "side. Each time the 10 cards are reshuffled, your task is to predict the number on "
            "the down side of the top card. Imagine that you will receive $100 for each downside "
            "number you correctly predict, and that you want to earn as much money as possible. "
            "What would you predict after shuffle #1?\n"
            "A. 1\nB. 2"
        ),
        "treatment": (
            "Consider the following situation: A die with 4 red faces and 2 green faces will be "
            "rolled 6 times. Before each roll you will be asked to predict which color (red or "
            "green) will show up once the die is rolled. Which color is most likely to show up "
            "after roll #1?\n"
            "A. red\nB. green"
        ),
    },
    "C-18": {
        "experiment_id": "abs_relative",
        "control_label": "calculator",
        "treatment_label": "jacket",
        "control": (
            "Imagine that you go to purchase a calculator for $30. The calculator salesperson "
            "informs you that the calculator you wish to buy is on sale for $20 at the other "
            "branch of the store which is ten minutes away by car. Would you drive to the other "
            "store?\nA. Yes\nB. No"
        ),
        "treatment": (
            "Imagine that you go to purchase a jacket for $250. The jacket salesperson informs "
            "you that the jacket you wish to buy is on sale for $240 at the other branch of the "
            "store which is ten minutes away by car. Would you drive to the other store?\n"
            "A. Yes\nB. No"
        ),
    },
}
