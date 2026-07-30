# ZooVision Contributor Guide

## Project State

This repository begins with an architecture brief for ZooVision, an overnight animal-welfare monitoring system. Treat the brief as the source of truth for product intent. It proposes a future implementation; do not describe planned providers, models, endpoints, or workflows as working until they have been implemented and verified.

Read `README.md` and `compass_artifact_wf-8953096d-23a5-5284-a231-458dcee08d71_text_markdown.md` before changing the product architecture.

## Product Invariants

- ZooVision is a welfare-support tool, not a medical device.
- It may observe, log, retrieve context, notify staff, and record human outcomes. It must not diagnose, recommend medication, dispense treatment, manipulate an enclosure, or expose actuator tools to an agent.
- Severity is determined only by deterministic, tested Python logic. Language models may extract, normalize, enrich, or phrase evidence, but they must not assign or override severity.
- Every non-`NONE` event must preserve the triggering rule in `rule_fired`, its source evidence, and the stable event identifier needed for idempotent writes.
- Only night-shift events can page staff. Day-shift observations refine context and baselines but do not alert.
- Baselines are per animal and behavior, calculated from prior daytime-only shifts. Night events must not update their own night's baseline.
- Human review is mandatory before real paging: support shadow mode and do not enable alert delivery automatically for a new baseline.
- When the system lacks evidence, record uncertainty or a data gap rather than inventing a conclusion.

## Implementation Direction

The intended pipeline has clear ownership boundaries:

```text
segment video -> ingest and analyze -> normalize observations
              -> enrich from graph -> deterministic triage
              -> idempotent graph write -> alert or baseline update
              -> scheduled morning report
```

- **Video analysis:** use structured responses for timestamped observations. Validate the schema at the boundary before data reaches the rule engine.
- **LLM use:** constrain outputs with schemas; supply deterministic baseline values as input rather than asking a model to calculate or interpret urgency.
- **Triage:** keep ordering explicit because the policy is first-match-wins. Unit-test the threshold boundaries and the selected `rule_fired` value.
- **Neo4j:** use idempotent `MERGE` operations keyed by stable IDs. Read-only agent access must stay read-only; application-owned writers are the only graph mutation path.
- **Vector data:** determine embedding dimensions at ingest rather than hard-coding a historical provider value.
- **Alerting:** alerts should contain the evidence clip, factual explanation, and a constrained action such as `welfare_check`, `verify_water`, or `observe`. Acknowledgement and escalation state must be persisted.
- **Reporting:** include every monitored animal, including animals with no notable events, and explicitly surface camera/data gaps.

## Data and Privacy

- Treat camera footage, animal care records, staff identities, contact details, and outcomes as sensitive operational data.
- Keep raw video, extracted clips, and analysis artifacts in separate paths with explicit retention policies. Proposed defaults are 7 days for raw chunks, 30 days for raw analysis JSON, and 90 days for alert clips; make these configuration, not hidden constants.
- Do not commit footage, credentials, API keys, production care records, personal contact information, or real webhook payloads.
- Use environment variables or a managed secret store for provider credentials. Add sanitized examples only.
- Log enough metadata for auditability without leaking source frames, care notes, or secrets into ordinary application logs.

## Evidence and Provider Boundaries

- Animal behavior recognition and non-speech animal-audio classification are not verified capabilities of the proposed video providers. Keep them behind validation/shadow-mode gates and report measured results honestly.
- Provider model names, quotas, embedding dimensions, timestamp accuracy, price, and free-tier limits can change. Confirm them through current official documentation and integration tests before relying on them.
- If a provider call fails or structured output is invalid, retry only within a bounded, observable policy. Record reduced coverage or a `DataGap`; never silently convert a failed analysis into a normal result.
- Preserve timestamp provenance: observations returned relative to a video chunk must be converted using the chunk's wall-clock start time and retain the source chunk reference.

## Testing Expectations

Add focused tests with any production code:

- unit tests for each triage rule, first-match precedence, cold-start behavior, and day/night routing;
- tests that prove daytime-only baseline updates and correct z-score handling;
- schema-validation tests for malformed or incomplete provider responses;
- idempotency tests for repeat ingestion and graph writes;
- integration tests using fixtures or recorded sanitized responses, not live provider calls by default;
- end-to-end coverage that verifies an alert contains a clip reference, `rule_fired`, and acknowledgement state.

Use labeled animal-video fixtures only when licensing and retention permit it. Keep live provider checks opt-in, clearly labeled, and separated from deterministic test suites.

## Change Discipline

- Make narrowly scoped changes that preserve the deterministic triage and human-review boundaries.
- Prefer explicit domain types and structured schemas over free-form dictionaries or text parsing.
- Document behavior-affecting threshold or retention changes in the README and tests.
- Do not add a model-powered fallback that can invent severity, diagnosis, or treatment instructions.
- If a change affects a staff-facing alert, validate wording for factuality, uncertainty, and the no-diagnosis constraint.
