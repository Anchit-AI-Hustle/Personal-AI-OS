# Invention Disclosure — Confidential

> **Purpose & honest scope.** This is an *invention-disclosure record*, not a
> granted patent or registered copyright. It exists to (a) describe the
> invention precisely, (b) establish a dated record of conception and
> reduction-to-practice, and (c) give a patent attorney everything needed to
> draft a filing. **No document and no software can make an idea "impossible to
> copy ever."** What the legal system offers is the *right to exclude others*
> (via an issued patent) and the *right to sue* for infringement/copying — not
> a technical impossibility of copying. The realistic protections, and how to
> get them, are listed at the end.

- **Title:** Always-On, Local-First Voice Assistant with Instruction-vs-Ambient
  Discrimination and Explicit Per-Action Consent for Any Off-Device Data Egress
- **Inventor:** Anchit Tandon
- **Date of this record:** 2026-06-23 (see git history for prior commits as
  corroborating timestamps of reduction-to-practice)
- **Status:** Reduced to practice — working implementation in this repository
  (Personal AI OS): continuous capture, on-device transcription (faster-whisper),
  instruction detection, workstream classification, local DB, autonomous
  reminders/daily-plan; off-device egress gated.

---

## 1. Field
Personal productivity assistants; always-on ambient voice capture; on-device
(edge) speech processing; privacy-preserving AI agents; consent-gated data
egress.

## 2. Problem addressed
Existing always-listening assistants (a) stream audio to the cloud by default,
creating privacy/security exposure; (b) rely on a single wake-word and discard
everything else, so they cannot act on natural instructions or maintain context;
and (c) externalize/store user data without granular, per-action consent. Users
who want a genuinely hands-off assistant must today trade away data control.

## 3. Summary of the invention
A system that listens continuously, transcribes **entirely on the user's own
device**, and:
1. **Discriminates** each transcribed segment as either a *direct instruction to
   the assistant* or *ambient speech not addressed to it* — without requiring a
   rigid single wake-word — and only acts on instructions.
2. Keeps **all captured data on-device by default**; nothing is transmitted or
   stored off-device as a side effect of listening.
3. **Gates every off-device data egress** (e.g., writing to a cloud document,
   sending an email/chat) behind an **explicit, per-action affirmative consent**
   obtained from the user via **either voice ("yes") or touch** — captured in the
   same modality stream the assistant already listens on.
4. **Classifies** captured work into separate work-streams and autonomously
   generates tasks, reminders, daily plans, and a day-wise activity log from the
   on-device data — with outbound notifications as an *optional* layer that
   degrades gracefully when disconnected.

## 4. Detailed description (enablement)
- **Continuous capture & silence gating.** Audio is captured in fixed chunks;
  an adaptively-calibrated silence threshold causes silent chunks to bypass
  transcription (prevents hallucinated text, saves compute).
- **On-device transcription.** Speech-to-text runs locally (no audio leaves the
  device).
- **Instruction-vs-ambient discrimination.** Each transcript segment is scored
  by a classifier that returns whether the user is *addressing/commanding the
  assistant* (wake-style address OR imperative clearly aimed at it) vs. talking
  about work or to other people. Default bias: false negatives over false
  positives.
- **Intent classification.** Instruction segments are typed (note, create/append
  external document, reminder, status update, query, …), each with a flag
  `stores_data_externally`.
- **Local-by-default persistence.** All results persist to an on-device store.
- **Consent-gated egress.** Any intent whose fulfillment writes data off-device
  is force-flagged to require confirmation; the system emits a short yes/no
  prompt and acts **only** upon an explicit affirmative consent signal, which may
  be (i) a spoken "yes" recognized from the same audio stream, or (ii) a touch
  confirmation on a UI surface. Absent consent, no data leaves the device.
- **Work-stream classification & autonomy.** Items are routed into distinct
  streams; tasks/reminders/daily-plans/activity-log are derived autonomously
  on-device. Reminders escalate by deadline proximity with varied, non-alarming
  phrasing and per-task cooldowns.

## 5. Claims (draft — for attorney refinement)
**Independent claim 1 (method).** A computer-implemented method comprising:
continuously capturing ambient audio on a user device and transcribing it
**locally on that device**; for each transcribed segment, classifying whether the
segment constitutes a direct instruction to an assistant versus ambient speech;
for segments classified as instructions, determining an intent and whether
fulfilling the intent would cause data to be stored or transmitted off the
device; persisting resulting data exclusively on the device when no off-device
egress is required; and, when off-device egress is required, withholding the
egress until an explicit affirmative consent for that specific action is received
from the user via a voice or touch modality.

**Independent claim 2 (system).** A device comprising a microphone, local
storage, a local speech-to-text engine, and a processor configured to perform the
method of claim 1.

**Dependent claims (examples).** …wherein silent segments are excluded from
transcription via an adaptively-calibrated threshold; …wherein the consent signal
is a spoken affirmative recognized from the same audio stream; …wherein each
off-device action requires a *separate* consent (no blanket/standing consent);
…wherein captured items are classified into a plurality of work-streams; …wherein
reminders are generated with escalation keyed to deadline proximity and per-item
cooldown; …wherein an on-device activity log is derived solely from work-related
segments.

## 6. Alternative embodiments (to broaden coverage / close loopholes)
- Consent via additional modalities (gesture, hardware button, glance).
- Instruction discrimination via on-device small model vs. remote model (claim
  both; emphasize on-device).
- Egress targets generalized: any cloud document, email, messaging, calendar,
  or third-party API.
- "Ephemeral consent token" scoped to one action and one payload, expiring
  immediately after use.
- Multi-user device with per-speaker consent.

## 7. What is (and isn't) novel — for the attorney
Novel combination: *continuous local transcription* + *instruction-vs-ambient
discrimination without rigid wake-word* + *default-local persistence* +
*mandatory per-action consent for any egress*, integrated into an autonomous
task/reminder system. Prior art exists for wake-word assistants, cloud
dictation, and on-device STT individually; the defensible position is the
**specific integrated flow and the consent-gated-egress guarantee**, not any
single component.

---

## 8. How to actually protect this (the real steps — honest)
No software step makes copying impossible. To obtain enforceable rights:
1. **Keep this confidential now.** Public disclosure can start clocks and bar
   rights in some jurisdictions. Do not publish/demo publicly before filing.
2. **File a provisional patent application** (USPTO and/or Indian Patent Office)
   — fast, low-cost, gives a 12-month priority date and "patent pending." Use a
   **patent attorney/agent**; this disclosure is the input they need.
3. **Within 12 months**, file the non-provisional / PCT for international scope.
4. **Copyright** of the code is automatic on authorship; you may *register* it
   for stronger enforcement/statutory damages. The git history corroborates
   authorship dates.
5. **Trademark** the product name separately if it has commercial value.
6. **Trade-secret** hygiene for anything you don't disclose (NDAs with anyone
   who sees it, access controls).
7. **Defensive publication** is the *opposite* strategy (prevents others
   patenting, but forfeits your own patent) — only if you decide not to file.

**Bottom line:** a granted patent gives you the right to *exclude and sue*, which
is the strongest available protection — but it requires a real filing through an
attorney. I can refine this disclosure, but I cannot file it, register copyright,
or guarantee un-copyable-ness, and I won't pretend otherwise.
