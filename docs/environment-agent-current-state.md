<!--
This note explains what the environment agent means in the product today.

Each section does one simple job:
- the opening line states the current reality clearly,
- the middle sections list what exists and what is still manual,
- the last sections explain where data sources fit and what is still missing.
-->

# Environment Agent Current State

Environment agent currently means host suggestions plus event injection support. It is not autonomous per-round world generation yet.

## What exists today

- Hosts can send manual broadcasts and manual environment notices from the host panel.
- External events are stored in the database as event records.
- Data source polling can fetch outside data and save those fetched items as event records.
- The environment suggestion path can read simulation context and propose host actions.
- Experiment-style scenes support next-round host message injection, so applied events can shape the following round.

## What is still manual or host-driven

- A host still decides whether to apply a suggestion or a saved external event.
- A host still decides when to inject an event and which node to inject it into.
- A host still sets up and maintains external data sources.
- The system does not yet run a separate autonomous environment actor after every round by default.

## Where external data sources fit

- External data sources produce candidate event records.
- Those records can be reviewed and then applied to a simulation.
- Polling alone does not change a running world automatically.

## Current limitations

- There is no always-on per-round environment actor that independently writes world events every round.
- Suggestion quality is still rule-based and grounded in available runtime history, so it is better than before but not full world modeling.
- Scene coverage is uneven: experiment scenes expose richer round history than older simulator scenes.
