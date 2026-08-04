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

### srma — 2 flag(s)

| population | agent_id | matched words | bio |
|---|---|---|---|
| pop_c1 | pop_c1_agent_085 | limited, year | I am a 34‑year‑old private‑sector executive who believes that disciplined, conservative principles—such as ... |
| pop_c2 | pop_c2_agent_060 | program, years | I am a seasoned strategist who balances principled compassion with pragmatic solutions, drawing on years of... |

### wealth_tax — 0 flag(s)

None.

### un_veto — 0 flag(s)

None.

### aesthetic_objectivity — 0 flag(s)

None.

### meaning_of_life — 3 flag(s)

| population | agent_id | matched words | bio |
|---|---|---|---|
| pop_a1 | pop_a1_agent_028 | believes, individual | I am a pragmatic leader who believes in sustainable, community-driven solutions that respect fiscal respons... |
| pop_a2 | pop_a2_agent_023 | believes, human | I am a pragmatic idealist who believes in evidence-based solutions and community-driven change, always weig... |
| pop_c2 | pop_c2_agent_023 | believes, individual | I am a young public servant who believes in fiscal responsibility and individual liberty, so I make decisio... |

### regifting — 3 flag(s)

| population | agent_id | matched words | bio |
|---|---|---|---|
| pop_a2 | pop_a2_agent_032 | finding, someone | I am someone who believes in finding common ground and practical solutions, drawing on decades of experienc... |
| pop_a2 | pop_a2_agent_092 | finding, someone | I am someone who believes in finding common ground and practical solutions, which is why I thrive in the no... |
| pop_b1 | pop_b1_agent_098 | finding, someone | I am someone who weighs competing viewpoints carefully before acting, believing that good governance means ... |

### shared_workplace — 0 flag(s)

None.

## Stance flags (LLM-based)

Stance checks were not run. Run them with `python3 scripts/population_reports.py --stance-check`.

## Regenerated personas

No bios were regenerated. Run `python3 scripts/population_reports.py --stance-check --regenerate-stance-flagged` to do so.

## Summary

| screen | flagged personas |
|---|---|
| keyword (>= 2 shared words) | 8 |
| stance (LLM) | not run |
| regenerated | 0 |

