OpsResolve

Summary  
- Build a supervisor-orchestrated, agent-based system that analyzes production incidents by querying ServiceNow (ticket/context), Splunk (logs), and Azure Application Insights (metrics/traces), then generates evidence-backed hypotheses and updates the incident with structured findings.  
- The system centralizes control flow in a deterministic supervisor, delegates data collection to specialized adapters, and uses an LLM for interpretation, correlation, and summarization (not for control flow).  
- Initial scope is read-oriented analysis with idempotent ServiceNow updates; later phases add change correlation, knowledge reuse, and gated remediation proposals.  
  
Goals and non-goals  
- Goals  
  - Reduce time-to-first-signal and time-to-mitigation during incidents.  
  - Provide consistent, auditable analysis and structured updates in ServiceNow and ChatOps.  
  - Safely orchestrate long-running queries with retries, partial results, and bounded loops.  
  - Enforce least-privilege and idempotency across systems.  
- Non-goals (initial)  
  - Free-form query generation (SPL/KQL) without human review.  
  - Fully autonomous remediation actions in production.  
  - Replacing existing monitoring/alerting; this consumes their outputs.  
  
Personas and stakeholders  
- On-call SRE/Engineer: needs rapid triage, clear evidence and next steps.  
- Incident Commander: wants a single source of truth and consistent updates.  
- Service Owner/Developer: needs root cause indicators and exemplars.  
- Problem Manager: wants durable knowledge (KEDB) and cross-incident insights.  
- Platform/Tooling Owner: cares about reliability, cost, and policy compliance.  
  
Key use cases  
- U1: New Sev-2 incident arrives in ServiceNow; system fetches context, fans out to Splunk and App Insights, correlates signals, and posts a structured summary within minutes.  
- U2: Ongoing incident with low-confidence findings; system widens time window, refines queries to specific endpoints/error signatures, and posts an updated hypothesis.  
- U3: Incident correlates with a recent deploy; system flags the change, provides pre/post deltas and error exemplars, and proposes a rollback plan for approval.  
- U4: System outage in one data source (e.g., Splunk throttling); system degrades gracefully, marks data quality, and still reports best-effort findings.  
  
Scope (MVP and phased rollout)  
- Phase 1 (MVP)  
  - Read-only analysis from ServiceNow, Splunk, and App Insights.  
  - Deterministic supervisor with bounded analysis loop.  
  - Structured ServiceNow comment with findings and evidence links (idempotent).  
  - Basic ChatOps notification (optional).  
- Phase 2  
  - Change correlation: deployments, feature flags, config changes.  
  - Knowledge/runbook retrieval (RAG) for mitigations and known errors.  
  - ServiceNow Problem/KEDB draft entries for review.  
- Phase 3  
  - Gated remediation proposals with human approval (restart, rollback, scale).  
  - Expanded playbooks and adaptive query strategies.  
  
Functional requirements (FR)  
- FR1 Intake and normalization  
  - Ingest incident triggers from ServiceNow (webhook or poll).  
  - Normalize service, environment, CI relations, severity, and time window (T0 ± configurable minutes).  
- FR2 Playbook selection  
  - Select one or more analysis playbooks based on incident attributes (error spike, latency, dependency failure) and service category.  
- FR3 Data collection (agents)  
  - Splunk agent: dispatch parametric SPL templates, poll job status, return compact summaries and exemplars.  
  - App Insights agent: run KQL templates for exceptions, latency, dependencies; return metrics deltas and exemplars.  
  - ServiceNow agent: read incident fields, CMDB relations, prior similar incidents; write structured comments and links idempotently.  
- FR4 Correlation and timeline  
  - Merge signals into a unified timeline with timestamps, sources, and correlation IDs (traceId/requestId) when available.  
  - Compute deltas and anomaly flags (e.g., p95 +45%, exception rate x3).  
- FR5 Hypothesis generation  
  - Produce 1–3 hypotheses with evidence, confidence, and explicit information gaps and next steps.  
- FR6 Iteration  
  - If confidence below threshold or gaps exist, refine queries or widen time window; loop with a max iteration budget.  
- FR7 Reporting  
  - Post a single structured ServiceNow comment with: summary, signals, hypotheses, next steps, evidence links, and system provenance.  
  - Optional ChatOps message to incident channel.  
- FR8 Policy and approvals  
  - Gate any write or remediation proposals by policy (severity, confidence, service scope) and require human approval.  
- FR9 Audit and artifacts  
  - Persist run state, queries executed, costs, and artifacts (charts, samples) with run/incident IDs.  
- FR10 Configuration  
  - Centralized configuration for playbooks, thresholds, rate limits, templates, and system mappings (CI ↔ Splunk/App Insights).  
  
