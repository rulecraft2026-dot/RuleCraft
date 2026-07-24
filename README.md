# RuleCraft

RuleCraft is a DataHub-grounded AI agent that turns experiment metadata into
actionable research context. It compares ARC solver runs, detects regressions
and improvements, traces experiment lineage, and writes durable tags and
findings back to DataHub.

Built for **Build with DataHub: The Agent Hackathon**.

## The problem

AI and ML experiments produce tasks, solver versions, hypotheses, metrics, and
failures. Those relationships are often scattered across notebooks and logs.
Without reliable lineage and metadata, the next researcher—or the next
agent—repeats old mistakes.

RuleCraft uses DataHub as a shared context layer:

1. **Read** experiment metadata and lineage.
2. **Reason** about score changes and affected tasks.
3. **Write back** regression tags and Markdown findings.

## Working MVP

The current vertical slice:

- loads two ARC experiment runs from JSON;
- compares per-task scores using a configurable threshold;
- detects meaningful regressions and improvements;
- produces structured findings;
- writes experiment properties, lineage, tags, and research notes through the
  DataHub Python SDK;
- includes an in-memory adapter for infrastructure-free tests and demos.

## Repository structure

```text
.
├── examples/
│   ├── arc_experiment_runs.json
│   ├── datahub_writeback.py
│   └── expected_findings.json
├── src/arc_lineage_agent/
│   ├── agent.py
│   ├── datahub_adapter.py
│   ├── demo.py
│   ├── graph.py
│   └── models.py
├── tests/
├── LICENSE
├── pyproject.toml
└── requirements.txt
```

## Quick demo without DataHub

Python 3.11 or newer is required.

```bash
python -m pip install -e .
rulecraft --input examples/arc_experiment_runs.json \
  --output examples/generated_findings.json
```

Expected console output:

```text
RuleCraft
- [regression] arc-001 regressed by 0.50 between solver-v1 and solver-v2.
- [improvement] arc-002 improved by 0.50 between solver-v1 and solver-v2.
Written tags: ['arc-improvement', 'arc-regression', 'needs-review']
```

## Run with DataHub OSS

### 1. Start DataHub

Docker must be installed and running.

```bash
python -m pip install -r requirements.txt
datahub docker quickstart
```

The default DataHub Graph Metadata Service endpoint is
`http://localhost:8080`.

### 2. Run the write-back example

```bash
python examples/datahub_writeback.py
```

The example creates two experiment datasets, adds baseline-to-candidate
lineage, runs the agent, and writes these tags to the candidate experiment:

- `arc-regression`
- `arc-improvement`
- `needs-review`

It also updates the candidate dataset description with Markdown findings.

For an authenticated endpoint:

```bash
set DATAHUB_GMS_URL=https://your-datahub.example.com
set DATAHUB_TOKEN=your-token
python examples/datahub_writeback.py
```

On macOS or Linux, use `export` instead of `set`.

## Test

```bash
python -m unittest discover -s tests -v
```

## Architecture

```text
ARC experiment JSON
        │
        ▼
ResearchLineageAgent ── compare scores ──► Findings
        │                                      │
        ▼                                      ▼
DataHubContextGraph ── lineage ──► DataHub ── tags + notes
```

`ResearchLineageAgent` depends on a small `ContextGraph` protocol. This keeps
the reasoning logic testable while allowing DataHub to be the production
context store.

## Hackathon category

Primary: **Agents That Do Real Work**

Secondary: **Open / Wildcard**

## Roadmap

- Read existing runs and lineage back from DataHub.
- Add DataHub MCP Server tools for agent-native metadata access.
- Trigger analysis from DataHub metadata-change events.
- Add a web demo showing the read → reason → write-back loop.

## License

Apache-2.0. See [LICENSE](LICENSE).
