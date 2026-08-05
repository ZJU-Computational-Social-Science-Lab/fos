# Topic-Leakage Screen (Phase 3, Step 2)

Screened 600 personas against the 7 proposal statements.

## Method

1. **Keyword flags:** each bio is split into content words (lowercased, punctuation stripped, expanded stopword list removed) and compared with the content words of each proposal statement. A persona is flagged when it shares **2 or more** distinctive content words with a proposal.
2. **Stance flags:** an LLM (configurable model) reviews each keyword-flagged bio against the proposal and confirms whether the bio reveals a stance toward the topic.
3. **Regeneration:** stance-flagged bios are regenerated in place — same archetype cell, same voting model, same generating model — and each regeneration is recorded below.

## Proposal content words (stopwords removed)

- **srma**: 1, acting, aerosol, authority, authorize, conditional, continuous, emergency, empowered, environment, halt, injection, international, limited, monitoring, mtso, nations, oversee, program, programme, stratospheric, ten, time, united, year, years
- **wealth_tax**: 2, 50, administered, annual, contingent, coordinated, debt, debtor, facility, global, imf, implement, individual, international, majority, million, net, pooled, proceeds, ratification, relief, signatory, south, sovereign, states, tax, usd
- **un_veto**: 60, abolished, applicable, binding, council, five, held, member, members, permanent, power, replaced, represented, rule, security, states, supermajority, un, veto, voting
- **aesthetic_objectivity**: aesthetic, artwork, beauty, better, genuinely, individual, matter, objective, others, purely, taste
- **meaning_of_life**: absent, being, believes, depend, feels, human, individual, life, meaning, objective, subjective
- **regifting**: acceptable, being, dishonesty, else, ethically, ever, finding, form, gift, giver, giving, original, someone, toward, unwanted
- **shared_workplace**: allowing, employees, full, organizations, physical, remote, require, shared, together

## Keyword flags (>= 2 shared distinctive content words)

### srma — 5 flag(s)

| population | agent_id | matched words | bio |
|---|---|---|---|
| pop_b1 | pop_b1_agent_045 | time, years | I am a dedicated community advocate and full-time carer who approaches every decision through a lens of soc... |
| pop_c1 | pop_c1_agent_045 | time, year | I am a 30‑to‑49‑year‑old, progressive‑thinking person who, though not currently in paid work, balances my t... |
| pop_c1 | pop_c1_agent_057 | time, year | I am a 35‑year‑old former civil‑engineer who, now living as a full‑time caregiver, approaches every challen... |
| pop_c1 | pop_c1_agent_086 | time, year | I am a 52‑year‑old former educator who, after retiring, balances my time between volunteering in the commun... |
| pop_c2 | pop_c2_agent_045 | time, year | I am a 32‑year‑old progressive activist who, as a full‑time caregiver, channels my compassion and forward‑t... |

### wealth_tax — 0 flag(s)

None.

### un_veto — 0 flag(s)

None.

### aesthetic_objectivity — 0 flag(s)

None.

### meaning_of_life — 10 flag(s)

| population | agent_id | matched words | bio |
|---|---|---|---|
| pop_a1 | pop_a1_agent_004 | being, believes | I am a progressive public servant in my twenties who believes that every policy decision should be measured... |
| pop_a1 | pop_a1_agent_097 | individual, life | I am a seasoned individual who values tradition and stability, and I approach every decision with the wisdo... |
| pop_a2 | pop_a2_agent_011 | being, individual | I am a progressive-minded individual currently not in paid work, and I make decisions by prioritizing commu... |
| pop_a2 | pop_a2_agent_035 | believes, human | I am a public servant who believes that systemic change is possible through inclusive policy-making and com... |
| pop_a2 | pop_a2_agent_044 | being, individual | I am a lifelong learner who values community and equity, and I make decisions by prioritizing collective we... |
| pop_a2 | pop_a2_agent_077 | believes, life | I am a lifelong learner who believes that every stage of life offers a chance to contribute, so I channel m... |
| pop_b1 | pop_b1_agent_070 | being, believes | I am a seasoned public servant who believes that decades of experience have taught me to prioritize equity ... |
| pop_c1 | pop_c1_agent_027 | believes, individual | I am a dedicated public servant who believes in the power of strong leadership and fiscal responsibility to... |
| pop_c1 | pop_c1_agent_069 | being, life | I am a seasoned public servant who uses my life experience and progressive values to guide fair, evidence‑b... |
| pop_c2 | pop_c2_agent_056 | individual, life | I am a thoughtful, middle‑aged individual who weighs options carefully, drawing on a balanced view of polit... |

### regifting — 3 flag(s)

| population | agent_id | matched words | bio |
|---|---|---|---|
| pop_a2 | pop_a2_agent_015 | being, someone | I am someone who values practical solutions and community well-being, often weighing diverse perspectives t... |
| pop_a2 | pop_a2_agent_078 | being, someone | I am someone who has lived through enough to know that progress comes from lifting everyone up, and I use m... |
| pop_b2 | pop_b2_agent_057 | finding, someone | I am someone who weighs multiple viewpoints carefully before forming opinions, finding purpose outside trad... |

### shared_workplace — 0 flag(s)

None.

## Stance flags (LLM-based)

No personas were flagged.

## Regenerated personas

No bios were regenerated. Run `python3 scripts/population_reports.py --stance-check --regenerate-stance-flagged` to do so.

## Summary

| screen | flagged personas |
|---|---|
| keyword (>= 2 shared words) | 18 |
| stance (LLM) | 0 |
| regenerated | 0 |

