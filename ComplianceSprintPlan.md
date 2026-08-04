# Compliance Sprint Plan

**Project:** Video Intelligence Platform
**Document Version:** 1.1
**Date:** April 10, 2026
**Author:** Kaan Taplamacıoğlu
**Audience:** Engineering and Legal Leadership
**Companion Document:** [LegalandOtherCompliances.md](./LegalandOtherCompliances.md)
**Status:** Draft — For Discussion

---

## Table of Contents

1. [Document Purpose](#1-document-purpose)
2. [How to Read This Plan](#2-how-to-read-this-plan)
3. [Team, Cadence, and Estimation Assumptions](#3-team-cadence-and-estimation-assumptions)
4. [Global Definition of Done](#4-global-definition-of-done)
5. [Legends](#5-legends)
6. [Timeline Summary](#6-timeline-summary)
7. [Sprint 0 — Kickoff and Governance](#7-sprint-0--kickoff-and-governance)
8. [Sprint 1 — Critical Misrepresentation Fix and Baseline Security](#8-sprint-1--critical-misrepresentation-fix-and-baseline-security)
9. [Sprint 2 — Encryption and Storage Migration](#9-sprint-2--encryption-and-storage-migration)
10. [Sprint 3 — Data Subject Rights (DSAR)](#10-sprint-3--data-subject-rights-dsar)
11. [Sprint 4 — Assessment and Documentation](#11-sprint-4--assessment-and-documentation)
12. [Sprint 5 — Jurisdiction-Specific Hardening](#12-sprint-5--jurisdiction-specific-hardening)
13. [Sprint 6 — Observability and Continuous Programs Bootstrap](#13-sprint-6--observability-and-continuous-programs-bootstrap)
14. [Parallel Long-Running Certification Track](#14-parallel-long-running-certification-track)
15. [Risk Register](#15-risk-register)
16. [Success Metrics per Sprint](#16-success-metrics-per-sprint)
17. [Cross-Reference Appendix](#17-cross-reference-appendix)

---

## 1. Document Purpose

This document translates the remediation roadmap contained in Section 11 of [LegalandOtherCompliances.md](./LegalandOtherCompliances.md) into a **concrete, sprint-level execution plan** suitable for import into an agile tracking system (Jira, Linear, GitHub Projects). Each sprint contains a set of tickets with explicit acceptance criteria, dependencies, effort estimates, and regulatory-regime mappings.

The plan is engineering-focused. It assumes the parallel engagement of qualified privacy counsel, a Data Protection Officer (DPO), and — for Turkish operation — a VERBIS-registered data controller representative. Legal review and administrative procedures that run in parallel to engineering work are noted where relevant but are not treated as owned by the engineering team.

**This plan is a draft for discussion.** Priorities, effort estimates, and sprint assignments should be validated with the deploying organisation's actual engineering and compliance leadership before execution begins.

---

## 2. How to Read This Plan

Each sprint is structured as follows:

- **Sprint Theme** — a short phrase summarising the sprint's objective.
- **Sprint Goal** — the measurable outcome the sprint must achieve.
- **Tickets** — individual units of work, each with a unique identifier (`COMP-NNN`).
- **Exit Criteria** — conditions that must be met before the sprint is considered complete.

Each ticket contains:

- **ID** — `COMP-NNN`, unique and stable across revisions.
- **Title** — imperative, verb-first.
- **Type** — Compliance, Security, Feature, Bug, Legal, or Infra.
- **Priority** — P0 (blocker), P1 (high), P2 (medium), P3 (low).
- **Effort** — engineering-days (legal and administrative work called out separately).
- **Owner Role** — backend, frontend, fullstack, DPO, legal, infra, ML.
- **Regime Mapping** — the regulations whose requirements the ticket satisfies.
- **Description** — two to four sentences of context.
- **Acceptance Criteria** — checkable conditions for Definition of Done.
- **Dependencies** — blocking and blocked-by relationships to other tickets.

---

## 3. Team, Cadence, and Estimation Assumptions

| Parameter | Assumption |
|---|---|
| Sprint length | 2 weeks |
| Team size | 1 fullstack engineer, plus access to DPO and privacy counsel as needed |
| Sprint capacity (engineering days) | 8 productive days per 10-day sprint (accounting for meetings, reviews, interrupts) |
| Estimation method | T-shirt sizing converted to engineering-days: XS = 0.5 day, S = 1 day, M = 2 days, L = 3 days, XL = 5 days |
| Velocity target | Sprint 1–3: conservative; Sprint 4+: normalized once observability baseline exists |
| Parallel legal review | Assumed available within 2 business days for ticket-level questions; 1 week for document reviews |
| Backfill assumption | If a sprint exceeds capacity, lowest-priority ticket is deferred to the next sprint and the risk register is updated |

**These assumptions should be re-negotiated with the deploying organisation's leadership before Sprint 0 begins.** In particular, team size is almost certainly larger in a real production organisation, which would compress the timeline.

---

## 4. Global Definition of Done

A ticket is considered Done only when all of the following are satisfied:

1. Code is merged to `main` and deployed to the staging environment.
2. All acceptance criteria listed in the ticket are checked.
3. Unit and integration tests cover the new behaviour; coverage does not regress.
4. Documentation (README, CLAUDE.md, API docs, runbook) is updated where the change affects documented behaviour.
5. Security review is completed for any ticket touching authentication, authorisation, encryption, or personal-data handling.
6. Privacy counsel review is completed for any ticket tagged with a regulatory regime.
7. Observability (logs, metrics, traces) is in place where applicable.
8. The ticket is linked to the satisfied regulatory-regime articles in Jira/Linear metadata.

---

## 5. Legends

### 5.1 Priority

| Code | Meaning | Response Expectation |
|---|---|---|
| **P0** | Blocker — legal risk, active misrepresentation, breach exposure | Same sprint, before any P1 |
| **P1** | High — required for minimum viable compliance | Same sprint if capacity allows; otherwise next sprint |
| **P2** | Medium — required for mature compliance programme | Within next 2 sprints |
| **P3** | Low — polish, continuous improvement | Backlog, scheduled when capacity permits |

### 5.2 Ticket Type

| Type | Scope |
|---|---|
| **Compliance** | Directly satisfies a regulatory requirement |
| **Security** | Reduces exposure to breach or unauthorised access |
| **Feature** | New user-facing capability |
| **Bug** | Correction of incorrect behaviour or misrepresentation |
| **Legal** | Work product owned by privacy counsel or DPO |
| **Infra** | Platform, deployment, observability |

### 5.3 Regime Mapping Shorthand

| Shorthand | Full Name |
|---|---|
| **GDPR** | General Data Protection Regulation (EU) 2016/679 |
| **CCPA** | California Consumer Privacy Act |
| **CPRA** | California Privacy Rights Act (amending CCPA) |
| **KVKK** | Kişisel Verilerin Korunması Kanunu (Turkey, Law 6698) |
| **SHIELD** | NY SHIELD Act (General Business Law §899-aa/bb) |
| **BIPA** | Illinois Biometric Information Privacy Act (740 ILCS 14) |
| **FTC §5** | Federal Trade Commission Act, Section 5 |
| **COPPA** | Children's Online Privacy Protection Act |
| **EU AI Act** | Regulation (EU) 2024/1689 |

### 5.4 Effort Shorthand

| T-Shirt | Days | Typical Scope |
|---|---|---|
| **XS** | 0.5 | Single file, single responsibility, trivial tests |
| **S** | 1 | Multi-file, single feature, straightforward tests |
| **M** | 2 | Cross-cutting, multiple endpoints, migration scripts |
| **L** | 3 | Multi-component, behavioural migration, feature flag rollout |
| **XL** | 5 | Architectural change, multi-sprint coordination, legal review dependency |

---

## 6. Timeline Summary

| Sprint | Calendar | Theme | Ticket Count | Engineering-Days | Cumulative Status |
|---|---|---|---|---|---|
| **Sprint 0** | Week 0 | Kickoff and governance | 3 | 2.5 | Prototype → Governed programme |
| **Sprint 1** | Weeks 1–2 | Critical fix + baseline security | 5 | 6.5 | Misrepresentation removed; basic security present |
| **Sprint 2** | Weeks 3–4 | Encryption and storage migration | 5 | 7.0 | Data-at-rest encryption active |
| **Sprint 3** | Weeks 5–6 | Data Subject Rights (DSAR) | 5 | 7.0 | Access, deletion, portability rights operational |
| **Sprint 4** | Weeks 7–8 | Assessment and documentation | 5 | 12.0 (incl. legal) | DPIA, ROPA, breach playbook complete |
| **Sprint 5** | Weeks 9–10 | Jurisdiction-specific hardening | 5 | 8.5 | Illinois, Turkey, EU, NY exposures reduced |
| **Sprint 6** | Weeks 11–12 | Observability and continuous programmes | 5 | 6.0 | Compliance becomes observable and continuous |
| **Parallel** | Months 3–18 | Certification track (SOC 2, ISO 27001) | 4 | Long-running | Enterprise procurement readiness |

**Estimated minimum time to baseline production readiness:** 12 weeks (Sprint 0 through Sprint 6), excluding long-running administrative processes (VERBIS registration, SOC 2 evidence window, ISO 27001 audit).

---

## 7. Sprint 0 — Kickoff and Governance

**Theme:** Establish programme governance and engage external stakeholders.
**Sprint Goal:** A governed compliance programme exists, with counsel engaged and a tracked backlog, before any engineering work begins.

---

#### COMP-000 — Engage privacy counsel and DPO

**Type:** Legal · **Priority:** P0 · **Effort:** XS (legal hours) · **Owner:** Legal

**Regime mapping:** GDPR Art. 37; KVKK Art. 16; organisational necessity

**Description:** Retain external privacy counsel or confirm internal counsel engagement for GDPR, CCPA/CPRA, KVKK, and US state-law matters. Appoint or confirm a DPO (or equivalent role) with documented responsibilities.

**Acceptance criteria:**
- [ ] Counsel engagement letter signed, scope covers surveyed regimes
- [ ] DPO identity and reporting line documented
- [ ] First compliance office-hour session scheduled
- [ ] Compliance backlog ownership assigned

**Dependencies:** None
**Blocks:** All Sprint 1+ tickets

---

#### COMP-001 — Assemble compliance working group

**Type:** Compliance · **Priority:** P0 · **Effort:** XS · **Owner:** Programme lead

**Regime mapping:** Organisational necessity

**Description:** Form a cross-functional working group containing engineering, legal, DPO, product, and security representation. Define decision authority, escalation path, and meeting cadence.

**Acceptance criteria:**
- [ ] Charter document committed to `docs/compliance/charter.md`
- [ ] RACI matrix for compliance decisions defined
- [ ] Weekly standing meeting scheduled
- [ ] Slack or Teams channel created for compliance discussion

**Dependencies:** COMP-000
**Blocks:** COMP-002

---

#### COMP-002 — Establish compliance backlog in Jira/Linear

**Type:** Infra · **Priority:** P0 · **Effort:** S · **Owner:** Programme lead

**Regime mapping:** GDPR Art. 30 (demonstrability); ISO 27001 A.5

**Description:** Create a dedicated project or component in the tracking system. Import this document's tickets. Configure custom fields for `regime-mapping`, `priority`, and `legal-review-status`. Establish labels for each regime.

**Acceptance criteria:**
- [ ] Compliance project created in tracking system
- [ ] All tickets from this document imported with metadata preserved
- [ ] Custom fields and labels configured
- [ ] Dashboard view created for the working group

**Dependencies:** COMP-001
**Blocks:** Sprint 1 tickets

---

**Sprint 0 Exit Criteria:**
- Counsel engaged; DPO appointed; working group chartered; backlog tracked.
- Any ticket added to Sprint 1 must have a regime-mapping field populated.

---

## 8. Sprint 1 — Critical Misrepresentation Fix and Baseline Security

**Theme:** Stop saying false things; turn on the basics.
**Sprint Goal:** No material misrepresentation remains in user-facing language; TLS, authentication, audit logging, and baseline encryption are active.

---

#### COMP-100 — Production-grade consent language rewrite

**Type:** Compliance / Bug · **Priority:** P0 · **Effort:** S · **Owner:** Fullstack + Legal

**Regime mapping:** FTC §5; GDPR Art. 5(1)(a), 12–14; KVKK Art. 4, 10; CCPA §1798.130

**Description:** The prototype's consent modal previously contained a material inconsistency ("no identifiable imagery ... is stored") that was inconsistent with the upload-flow implementation. A draft correction has been applied to the prototype and is available in `frontend/src/pages/DetectionPage.tsx` and `frontend/src/pages/LiveStreamPage.tsx`. This ticket covers the **production** version: legal review, multilingual support (English, Spanish, Turkish initially), accessibility compliance (WCAG 2.1 AA), and granular purpose-specific opt-ins.

**Acceptance criteria:**
- [ ] Consent language reviewed and approved by privacy counsel
- [ ] English, Spanish, and Turkish variants available
- [ ] Language accurately reflects each data flow (upload, webcam, RTSP, demo)
- [ ] Granular opt-ins for distinct processing purposes (analysis, clip retention, telemetry)
- [ ] Consent withdrawal UX linked from the consent modal
- [ ] Locale auto-detection from `Accept-Language` header
- [ ] WCAG 2.1 AA conformance verified
- [ ] Consent events logged to audit trail
- [ ] Regression tests for consent enforcement at the API boundary

**Dependencies:** COMP-002
**Blocks:** COMP-300 (DSAR withdrawal), COMP-400 (DPIA)

---

#### COMP-101 — Introduce TLS termination (nginx / Traefik + Let's Encrypt)

**Type:** Security · **Priority:** P0 · **Effort:** S · **Owner:** Infra

**Regime mapping:** GDPR Art. 32; CCPA §1798.100(e); KVKK Art. 12; SHIELD §899-bb(2)(b)

**Description:** The prototype's default development configuration runs on HTTP and `ws://`. Introduce a reverse proxy (Traefik preferred for automatic certificate management) that terminates TLS and forwards cleartext only over the Docker network.

**Acceptance criteria:**
- [ ] Traefik (or nginx) added to `docker-compose.yml`
- [ ] Let's Encrypt ACME configured for the target domain
- [ ] HTTP traffic redirected to HTTPS with HSTS header
- [ ] WebSocket upgraded to `wss://`
- [ ] TLS 1.2 minimum, TLS 1.3 preferred, weak ciphers disabled
- [ ] Certificate auto-renewal verified
- [ ] SSL Labs score A or higher
- [ ] Staging environment deployment verified

**Dependencies:** None
**Blocks:** COMP-102 (secure cookie transport)

---

#### COMP-102 — JWT authentication with role-based access control

**Type:** Security · **Priority:** P0 · **Effort:** L · **Owner:** Backend + Frontend

**Regime mapping:** GDPR Art. 32; CCPA §1798.100(e); KVKK Art. 12; SHIELD §899-bb(2)(b)

**Description:** Introduce a `users` table, password hashing via bcrypt (cost 12), and JWT-based session tokens delivered via HttpOnly, Secure, SameSite=Strict cookies. Implement three baseline roles: Administrator, Operator, Viewer. All mutating endpoints require authentication; destructive endpoints (delete video, delete clip, stop session) require Administrator role.

**Acceptance criteria:**
- [ ] `users` table with secure schema (no plaintext secrets)
- [ ] bcrypt password hashing at cost 12
- [ ] Login endpoint with rate limiting (5 attempts / 15 minutes / IP)
- [ ] JWT issued via HttpOnly+Secure+SameSite=Strict cookie
- [ ] `Depends(require_auth)` middleware blocks unauthenticated access
- [ ] `Depends(require_role("admin"))` enforcement on delete endpoints
- [ ] Frontend `AuthContext` with automatic redirect to login page
- [ ] Logout invalidates JWT on the server side (token revocation list)
- [ ] Session TTL set to 24 hours with sliding refresh
- [ ] Admin, Operator, Viewer seed users created by migration script
- [ ] Unit and integration tests cover auth success and failure paths
- [ ] Security review passed

**Dependencies:** COMP-101
**Blocks:** COMP-103 (audit log references user_id), COMP-300 (DSAR requires authenticated subject)

---

#### COMP-103 — Append-only audit log infrastructure

**Type:** Compliance · **Priority:** P0 · **Effort:** M · **Owner:** Backend

**Regime mapping:** GDPR Art. 30, 32; CCPA §1798.130(a)(5); KVKK Art. 16; SHIELD §899-bb(2)(b)

**Description:** Create an `audit_log` table with append-only semantics (database-level trigger prevents UPDATE or DELETE). Log every authenticated action that touches personal data: video upload, video view, video delete, clip create, clip download, clip delete, detection view, session start, session stop. Each entry contains user_id, action, resource_type, resource_id, metadata JSON, IP address (truncated per GDPR), and timestamp.

**Acceptance criteria:**
- [ ] `audit_log` table schema committed
- [ ] Database trigger enforces append-only
- [ ] Audit write helper (`audit_log.record(action, resource, user, metadata)`)
- [ ] All mutating endpoints call the helper
- [ ] IP addresses anonymised (last octet truncated for IPv4; last 80 bits for IPv6)
- [ ] Audit log retention set to 90 days (configurable)
- [ ] Admin endpoint to query audit log with pagination
- [ ] Integration tests verify audit writes on every covered action

**Dependencies:** COMP-102
**Blocks:** COMP-300 (DSAR uses audit log to prove access), COMP-400 (DPIA references audit log)

---

#### COMP-104 — Enable filesystem-level encryption on host volumes

**Type:** Security / Infra · **Priority:** P0 · **Effort:** S · **Owner:** Infra

**Regime mapping:** GDPR Art. 32; CCPA §1798.100(e); KVKK Art. 12; SHIELD §899-bb(2)(b)

**Description:** Interim solution for at-rest encryption before COMP-200/201 migrate to dedicated encrypted stores. Enable LUKS on on-premise hosts or encrypted EBS/GCE disks on cloud hosts. Document the key management procedure.

**Acceptance criteria:**
- [ ] Encrypted volume provisioned for staging environment
- [ ] Bind mount target (`backend/storage`) resides on encrypted volume
- [ ] Key rotation procedure documented in `docs/compliance/key-management.md`
- [ ] Recovery procedure tested (restore from encrypted backup)
- [ ] Runbook committed to repository

**Dependencies:** None
**Blocks:** Superseded by COMP-200/201 in Sprint 2

---

**Sprint 1 Exit Criteria:**
- No user-facing surface contains a materially false privacy claim.
- TLS active on staging; A+ on SSL Labs.
- Authentication and RBAC enforced on all mutating endpoints.
- Audit log writes verified for every covered action.
- Filesystem-level at-rest encryption active on staging.

---

## 9. Sprint 2 — Encryption and Storage Migration

**Theme:** Move data to encrypted, managed stores; enforce retention.
**Sprint Goal:** SQLite is replaced by PostgreSQL with TDE; uploads and clips live in object storage with server-side encryption; automated retention is active.

---

#### COMP-200 — Migrate SQLite to PostgreSQL with Transparent Data Encryption

**Type:** Infra / Compliance · **Priority:** P0 · **Effort:** L · **Owner:** Backend + Infra

**Regime mapping:** GDPR Art. 32; KVKK Art. 12

**Description:** Introduce PostgreSQL 16 with `pgcrypto` and Transparent Data Encryption (via managed service: AWS RDS, GCP Cloud SQL, Azure Database for PostgreSQL). Migrate existing schemas via Alembic. Retain the SQLite code path for local development with a feature flag, but disable it in production.

**Acceptance criteria:**
- [ ] SQLAlchemy dialect supports both SQLite (dev) and PostgreSQL (prod)
- [ ] Alembic migrations generated and applied
- [ ] Managed PostgreSQL instance provisioned with encryption-at-rest enabled
- [ ] Connection via TLS (`sslmode=require`)
- [ ] Backup schedule configured (daily, 30-day retention)
- [ ] Point-in-time recovery enabled
- [ ] Staging data migration rehearsed
- [ ] Production migration runbook committed
- [ ] Cost estimate documented

**Dependencies:** COMP-104 (interim encryption bridges the gap)
**Blocks:** COMP-201 (object storage migration follows)

---

#### COMP-201 — Move uploads and clips to object storage with server-side encryption

**Type:** Infra / Compliance · **Priority:** P0 · **Effort:** L · **Owner:** Backend + Infra

**Regime mapping:** GDPR Art. 32; CCPA §1798.100(e); KVKK Art. 12

**Description:** Replace the local filesystem (`storage/uploads`, `storage/clips`, `storage/incidents` if applicable) with an object store (S3 with SSE-KMS, or GCS with CMEK). Introduce a storage abstraction layer so local development can still use the filesystem. Signed URLs (short TTL) replace the static file server for streaming.

**Acceptance criteria:**
- [ ] Storage abstraction interface (`StorageBackend`) implemented
- [ ] `S3StorageBackend` and `GCSStorageBackend` concrete implementations
- [ ] `LocalStorageBackend` retained for development with feature flag
- [ ] SSE-KMS (or CMEK) configured on production bucket
- [ ] Bucket policy denies unencrypted uploads
- [ ] Signed URLs issued for video streaming with 15-minute TTL
- [ ] `/api/videos/{id}/stream` updated to redirect to signed URL
- [ ] ffmpeg clip generation reads and writes via the storage abstraction
- [ ] Staging migration rehearsed
- [ ] Production migration runbook committed

**Dependencies:** COMP-200
**Blocks:** COMP-301 (deletion must reach object storage)

---

#### COMP-202 — Automated retention policy enforcement

**Type:** Compliance · **Priority:** P1 · **Effort:** S · **Owner:** Backend

**Regime mapping:** GDPR Art. 5(1)(e); KVKK Art. 4, 7; BIPA §15(a) (≤3-year biometric retention)

**Description:** Introduce APScheduler (or a dedicated worker) that enforces per-data-type retention policies. Defaults: uploaded videos 365 days, clips 365 days, audit logs 90 days, pose landmarks 30 days, incident clips 30 days. Retention periods are configurable via environment variables.

**Acceptance criteria:**
- [ ] APScheduler integrated; job registered for each data type
- [ ] Retention periods configurable via environment variables
- [ ] Default values documented in `docs/compliance/retention-policy.md`
- [ ] Soft-delete pattern with 7-day recovery window before hard deletion
- [ ] Deletion events recorded in audit log
- [ ] Admin report endpoint exposes last-run status per job
- [ ] Integration test simulates a 400-day clock advance and verifies deletion

**Dependencies:** COMP-103 (audit log); COMP-201 (object storage for media deletion)
**Blocks:** COMP-301 (deletion workflow depends on retention infrastructure)

---

#### COMP-203 — Publish standalone privacy policy document

**Type:** Legal · **Priority:** P0 · **Effort:** S (engineering) + legal review · **Owner:** Legal + Frontend

**Regime mapping:** GDPR Art. 12–14; CCPA §1798.130; KVKK Art. 10

**Description:** Draft, legal-review, and publish a standalone privacy policy document covering all processing activities. The document is rendered at `/privacy` as a static page and linked from every consent modal, the footer, and the API documentation.

**Acceptance criteria:**
- [ ] Draft policy covers purposes, lawful bases, retention, rights, contact
- [ ] Legal review completed
- [ ] Published at `/privacy` in the frontend
- [ ] Machine-readable version at `/privacy.json`
- [ ] Linked from consent modals, footer, API docs
- [ ] Version history maintained (`privacy_policy_versions` table)
- [ ] Users notified of material changes via email (when email is available)

**Dependencies:** COMP-000 (counsel), COMP-100 (consent alignment)
**Blocks:** COMP-204 (granular consent references the policy sections)

---

#### COMP-204 — Granular purpose-specific consent with withdrawal UX

**Type:** Compliance / Feature · **Priority:** P1 · **Effort:** M · **Owner:** Fullstack

**Regime mapping:** GDPR Art. 6, 7; CPRA §1798.121; KVKK Art. 11; CPRA sensitive PI limit right

**Description:** Replace the current all-or-nothing consent boolean with a granular consent model. Purposes: (1) pose-based activity analysis, (2) clip retention and replay, (3) product telemetry, (4) security alerting via third-party channels. Users can opt in or out of each independently and withdraw consent from a settings page.

**Acceptance criteria:**
- [ ] `consent_purposes` table with one row per (user, purpose, granted_at, withdrawn_at)
- [ ] Consent modal shows each purpose with its own checkbox and explanation
- [ ] Backend enforces per-purpose consent at processing boundaries
- [ ] Settings page lists all granted consents with a one-click withdrawal button
- [ ] Withdrawal takes effect immediately and is logged
- [ ] Accessibility (WCAG 2.1 AA) verified
- [ ] Integration tests verify per-purpose enforcement

**Dependencies:** COMP-100, COMP-203
**Blocks:** COMP-300 (DSAR workflow depends on consent records)

---

**Sprint 2 Exit Criteria:**
- PostgreSQL with TDE is the production database.
- Uploaded media resides in encrypted object storage.
- Retention policy is enforced on schedule.
- Privacy policy is published and linked.
- Granular consent is operational.

---

## 10. Sprint 3 — Data Subject Rights (DSAR)

**Theme:** Give data subjects their rights in a verifiable, audit-friendly way.
**Sprint Goal:** Access, deletion, portability, and consent withdrawal rights are implemented end to end with admin-side review workflow.

---

#### COMP-300 — DSAR Access endpoint (right to know)

**Type:** Compliance / Feature · **Priority:** P1 · **Effort:** M · **Owner:** Backend + Frontend

**Regime mapping:** GDPR Art. 15; CCPA §1798.110; KVKK Art. 11

**Description:** Implement a "My Data" endpoint that returns all personal data the system holds about the authenticated user: uploaded videos, generated clips, consent events, audit log entries (scoped to self), and derived detection records. Produced as a structured JSON bundle and downloadable as a single archive.

**Acceptance criteria:**
- [ ] `GET /api/dsar/access` returns a JSON manifest
- [ ] `GET /api/dsar/access/download` returns a zip archive
- [ ] Archive includes all raw data types listed above
- [ ] Response is signed with a server key for integrity verification
- [ ] Request logged in audit trail
- [ ] Rate-limited to one request per 24 hours per user
- [ ] Admin view available for authorised staff to process requests on behalf of users
- [ ] Integration tests cover happy path and rate-limiting

**Dependencies:** COMP-102, COMP-103, COMP-204
**Blocks:** None

---

#### COMP-301 — DSAR Deletion endpoint with admin queue

**Type:** Compliance / Feature · **Priority:** P1 · **Effort:** M · **Owner:** Backend + Frontend

**Regime mapping:** GDPR Art. 17; CCPA §1798.105; KVKK Art. 7, 11

**Description:** Implement a "Delete my data" flow. User requests go into a review queue visible to administrators. Administrators confirm deletion, which cascades through the database, object storage, audit log (except for the deletion record itself), and backup tombstones. Legal hold flag overrides deletion for the duration specified by counsel.

**Acceptance criteria:**
- [ ] `POST /api/dsar/deletion` creates a request
- [ ] `GET /api/admin/dsar/pending` returns pending requests (admin-only)
- [ ] `POST /api/admin/dsar/{id}/approve` executes deletion
- [ ] Deletion cascades to PostgreSQL, object storage, and derived records
- [ ] Tombstone records remain to satisfy audit obligations
- [ ] Legal hold flag respected
- [ ] User receives confirmation via email (stubbed if email not available)
- [ ] Integration tests cover cascade completeness

**Dependencies:** COMP-102, COMP-201, COMP-202, COMP-300
**Blocks:** None

---

#### COMP-302 — DSAR Portability endpoint

**Type:** Compliance / Feature · **Priority:** P2 · **Effort:** S · **Owner:** Backend

**Regime mapping:** GDPR Art. 20; CCPA §1798.130; KVKK Art. 11

**Description:** Provide the user's structured data in a commonly used, machine-readable format (JSON primary, CSV secondary) suitable for transfer to another controller. Video files are provided as the original MP4.

**Acceptance criteria:**
- [ ] `GET /api/dsar/portability?format=json` returns structured JSON
- [ ] `GET /api/dsar/portability?format=csv` returns CSV export
- [ ] Video files included via signed URLs with 7-day TTL
- [ ] Schema documented in `docs/compliance/dsar-portability-schema.md`
- [ ] Integration tests verify format correctness

**Dependencies:** COMP-300
**Blocks:** None

---

#### COMP-303 — Consent withdrawal UX

**Type:** Compliance / Feature · **Priority:** P1 · **Effort:** S · **Owner:** Frontend

**Regime mapping:** GDPR Art. 7(3); CPRA §1798.121; KVKK Art. 11

**Description:** Withdrawing consent must be as easy as giving it. Add a `/settings/privacy` page that lists all granted consents and exposes a one-click withdrawal button per purpose. Withdrawal takes effect immediately and logs an event. Processing dependent on the withdrawn purpose stops within the next scheduler cycle.

**Acceptance criteria:**
- [ ] `/settings/privacy` page lists all consent purposes with status
- [ ] One-click withdrawal button per purpose with confirmation dialog
- [ ] Withdrawal event logged and audit trail updated
- [ ] Backend stops purpose-dependent processing within 5 minutes
- [ ] Email confirmation sent (stubbed if unavailable)
- [ ] Accessibility (WCAG 2.1 AA) verified

**Dependencies:** COMP-204
**Blocks:** None

---

#### COMP-304 — Children age gate and parental consent

**Type:** Compliance / Feature · **Priority:** P1 · **Effort:** M · **Owner:** Fullstack + Legal

**Regime mapping:** COPPA; GDPR Art. 8; KVKK Art. 6

**Description:** Introduce an age gate at account creation. Users who declare their age as under 13 (COPPA) or under 16 (GDPR default, configurable per member state) are routed to a parental consent flow. Unverified child accounts cannot process data.

**Acceptance criteria:**
- [ ] Age declaration field at signup
- [ ] Under-13 routed to parental consent flow
- [ ] Under-16 routed to parental consent flow in jurisdictions where this threshold applies
- [ ] Parental email verification required
- [ ] Unverified child accounts cannot upload or start streams
- [ ] Age-gate logic covered by integration tests
- [ ] Legal sign-off on flow wording

**Dependencies:** COMP-102, COMP-204
**Blocks:** None

---

**Sprint 3 Exit Criteria:**
- Users can request access, deletion, portability, and consent withdrawal.
- Admin-side review queue operational.
- Children's data flow gated and documented.

---

## 11. Sprint 4 — Assessment and Documentation

**Theme:** Document everything; satisfy procedural duties.
**Sprint Goal:** DPIA, ROPA, incident response runbook, and data processing agreements are published and approved.

---

#### COMP-400 — Data Protection Impact Assessment (DPIA)

**Type:** Compliance / Legal · **Priority:** P0 · **Effort:** XL (5 engineering days + legal review) · **Owner:** DPO + Backend + Legal

**Regime mapping:** GDPR Art. 35(3)(c) (mandatory for systematic surveillance); KVKK Art. 13 (analogous risk assessment)

**Description:** Conduct a formal DPIA for the video intelligence processing activity. Identify risks, mitigations, and residual risk. If residual high risk remains, initiate prior consultation with the supervisory authority (Art. 36).

**Acceptance criteria:**
- [ ] Processing context and purposes documented
- [ ] Necessity and proportionality assessment completed
- [ ] Risks to rights and freedoms identified and scored
- [ ] Mitigations mapped to specific tickets in this plan
- [ ] Residual risk scored
- [ ] DPO sign-off
- [ ] DPIA published to `docs/compliance/dpia-v1.md`
- [ ] Schedule for next review set (12 months or on material change)

**Dependencies:** COMP-000; all Sprint 1–3 work
**Blocks:** Production deployment

---

#### COMP-401 — Records of Processing Activities (ROPA)

**Type:** Compliance / Legal · **Priority:** P1 · **Effort:** L · **Owner:** DPO + Backend

**Regime mapping:** GDPR Art. 30; KVKK VERBIS requirements

**Description:** Prepare the Article 30 ROPA document covering all processing activities, data categories, recipients, retention, and security measures. The ROPA is a living document maintained alongside the code base.

**Acceptance criteria:**
- [ ] ROPA template adopted
- [ ] All processing activities enumerated
- [ ] Data categories, recipients, retention, and security mapped
- [ ] Published to `docs/compliance/ropa-v1.md`
- [ ] Review cadence set (quarterly)
- [ ] Change control process documented

**Dependencies:** COMP-400
**Blocks:** COMP-501 (VERBIS registration uses the ROPA)

---

#### COMP-402 — Incident response runbook and breach notification playbook

**Type:** Security / Legal · **Priority:** P0 · **Effort:** M · **Owner:** Infra + Legal

**Regime mapping:** GDPR Art. 33 (72-hour); CCPA §1798.82; KVKK; NY SHIELD §899-aa

**Description:** Produce an incident response runbook covering detection, containment, eradication, recovery, and notification. Specifically include the 72-hour notification deadline mechanics and the contact list for regulators in each jurisdiction.

**Acceptance criteria:**
- [ ] Runbook published to `docs/compliance/incident-response.md`
- [ ] On-call rotation defined
- [ ] Regulator contact list per jurisdiction
- [ ] 72-hour notification template drafted in English, Spanish, Turkish
- [ ] Tabletop exercise conducted
- [ ] After-action review template committed

**Dependencies:** COMP-103 (audit log supports forensics); COMP-000
**Blocks:** Production deployment

---

#### COMP-403 — Data Processing Agreement (DPA) templates

**Type:** Legal · **Priority:** P1 · **Effort:** S (engineering) + legal review · **Owner:** Legal

**Regime mapping:** GDPR Art. 28; CCPA §1798.140(ag)

**Description:** Draft DPA templates for all sub-processors (cloud providers, email, monitoring, analytics). Execute DPAs with each vendor before production traffic is enabled.

**Acceptance criteria:**
- [ ] DPA template for each current vendor
- [ ] Standard Contractual Clauses (SCCs) attached for EU transfers
- [ ] Signed DPAs on file with legal
- [ ] Vendor register maintained in `docs/compliance/vendor-register.md`

**Dependencies:** COMP-000; COMP-201 (defines cloud storage vendors)
**Blocks:** Production deployment

---

#### COMP-404 — Model card and fairness assessment

**Type:** Compliance · **Priority:** P2 · **Effort:** M · **Owner:** ML + DPO

**Regime mapping:** EU AI Act; NYC Local Law 144; GDPR Art. 22, Recital 71

**Description:** Publish a model card for the BiLSTM classifier following the Google Model Cards template. Include intended use, training data provenance (DCSASS), known limitations, fairness evaluation across available demographic slices, and decision boundary documentation.

**Acceptance criteria:**
- [ ] Model card published to `docs/ml/model-card-bilstm-v5.md`
- [ ] Training data provenance documented
- [ ] Evaluation metrics disaggregated where possible
- [ ] Known limitations stated
- [ ] Intended use and out-of-scope uses listed
- [ ] DPO sign-off

**Dependencies:** COMP-002
**Blocks:** None

---

**Sprint 4 Exit Criteria:**
- DPIA, ROPA, incident response runbook, DPA templates, and model card are published and approved.
- No outstanding procedural compliance gap under GDPR or KVKK.

---

## 12. Sprint 5 — Jurisdiction-Specific Hardening

**Theme:** Address the high-liability jurisdictions directly.
**Sprint Goal:** Illinois BIPA, Turkey KVKK VERBIS, California CPRA sensitive-PI rights, and NY SHIELD documentation obligations are addressed.

---

#### COMP-500 — Illinois BIPA consent flow with 3-year retention schedule

**Type:** Compliance / Feature · **Priority:** P1 · **Effort:** M · **Owner:** Fullstack + Legal

**Regime mapping:** BIPA §15

**Description:** For any Illinois-based users (detected via IP geolocation or self-declaration), require a BIPA §15(b) written informed consent before any pose extraction. Retention period is capped at three years or until the purpose is satisfied, whichever is shorter. Publish a BIPA-specific retention and destruction schedule.

**Acceptance criteria:**
- [ ] Illinois detection by IP or declared state
- [ ] Separate BIPA consent modal with the §15(b) required elements
- [ ] Consent captured as a standalone record with signature / click timestamp
- [ ] 3-year retention ceiling enforced in the retention scheduler
- [ ] BIPA destruction schedule published
- [ ] Legal sign-off

**Dependencies:** COMP-100, COMP-202, COMP-204
**Blocks:** Illinois market launch

---

#### COMP-501 — Turkey VERBIS registration

**Type:** Legal · **Priority:** P1 · **Effort:** L (engineering) + 4–8 weeks administrative · **Owner:** Legal + DPO

**Regime mapping:** KVKK Art. 16

**Description:** Complete VERBIS (Veri Sorumluları Sicil Bilgi Sistemi) registration for the Turkish market. The ROPA prepared in COMP-401 provides the technical content. Register data controller and contact person (irtibat kişisi) details.

**Acceptance criteria:**
- [ ] Data controller and contact person appointed
- [ ] ROPA translated to Turkish where required
- [ ] VERBIS application submitted
- [ ] Confirmation of registration received
- [ ] Annual review scheduled

**Dependencies:** COMP-401
**Blocks:** Turkish market launch

---

#### COMP-502 — California CPRA sensitive-PI limit right

**Type:** Compliance / Feature · **Priority:** P1 · **Effort:** M · **Owner:** Fullstack + Legal

**Regime mapping:** CPRA §1798.121

**Description:** Implement the "Limit the Use and Disclosure of My Sensitive Personal Information" right required by CPRA for sensitive PI. Expose a user-facing toggle that restricts processing of pose data (as behavioural biometric under the broad reading) to the specific purposes permitted under §1798.121(b).

**Acceptance criteria:**
- [ ] "Limit Sensitive PI" toggle on `/settings/privacy`
- [ ] Backend enforces the limitation in processing pipelines
- [ ] Homepage "Do Not Sell or Share" link per CPRA §1798.135(a)(1)
- [ ] Integration tests verify enforcement

**Dependencies:** COMP-204, COMP-303
**Blocks:** California market launch

---

#### COMP-503 — EU data residency routing

**Type:** Infra · **Priority:** P2 · **Effort:** L · **Owner:** Infra

**Regime mapping:** GDPR Chapter V (Art. 44–50)

**Description:** For EU-origin traffic, route to an EU-resident infrastructure region. Introduce a routing layer (Cloudflare Workers, AWS Route 53 geolocation) that inspects source IP and directs traffic. For traffic that cannot be routed (e.g., mixed origin), Standard Contractual Clauses cover transfers.

**Acceptance criteria:**
- [ ] EU region infrastructure provisioned
- [ ] Routing layer deployed
- [ ] SCCs executed with all sub-processors
- [ ] Transfer Impact Assessment (TIA) completed
- [ ] Cost impact documented

**Dependencies:** COMP-201, COMP-403
**Blocks:** EU market launch

---

#### COMP-504 — NY SHIELD Act reasonable security documentation

**Type:** Security / Legal · **Priority:** P2 · **Effort:** S · **Owner:** Infra + Legal

**Regime mapping:** NY SHIELD §899-bb(2)(b)

**Description:** Produce the reasonable security programme documentation required by the SHIELD Act. Small business exception does not apply. The programme incorporates administrative, technical, and physical safeguards from earlier sprints.

**Acceptance criteria:**
- [ ] Reasonable Security Programme document published
- [ ] Administrative, technical, physical safeguards enumerated
- [ ] Workforce training documented
- [ ] Vendor oversight documented
- [ ] Annual review cadence set

**Dependencies:** COMP-102, COMP-103, COMP-402
**Blocks:** NY market operation

---

**Sprint 5 Exit Criteria:**
- High-liability jurisdictions have specific, documented compliance pathways.
- Market launch checklist can be satisfied for Illinois, Turkey, California, and New York.

---

## 13. Sprint 6 — Observability and Continuous Programs Bootstrap

**Theme:** Make compliance observable and continuous.
**Sprint Goal:** Structured logs, metrics, drift monitoring, and recurring review cadences are live.

---

#### COMP-600 — Privacy-relevant metrics dashboard

**Type:** Infra · **Priority:** P2 · **Effort:** M · **Owner:** Infra + Backend

**Regime mapping:** GDPR Art. 32 (demonstrability); KVKK Art. 12

**Description:** Expose Prometheus metrics for compliance-relevant signals: DSAR request count and latency, consent grant and withdrawal counts, retention cron run status, authentication failure rate, model confidence distribution, incident clip generation count. Publish a Grafana dashboard.

**Acceptance criteria:**
- [ ] `/metrics` endpoint exposes Prometheus format
- [ ] Counters, histograms, and gauges defined per signal
- [ ] Grafana dashboard JSON committed to `observability/grafana/compliance.json`
- [ ] Alerting thresholds set (e.g., DSAR latency > 48h triggers page)
- [ ] Documentation in `docs/observability/compliance-metrics.md`

**Dependencies:** COMP-300, COMP-301, COMP-202
**Blocks:** None

---

#### COMP-601 — Quarterly access review process

**Type:** Compliance · **Priority:** P2 · **Effort:** S · **Owner:** Programme lead

**Regime mapping:** GDPR Art. 32; ISO 27001 A.9

**Description:** Establish a quarterly access review process. Every quarter, a report is generated listing all users, their roles, and their access patterns. The compliance working group reviews and revokes unused access.

**Acceptance criteria:**
- [ ] Access review report generator script
- [ ] Calendar invites set for the next four quarters
- [ ] Review template in `docs/compliance/access-review-template.md`
- [ ] First review conducted and documented

**Dependencies:** COMP-102, COMP-103
**Blocks:** None

---

#### COMP-602 — Monthly data deletion audit

**Type:** Compliance · **Priority:** P2 · **Effort:** S · **Owner:** Backend

**Regime mapping:** GDPR Art. 5(1)(e); KVKK Art. 4

**Description:** Schedule a monthly audit script that verifies that retention policies are being enforced. The script counts records per data type, compares against expected retention bounds, and flags anomalies.

**Acceptance criteria:**
- [ ] Audit script committed
- [ ] Scheduled via APScheduler
- [ ] Report emailed to the compliance working group
- [ ] Anomaly threshold triggers a P1 ticket automatically

**Dependencies:** COMP-202
**Blocks:** None

---

#### COMP-603 — Model drift monitoring

**Type:** ML / Compliance · **Priority:** P2 · **Effort:** M · **Owner:** ML

**Regime mapping:** EU AI Act; GDPR Art. 5(1)(d) (accuracy principle)

**Description:** Introduce statistical monitoring of the feature distribution (231-dim pose vector) at inference time. Compare against the training distribution baseline. Raise an alert when drift exceeds a configured threshold, indicating the model may need retraining.

**Acceptance criteria:**
- [ ] Training distribution baseline saved
- [ ] Inference-time distribution computed in a sliding window
- [ ] KL divergence or PSI metric computed and emitted as metric
- [ ] Alert configured at threshold
- [ ] Runbook documents the retrain workflow

**Dependencies:** COMP-404, COMP-600
**Blocks:** None

---

#### COMP-604 — Annual penetration test procurement

**Type:** Security · **Priority:** P1 · **Effort:** S (engineering) + external vendor cost · **Owner:** Infra + Programme lead

**Regime mapping:** GDPR Art. 32; SOC 2 CC4.1

**Description:** Procure an external penetration test. Scope covers the public API, authentication, authorisation, and data exfiltration paths. Remediate findings before the next review cycle.

**Acceptance criteria:**
- [ ] Vendor selected and contract executed
- [ ] Scope document signed
- [ ] Test conducted
- [ ] Report delivered
- [ ] Findings triaged into remediation tickets
- [ ] Retest scheduled

**Dependencies:** COMP-102, COMP-103, COMP-200, COMP-201
**Blocks:** None

---

**Sprint 6 Exit Criteria:**
- Compliance signals are visible in the observability stack.
- Recurring review cadences are scheduled and running.
- Penetration test engagement is active.

---

## 14. Parallel Long-Running Certification Track

These work streams run in parallel to the sprint cadence and have timelines measured in months rather than weeks.

---

#### COMP-900 — SOC 2 Type I preparation (6 months)

**Type:** Compliance · **Priority:** P2 · **Effort:** Multi-month, multi-stakeholder · **Owner:** Programme lead + external auditor

**Description:** Engage a SOC 2 auditor for a Type I attestation. Map existing controls to Trust Services Criteria (Security, Availability, Confidentiality, Privacy, Processing Integrity). Close gaps iteratively.

**Success criteria:**
- Type I report issued
- Readiness for Type II evidence window established

---

#### COMP-901 — SOC 2 Type II (12 months including 6-month evidence window)

**Type:** Compliance · **Priority:** P2 · **Effort:** Multi-month · **Owner:** Programme lead + external auditor

**Description:** Operate controls continuously during the evidence window, collecting automated and manual evidence. Submit for Type II attestation.

**Success criteria:**
- Type II report issued
- Enterprise procurement blockers removed

---

#### COMP-902 — ISO / IEC 27001 certification (12–18 months)

**Type:** Compliance · **Priority:** P3 · **Effort:** Multi-month · **Owner:** Programme lead + external auditor

**Description:** Implement an Information Security Management System (ISMS) meeting ISO/IEC 27001 requirements. Conduct internal audit, management review, and stage 1 / stage 2 external audit.

**Success criteria:**
- ISO/IEC 27001 certificate issued
- Statement of Applicability (SoA) published

---

#### COMP-903 — C5 attestation (Germany) — if EU public-sector market is targeted

**Type:** Compliance · **Priority:** P3 · **Effort:** Multi-month · **Owner:** Programme lead

**Description:** Prepare for the German BSI C5 attestation required by public-sector customers in Germany. Overlaps significantly with ISO/IEC 27001.

**Success criteria:**
- C5 attestation issued
- German public-sector market accessible

---

## 15. Risk Register

| Risk | Likelihood | Impact | Mitigation | Owner |
|---|---|---|---|---|
| Legal counsel unavailable within 2 business days for Sprint 1 ticket questions | Medium | High | Retain a second firm on standby; batch questions weekly | Programme lead |
| Managed PostgreSQL cost exceeds budget | Low | Medium | Use smaller instance initially; scale up once traffic justifies | Infra |
| Object storage migration breaks ffmpeg clip generation | Medium | High | Feature flag with gradual rollout; maintain local filesystem fallback during migration | Backend |
| DPIA reveals residual high risk requiring supervisory authority consultation | Medium | High | Budget 8 additional weeks for consultation before production launch | DPO |
| BIPA consent flow misses required element, creating class-action exposure | Low | Very High | Two-lawyer review of the consent wording; template from Illinois-specialised firm | Legal |
| VERBIS registration rejected | Low | Medium | Engage a Turkish privacy lawyer familiar with VERBIS; retry with corrections | Legal |
| Retention cron deletes data inside an unrelated legal hold | Medium | Very High | Legal hold flag at the record level; deletion job respects the flag | Backend |
| Penetration test finds P0 vulnerabilities | Medium | High | Budget for 1 remediation sprint immediately after the test | Infra |
| Team size reduced mid-programme | Medium | High | Document everything; keep ticket acceptance criteria precise so handover is possible | Programme lead |
| Model drift monitoring fires continuously after deployment | Medium | Medium | Conservative threshold in first month; tighten after baseline established | ML |

---

## 16. Success Metrics per Sprint

| Sprint | Primary Metric | Target |
|---|---|---|
| **Sprint 0** | Governance artifacts published | Counsel engaged, working group chartered, backlog in tracker |
| **Sprint 1** | Misrepresentation removed; TLS active; auth enforced | 0 false claims in UI; SSL Labs A+; 100 % of mutating endpoints gated |
| **Sprint 2** | Encryption at rest; retention enforced | 100 % of personal data in encrypted store; retention cron green |
| **Sprint 3** | DSAR rights operational | < 48 h response SLO on access, deletion, portability |
| **Sprint 4** | DPIA and ROPA published | Both documents approved by DPO and counsel |
| **Sprint 5** | Jurisdiction-specific pathways open | Illinois, Turkey, California, NY market launch checklists satisfied |
| **Sprint 6** | Compliance observable and continuous | Grafana dashboard live; quarterly review scheduled; pentest contract executed |

---

## 17. Cross-Reference Appendix

This sprint plan is derived from Section 11 of [LegalandOtherCompliances.md](./LegalandOtherCompliances.md). The following table maps the source roadmap items to the tickets above.

| Source (LegalandOtherCompliances.md Section 11) | Sprint | Ticket(s) |
|---|---|---|
| Align consent modal language with the actual data flow | Sprint 1 | COMP-100 |
| Introduce TLS termination via nginx or Traefik | Sprint 1 | COMP-101 |
| Implement JWT-based authentication and role-based access control | Sprint 1 | COMP-102 |
| Implement append-only audit logging | Sprint 1 | COMP-103 |
| Implement an automated retention policy with configurable TTL | Sprint 2 | COMP-202 |
| Migrate SQLite to PostgreSQL with Transparent Data Encryption | Sprint 2 | COMP-200 |
| Move clip and upload storage from local filesystem to object storage with server-side encryption | Sprint 2 | COMP-201 |
| Publish a standalone privacy policy document | Sprint 2 | COMP-203 |
| Implement DSAR endpoints (access, deletion, portability) | Sprint 3 | COMP-300, COMP-301, COMP-302 |
| Design and execute a DPIA for the surveillance processing activity | Sprint 4 | COMP-400 |
| Prepare ROPA and, for Turkish operation, complete VERBIS registration | Sprint 4, Sprint 5 | COMP-401, COMP-501 |
| Implement incident response runbook with 72-hour breach notification workflow | Sprint 4 | COMP-402 |
| Implement granular, purpose-specific consent with a frictionless withdrawal experience | Sprint 2, Sprint 3 | COMP-204, COMP-303 |
| Implement children's data safeguards with age gating | Sprint 3 | COMP-304 |
| Implement BIPA-compliant written informed consent flow for Illinois users | Sprint 5 | COMP-500 |
| Quarterly access review | Sprint 6 | COMP-601 |
| Annual penetration testing | Sprint 6 | COMP-604 |
| Privacy impact assessment refresh | Ongoing | COMP-400 (annually) |
| Model card maintenance and bias monitoring | Sprint 4, Sprint 6 | COMP-404, COMP-603 |
| Data deletion audit | Sprint 6 | COMP-602 |
| SOC 2 Type I, Type II, ISO 27001, C5 | Parallel | COMP-900 through COMP-903 |

---

**End of Document**
