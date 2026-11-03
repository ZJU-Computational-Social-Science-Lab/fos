# INTEGRATION_PROMPTS.md — rendered prompts with the adapted real-respondent pool



One experiment per family, both disclosure arms, persona 0 of the adapted twin2k10r Config A pool (real Twin-2K-500 respondents; persona ids only, never pid/pool_id). Texts are the frozen stimuli of each pipeline, rendered verbatim by the pipeline's own prompt code — nothing was rewritten.



### Twin-2K family — `allais`

#### arm: form1 (blinded)

```
=== SYSTEM ===
You are a survey respondent.

=== USER ===
EMBODY THIS PERSON:
age_bracket: 18-29
gender: Male
education: Some college, no degree
household_income_bracket: $75,000-$100,000
ethnicity: Black
marital_status: Never been married
household_size_bracket: 4

Choose between:

A. One million dollars for sure
B. 89% probability of one million dollars 10% probablity of five miillion dollars 1% probability of nothing

Answer with only the corresponding uppercase letter.
```

#### arm: form1 (unblinded)

```
=== SYSTEM ===
You are a survey respondent.

This question comes from a randomized experiment. Participants were randomly assigned to one of the experimental versions listed below, and each participant saw only the version assigned to them. The version shown to you below was randomly assigned. Because the experimental condition was randomly assigned, do not infer any other differences in the participant or surrounding situation from which version was shown.

The experimental versions are:
Version 1:
Choose between:
Version 2:
Choose between:

=== USER ===
EMBODY THIS PERSON:
age_bracket: 18-29
gender: Male
education: Some college, no degree
household_income_bracket: $75,000-$100,000
ethnicity: Black
marital_status: Never been married
household_size_bracket: 4

Choose between:

A. One million dollars for sure
B. 89% probability of one million dollars 10% probablity of five miillion dollars 1% probability of nothing

Answer with only the corresponding uppercase letter.
```

### ML1 family — `T2KX-ml1_gamblers_fallacy`

#### arm: two_sixes (blinded)

```
=== SYSTEM ===
You are a survey respondent.

=== USER ===
EMBODY THIS PERSON:
age: 18-29
gender: Male
education: Some college, no degree
household_income: $75,000-$100,000
ethnicity: Black
marital_status: Never been married
household_size: 4

Imagine that you are in a casino and you happen to pass a man rolling dice. You observe him roll three dice and one comes up 3, and two come up 6's. Based on your imagined scenario, how many times do you think the man had rolled the dice before you walked by?

A. 0
B. 1
C. 2
D. 3
E. 4
F. 5
G. 6
H. 7
I. 8
J. 9
K. 10 or more

Answer with only the corresponding uppercase letter.
```

#### arm: two_sixes (unblinded)

```
=== SYSTEM ===
You are a survey respondent.

This question comes from a randomized experiment. Participants were randomly assigned to one of the experimental versions listed below, and each participant saw only the version assigned to them. The version shown to you below was randomly assigned. Because the experimental condition was randomly assigned, do not infer any other differences in the participant or surrounding situation from which version was shown.

The experimental versions are:
Version 1:
Imagine that you are in a casino and you happen to pass a man rolling dice. You observe him roll three dice and one comes up 3, and two come up 6's. Based on your imagined scenario, how many times do you think the man had rolled the dice before you walked by?
A. 0
B. 1
C. 2
D. 3
E. 4
F. 5
G. 6
H. 7
I. 8
J. 9
K. 10 or more
Version 2:
Imagine that you are in a casino and you happen to pass a man rolling dice. You observe him roll three dice and all three come up 6's. Based on your imagined scenario, how many times do you think the man had rolled the dice before you walked by?
A. 0
B. 1
C. 2
D. 3
E. 4
F. 5
G. 6
H. 7
I. 8
J. 9
K. 10 or more

=== USER ===
EMBODY THIS PERSON:
age: 18-29
gender: Male
education: Some college, no degree
household_income: $75,000-$100,000
ethnicity: Black
marital_status: Never been married
household_size: 4

Imagine that you are in a casino and you happen to pass a man rolling dice. You observe him roll three dice and one comes up 3, and two come up 6's. Based on your imagined scenario, how many times do you think the man had rolled the dice before you walked by?

A. 0
B. 1
C. 2
D. 3
E. 4
F. 5
G. 6
H. 7
I. 8
J. 9
K. 10 or more

Answer with only the corresponding uppercase letter.
```

### ML2 family — `T2KX-ml2_hauser_s1`

#### arm: side_effect (blinded)

```
=== SYSTEM ===
You are a survey respondent.

=== USER ===
EMBODY THIS PERSON:
age: 18-29
gender: Male
education: Some college, no degree
household_income: $75,000-$100,000
ethnicity: Black
marital_status: Never been married
household_size: 4

Please read the following information carefully. Then, answer the question below.
Denise is a passenger on a train whose driver has just shouted that the train's brakes have failed, and who then fainted of the shock. On the track ahead are five people; the banks are so steep that they will not be able to get off the track in time. The track has a side track leading off to the right, and Denise can turn the train onto it. Unfortunately there is one person on the right hand track. Denise can turn the train, killing the one; or she can refrain from turning the train, letting the five die.

Is it morally permissible for Denise to switch the train to the side track?

A. Yes
B. No

Answer with only the corresponding uppercase letter.
```

