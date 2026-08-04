# Legal and Other Compliance Assessment

**Project:** Video Intelligence Platform (Prototype)
**Document Version:** 1.1
**Date:** April 10, 2026
**Author:** Kaan Taplamacıoğlu
**Audience:** Engineering / Technical Review
**Status:** Self-Assessment

---

## Table of Contents

1. [Document Purpose and Scope](#1-document-purpose-and-scope)
2. [Executive Summary](#2-executive-summary)
3. [Disclaimer](#3-disclaimer)
4. [System Under Review](#4-system-under-review)
5. [Applicable Regulatory Landscape](#5-applicable-regulatory-landscape)
6. [Compliance Requirements Matrix](#6-compliance-requirements-matrix)
7. [Legal Analysis: Classification of Pose Landmarks as Biometric Data](#7-legal-analysis-classification-of-pose-landmarks-as-biometric-data)
8. [Comparison to Industry Privacy Commitments](#8-comparison-to-industry-privacy-commitments)
9. [Privacy-Positive Design Elements Present in the Prototype](#9-privacy-positive-design-elements-present-in-the-prototype)
10. [Identified Gaps and Risk Analysis](#10-identified-gaps-and-risk-analysis)
11. [Roadmap to Production Compliance](#11-roadmap-to-production-compliance)
12. [Honest Communication Guidance](#12-honest-communication-guidance)
13. [Conclusion](#13-conclusion)
14. [Appendix A — Glossary](#appendix-a--glossary)
15. [Appendix B — Regulatory References](#appendix-b--regulatory-references)
16. [Appendix C — Document Revision History](#appendix-c--document-revision-history)

---

## 1. Document Purpose and Scope

This document provides a transparent, engineering-level compliance assessment of the Video Intelligence Platform prototype in its current state. Its purpose is threefold:

1. **Honesty.** To state the prototype's present compliance posture without overclaiming or understating.
2. **Awareness.** To demonstrate an informed understanding of the legal and regulatory landscape governing video surveillance and biometric analysis in the jurisdictions a real-world retail surveillance vendor would operate in or be commercially adjacent to (United States — federal, California, Illinois, New York, Texas, Virginia, Colorado; Turkey; European Union; United Kingdom).
3. **Forward Readiness.** To provide a concrete, sequenced remediation roadmap that closes each identified gap when the prototype is advanced toward production.

This document is not a marketing claim of compliance. It is a candid internal audit intended to be read alongside the code, and to serve as a reference point for any future conversation about productionisation, customer commitments, or regulator inquiries.

**In scope:** The four primary regulatory regimes directly relevant to the prototype's processing activity (GDPR, CCPA/CPRA, KVKK, NY SHIELD Act), plus targeted analysis of Illinois BIPA, New York City's Biometric Identifier Information Law, the FTC Act §5, and COPPA.

**Out of scope:** Sector-specific regulations (HIPAA, GLBA, PCI DSS), certification programs (ISO 27001, SOC 2) beyond summary mention, and jurisdictions not surveyed below. Their omission does not imply non-applicability; production deployment should include an expanded review under qualified counsel.

---

## 2. Executive Summary

The prototype, in its present state, **does not meet production-grade compliance requirements** under any of the major regulatory regimes surveyed. This outcome is consistent with, and expected of, a time-constrained prototype whose scope explicitly excluded legal-grade hardening.

Notwithstanding the compliance gaps, the prototype exhibits several deliberate, privacy-positive design choices — including consent modal gating, in-memory-only live-stream frame handling, and browser-side webcam pose inference — that demonstrate a privacy-by-design intent and would meaningfully accelerate remediation in a production setting.

**Principal findings:**

- **No data-at-rest encryption** is implemented. The SQLite database and user-supplied MP4 files are persisted in cleartext on the host filesystem.
- **No data-in-transit encryption** is configured by default. Development runs on HTTP and unencrypted WebSockets.
- **No authentication, authorization, or audit logging** is present. Any party with network access to the backend may upload, view, or delete content.
- **No formal Data Subject Access Request (DSAR) workflow** exists. Deletion is available only via a manual API call.
- **No automated data retention or deletion policy** is enforced. Data persists indefinitely.
- A **material inconsistency** exists between the consent modal's representation ("no identifiable imagery … stored") and the implementation (raw uploaded video files persist on disk in their original form). This inconsistency is addressed in Section 8.1 as a priority remediation item.
- Conversely, the **live-stream pipeline does not persist raw frames to disk**, and **webcam pose inference is performed client-side in the browser**. Both are meaningful privacy-preserving architectural choices.

**Overall posture:** Prototype. Not fit for production deployment without the remediation described in Section 11. Fit for engineering review and demonstration with the honest framing described in Section 12.

---

## 3. Disclaimer

The author is not a licensed attorney. This document is an engineering-level assessment of the prototype's alignment with published regulatory requirements. It does not constitute legal advice.

Regulatory interpretation evolves through case law, supervisory-authority guidance, and statutory amendment. Fines and penalties cited herein are illustrative and reflect the author's understanding as of the document date; actual exposure depends on facts, forum, and counsel.

Any production deployment of the software described herein should be reviewed by:

- Qualified privacy counsel licensed in each relevant jurisdiction,
- A Data Protection Officer (DPO) where GDPR Article 37 or comparable obligations apply,
- For Turkish deployments, a VERBIS-registered data controller representative,
- For Illinois deployments, counsel familiar with Illinois BIPA class-action case law.

The author welcomes correction from qualified legal and compliance professionals on any point made below.

---

## 4. System Under Review

### 4.1 System Description

The project is a fullstack video intelligence prototype consisting of:

- **Backend:** Python 3.11, FastAPI, SQLite via SQLAlchemy, OpenCV, ffmpeg, MediaPipe Tasks API, TensorFlow / Keras
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, Video.js, MediaPipe Tasks Vision (JavaScript / WebAssembly)
- **Deployment:** Docker Compose (development topology), host bind-mount for persistent storage
- **Machine Learning Pipeline:** Two-tier classifier —
  - Tier 1 (MobileNetV2 frame-level binary classifier, fallback)
  - Tier 2 (MediaPipe BlazePose GHUM → 231-dimensional feature vector → StandardScaler → BiLSTM binary classifier → scipy peak-detection post-processing)

### 4.2 Data Inventory

The following table catalogues every category of data that the prototype collects, derives, or persists.

| # | Data Category | Storage Location | Format | At-Rest Encryption | Retention Control |
|---|---|---|---|---|---|
| 1 | Uploaded source video files (user-supplied MP4) | `storage/uploads/{uuid}.mp4` | Cleartext MP4 container | **None** | Manual deletion only |
| 2 | Generated clip files | `storage/clips/{uuid}.mp4` | Cleartext MP4 container | **None** | Manual deletion only |
| 3 | Video, clip, and detection metadata | `storage/app.db` (SQLite) | Cleartext database file | **None** | Manual deletion only |
| 4 | Detection results (labels, confidence, timestamps) | `detection_results` table | Cleartext rows | **None** | Cascade with parent video |
| 5 | Pose landmarks (uploaded video pipeline) | Computed on demand; not persisted | N/A | N/A | Ephemeral |
| 6 | Live webcam frames (server-side classify path) | Not processed server-side — backend never calls `cv2.VideoCapture(0)` for webcam sessions | N/A | N/A | N/A |
| 7 | Live RTSP frames | In-memory pipeline only | N/A | N/A | Not persisted |
| 8 | Stream session metadata | `stream_sessions` table | Cleartext rows | **None** | Manual deletion only |
| 9 | Consent flag | `stream_sessions.consent_given` | Boolean column | **None** | Linked to session lifetime |
| 10 | Authentication credentials | Not collected | N/A | N/A | N/A |
| 11 | Audit log | Not implemented | N/A | N/A | N/A |
| 12 | Browser-side pose landmarks (live webcam, canvas overlay) | Client memory only | Transient React state (33 × `NormalizedLandmark`) | N/A | Discarded on next frame |
| 13 | Browser MediaRecorder video blob (live webcam clip recording) | Client memory only (`Blob[]` chunks in `recordingChunksRef`) | MP4 (Chrome/Safari) or WebM (Firefox) timeslice chunks | N/A | Discarded on stream release, session stop, or explicit "Save to Library" (which uploads to server as data category #1 + #2) |
| 14 | Pose feature vectors in transit to `/classify-pose` | HTTP request body only; not persisted server-side | `list[list[float]]` 20 × 132 floats | TLS recommended for production | Processed synchronously and discarded; only derived `StreamDetection` row may persist if `session_id` provided and threshold crossed |
| 15 | Stream detection events (browser-classified) | `stream_detections` table (only when `classify-pose` called with `session_id` and threshold met) | Cleartext rows | **None** | Manual deletion only |
| 16 | Committed demo videos (public-source research samples) | `backend/demo_videos/*.mp4` (in repository) | Cleartext MP4 | **None** | Never deleted (read-only source for seed) |

### 4.3 Data Subjects

The prototype may process personal data pertaining to:

- Individuals visible in user-uploaded surveillance footage,
- Individuals visible in live webcam streams when the operator selects the webcam source,
- Individuals visible in RTSP camera feeds when the operator configures such a source.

No operator identity is collected, as no user accounts exist in the current implementation.

### 4.4 Processing Purposes

- Video metadata extraction (duration, frame count, resolution, FPS)
- Pose-based behavioural analysis and suspicious activity classification
- Clip generation for review and evidence preservation
- Real-time alert delivery to the operator interface via WebSocket

### 4.5 Personal Data Categories Potentially Present

- **General personal data.** Faces, voice audio tracks, gait, clothing, licence plates, and other identifying visual elements present in source video.
- **Behavioural — potentially biometric — data.** MediaPipe-derived pose landmarks (33 keypoints per frame). The regulatory classification of this derived data is analysed in Section 7.
- **Special-category data (GDPR Art. 9 / KVKK Art. 6).** Potentially present in source video if subjects include children, identifiable individuals in sensitive contexts, or content revealing racial or ethnic origin, religious beliefs, or health status.

---

## 5. Applicable Regulatory Landscape

The following statutes and regulations are potentially relevant to a video surveillance and biometric analysis application deployed in, or serving data subjects located in, jurisdictions relevant to a typical retail surveillance vendor.

### 5.1 European Union

- **General Data Protection Regulation (GDPR)**, Regulation (EU) 2016/679
- Member-state implementing legislation (applied case by case)

### 5.2 United Kingdom

- **UK GDPR** (post-Brexit UK adaptation)
- **Data Protection Act 2018**

### 5.3 United States — Federal

- **Federal Trade Commission Act, Section 5** — prohibition of unfair or deceptive acts or practices
- **Children's Online Privacy Protection Act (COPPA)** — data of children under thirteen
- **Video Privacy Protection Act (VPPA)** — narrow scope, relevant as background

### 5.4 United States — State Level

- **California Consumer Privacy Act (CCPA)**, Cal. Civ. Code §1798.100 et seq.
- **California Privacy Rights Act (CPRA)** — amending CCPA, effective January 1, 2023
- **New York SHIELD Act** — General Business Law §899-aa and §899-bb
- **New York City Biometric Identifier Information Law**, NYC Admin. Code §22-1201 et seq.
- **Illinois Biometric Information Privacy Act (BIPA)**, 740 ILCS 14/1 et seq.
- **Texas Capture or Use of Biometric Identifier Act (CUBI)**, Tex. Bus. & Com. Code §503.001
- **Texas Data Privacy and Security Act (TDPSA)** — effective July 1, 2024
- **Virginia Consumer Data Protection Act (VCDPA)** — effective January 1, 2023
- **Colorado Privacy Act (CPA)** — effective July 1, 2023
- **Connecticut Data Privacy Act (CTDPA)**
- **Utah Consumer Privacy Act (UCPA)**
- **Washington My Health My Data Act** — potentially applicable to biometric-adjacent data

### 5.5 Turkey

- **Kişisel Verilerin Korunması Kanunu (KVKK)**, Law No. 6698
- **VERBIS** (Veri Sorumluları Sicil Bilgi Sistemi) registration obligation for qualifying data controllers
- **KVK Kurulu** (Personal Data Protection Board) interpretive decisions and guidelines

### 5.6 Additional Frameworks Considered

- **ISO/IEC 27001** — Information Security Management System
- **SOC 2 Type II** — Trust Services Criteria, commonly required in enterprise procurement
- **NIST Cybersecurity Framework** and **NIST Privacy Framework** — reference models for controls and governance
- **EU AI Act (Regulation (EU) 2024/1689)** — risk-based regulation of AI systems, applicable to biometric categorisation and surveillance-adjacent AI

---

## 6. Compliance Requirements Matrix

The matrix below evaluates the prototype against the principal requirements of the four most directly relevant regimes. Cells are marked as Compliant (✓), Partially Compliant (~), Non-Compliant (✗), or Not Applicable (—).

### 6.1 Substantive Requirements Matrix

| # | Requirement | GDPR | CCPA / CPRA | KVKK | NY SHIELD | Prototype Status |
|---|---|---|---|---|---|---|
| 1 | Published privacy notice / policy document | Art. 12–14 | §1798.130 | Art. 10 | §899-bb(2) | ✗ Consent modal text only; no standalone policy |
| 2 | Lawful basis for processing (consent or equivalent) | Art. 6 | Opt-out framework | Art. 5–6 | — | ~ Captured as boolean; not granular or purpose-specific |
| 3 | Explicit consent for sensitive / biometric data | Art. 9(2)(a) | §1798.121 (sensitive PI limit right) | Art. 6 (special category) | — | ✗ No tiered consent; all-or-nothing |
| 4 | Right to withdraw consent as easily as given | Art. 7(3) | Right to opt-out | Art. 11 | — | ✗ No withdrawal mechanism |
| 5 | Right of access by data subject | Art. 15 | §1798.110 | Art. 11 | — | ✗ Not implemented |
| 6 | Right to rectification | Art. 16 | §1798.106 (CPRA) | Art. 11 | — | ✗ Not implemented |
| 7 | Right to erasure / deletion | Art. 17 | §1798.105 | Art. 7, 11 | — | ~ Manual delete endpoint exists; no DSAR workflow |
| 8 | Right to data portability | Art. 20 | §1798.130 | Art. 11 | — | ✗ Not implemented |
| 9 | Right to object to automated decision-making | Art. 22 | — | Art. 11 | — | ✗ Not implemented |
| 10 | Encryption of personal data at rest | Art. 32 | §1798.100(e) | Art. 12 | §899-bb(2)(b) | ✗ Not implemented |
| 11 | Encryption of personal data in transit | Art. 32 | §1798.100(e) | Art. 12 | §899-bb(2)(b) | ✗ Not configured by default |
| 12 | Access control and authentication | Art. 32 | §1798.100(e) | Art. 12 | §899-bb(2)(b) | ✗ Not implemented |
| 13 | Audit logging of personal-data access | Art. 30, 32 | §1798.130(a)(5) | Art. 16 | §899-bb(2)(b) | ✗ Not implemented |
| 14 | Records of Processing Activities (ROPA) | Art. 30 | — | Art. 16 (VERBIS) | — | ✗ Not prepared |
| 15 | Data Protection Impact Assessment (DPIA / PIA) | Art. 35 (mandatory for systematic surveillance) | Risk assessment under CPRA | Art. 13 | — | ✗ Not conducted |
| 16 | Data breach notification procedure | Art. 33 (72 hours) | §1798.82 | Art. 12/5 | §899-aa | ✗ No incident response runbook |
| 17 | Data retention policy and enforced deletion | Art. 5(1)(e) | §1798.100(a)(3) | Art. 4, 7 | — | ✗ Indefinite retention |
| 18 | Designation of a DPO (where applicable) | Art. 37 | — | Art. 16 (irtibat kişisi) | — | ✗ Not designated |
| 19 | Data Processing Agreement with processors | Art. 28 | §1798.140(ag) | Art. 12 | — | ✗ Not in place |
| 20 | Children's data protection (age verification) | Art. 8 | §1798.120(c) + COPPA | Art. 6 | — | ✗ No age gate |
| 21 | Cross-border transfer safeguards | Art. 44–50 (SCCs) | — | Art. 9 (explicit consent) | — | — (local deployment only) |
| 22 | VERBIS registration (Turkey) | — | — | Art. 16 | — | ✗ Required for production; not applicable at prototype stage |
| 23 | BIPA written informed consent (Illinois) | — | — | — | — | ✗ Not implemented; analysed in Section 7 |
| 24 | Biometric retention schedule (≤ 3 years, Illinois) | — | — | — | — | ✗ Not implemented |
| 25 | Algorithmic transparency and model documentation | Art. 22, Recital 71 | ADMT proposed regulations | Art. 11 | — | ~ Source code open; no formal model card |

### 6.2 Aggregate Scoring (Illustrative)

| Regime | Requirements Evaluated | ✓ Compliant | ~ Partial | ✗ Non-Compliant |
|---|---|---|---|---|
| GDPR | 21 | 0 | 3 | 18 |
| CCPA / CPRA | 17 | 0 | 2 | 15 |
| KVKK | 19 | 0 | 2 | 17 |
| NY SHIELD Act | 7 | 0 | 0 | 7 |

The prototype does not meet the substantive threshold for any regime surveyed. Scoring is illustrative and provided for pattern recognition, not as an authoritative compliance determination.

---

## 7. Legal Analysis: Classification of Pose Landmarks as Biometric Data

The prototype's core technical premise — that processing MediaPipe-derived pose landmarks rather than raw pixel data reduces regulatory exposure — is legally defensible under some regimes and contestable under others. A careful analysis follows.

### 7.1 GDPR (Articles 4(14) and 9)

GDPR defines biometric data as:

> "personal data resulting from specific technical processing relating to the physical, physiological or behavioural characteristics of a natural person, which allow or confirm the **unique identification** of that natural person." *(Art. 4(14), emphasis added)*

Processing such data falls under Article 9 special-category restrictions **only when the purpose is unique identification**.

**Application to the prototype.** The BiLSTM classifier outputs behavioural class labels (Normal / Suspicious); pose sequences are not cross-referenced against any identity database. Under GDPR, the derived pose data is therefore arguably **not "biometric data" in the Article 9 sense**. The source video, however, contains facial imagery and other direct identifiers and remains general personal data under Article 4(1).

**Defensibility:** Moderate to strong, provided the "no unique identification" boundary is respected in code, documented in processing records, and enforced at the pipeline level.

### 7.2 California CCPA and CPRA

The pre-CPRA CCPA defined biometric information broadly to include:

> "physiological, biological, or behavioral characteristics … that can be used, singly or in combination with each other or with other identifying data, to establish individual identity." *(Cal. Civ. Code §1798.140(b), original)*

CPRA subsequently amended the definition of "sensitive personal information" to include:

> "biometric information for the purpose of **uniquely identifying a consumer**." *(Cal. Civ. Code §1798.140(ae)(2)(A), emphasis added)*

**Application to the prototype.** The narrower CPRA definition mirrors GDPR's purpose-based scope and is defensible on the same reasoning. The broader pre-amendment CCPA definition is a weaker basis for exclusion, as gait-like behavioural data falls within its scope regardless of purpose. Consumers retain a "right to limit the use and disclosure of sensitive personal information" under CPRA §1798.121, which the prototype does not implement.

**Defensibility:** Moderate.

### 7.3 Illinois BIPA (740 ILCS 14)

BIPA defines a "biometric identifier" exhaustively as:

> "a retina or iris scan, fingerprint, voiceprint, or scan of hand or face geometry."

Gait and pose are not enumerated. The broader term "biometric information" is defined as "any information … based on an individual's biometric identifier used to identify an individual" and inherits the narrow list.

**Application to the prototype.** Pose-based gait data is **likely outside BIPA's enumerated scope**, subject to judicial interpretation. However, BIPA applies immediately if face geometry is computed at any stage (for example, via facial landmark detection or any future extension that derives facial measurements). A documented engineering boundary prohibiting face-geometry extraction is advisable.

**Defensibility:** Strong for pose-only processing; requires an explicit and enforced engineering boundary against face-geometry extraction.

**Notable risk:** BIPA provides a private right of action. Statutory damages range from USD 1,000 per negligent violation to USD 5,000 per intentional violation, plus attorneys' fees. Class action settlements in this space have included Facebook (USD 650 million), TikTok (USD 92 million), and Google (USD 100 million).

### 7.4 KVKK (Turkey)

KVKK Article 6 classifies biometric data as *özel nitelikli kişisel veri* (special-category personal data). The Personal Data Protection Board (Kişisel Verileri Koruma Kurulu) has interpreted biometric data to encompass *physiological, biological, or behavioural* characteristics in its published guidelines, adopting a definition broader than GDPR's purpose-based scope.

**Application to the prototype.** Under the Board's broad interpretation, pose-based gait data is **likely classifiable as behavioural biometric data** and therefore special-category. Processing requires explicit consent and additional technical and administrative safeguards under Article 6. VERBIS registration is required for most production data controllers.

**Defensibility:** Weak. KVKK is the most expansive of the regimes surveyed with respect to behavioural biometrics.

### 7.5 Summary of Classification Risk

| Regime | Defensibility of "pose-only is non-biometric" | Notes |
|---|---|---|
| GDPR | Strong, if no unique-identification purpose | Document purpose strictly in ROPA |
| CPRA (California) | Moderate to strong | Same purpose-based analysis; sensitive-PI limit right remains |
| CCPA (pre-amendment reading) | Weak | Broader behavioural definition |
| BIPA (Illinois) | Strong | Pose not enumerated; face geometry must be prohibited |
| New York City Biometric Identifier Information Law | Moderate | Definition tied to facial, voice, and geometric scans |
| Texas CUBI | Strong | Enumerated list; gait excluded |
| KVKK (Turkey) | Weak | Behavioural data explicitly included by Board guidance |

**Conclusion.** The pose-only architecture is a legitimate legal strategy under several regimes but cannot be relied upon universally. The strongest mitigations in production are (i) strict purpose documentation, (ii) absence of identity linking, (iii) retention minimisation, and (iv) regime-specific consent flows — notably for Illinois and Turkey.

**Independent concern.** The source video files themselves are general personal data in every surveyed jurisdiction, regardless of how derived features are classified. The prototype's storage of raw source video must be addressed independently of the pose-classification question.

---

## 8. Comparison to Industry Privacy Commitments

A production-grade video surveillance / biometric analysis vendor would typically publish privacy commitments aligned with SOC 2 Trust Services Criteria, ISO/IEC 27001 controls, and GDPR Article 32 technical measures. The following table evaluates the prototype against these widely-adopted industry-standard commitments — the same commitments that any serious commercial deployment would be expected to meet.

### 8.1 Commitment-by-Commitment Evaluation

| # | Industry-Standard Commitment | Prototype Implementation | Assessment |
|---|---|---|---|
| 1 | **Encryption in transit (TLS)** | Development runs on HTTP and unencrypted WebSockets; Docker Compose does not terminate TLS. | **Not met** |
| 2 | **Encryption at rest (AES-256 or equivalent)** | SQLite database and MP4 files are stored in cleartext on the host filesystem. | **Not met** |
| 3 | **Data minimization / anonymization — process behavioural signals, not personal identifiers** | Pose extraction is implemented as the inference input, but raw source video (containing faces and other direct identifiers) persists in `storage/uploads/`. | **Not met — material inconsistency with representation** |
| 4 | **Access control — authorised personnel only, periodic audits** | No authentication, authorisation, or audit logging is implemented. | **Not met** |
| 5 | **Regulatory compliance — GDPR, CCPA, KVKK adherence** | Consent modal exists; no DSAR, retention, breach, or ROPA processes. | **Not met** |
| 6 | **Data retention — retain only as necessary, secure deletion** | No automated retention policy; data persists indefinitely until manual deletion. | **Not met** |
| 7 | **Privacy by Design (GDPR Article 25)** | Design intent is visible (consent modal, pose-only framing, browser-side webcam processing), but implementation contradicts the intent by persisting raw source video. | **Partially met (intent only)** |
| 8 | **Transparency and customer control** | Consent modal text exists; no user-facing dashboard; no configurable privacy controls. | **Partially met** |
| 9 | **Cloud platform with attested security controls (SOC 2 / ISO 27001 cloud)** | The prototype uses local Docker and SQLite; no managed cloud platform integration. | **Not applicable to local prototype** |
| 10 | **On-premise / local-deployment option** | Docker Compose enables fully local operation. | **Met (incidentally)** |

**Aggregate:** One of ten commitments substantively met; two partially met; seven not met; one not applicable. This pattern is typical for an early-stage prototype and would be addressed by the remediation roadmap in Section 11.

### 8.2 Material Inconsistency Between Representation and Implementation

Particular attention is drawn to Commitment #3. The prototype's consent modal states:

> *"Only skeleton keypoints (33 body landmarks) are extracted and analyzed. No identifiable imagery, faces, or personally identifiable information (PII) is stored or transmitted."*

This statement is **factually inaccurate with respect to the upload workflow**, which persists the raw MP4 file at `storage/uploads/{uuid}.mp4`. The statement is accurate with respect to the live-stream workflow, which does not persist raw frames.

**Regulatory implications:**

- **FTC Act §5.** Unfair or deceptive practices are actionable by the Federal Trade Commission. Misaligned consent language exposes the operator to enforcement action.
- **GDPR Article 5(1)(a).** The principle of "lawfulness, fairness, and transparency" requires accurate disclosure. Inaccurate consent language may invalidate the legal basis for processing.
- **KVKK Article 4 and Article 10.** The *aydınlatma yükümlülüğü* (duty to inform) requires accurate and complete disclosure prior to processing.

**Recommendation.** Prior to any non-development use of the system, the consent language must be corrected to accurately reflect the data flow, or the implementation must be changed to match the representation (for example, by deleting raw uploads immediately after feature extraction). This is a known priority remediation item.

---

## 9. Privacy-Positive Design Elements Present in the Prototype

Notwithstanding the gaps catalogued above, the prototype incorporates several design choices that reduce its personal-data footprint and would accelerate production remediation.

1. **Mandatory consent gating at the API boundary.** The backend rejects live-stream start requests with `consent_given=false` by returning HTTP 400 with an explanatory message. Consent is persisted on the `stream_sessions.consent_given` column and is therefore auditable server-side, not merely a client-side pretence.

2. **Live-stream frames are not persisted to disk.** The stream processor holds frames only in memory during the read–inference–discard cycle. No `cv2.VideoWriter` is invoked and no ring-buffer is maintained. Raw webcam and RTSP frames do not enter persistent storage at any point.

3. **Browser-side MediaPipe pose inference for live webcam sources.** Live webcam frames never leave the client for the analysis pipeline. Pose landmarks are computed in the user's browser via `@mediapipe/tasks-vision` running in WebAssembly, with GPU delegation where available. Only derived 132-float pose vectors (33 landmarks × x/y/z/visibility) are transmitted to the backend — not raw pixels. This architecture is an explicit privacy-by-design implementation aligned with GDPR Article 25.

4. **Pose-only inference pipeline.** The 231-dimensional feature vector consumed by the BiLSTM classifier is derived exclusively from normalised pose coordinates, velocities, and visibility scores. No raw pixel data flows into the classifier. This constrains the attack surface for subsequent memorisation or leakage of identifying imagery through the model.

5. **On-premise-capable deployment topology.** The Docker Compose configuration enables fully local operation. No third-party cloud services, vendor APIs, or telemetry endpoints are invoked during inference. Data residency is implicitly controlled by the operator's deployment environment, eliminating GDPR Chapter V and KVKK Article 9 concerns in the default mode.

6. **Explicit consent-rejection enforcement.** The backend does not rely on client-side consent checks. A 400 response with a human-readable message is returned server-side whenever consent is missing or false. A documented enforcement mechanism is present, not merely a disclaimer.

7. **Open source code base.** The entire stack is available for inspection by any reviewer and, if relevant, by counsel. Algorithmic transparency under GDPR Recital 71 is directly achievable via code review.

8. **Single-tenant, local development topology.** No cross-border data transfer occurs in the default operational mode, eliminating a major class of GDPR Chapter V and KVKK Article 9 exposures for the prototype.

9. **Stateless browser-to-backend classifier (`POST /api/livestream/classify-pose`).** The webcam real-time BiLSTM classification path is implemented as a stateless HTTP endpoint that accepts only derived pose vectors (no raw frames, no session state, no video upload). The backend explicitly **does not call `cv2.VideoCapture(0)` or any camera-access API** for webcam sessions; all inference operates on browser-computed features. This design has two privacy consequences: (a) the attack surface for raw frame interception or leakage is eliminated on the classification path, and (b) the claim "backend never accesses the webcam" is architecturally enforced, not merely documented.

10. **Browser-local recording with explicit-action persistence (`MediaRecorder`).** The live-stream webcam clip feature uses the browser's native `MediaRecorder` API to capture the webcam stream **in browser memory only**. No upload occurs implicitly. Frames become server-side persistent data **only** when the user explicitly clicks "Save to Library", at which point the blob is uploaded via `POST /api/livestream/save-recording` and stored as a Video + Clip record. "Download Recording" generates a local file via `URL.createObjectURL` without any backend round-trip. This matches the GDPR Article 5(1)(b) purpose-limitation principle: frames are captured only for the narrow purpose of the user's subsequent explicit save action, and are discarded on every recorder restart, browser reload, or session stop.

11. **Concurrency hardening for multi-session inference.** A module-level `threading.Lock` in `backend/app/routers/livestream.py` serializes BiLSTM `predict()` calls across concurrent sessions. This prevents race conditions inside the shared TensorFlow Keras model instance that could otherwise produce inconsistent predictions or cross-session state leakage. The lock is acquired only for the duration of the synchronous predict call (~20-50 ms) and has negligible user-visible latency impact.

These elements do not, individually or collectively, establish regulatory compliance. They establish that the **design intent** of the prototype is consistent with privacy-by-design principles, and that production remediation is an incremental, non-architectural effort rather than a foundational rewrite.

---

## 10. Identified Gaps and Risk Analysis

Gaps are ordered by severity of regulatory exposure if the prototype were deployed to production in its current state.

### 10.1 Critical Gaps

| Gap | Regime(s) | Illustrative Exposure |
|---|---|---|
| Raw video files stored in cleartext on disk | GDPR Art. 32; CCPA §1798.100(e); KVKK Art. 12; NY SHIELD §899-bb | Breach notification obligations; GDPR Art. 83 fines up to 4 % of global annual turnover or EUR 20 million, whichever is higher |
| Consent statement materially misrepresents data retention | FTC Act §5; GDPR Art. 5(1)(a); KVKK Art. 4 and Art. 10 | FTC consent decree; invalidation of legal basis for processing; administrative fines |
| No authentication or access control | GDPR Art. 32; CCPA §1798.100(e); KVKK Art. 12; NY SHIELD | Unauthorised-access incidents trigger breach notification; per-record liability under BIPA (USD 1,000–5,000) if face geometry is at any stage extracted |
| No DSAR / right-to-deletion workflow | GDPR Art. 15–17; CCPA §1798.105–110; KVKK Art. 11 | Per-request administrative penalties; regulator orders |
| No data retention or automated deletion policy | GDPR Art. 5(1)(e); KVKK Art. 4(2)(ç) | Storage-limitation violations; fines |

### 10.2 High-Severity Gaps

| Gap | Regime(s) | Illustrative Exposure |
|---|---|---|
| No DPIA for high-risk surveillance processing | GDPR Art. 35(3)(c) | Mandatory supervisory-authority consultation if residual high risk exists; procedural fine independent of any substantive violation |
| No Records of Processing Activities (ROPA) | GDPR Art. 30; KVKK VERBIS | Inspection failures; VERBIS registration refusal in Turkey |
| No audit log | All four regimes | Inability to demonstrate compliance; breach-scope determination blocked |
| No TLS termination in the default configuration | All four regimes | Man-in-the-middle exposure; breach trigger |
| No breach notification runbook | GDPR Art. 33 (72-hour deadline); CCPA §1798.82; KVKK; NY SHIELD §899-aa | Missed deadlines are independently fineable |

### 10.3 Jurisdiction-Specific High Risks

| Jurisdiction | Risk | Explanation |
|---|---|---|
| **Illinois (BIPA)** | Private right of action; USD 1,000 per negligent violation, USD 5,000 per intentional violation; class-action risk | If face geometry is computed at any stage, BIPA §15(b) written-consent requirements attach immediately. Settlements in this space have exceeded USD 100 million (Facebook USD 650M; TikTok USD 92M; Google USD 100M). |
| **Turkey (KVKK)** | Broad definition of biometric data; VERBIS registration requirement | Pose-as-biometric interpretation under Turkish Board guidance creates exposure absent explicit consent, VERBIS registration, and tiered consent flows. Administrative fines in 2026 range from approximately TRY 50,000 to TRY 5,300,000 per infraction. |
| **European Union (GDPR)** | Mandatory DPIA for systematic surveillance processing | Deployment without a DPIA is itself a procedural violation; penalties are independent of substantive processing violations. |
| **California (CPRA)** | Right to limit sensitive PI use; automated decision-making transparency | CPRA sensitive-PI framework is not implemented. Upcoming ADMT (Automated Decision-Making Technology) regulations may impose additional disclosure duties. |
| **European Union (AI Act)** | Biometric categorisation and remote identification restrictions | Depending on the deployment context and jurisdiction, certain biometric-adjacent uses may be prohibited or classified as high-risk under the EU AI Act. |

### 10.4 Procedural and Documentation Gaps

| Gap | Impact |
|---|---|
| No standalone privacy policy document | Unable to satisfy notice obligations under any regime |
| No cookie / tracker inventory | Not applicable to the prototype; becomes applicable on public deployment |
| No children's data handling procedure (COPPA / GDPR Art. 8) | Cannot process footage containing minors without age gating |
| No vendor / sub-processor register | Required under GDPR Art. 28 once third-party services are added |
| No data classification taxonomy | Blocks role-based access control design |
| No model card or fairness assessment | Creates bias and discrimination exposure under emerging AI regulations (EU AI Act; NYC Local Law 144 in the employment context) |

---

## 11. Roadmap to Production Compliance

The following remediation items, if implemented, would bring the prototype to a baseline suitable for supervised production deployment. Effort estimates are engineering-only and exclude legal review, DPO engagement, and certification programmes (ISO 27001, SOC 2), which have independent and longer timelines.

### 11.1 Immediate Remediation (Weeks 1–2)

| Item | Effort | Regime(s) Satisfied |
|---|---|---|
| Align consent modal language with the actual data flow, or delete raw uploads after processing | 0.5 day | FTC §5; GDPR Art. 5(1)(a); KVKK Art. 4 |
| Introduce TLS termination via nginx or Traefik with Let's Encrypt | 0.5 day | GDPR Art. 32; all others |
| Implement JWT-based authentication and role-based access control (admin / operator / viewer) | 1.5 days | GDPR Art. 32; all others |
| Implement append-only audit logging | 1 day | GDPR Art. 30; all others |
| Implement an automated retention policy with configurable TTL (default 30 days for incident clips, 90 days for audit logs) | 0.5 day | GDPR Art. 5(1)(e); KVKK Art. 4 |
| Migrate SQLite to PostgreSQL with Transparent Data Encryption (TDE) or enable filesystem-level encryption (LUKS, encrypted EBS, encrypted host volumes) | 1 day | GDPR Art. 32; KVKK Art. 12 |
| Move clip and upload storage from local filesystem to object storage with server-side encryption (S3 SSE-KMS, GCS CMEK, Azure Blob CMK) | 1 day | GDPR Art. 32; CCPA §1798.100(e) |
| Publish a standalone privacy policy document | 1 day engineering, plus legal review | GDPR Art. 12–14; all others |

### 11.2 Structural Remediation (Weeks 3–6)

| Item | Effort | Regime(s) Satisfied |
|---|---|---|
| Implement DSAR endpoints (access, deletion, portability) and an administrative dashboard | 3 days | GDPR Art. 15–20; CCPA §1798.105–130; KVKK Art. 11 |
| Design and execute a DPIA for the surveillance processing activity | 5 days engineering, plus legal review | GDPR Art. 35 |
| Prepare ROPA and, for Turkish operation, complete VERBIS registration | 3 days engineering, plus legal review, plus 4–8 weeks administrative | GDPR Art. 30; KVKK Art. 16 |
| Implement incident response runbook with 72-hour breach notification workflow | 2 days engineering, plus legal review | GDPR Art. 33; CCPA §1798.82; KVKK; NY SHIELD |
| Implement granular, purpose-specific consent with a frictionless withdrawal experience | 2 days | GDPR Art. 7(3); CPRA limit right; KVKK Art. 11 |
| Implement children's data safeguards with age gating | 1 day | COPPA; GDPR Art. 8 |
| Implement BIPA-compliant written informed consent flow for Illinois users, with a retention schedule not exceeding three years | 2 days | BIPA §15 |

### 11.3 Continuous Programmes (Ongoing)

| Item | Cadence | Purpose |
|---|---|---|
| Access review | Quarterly | GDPR Art. 32 |
| Security penetration testing | Annually | GDPR Art. 32 |
| Privacy impact assessment refresh | On material change | GDPR Art. 35 |
| Model card maintenance and bias monitoring | Per model version | EU AI Act; emerging US state AI laws |
| Data deletion audit | Monthly | Retention enforcement verification |

### 11.4 Certification Track (Parallel, 6–18 Months)

| Target | Timeline | Value |
|---|---|---|
| SOC 2 Type I | 6 months | Enterprise procurement |
| SOC 2 Type II | 12 months (including a 6-month evidence window) | Enterprise procurement |
| ISO / IEC 27001 certification | 12–18 months | International procurement |
| C5 attestation (Germany) | 12–18 months | European public sector |

---

## 12. Honest Communication Guidance

The following communication principles apply to the prototype's compliance posture, both internally and in any customer-facing context.

### 12.1 Statements That Must Not Be Made

Each of the following is factually incorrect for the prototype in its current state and must not be made in marketing, documentation, customer conversations, or demos:

- "The prototype is GDPR compliant."
- "The prototype is CCPA compliant."
- "The prototype is KVKK compliant."
- "No personal data is stored."
- "No personally identifiable information is stored."
- "All data is encrypted."
- "Access is restricted to authorised personnel."

### 12.2 Statements That Can Be Made Truthfully

- "The prototype demonstrates privacy-by-design intent through consent gating, in-memory-only live-stream handling, and browser-side webcam inference."
- "The prototype's live-stream architecture does not persist raw video frames from webcam or RTSP sources."
- "Webcam pose inference is performed client-side, so raw webcam frames never reach the server."
- "A documented compliance gap analysis and remediation roadmap for production transition has been prepared."
- "The prototype is suitable for engineering review and demonstration, but is not fit for production deployment without the remediation described in the compliance assessment."

### 12.3 Communicating the Compliance Posture

When compliance is raised in a technical review, the following framing is accurate:

> "The prototype is privacy-aware in design but not production-compliant in implementation. The gaps are catalogued against GDPR, CCPA/CPRA, KVKK, and the NY SHIELD Act, with a sequenced remediation plan. The most material item is aligning the consent language with the actual upload data flow, followed by introducing encryption at rest, access control, and a DSAR workflow. These would be the first sprint of any production transition, subject to the deploying organisation's legal counsel on specific wording and process requirements under their existing compliance programme."

This framing acknowledges the prototype's status honestly and demonstrates informed understanding of the regulatory landscape.

---

## 13. Conclusion

The Video Intelligence Platform prototype, in its current state, is a privacy-aware engineering exercise that **does not comply** with the principal regulatory regimes surveyed (GDPR, CCPA/CPRA, KVKK, NY SHIELD Act). This outcome is expected and appropriate for a time-constrained prototype.

The prototype exhibits deliberate privacy-positive design elements — in-memory live-stream handling, browser-side pose inference, consent gating, on-premise capability — that reduce its personal-data footprint below what a naive implementation would produce. These elements form the foundation on which production remediation can be built incrementally rather than requiring architectural rework.

The most urgent remediation item is the **alignment of the consent modal's language with the actual upload data flow**. This is a factual-accuracy issue with direct exposure under FTC Act §5 and GDPR Article 5(1)(a), and it should be corrected before any non-development use of the system.

The remediation roadmap described in Section 11 is intended to be executed under the direction of qualified legal counsel and engineering leadership, and the analysis can be extended to jurisdictions and frameworks outside the current document scope as required.

The author welcomes correction, direction, and counsel on every point made above.

---

## Appendix A — Glossary

| Term | Definition |
|---|---|
| **ADMT** | Automated Decision-Making Technology |
| **BIPA** | Biometric Information Privacy Act (Illinois, 740 ILCS 14) |
| **BlazePose GHUM** | Google's pose estimation model used by MediaPipe |
| **CCPA** | California Consumer Privacy Act |
| **COPPA** | Children's Online Privacy Protection Act |
| **CPRA** | California Privacy Rights Act |
| **CUBI** | Capture or Use of Biometric Identifier Act (Texas) |
| **DPA** | Data Processing Agreement |
| **DPIA** | Data Protection Impact Assessment |
| **DPO** | Data Protection Officer |
| **DSAR** | Data Subject Access Request |
| **EU AI Act** | Regulation (EU) 2024/1689 on Artificial Intelligence |
| **FTC** | Federal Trade Commission (United States) |
| **GDPR** | General Data Protection Regulation |
| **KVK Kurulu** | Kişisel Verileri Koruma Kurulu (Turkish Personal Data Protection Board) |
| **KVKK** | Kişisel Verilerin Korunması Kanunu (Turkish Personal Data Protection Law) |
| **PI** | Personal Information (CCPA / CPRA term) |
| **PII** | Personally Identifiable Information |
| **ROPA** | Records of Processing Activities (GDPR Art. 30) |
| **SCC** | Standard Contractual Clauses (EU cross-border transfers) |
| **SHIELD Act** | Stop Hacks and Improve Electronic Data Security Act (New York) |
| **TDPSA** | Texas Data Privacy and Security Act |
| **TLS** | Transport Layer Security |
| **VCDPA** | Virginia Consumer Data Protection Act |
| **VERBIS** | Veri Sorumluları Sicil Bilgi Sistemi (Turkey's data controller registry) |

---

## Appendix B — Regulatory References

- **GDPR:** Regulation (EU) 2016/679 of the European Parliament and of the Council of 27 April 2016 on the protection of natural persons with regard to the processing of personal data and on the free movement of such data.
- **CCPA:** California Civil Code, Title 1.81.5, §§1798.100–1798.199.100.
- **CPRA:** Proposition 24 (2020), amending CCPA.
- **BIPA:** 740 Illinois Compiled Statutes 14/.
- **NY SHIELD Act:** New York General Business Law §899-aa (breach notification) and §899-bb (reasonable security requirements).
- **NYC Biometric Identifier Information Law:** New York City Administrative Code §22-1201 et seq.
- **KVKK:** Law No. 6698 of the Republic of Turkey, published in the Official Gazette, issue 29677, 7 April 2016.
- **Texas CUBI:** Texas Business and Commerce Code §503.001.
- **Texas TDPSA:** House Bill 4, 88th Legislature (2023).
- **VCDPA:** Virginia Code §59.1-575 et seq.
- **Colorado CPA:** Colorado Revised Statutes §6-1-1301 et seq.
- **FTC Act §5:** 15 U.S. Code §45.
- **COPPA:** 15 U.S. Code §§6501–6506.
- **EU AI Act:** Regulation (EU) 2024/1689.

---

## Appendix C — Document Revision History

| Version | Date | Author | Change Summary |
|---|---|---|---|
| 1.0 | 2026-04-10 | Kaan Taplamacıoğlu | Initial draft. Covers GDPR, CCPA/CPRA, KVKK, NY SHIELD Act, Illinois BIPA, and FTC Act §5. Includes compliance matrix, biometric classification analysis, industry commitment comparison, gap analysis, and production remediation roadmap. |

---

**End of Document**
