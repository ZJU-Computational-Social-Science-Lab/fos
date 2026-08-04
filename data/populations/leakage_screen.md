# Topic-Leakage Screen (Phase 3, Step 2)

Screened 600 personas against the 7 proposal statements.

## Method

1. **Keyword overlap:** each bio is split into content words (lowercased, punctuation stripped, English stopwords removed) and compared with the content words of each proposal statement.
2. **Direct-reference flags:** each bio is checked against a topic keyword group per proposal (art/aesthetics, gifts, wealth/tax, meaning/purpose, workplace/office, veto/UN, SRMA).
3. Flagged personas are **reported only** — none were regenerated or altered.

## Proposal content words (stopwords removed)

- **srma**: 1, acting, aerosol, authority, authorize, conditional, continuous, emergency, empowered, environment, halt, injection, international, limited, monitoring, mtso, nations, oversee, program, programme, stratospheric, ten, time, united, year, years
- **wealth_tax**: 2, 50, administered, annual, assets, contingent, coordinated, debt, debtor, facility, global, imf, implement, individual, international, majority, million, net, pooled, proceeds, ratification, relief, signatory, south, sovereign, states, tax, usd, wealth
- **un_veto**: 60, abolished, applicable, binding, council, five, held, member, members, permanent, power, replaced, represented, rule, security, states, supermajority, un, veto, voting
- **aesthetic_objectivity**: aesthetic, artwork, beauty, better, genuinely, individual, matter, objective, others, purely, taste, value, works
- **meaning_of_life**: absent, being, believes, depend, feels, human, individual, life, meaning, objective, subjective
- **regifting**: acceptable, being, dishonesty, else, ethically, ever, finding, form, gift, giver, giving, original, someone, toward, unwanted
- **shared_workplace**: allowing, employees, full, organizations, physical, remote, require, shared, together, work, workplace

## Flagged personas (direct topic references)

### srma — 0 flag(s)

None.

### wealth_tax — 3 flag(s)

| population | agent_id | matched keywords | bio |
|---|---|---|---|
| pop_c1 | pop_c1_agent_086 | assets | I am a pragmatic, risk‑averse professional who values fiscal responsibility and personal liberty, using dat... |
| pop_c1 | pop_c1_agent_098 | assets | I am a seasoned private‑sector strategist who values disciplined, market‑driven solutions and a conservativ... |
| pop_c2 | pop_c2_agent_056 | wealth | I am a seasoned advocate who balances a wealth of life experience with a steadfast belief in progressive va... |

### un_veto — 0 flag(s)

None.

### aesthetic_objectivity — 0 flag(s)

None.

### meaning_of_life — 8 flag(s)

| population | agent_id | matched keywords | bio |
|---|---|---|---|
| pop_a1 | pop_a1_agent_083 | meaningful | I am a pragmatic problem-solver who values tradition and efficiency, applying conservative fiscal principle... |
| pop_a1 | pop_a1_agent_096 | meaningful | I am a young public servant driven by a belief that inclusive policies and community input are the best too... |
| pop_b1 | pop_b1_agent_034 | meaningful | I am driven by a deep belief in equity and social justice, approaching every challenge with empathy, data-i... |
| pop_b1 | pop_b1_agent_047 | meaningful | I am driven by a deep belief in equity and social justice, channeling my idealism into strategic nonprofit ... |
| pop_b2 | pop_b2_agent_002 | meaningful | I am a pragmatic idealist who weighs competing perspectives to find balanced solutions that can actually mo... |
| pop_b2 | pop_b2_agent_005 | purpose | I am a purpose-driven professional in the private sector who leverages market innovation to advance progres... |
| pop_b2 | pop_b2_agent_065 | meaningful | I am a pragmatist who weighs both sides of every issue before committing to action, trusting that private e... |
| pop_b2 | pop_b2_agent_073 | meaningful | I am driven by a deep commitment to equity and social progress, approaching every policy decision through a... |

### regifting — 0 flag(s)

None.

### shared_workplace — 41 flag(s)

