# NEXUS PRD

## 1. Document Metadata

- Product Name: NEXUS
- Full Name: Neural Evolutionary Xenogenous Universal Software-civilization
- Document Type: Product Requirements Document
- Status: Draft v0.1
- Primary Intent: Build a supervised autonomous software-civilization platform that converts natural language intent into production-minded software systems
- Primary Mode: Local-first autonomous development platform with policy-gated evolution
- North Star: Human defines **what** to build; NEXUS increasingly handles **how** to design, implement, validate, and improve it

---

## 2. Product Summary

NEXUS is not a single coding agent and not just an IDE assistant.

NEXUS is a multi-agent software production system that:
- accepts natural language product intent from humans,
- decomposes that intent into executable engineering tasks,
- delegates work to specialized AI agents,
- writes and modifies code in isolated workspaces,
- runs tests, reviews, and security checks,
- stores its knowledge, decisions, and failures,
- improves future work using prior runs,
- and eventually performs limited self-improvement on its own platform.

NEXUS must operate as a **supervised autonomous software civilization**:
- autonomous enough to continue working without constant human interaction,
- structured enough to be auditable,
- safe enough to be constrained by policy,
- and evolvable enough to become better over time.

---

## 3. Problem Statement

### 3.1 Current State of AI Coding Systems

Existing AI coding workflows are powerful but limited:
- They are session-bound and forgetful.
- They generate code, but often lack strong verification loops.
- They can help on individual tasks, but do not behave like a coordinated engineering organization.
- They rarely preserve durable decision context across projects.
- They are weak at long-running autonomous execution without explicit structure.
- They can be unsafe when connected to real infrastructure without robust controls.

### 3.2 Core User Pain

Users increasingly know what they want to build, but the path from intent to reliable software remains fragmented:
- Requirements live in chat
- Architecture lives in the user's head
- Code lives in repos
- Tests come later or never
- Security is reactive
- Deployment is fragile
- Lessons from one project are not reused in the next

### 3.3 Opportunity

There is an opportunity to create a system that behaves less like a chatbot and more like a **software civilization**:
- role-specialized,
- memory-backed,
- policy-constrained,
- evidence-driven,
- and capable of repeated, compounding improvement.

---

## 4. Product Vision

NEXUS enables a future where a human can state:

> "Build me a SaaS for team task management with email login, dashboard, audit logs, and Stripe-ready billing hooks."

and NEXUS can:
- interpret the request,
- propose a system design,
- generate the codebase,
- create tests and deployment paths,
- verify quality and security,
- present progress in an embassy dashboard,
- and improve itself over time without losing safety guarantees.

NEXUS should feel like:
- a software company in a box,
- an autonomous engineering operating system,
- and a policy-governed civilization for building software.

---

## 5. Product Goals

### 5.1 Primary Goals

1. **Natural Language to Software**
   - Convert user intent into runnable software systems.

2. **Multi-Agent Coordination**
   - Use specialized agents with explicit roles rather than a single undifferentiated model loop.

3. **Evidence-Based Change**
   - All important changes must be linked to rationale, artifacts, test results, and risk context.

4. **Durable Memory**
   - Preserve code knowledge, decisions, incidents, failures, and reusable patterns across runs.

5. **Safe Autonomy**
   - Allow extended autonomous operation while enforcing policy, isolation, and human override.

6. **Limited Self-Improvement**
   - Enable NEXUS to improve its workflows and selected internal components under strict safeguards.

### 5.2 Secondary Goals

- Reusability across projects
- Local-first reproducibility
- Strong observability and auditability
- Clear human intervention points
- Gradual expansion from solo builder tool to platform

---

## 6. Non-Goals (Initial Release Scope)

The following are explicitly out of scope for the initial real release, even if the architecture should remain extensible toward them:

- Hundreds of simultaneously active agents by default
- Fully autonomous production deployment without approval
- Unrestricted self-rewriting of core policy/governance systems
- Full multi-cloud active deployment in v1
- Universal IoT orchestration as a first-class must-have
- Formal verification of the entire platform
- Global, open-ended autonomous internet operation
- A claim of complete software replacement for human engineers

NEXUS v1 is about **safe, supervised, high-leverage autonomy**, not total omnipotence.

---

## 7. Target Users

### 7.1 Primary Users

#### A. Solo Builders / Founders
People who know what they want to build but cannot or do not want to manually perform every engineering task.

Needs:
- fast scaffolding
- architecture help
- autonomous execution while away
- clear logs and controllable automation

#### B. Technical Product Builders
PMs, tech leads, or operators who need a system that can turn intent into implementation plans and code.

Needs:
- structured decomposition
- visibility into decisions
- reviewability
- controlled delegation

#### C. AI-Native Engineers
Developers who want an autonomous system to handle repetitive, structural, or review-heavy work.

