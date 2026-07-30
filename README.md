# ZooVision

ZooVision is a night time animal monitoring system for zoo and sanctuary teams. It turns recorded enclosure video into timestamped behavior observations, compares those observations with each animal's own daytime baseline, and sends staff evidence-backed welfare-check prompts when deterministic rules find something unusual.

> **Project status:** architecture and product design. This repository currently contains the design brief; no production service or model integration has been implemented yet.

## The Product

ZooVision helps a keeper answer a practical overnight question: *which animals need a check, and why?* It is designed around an individual animal baseline rather than a generic anomaly score.

The intended keeper flow is:

1. Cameras produce closed, roughly 15-minute enclosure-video segments.
2. Video analysis extracts structured, timestamped observations.
3. A deterministic rule engine compares observations with prior **daytime-only** behavior baselines.
4. Meaningful night-time deviations create an alert with a short evidence clip.
5. The next shift receives a briefing that lists every animal, data gaps, notable events, and recorded outcomes.

For example, an unusual 14-minute pacing event can become a `MODERATE` welfare-check prompt if it exceeds that animal's normal pattern. The alert must explain the observed evidence and link to the clip; it must not diagnose an animal or prescribe treatment.

## Design Principles

- **Individual baselines:** calculate behavior frequency and duration per animal, using a rolling 7-14 day daytime-only history. Never feed night events into that night's baseline.
- **Deterministic urgency:** models extract and organize evidence, while Python rules alone assign severity and preserve a `rule_fired` audit trail.
- **Human decision-making:** the product observes, logs, and notifies. It never diagnoses, dispenses medication, controls equipment, or takes physical action.
- **Evidence first:** retain event timestamps, source clips, confidence, baseline deltas, care context, and outcomes so staff can inspect every recommendation.
- **Shadow before paging:** new baselines must run in staff-reviewed shadow mode before real alert delivery is enabled.
- **Explicit uncertainty:** animal behavior and non-speech animal-audio recognition are unverified extensions of the proposed video models and require empirical validation before trust is claimed.

## Intended Architecture

| Layer | Intended responsibility |
| --- | --- |
| Camera segmentation | Convert RTSP/ONVIF camera feeds into timestamped MP4 segments. |
| TwelveLabs Pegasus 1.5 | Produce schema-constrained behavior observations per video chunk. |
| TwelveLabs Marengo 3.0 | Create video embeddings and retrieve visually similar clips from an individual animal's history. |
| Strands Agents | Orchestrate the fixed, auditable day/night pipeline. |
| OpenAI GPT-5.6 Terra | Merge structured evidence with graph context and phrase staff-facing messages; never decide severity. |
| Deterministic Python | Compute baseline deltas, apply triage rules, and enforce escalation behavior. |
| Neo4j Aura | Store the animal context graph, event history, baselines, outcomes, and vector-searchable clips. |
| S3-compatible object storage | Retain raw segments, analysis JSON, and extracted alert clips under explicit lifecycle policies. |

The planned orchestration is:

```text
camera segment -> ingest -> structured observations + embeddings
               -> context enrichment -> deterministic triage
               -> graph write -> night alert or baseline update
               -> scheduled morning briefing
```

## Triage Contract

The rule engine is deliberately separate from model output. The initial policy is first-match-wins:

| Signal | Severity |
| --- | --- |
| Fighting or escape attempt | `CRITICAL` |
| Vomiting | `HIGH` |
| Pacing for more than 20 minutes with no water contact for 6 hours | `HIGH` |
| Pacing for more than 10 minutes | `MODERATE` |
| Inactivity more than two standard deviations above baseline | `MODERATE` |
| Baseline delta greater than 2.5 | `MODERATE` |
| Water bowl tipped | `LOW` |
| Anything else | `NONE` |

Only non-`NONE` events occurring during the configured night shift can trigger a page. Day-shift events are retained for staff context and baseline refinement.

## Data Model

The planned Neo4j graph centers on `Animal`, `Enclosure`, `Shift`, `Event`, `BaselineProfile`, `CareRecord`, `Alert`, `Outcome`, `Clip`, and `DataGap` nodes. Event writes are idempotent and keyed by a stable hash of the animal, chunk, timestamp, and behavior.

Important relationships include:

```text
(Animal)-[:PERFORMED]->(Event)-[:OCCURRED_DURING]->(Shift)
(Event)-[:DEVIATES_FROM { z }]->(BaselineProfile)
(Event)-[:TRIGGERED]->(Alert)
(Event)-[:RESOLVED_BY]->(Outcome)
(Animal)-[:HAS_BASELINE]->(BaselineProfile)
(Event)-[:HAS_CLIP]->(Clip)
```

## Safety and Validation

ZooVision is a welfare-support tool, not a medical device. It is not a diagnostic or treatment system, and it must never be represented as one.

Before a demo or deployment, validate these assumptions against labeled animal footage and actual provider behavior:

- whether structured video analysis recognizes the chosen animal-behavior vocabulary;
- whether animal sounds can be detected reliably enough to influence review;
- clip-to-event timestamp accuracy;
- actual model identifiers, quotas, pricing, embedding dimensions, and platform limits;
- false-positive and false-negative rates in shadow mode.

The initial demo design uses pre-analyzed footage so the experience remains reliable within limited video-analysis quotas. Any live claim should identify exactly which portion of the pipeline ran live.

## Roadmap

1. Start from the `jpadams/video-context-graph` ingestion, agent, vector, and graph plumbing.
2. Replace its generic video ontology with the ZooVision animal, event, and baseline model.
3. Implement and test the deterministic triage engine and daytime-only baseline computation.
4. Add night alerting, acknowledgement/escalation, morning briefings, and keeper outcome capture.
5. Validate on labeled animal footage, run a shadow period, and document measured accuracy before enabling real pages.

## Source Brief

The full technical architecture, provider references, data schema, product journey, and hackathon plan are in [the original design brief](./compass_artifact_wf-8953096d-23a5-5284-a231-458dcee08d71_text_markdown.md).