| population | agent_id | matched keywords | bio |
|---|---|---|---|
| pop_a1 | pop_a1_agent_006 | work | I am a pragmatic problem-solver who values collaboration and evidence-based solutions, always seeking to ba... |
| pop_a1 | pop_a1_agent_015 | work | I am a pragmatic problem-solver who values practical solutions over ideology, balancing innovation with sta... |
| pop_a1 | pop_a1_agent_017 | work | I am someone who values practical solutions and community impact, often balancing different perspectives to... |
| pop_a1 | pop_a1_agent_029 | work | I am driven by a deep belief in collective action and equity, so I approach every challenge by asking how m... |
| pop_a1 | pop_a1_agent_049 | work | I am a seasoned professional who values tradition, self-reliance, and practical experience, and I make deci... |
| pop_a1 | pop_a1_agent_051 | work | I am a young conservative who believes in limited government and personal responsibility, and I apply these... |
| pop_a1 | pop_a1_agent_055 | work | I am a pragmatic public servant who values tradition and fiscal responsibility, prioritizing stability and ... |
| pop_a1 | pop_a1_agent_076 | work | I am a seasoned professional who values stability, hard work, and personal responsibility, and I make decis... |
| pop_a2 | pop_a2_agent_003 | work | I am a young conservative who channels my passion for fiscal responsibility and community values into pract... |
| pop_a2 | pop_a2_agent_006 | work | I am a seasoned professional who values stability, hard work, and practical solutions, drawing on decades o... |
| pop_a2 | pop_a2_agent_027 | work | I am driven by a deep belief in systemic change, so I approach my nonprofit work by centering community voi... |
| pop_a2 | pop_a2_agent_028 | work | I am a pragmatic problem-solver who values balanced solutions and practical outcomes in my work. |
| pop_a2 | pop_a2_agent_036 | work | I am someone who values balanced, practical solutions and believes in making a tangible difference by bridg... |
| pop_a2 | pop_a2_agent_059 | work | I am a forward-thinking professional who values collaboration and innovation, always seeking to drive posit... |
| pop_a2 | pop_a2_agent_076 | work | I am a pragmatic problem-solver who values practical solutions and collaboration, balancing innovation with... |
| pop_a2 | pop_a2_agent_085 | work | I am a pragmatic problem-solver who values collaboration and evidence-based solutions, often seeking common... |
| pop_b1 | pop_b1_agent_034 | work | I am driven by a deep belief in equity and social justice, approaching every challenge with empathy, data-i... |
| pop_b1 | pop_b1_agent_043 | works | I am a pragmatic problem-solver who weighs competing perspectives carefully before committing to solutions ... |
| pop_b1 | pop_b1_agent_047 | work | I am driven by a deep belief in equity and social justice, channeling my idealism into strategic nonprofit ... |
| pop_b1 | pop_b1_agent_051 | work | I am a pragmatist who weighs multiple perspectives before committing to solutions, channeling my idealism i... |
| pop_b1 | pop_b1_agent_054 | work | I am driven by a lifelong commitment to equity and social justice, approaching every decision through the l... |
| pop_b1 | pop_b1_agent_067 | work | I am driven by a deep belief that systemic change happens from the ground up, so I channel my energy into g... |
| pop_b1 | pop_b1_agent_071 | work | I am a pragmatic problem-solver who weighs competing perspectives carefully before acting, valuing evidence... |
| pop_b1 | pop_b1_agent_090 | works | I am a seasoned business leader who relies on decades of hard-won experience and time-tested principles to ... |
| pop_b1 | pop_b1_agent_092 | workplace | I am a pragmatic problem-solver who weighs both sides of every issue before taking action, trusting that in... |
| pop_b1 | pop_b1_agent_098 | work | I am someone who weighs competing viewpoints carefully before acting, believing that good governance means ... |
| pop_b2 | pop_b2_agent_002 | work | I am a pragmatic idealist who weighs competing perspectives to find balanced solutions that can actually mo... |
| pop_b2 | pop_b2_agent_011 | work | I am a pragmatic professional who weighs both sides of every issue before making data-driven decisions that... |
| pop_b2 | pop_b2_agent_021 | work | I am driven by a deep belief in social equity, channeling my strategic thinking and collaborative spirit in... |
| pop_b2 | pop_b2_agent_025 | work | I am a results-driven professional who values free-market solutions, personal responsibility, and building ... |
| pop_b2 | pop_b2_agent_032 | work | I am driven by self-reliance and free-market principles, trusting that hard work, personal responsibility, ... |
| pop_b2 | pop_b2_agent_036 | workplace | I am a private-sector professional who drives decisions through data and innovation while championing progr... |
| pop_b2 | pop_b2_agent_052 | workplace | I am a mid-career professional who leverages my private sector experience to drive innovation while champio... |
| pop_b2 | pop_b2_agent_064 | work | I am a seasoned professional who weighs both sides of every issue carefully, drawing on decades of private-... |
| pop_b2 | pop_b2_agent_089 | work | I am driven by a deep belief that communities solve problems better than government does, so I channel my i... |
| pop_b2 | pop_b2_agent_097 | work | I am a seasoned advocate who draws on decades of lived experience to challenge systemic inequities, approac... |
| pop_b2 | pop_b2_agent_098 | work | I am a pragmatic young professional who weighs both sides of every issue before committing to data-driven s... |
| pop_c1 | pop_c1_agent_080 | work | I am a seasoned private‑sector strategist who blends a cautious, value‑driven mindset with a practical eye ... |
| pop_c2 | pop_c2_agent_063 | workplace | I am a 24-year-old private sector professional who balances a pragmatic, risk‑averse mindset with an open‑t... |
| pop_c2 | pop_c2_agent_070 | work | I am a seasoned advocate who trusts collaborative dialogue and evidence-driven policy to guide my nonprofit... |
| pop_c2 | pop_c2_agent_087 | work | I am a young, conservative private-sector professional who values decisive action, efficient problem‑solvin... |

### Summary counts

| proposal | flagged personas | populations affected |
|---|---|---|
| srma | 0 | - |
| wealth_tax | 3 | pop_c1, pop_c2 |
| un_veto | 0 | - |
| aesthetic_objectivity | 0 | - |
| meaning_of_life | 8 | pop_a1, pop_b1, pop_b2 |
| regifting | 0 | - |
| shared_workplace | 41 | pop_a1, pop_a2, pop_b1, pop_b2, pop_c1, pop_c2 |

## Keyword overlap with proposal statements (content words)

| proposal | personas with >=1 overlap | max overlap words |
|---|---|---|
| srma | 48 | 2 |
| wealth_tax | 20 | 1 |
| un_veto | 18 | 1 |
| aesthetic_objectivity | 31 | 2 |
| meaning_of_life | 107 | 2 |
| regifting | 34 | 2 |
| shared_workplace | 44 | 1 |