Needs:
- parallelization
- memory
- code review and repair loops
- self-improving workflows

### 7.2 Secondary Users

- research engineers
- platform teams
- internal tools teams
- innovation labs

---

## 8. Core User Stories

### 8.1 Build New Software
As a user, I want to describe a product in natural language and have NEXUS produce a working software baseline with architecture, code, tests, and run instructions.

### 8.2 Extend Existing Repositories
As a user, I want NEXUS to analyze an existing codebase and safely add features or fix bugs through structured workflows.

### 8.3 Review and Harden Systems
As a user, I want NEXUS to review code quality, security posture, and operational readiness before I ship.

### 8.4 Learn from Past Runs
As a user, I want NEXUS to remember what worked or failed in previous runs and improve its future performance.

### 8.5 Improve Itself Safely
As a user, I want NEXUS to identify weaknesses in its own workflows and propose or apply constrained improvements.

---

## 9. Product Principles

1. **Safety over raw autonomy**
2. **Verification over generation**
3. **Working vertical slices over broad hollow demos**
4. **Evidence over intuition**
5. **Local-first reproducibility**
6. **Auditable autonomy**
7. **Policy-preserving self-improvement**
8. **Humans retain the right to intervene, redirect, or stop**

---

## 10. Core System Overview

NEXUS has seven top-level product domains:

1. Human Embassy
2. Agent Parliament
3. Knowledge Brain
4. Evolutionary Code Engine
5. Distributed Execution Fabric
6. Security Membrane
7. Self-Bootstrap Layer

These domains must compose into one coherent system rather than exist as unrelated demos.

---

## 11. Functional Requirements

## 11.1 Human Embassy

The Human Embassy is the user-facing diplomatic layer between humans and the software civilization.

### Requirements
- Accept natural language requests through API and UI
- Display run status in real time
- Show active agents, artifacts, decisions, and logs
- Surface approvals, warnings, and blocked items
- Provide audit history for all major actions
- Provide emergency stop / freeze control
- Provide replay or resume capability for past runs

### Initial v1 Acceptance
- User can submit a request
- User can view plan, tasks, current status, and artifacts
- User can see run logs and decision summaries

---

## 11.2 Agent Parliament

The Agent Parliament is the collaborative multi-agent execution layer.

### Requirements
- Role-based agent specialization
- Structured agent I/O schemas
- Shared task graph and execution state
- Delegation and subtask spawning
- Review and critique between agents
- Policy-gated decision making
- Run budgets and prioritization

### Initial v1 Agent Set
- Planner
- Architect
- Implementer
- Tester
- Reviewer
- Security
- DevOps
- Librarian
- Judge

### Initial v1 Acceptance
- A user request triggers at least a Planner → Architect → Implementer → Tester → Reviewer flow
- Each agent emits structured artifacts
- A judge/decision layer determines next action

---

## 11.3 Knowledge Brain

The Knowledge Brain stores and retrieves durable context.

### Requirements
- Store source code embeddings or searchable code context
- Store decisions, incidents, task outcomes, and run summaries
- Link artifacts across runs
- Support retrieval for future tasks
- Preserve successful patterns and failure lessons
- Allow compression/archival of low-value stale memory

### Data Types
- source files
- generated artifacts
- decisions
- failures
- evaluations
- run summaries
- reusable templates
- known good patterns

### Initial v1 Acceptance
- Prior run artifacts are searchable
- New runs can reference previous outcomes
- Core decisions are indexed and linked

---

## 11.4 Evolutionary Code Engine

The Evolutionary Code Engine improves implementations over time.

### Requirements
- Evaluate multiple candidate implementations
- Compare implementations using performance, maintainability, and safety criteria
- Support iterative generation → test → evaluate → patch loops
- Allow limited evolutionary or search-based optimization in selected domains
- Track which changes genuinely improved outcomes

### Initial v1 Constraints
- Do not require full genetic programming everywhere
- Start with bounded improvement loops
- Focus on code repair, benchmark-guided optimization, and workflow improvement
- Expand evolutionary strategies later

### Initial v1 Acceptance
- NEXUS can improve at least one internal or target component through an evidence-based iteration loop

---

## 11.5 Distributed Execution Fabric

The Distributed Execution Fabric executes tasks and generated code safely.

### Requirements
- Create isolated workspaces per run/project
- Execute build, test, lint, and runtime commands
- Persist artifacts and logs
- Support queue-based asynchronous task execution
- Abstract local execution from future K8s execution
- Enable restart/resume semantics

### Initial v1 Scope
- Local-first execution using Docker and isolated folders/workspaces
- Queue or event-driven orchestration
- Optional local K8s abstraction hooks

### Initial v1 Acceptance
- NEXUS can create a workspace, generate code, run tests, and store results without contaminating the main control plane

