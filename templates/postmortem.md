# Postmortem: <title>

> Blameless: we look for system and process causes, not people to blame.

| | |
|---|---|
| **Date** | YYYY-MM-DD |
| **Authors** | |
| **Status** | Draft / In review / Final |
| **Severity** | SEV1 / SEV2 / SEV3 |
| **Duration** | detected HH:MM → mitigated HH:MM → resolved HH:MM (TZ) |
| **Error budget consumed** | <x>% of 30-day budget for <SLO> |

## Summary

<3–4 sentences: what happened, impact, how it was fixed>

## Impact

- Users / tenants affected:
- Requests failed or slow:
- Data loss: yes / no

## Timeline

| Time | Event |
|---|---|
| | Trigger (deploy, traffic spike, AZ event…) |
| | Alert fired (which one?) |
| | Acknowledged |
| | Mitigation applied |
| | Resolved |

## Root cause(s)

<Use "5 whys" or a causal tree. Usually more than one contributing factor.>

## Detection

- Did an SLO alert catch it? How long after impact started?
- Would a better alert have caught it sooner?

## What went well / what didn't / where we got lucky

## Action items

| Action | Type (prevent / detect / mitigate) | Owner | Ticket | Due |
|---|---|---|---|---|
| | | | | |