Non-functional requirements (NFR)  
- NFR1 Reliability: tolerate transient errors; retries with backoff; graceful degradation on source outages.  
- NFR2 Performance: time-to-first-signal target ≤ 3–5 minutes for standard workloads; fan-out queries in parallel.  
- NFR3 Cost control: per-incident token and API cost budgets with guardrails; cache results for short TTL.  
- NFR4 Security: least-privilege tokens, secret storage in Key Vault, PII redaction in samples, comprehensive audit logs.  
- NFR5 Observability: structured logs, traces, and metrics (latency, success rates, loops, costs) per component.  
- NFR6 Idempotency: deduplication keys for ServiceNow writes; persisted job IDs for long-running queries.  
  
System architecture (logical)  
- Supervisor (orchestrator/state machine)  
  - Responsible for control flow, state tracking, playbook selection, hypothesis scoring, iteration, and reporting.  
  - Deterministic nodes and conditional transitions; supports pause/resume via checkpointing.  
- Specialized agents  
  - ServiceNow adapter: read/write with idempotent updates; CMDB querying.  
  - Splunk adapter: async job lifecycle, parametric SPL execution, result shaping.  
  - App Insights adapter: KQL execution, metrics/traces aggregation, result shaping.  
  - Optional: Deployments/feature flags adapter; Knowledge/RAG; Communications (Slack/Teams).  
- Shared services  
  - Playbook registry and template library (versioned SPL/KQL patterns).  
  - Schema/contract registry for agent inputs/outputs.  
  - State/checkpoint store and short-ttl cache.  
  - Artifact store for charts and samples.  
  - Policy engine (RBAC, approval rules).  
  - Telemetry pipeline (logs/metrics/traces).  
  
Data model (core state)  
- Incident context: incident_id, severity, service, environment, CI relations, reporter, T0, initial time window.  
- Signals:  
  - Splunk: top_exceptions[], error_spike flag, spike_window, sample stacktraces (redacted), trace_ids[], counts_by_host[], evidence links.  
  - App Insights: exception_spike flag, p95/p99 deltas, dependency_failures[], affected_endpoints[], trace_ids[], evidence links.  
  - Changes (phase 2): deploys, feature flags, config changes in window.  
- Hypotheses: text, evidence[], confidence (0–1), gaps[], next_steps[], risk_level.  
- Actions: dispatched queries, collected artifacts, ServiceNow updates (with dedup keys), proposed remediations.  
- Timeline: ordered events across sources with timestamps and source metadata.  
- Output: summary, likely cause, mitigations, pending actions, data quality notes.  
  
Agent contracts (interfaces)  
- Common input to agents: {incident_id, service, environment, time_window, correlation_tokens?, query_params?}  
- Common output from agents:  
  - results: structured summary per template.  
  - completeness: data coverage and quality indicators (e.g., percent of time window searched).  
  - latency and cost estimates.  
  - evidence links to raw systems (search job URLs, charts).  
- Contract principles:  
  - Strict schemas with minimal, high-signal fields.  
  - Parametric template selection; no free-form SPL/KQL in MVP.  
  - Clear error modes: transient vs terminal, with guidance for retries or fallback.  
  
Control flow (happy path)  
- Intake: supervisor receives incident → normalize context and time window.  
- Fan-out: run Splunk and App Insights queries in parallel; agents dispatch jobs and stream partials.  
- Join: correlate signals and build a unified timeline; compute anomalies/deltas.  
- Analyze: generate hypotheses with confidence and gaps.  
- Decide: if confidence < threshold, refine/widen; else prepare report.  
- Report: post structured ServiceNow comment and optional ChatOps update; attach artifacts.  
- Finish: persist state; if enabled, draft KEDB entry for review.  
  
Safety and compliance  
- Least-privilege, separate read/write identities per system.  
- Redaction of PII/secrets in exemplars; volume caps for raw samples.  
- Idempotent ServiceNow updates with dedup keys; no ticket churn.  
- Strict logging of generated queries/templates and all write operations.  
- Approval gates for any state-changing actions (remediation, backfills).  
  
Observability and SLOs  
- Metrics  
  - Time-to-first-signal, time-to-report, query latencies per adapter, success/error rates, loops per incident, cost per incident.  
  - Hypothesis precision proxy: percent of incidents with confidence ≥ threshold; post-incident validation rate.  
- Logs and traces  
  - Per-node input/output sizes, decisions taken, retries, timeouts, circuit breakers.  
- SLOs (targets)  
  - P50 time-to-first-signal ≤ 3 minutes, P90 ≤ 6 minutes.  
  - ≥ 95% successful ServiceNow updates without duplicates.  
  - ≥ 90% of runs complete with at least one usable hypothesis.  
  