---

## 11.6 Security Membrane

The Security Membrane is the governing protective boundary.

### Requirements
- Secret scanning
- dependency auditing
- permission boundary enforcement
- workspace isolation
- policy checks before sensitive actions
- audit logging of security-relevant events
- blocked-action reporting
- safe defaults for deployment and external access

### Initial v1 Scope
- no automatic real production deployment
- no unrestricted secret usage
- no unrestricted network escalation
- local mock paths for risky integrations

### Initial v1 Acceptance
- Security checks run automatically before risky actions
- Sensitive operations are blocked or gated
- Audit logs exist for security decisions

---

## 11.7 Reality Interface

The Reality Interface connects NEXUS to real systems.

### Requirements
- repo integration
- REST and GraphQL connector abstractions
- database schema introspection hooks
- infrastructure-as-code scaffolding hooks
- external API integration paths
- git-based code lifecycle support

### Initial v1 Scope
- Git-backed workflow
- REST API integration scaffolding
- database schema support
- CI/CD scaffolding
- local deployment path

### Initial v1 Acceptance
- NEXUS can generate a runnable service that uses real interfaces or mocks with clean extension paths

---

## 11.8 Self-Bootstrap Layer

The Self-Bootstrap Layer lets NEXUS improve its own non-core components safely.

### Requirements
- self-analysis of code, logs, and failure patterns
- proposal generation for internal improvements
- policy-gated application of self-patches
- rollback support
- self-evaluation artifact generation

### Forbidden Early Behaviors
- disabling policy checks
- weakening permission boundaries
- removing human oversight hooks
- altering safety-critical governance without explicit approval

### Initial v1 Acceptance
- NEXUS can identify one weakness in its own platform and implement a bounded, reversible improvement

---

## 12. Agent Role Definitions

### Planner Agent
Transforms user intent into goals, constraints, milestones, and task graph.

### Architect Agent
Designs system boundaries, modules, interfaces, and data models.

### Implementer Agent
Writes and edits code, configs, scripts, and docs required for execution.

### Test Agent
Creates and runs tests, then reports failures and confidence.

### Reviewer Agent
Performs quality, structure, and maintainability review.

### Security Agent
Performs risk analysis and security review.

### DevOps Agent
Builds runbooks, local infra, CI, containers, and preview workflows.

### Librarian Agent
Indexes artifacts and links knowledge across runs.

### Judge Agent
Scores proposals, compares options, and chooses next actions.

---

## 13. Governance and Approval Model

NEXUS must never behave like an unconstrained agent swarm.

### Governance Rules
- All major architectural changes require recorded decision summaries
- Risky actions require policy checks
- Destructive actions require human approval
- Self-improvement is allowed only in bounded scope
- All agent outputs must be attributable

### Approval Tiers

#### Tier 0: Autonomous
Safe local file generation, tests, docs, and internal refactors

#### Tier 1: Policy-Gated
Dependency additions, wider file changes, internal workflow changes

#### Tier 2: Human Approval Required
Real secrets, external billing systems, destructive migrations, production deployment, policy relaxation

---

## 14. Data Model Requirements

NEXUS should treat all meaningful work as linked artifacts.

### Core Entities
- Project
- Run
- Agent
- Task
- TaskGraph
- Artifact
- Decision
- Evaluation
- PolicyCheck
- Workspace
- MemoryEntry
- ImprovementProposal
- DeploymentRecord
- AuditEvent

### Requirements
- Every run must be traceable
- Every major change must be attributable
- Artifacts must be linkable to the task and agent that created them
- Retrieval must work across prior runs
- Failures must be first-class records, not discarded noise

---

## 15. UX / Operator Experience

The Human Embassy UI/API should allow the operator to:
- submit a request
- inspect the generated plan
- see current phase and active agents
- inspect files changed and artifacts generated
- review test/security outcomes
- pause/resume/stop runs
- inspect prior runs and decisions
- inspect self-improvement proposals

The UX should feel like:
- mission control for an autonomous engineering civilization

---

## 16. Non-Functional Requirements

### 16.1 Reliability
- Restartable after interruption
- Durable run records
- Graceful handling of partial failure

### 16.2 Security
- Secrets never hardcoded
- Safe-by-default workflows
- Block dangerous actions without approval

### 16.3 Observability
- Structured logs
- Run timelines
- Artifact traces
- Agent accountability

### 16.4 Maintainability
- Typed interfaces
- Modular services
- Clear boundaries
- Documentation kept up to date

### 16.5 Reproducibility
- Local-first setup
- Deterministic or bounded-repeatable execution paths where possible
- One-command or low-friction development startup

### 16.6 Extensibility
- New agents can be added without rewriting the whole system
- Memory backends can evolve
- Execution layer can move from local-first to cluster-backed

