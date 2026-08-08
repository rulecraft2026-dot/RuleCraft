# RuleCraft — Devpost copy

## Tagline

The DataHub-native safety gate that simulates an AI experiment's downstream blast radius before promotion.

## Inspiration

Aggregate experiment scores hide local regressions. A candidate solver can look better while breaking the benchmark, model release, or research dashboard that depends on one critical task. Run logs know the score; only the organizational context graph knows what the result can damage.

## What it does

RuleCraft compares baseline and candidate ARC solver runs, reads transitive downstream lineage from DataHub, and turns each measured regression into an asset-level risk simulation. Its deterministic gate approves safe candidates, requests owner approval for ambiguous ones, or blocks high-risk promotion. It then verifies that the decision matches the evidence and writes the finding, risk, remediation, and gate status back to DataHub so the next researcher or agent inherits the decision context.

## How we built it

The Python agent follows **Context → Reason → Simulate → Act → Verify → Remember**. `DataHubContextGraph` reads lineage through DataHub's OpenAPI graph and emits Metadata Change Proposals for experiment properties, lineage, tags, and decision memory. A small graph protocol gives the same workflow an infrastructure-free deterministic test adapter without pretending that adapter is DataHub.

## Why DataHub is essential

The JSON run data can reveal a regression, but it cannot reveal the downstream benchmark, release, dashboard, criticality, or responsible team. Those relationships come from DataHub. RuleCraft also contributes the final decision back to the graph, closing the loop instead of acting as a read-only metadata wrapper.

## What makes it different

RuleCraft is not a chatbot, catalog search box, or lineage viewer. Its signature **Counterfactual Experiment Blast-Radius Gate** converts lineage into a pre-release decision and durable organizational memory.

## Reproducible result

In the included scenario RuleCraft inspects 5 entities, traverses 3 lineage edges, identifies 3 impacted assets and 3 material risks, proposes 3 owner-specific actions, blocks the release at risk 95/100, verifies the decision, and records one decision-memory write-back. The machine-readable report is committed under `examples/` and can be regenerated with the documented CLI.

## 3-minute demo script

1. **0:00–0:20 — Problem:** show candidate aggregate improvement and hidden `arc-001` regression.
2. **0:20–0:45 — DataHub context:** show candidate lineage reaching the hard benchmark, model release, and leaderboard.
3. **0:45–1:25 — Signature feature:** run RuleCraft; reveal paths, owners, per-asset risk, and the 95/100 block decision.
4. **1:25–1:55 — Action and verification:** show remediation and deterministic PASS—not a generated success claim.
5. **1:55–2:25 — Remember:** refresh DataHub and show `rulecraft-blocked`, impacted count, max risk, verification, and remediation.
6. **2:25–2:45 — Evidence:** show the 10 passing tests and generated JSON report.
7. **2:45–2:55 — Close:** “DataHub tells teams what is connected. RuleCraft decides whether an AI experiment is safe—and remembers why.”

## Recording truth requirement

Do not reuse the old video as evidence of the new blast-radius feature. Record the upgraded `examples/datahub_writeback.py` flow against a running DataHub instance, and only show metrics produced in that run.