#### arm: side_effect (unblinded)

```
=== SYSTEM ===
You are a survey respondent.

This question comes from a randomized experiment. Participants were randomly assigned to one of the experimental versions listed below, and each participant saw only the version assigned to them. The version shown to you below was randomly assigned. Because the experimental condition was randomly assigned, do not infer any other differences in the participant or surrounding situation from which version was shown.

The experimental versions are:
Version 1:
Is it morally permissible for Denise to switch the train to the side track?
A. Yes
B. No
Version 2:
Is it morally permissible for Frank to shove the man?
A. Yes
B. No

=== USER ===
EMBODY THIS PERSON:
age: 18-29
gender: Male
education: Some college, no degree
household_income: $75,000-$100,000
ethnicity: Black
marital_status: Never been married
household_size: 4

Please read the following information carefully. Then, answer the question below.
Denise is a passenger on a train whose driver has just shouted that the train's brakes have failed, and who then fainted of the shock. On the track ahead are five people; the banks are so steep that they will not be able to get off the track in time. The track has a side track leading off to the right, and Denise can turn the train onto it. Unfortunately there is one person on the right hand track. Denise can turn the train, killing the one; or she can refrain from turning the train, letting the five die.

Is it morally permissible for Denise to switch the train to the side track?

A. Yes
B. No

Answer with only the corresponding uppercase letter.
```

### TESS family — `T2KX-howard823`

#### arm: control (blinded)

```
=== SYSTEM ===
You are a survey respondent.

=== USER ===
EMBODY THIS PERSON:
age: 18-29
gender: Male
education: Some college, no degree
household_income: $75,000-$100,000
ethnicity: Black
marital_status: Never been married
household_size: 4

Please take some time to estimate your expenses for the next week. Think about all the expenses you will incur except monthly expenses like rent that happen to be due in the next week.

Please enter your total estimated expenses (in dollars) for the next week. Your estimate should account for all the expenses you will incur except monthly expenses like rent that happen to be due in the next week.

A. $0
B. $1 to $100
C. $1 to $200
D. $1 to $300
E. $1 to $400
F. $1 to $500
G. $1 to $600
H. $1 to $700
I. $1 to $800
J. $1 to $900
K. $1 to $1000
L. more than $1000

Answer with only the corresponding uppercase letter.
```

#### arm: control (unblinded)

```
=== SYSTEM ===
You are a survey respondent.

This question comes from a randomized experiment. Participants were randomly assigned to one of the experimental versions listed below, and each participant saw only the version assigned to them. The version shown to you below was randomly assigned. Because the experimental condition was randomly assigned, do not infer any other differences in the participant or surrounding situation from which version was shown.

The experimental versions are:
Version 1:
Please enter your total estimated expenses (in dollars) for the next week. Your estimate should account for all the expenses you will incur except monthly expenses like rent that happen to be due in the next week.
A. $0
B. $1 to $100
C. $1 to $200
D. $1 to $300
E. $1 to $400
F. $1 to $500
G. $1 to $600
H. $1 to $700
I. $1 to $800
J. $1 to $900
K. $1 to $1000
L. more than $1000
Version 2:
Please take some time to estimate your expenses for the next week. Think about all the expenses you will incur except monthly expenses like rent that happen to be due in the next week.
Now consider why your expenses for next week might be different from that of any other week. In the spaces provided below, please type 3 reasons why your expenses for next week might be different from that of any other week.
Please enter your total estimated expenses (in dollars) for the next week. Your estimate should account for all the expenses you will incur except monthly expenses like rent that happen to be due in the next week.
A. $0
B. $1 to $100
C. $1 to $200
D. $1 to $300
E. $1 to $400
F. $1 to $500
G. $1 to $600
H. $1 to $700
I. $1 to $800
J. $1 to $900
K. $1 to $1000
L. more than $1000
Version 3:
Please take some time to estimate your expenses for the next week. Think about all the expenses you will incur except monthly expenses like rent that happen to be due in the next week.
Now consider why your expenses for next week might be similar to that of any other week. In the spaces provided below, please type 3 reasons why your expenses for next week might be similar to that of any other week.
Please enter your total estimated expenses (in dollars) for the next week. Your estimate should account for all the expenses you will incur except monthly expenses like rent that happen to be due in the next week.
A. $0
B. $1 to $100
C. $1 to $200
D. $1 to $300
E. $1 to $400
F. $1 to $500
G. $1 to $600
H. $1 to $700
I. $1 to $800
J. $1 to $900
K. $1 to $1000
L. more than $1000

=== USER ===
EMBODY THIS PERSON:
age: 18-29
gender: Male
education: Some college, no degree
household_income: $75,000-$100,000
ethnicity: Black
marital_status: Never been married
household_size: 4

Please take some time to estimate your expenses for the next week. Think about all the expenses you will incur except monthly expenses like rent that happen to be due in the next week.

Please enter your total estimated expenses (in dollars) for the next week. Your estimate should account for all the expenses you will incur except monthly expenses like rent that happen to be due in the next week.

A. $0
B. $1 to $100
C. $1 to $200
D. $1 to $300
E. $1 to $400
F. $1 to $500
G. $1 to $600
H. $1 to $700
I. $1 to $800
J. $1 to $900
K. $1 to $1000
L. more than $1000

Answer with only the corresponding uppercase letter.
```