---

## 17. Proposed Technical Architecture

### 17.1 Recommended Initial Stack
- Python for orchestration core
- FastAPI for APIs
- PostgreSQL for structured data
- Redis for queues/event streams
- Vector retrieval via Qdrant or pgvector
- Next.js + TypeScript for Embassy UI
- Docker / docker-compose for local orchestration
- Optional kind/k3d abstraction for local cluster evolution

### 17.2 Architectural Shape
- `core/` for runtime, orchestration, agents, policies
- `brain/` for memory and retrieval
- `embassy/` for user API/UI
- `execution/` or `fabric/` for workspaces and command execution
- `security/` for policies, scans, audits
- `bootstrap/` for self-improvement flows
- `tests/` for unit, integration, adversarial, and end-to-end cases

### 17.3 Key Design Choice
NEXUS must be built as a system of:
- explicit state
- explicit artifacts
- explicit policies
- explicit memory
not as a loose chat chain.

---

## 18. Release Strategy

## 18.1 North Star Release
A system where a nontrivial product request can be converted into:
- architecture
- code
- tests
- documentation
- local deployment path
- reviewable artifacts
- traceable decisions
- safe future iteration

## 18.2 First Real Release (Target)
The first serious release should prioritize:
- one working end-to-end software generation flow
- agent orchestration
- durable artifact logging
- human dashboard
- security gate basics
- local-first reproducibility

This is more important than claiming hundreds of agents or full multicloud orchestration.

---

## 19. Milestones

### Milestone 1 — Foundation
Deliver:
- repo scaffold
- orchestration core
- task state model
- workspace model
- base API
- initial docs

Success:
- system boots locally
- request can be registered and tracked

### Milestone 2 — Parliament
Deliver:
- core agent implementations
- task decomposition
- structured outputs
- basic decision layer

Success:
- request triggers multi-agent workflow

### Milestone 3 — Brain
Deliver:
- memory persistence
- retrieval hooks
- decision indexing
- artifact linking

Success:
- run N can reference run N-1 meaningfully

### Milestone 4 — Verification Fabric
Deliver:
- build/test loop
- isolated execution
- security checks
- review summaries

Success:
- code changes are verifiable

### Milestone 5 — Embassy
Deliver:
- operator dashboard
- run viewer
- approvals and status visualization
- emergency stop

Success:
- operator can monitor and control the system

### Milestone 6 — Limited Self-Bootstrap
Deliver:
- self-analysis flow
- bounded improvement proposal
- safe self-patch pathway

Success:
- NEXUS improves a non-core subsystem safely

---

## 20. Success Metrics

### 20.1 Product Metrics
- time from prompt to runnable artifact
- percentage of requests that produce a bootable project
- test pass rate
- reduction in human intervention over time
- reuse rate of prior knowledge
- number of successful end-to-end runs

### 20.2 Safety Metrics
- zero secret leaks
- zero unauthorized destructive actions
- zero policy bypasses
- count of blocked risky actions

### 20.3 Learning Metrics
- repeated failure reduction
- patch success rate
- quality gain from prior memory use
- self-improvement proposals accepted and validated

---

## 21. Risks

### 21.1 Technical Risks
- agent drift and inconsistency
- over-generation without verification
- brittle orchestration state
- memory pollution
- false confidence from weak tests

### 21.2 Product Risks
- too much breadth, not enough working depth
- beautiful architecture with little executable value
- poor operator trust due to opacity
- autonomy that creates more cleanup than leverage

### 21.3 Security Risks
- excessive permissions
- unsafe dependency ingestion
- dangerous self-modification
- unreviewed infrastructure changes

### Mitigation Strategy
- strong policy boundaries
- local-first execution
- auditable artifacts
- explicit approval gates
- narrow, real vertical slices before breadth expansion

---

## 22. Open Questions

- What is the default budget model for runs, agents, and tools?
- How should agent quality be scored over time?
- When should the system switch from local-first execution to cluster-backed execution?
- What degree of self-improvement is acceptable without explicit human review?
- Which memory items are durable vs. compressible vs. disposable?
- How should NEXUS compare candidate implementations fairly across languages?
- What constitutes "enough evidence" for a self-generated patch to be trusted?

---

## 23. Definition of Done

A release of NEXUS is considered meaningfully complete when:

1. A user can submit a software request in natural language.
2. NEXUS decomposes the request into a structured execution plan.
3. Multiple specialized agents collaborate on the implementation.
4. Code, tests, decisions, and logs are stored as first-class artifacts.
5. The generated system can be built or run locally.
6. A human can inspect the entire process through the embassy interface or API.
7. Risky operations are policy-gated.
8. NEXUS can perform at least one bounded self-improvement cycle safely.
9. The entire workflow is restartable and auditable.