Playbook strategy  
- Initial playbooks (per source)  
  - Error spike by service/env with top exception classes and stacks.  
  - Latency increase (p95/p99) with endpoint breakdown.  
  - Dependency failure breakdown with impacted downstreams.  
  - Change correlation (phase 2): pre/post deploy deltas and error class diff.  
- Governance  
  - Versioned templates with owners; selection rationale logged.  
  - Review loop on hit-rate and false positives to evolve templates.  
  
User experience (UX surfaces)  
- ServiceNow  
  - Single structured comment per iteration, updated idempotently.  
  - Content: summary, key signals (bulleted), hypotheses with confidence, next steps, evidence links, data quality notes.  
- ChatOps (optional)  
  - Short message with headline findings and a link to the ticket/artifacts.  
- KEDB/Knowledge (phase 2)  
  - Auto-drafted entry with cause, fix, evidence, and links for human review.  
  
Operations and rollout  
- Phase 1 shadow: run read-only alongside live incidents; do not write to ServiceNow; collect telemetry and compare against human analyses.  
- Phase 1 GA: enable ServiceNow comments with dedup; rate-limit updates; weekly review of costs and accuracy.  
- Phase 2: enable change correlation and KEDB drafts; refine playbooks; optional ChatOps announcements.  
- Phase 3: introduce gated remediation proposals for selected services with clear rollback plans and approval workflow.  
  
Success metrics and targets  
- Reduce median time-to-first-signal by 40–60% vs baseline.  
- Achieve ≥ 70% of incidents with a hypothesis confidence ≥ 0.6 within 10 minutes.  
- Reduce manual log/metric query toil by ≥ 50% during triage (survey-based).  
- Maintain ServiceNow update duplication rate < 1%.  
- Keep average cost per incident within budget (define $/incident target).  
  
Testing and validation  
- Backtests on historical incidents with known outcomes; compute hypothesis accuracy and latency.  
- Golden scenarios for common failure modes with expected signals and conclusions.  
- Chaos drills: simulate data source degradation and confirm graceful fallback and data quality flags.  
- Red-team the LLM prompts to ensure safe, bounded outputs and template selection.  
  
Risks and mitigations  
- Risk: Free-form query hallucinations produce costly or unsafe searches.  
  - Mitigation: parametric templates only; human approval for ad hoc queries.  
- Risk: Long-running queries delay analysis.  
  - Mitigation: async dispatch/poll; partial results; bounded loops and adaptive windows.  
- Risk: Duplicate or noisy ticket updates.  
  - Mitigation: dedup keys, throttling, and a single structured comment pattern.  
- Risk: Data source outages or throttling.  
  - Mitigation: circuit breakers, degradation plan, clear data quality notes, and escalation to human.  
- Risk: Privacy leakage via raw exemplars.  
  - Mitigation: redaction pipeline and volume caps; evidence links over raw dumps.  
  
Dependencies and assumptions  
- ServiceNow access to incidents and CMDB; webhook or polling configured.  
- Splunk and App Insights API access with appropriate scopes.  
- Mapping of ServiceNow CIs to Splunk indexes and App Insights resources.  
- Secrets stored in Key Vault; RBAC policies available.  
- LangGraph (or equivalent) for orchestrated stateful runs and checkpointing.  
  
Acceptance criteria (MVP)  
- On receiving a Sev-1/2 incident, the system posts a structured comment with findings within 10 minutes in ≥ 90% of cases.  
- The system correlates at least two sources (Splunk and App Insights) for ≥ 80% of analyzed incidents.  
- All ServiceNow writes are idempotent and logged with a dedup key; no duplicate comments in a 24h period for the same incident.  
- All queries executed are traceable to a template and recorded with parameters, latency, and cost.  
- The system continues to produce a best-effort report when one data source is unavailable, with a data quality note.  
  
Open questions  
- What is the canonical mapping between ServiceNow CI/service and Splunk/App Insights resources? Who owns it?  
- Which services are in-scope for Phase 1, and what are the expected volumes/severities?  
- What confidence threshold and policy rules gate remediation proposals per service?  
- What PII redaction rules apply to log exemplars (regex lists, sensitive keys)?  
- Do we require ChatOps integration in MVP, and which platform (Slack/Teams)?  
  
Next steps  
- Confirm in-scope services and data source credentials.  
- Define initial playbooks and template parameters per service category.  
- Finalize ServiceNow comment schema and dedup key strategy.  
- Establish success metric baselines and agree on targets.  
- Plan Phase 1 shadow rollout and stakeholder review cadence.  
  
If you want, I can tailor this spec to your org by filling in service mappings, initial playbooks, and concrete acceptance thresholds based on your current incident data.