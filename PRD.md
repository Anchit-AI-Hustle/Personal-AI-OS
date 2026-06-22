# PRD — Always-On, Local-First Voice Assistant ("Smart Reminder + Notemaker")

> **Portable product brief.** Self-contained so it can be moved to another
> account/workspace. Captures the product vision, the complete and accurate set
> of requirements as asked, the architecture, the novel/IP mechanism, and — in
> the appendix — the **full record of the asks with the important dialogues in
> bold**.

- **Owner:** Anchit Tandon
- **Date:** 2026-06-23
- **Status:** Core (local) built & verified; cloud/interactive layers specified, pending dependencies
- **Related docs:** `INVENTION_DISCLOSURE.md` (IP), `ARCHITECTURE.md`, `CLAUDE.md`

---

## 1. One-line idea
An assistant that is **always listening on your own device, transcribes
everything locally, recognises when it's actually being given an instruction,
keeps all data on-device by default, and only ever sends data off-device after
an explicit per-action "yes" (voice or touch)** — while autonomously turning
your work into tasks, reminders, a daily plan, and an activity log.

## 2. Problem
- Always-listening assistants stream audio to the cloud → privacy/security risk.
- Wake-word assistants discard everything else → can't act on natural instructions or keep context.
- Task tracking depends on humans to log and to mark things done → things get missed and go stale.
- Cross-device (laptop + phone) productivity tools force a cloud-data trade-off.

## 3. Core innovation (the defensible idea — see INVENTION_DISCLOSURE.md)
Continuous **on-device** transcription **+** instruction-vs-ambient
discrimination (no rigid single wake-word) **+** **local-by-default**
persistence **+** **mandatory explicit per-action consent (voice/touch) for any
off-device egress** — integrated into an autonomous task/reminder/notemaker.

## 4. Users & platforms
- **Primary user:** the individual (single-user today; multi-user is a future, larger build).
- **Laptop (Mac + Windows):** records + processes + full dashboard. *(Recording is laptop-only — mobile OSes block continuous background mic.)*
- **Phone:** view & manage (Google Sheet view and/or hosted dashboard) + quick voice-note/reply. *(No background recording on phone — replaced by a one-tap voice note.)*
- Cross-platform autostart: one command auto-detects the OS and installs always-on launch.

## 5. Complete requirements (as asked — accurate)
### 5.1 Capture & intelligence
- **Always-on listening whenever the laptop is on**, on **both Windows and Mac**, with the data viewable from anywhere.
- **No task is ever missed** in capture.
- **Accurate task statement after summarising**, with **no detail missed**.
- **Correct task grouping** — never split one task into many, never merge many into one; dedupe repeats.
- **Two work-streams**, split by topic: **(1) Vahdam D2C work** and **(2) the user's own AI/side projects** (e.g. a "Jarvis", resume, this OS) — life-admin excluded.
- Inputs unified: **voice + email (Gmail) + Google Chat**.
- **Always-on instruction hook:** detect when the assistant is *being instructed* (vs. ambient talk); full transcription so it can act.

### 5.2 Outputs & surfaces
- **Google Sheet** kept **auto-filled**, with the two work-streams as **two sub-tabs**.
- **Dashboard** with the two work-streams as **two tabs**; reachable on **phone and laptop** (hosted).
- **Day-wise activity log** — what was done and when — **office-work + AI-project items only**.

### 5.3 Autonomy & nudges
- **Do not depend on the user to mark a task complete** — verify completion another way (bot asks → 1-tap confirm; infer from later mail/chat).
- **Send each person their tasks** via **email + Google Chat** (for now: from the user's own account, to the user only — both mail and chat must arrive).
- **Deadline reminders** that escalate as the date nears, with **interactive 1-click Yes/No replies**, in **varied, non-panicky styles**.
- **Daily morning email** (from self, to self): **what to complete today based on plans**.
- **During-day check-ins:** ask "on track? any updates?" → update **remarks + day-wise per-task status**.
- **Quick note / voice note** capture → updates **both the dashboard and the sheet**.
- Summed up by the user as a **"smart reminder + notemaker" product**.

### 5.4 Data, privacy & consent (non-negotiable)
- **Local-first / on-device by default. Complete data security. No online storage of data unless explicitly requested.**
- When the user *does* request storage (e.g. "put this in a Google Doc"), the assistant creates/opens it (via connector/API) and proceeds.
- **Every off-device action requires the user's explicit permission — by voice ("yes") or touch — before it is used/sent.**
- A "complete data transfer/export" option goes **only to the device it runs on**.

### 5.5 IP
- **Patent + copyright the idea/mechanism before business use** (see `INVENTION_DISCLOSURE.md`). Realistic protection = provisional patent via attorney + copyright registration; honest caveat: no protection makes copying *technically impossible*, it makes it *legally enforceable*.

## 6. Architecture (local-first)
```
Mic (laptop) ─► chunked capture ─► on-device Whisper ─► transcript
       │                                              │
       ├─► instruction detector ──► command (local act / consent-gated egress)
       └─► extractor (Groq/local) ─► classify workstream + group tasks
                                           │
                                           ▼
                                   local SQLite  ──► dashboard (2 tabs)
                                           │        activity log, reminders, daily plan
                                           └─►(optional, consent-gated) Google Sheet / email / Chat
```
- LLM provider chain (Groq default on Workspace accounts; Gemini blocked there).
- Outbound (Sheet/email/Chat) is an **optional layer that no-ops gracefully** without credentials.

## 7. Status & roadmap
**Built & verified (local, on-device, no cloud):**
- Recording → on-device transcription → workstream classification → correct grouping → local DB
- Two-tab dashboard; day-wise activity log; reminder + daily-plan engine; local-only run mode; cross-platform autostart
- Voice-command hook (instruction detection + intent + consent-gating logic)

**Specified, pending dependencies:**
- **Needs `credentials.json`:** Google Sheet auto-fill (2 tabs), daily email, Chat delivery, completion inference from mail/chat
- **Needs an always-on hosted backend:** phone-reachable dashboard + receiving interactive Yes/No replies + Chat-bot inbound + the **consent channel** (capturing the spoken/typed "yes")
- **Multi-user** (accounts + per-user data): future, larger build

## 8. Honest constraints (so the next owner isn't surprised)
- Phone **cannot** record in the background (OS rule) → one-tap voice note instead.
- True zero-input completion detection is unreliable → realistic = proactive ask + 1-tap confirm.
- Interactive replies/bot need a public backend (laptop can send but not reliably *receive* webhooks).
- This repo started as a Windows-targeted Vahdam tool; it's being generalised — some labels/paths still say "Vahdam".

---

## Appendix A — The asks, captured (important dialogues in **bold**)
*Faithful record of the requests that define this product, in order. Bold marks the load-bearing asks.*

1. *"This **blocking should happen all the time when the laptop is on**, be it this laptop or any other laptop. **It should work for both Windows and Mac.** Wherever I am opening the website."*
2. *"You need to **detect if it's a Windows laptop or a Mac laptop and accordingly give the command** that should be run in the code."*
3. *"**The sheet and the dashboard to be updated with every data**, also ensure the **data from mails and [Google Chat]** also keeps getting synced. **Smartly divide it into two parts** — **one part my own AI projects, and one part Vahdam-related work** — **two different sub-sheets in the same sheet and two different tabs in the dashboard.**"*
4. *"If it's a … task related to **D2C growth** … it will be [Vahdam]. Otherwise, if it's a **random project, like a resume or a Jarvis** … it'll be in the other one."*
5. *"I can ensure that the **tasks are assigned and stated correctly after summarising**, and **no detail should be missed in any task**, and **each task should be grouped correctly** — there shouldn't be a case where five tasks are written independently but it's actually one task, or vice versa."*
6. *"I want **all** — the **phone audio, Google Sheet view and hosting dashboard view** … **easy to follow every day without me needing to manage it** … **no task ever gets missed** … **the sheet gets auto-filled**."*
7. *"**Do not depend on the user or me to update if the task has been completed** — figure out how it can be verified — maybe a **Google Chat bot integration**, with **tasks for the respective people being sent to them as a mail and Google Chat message** … from my account to me only for now."*
8. *"I should also get **reminders when deadlines are coming closer** … an **option to reply with just a button click with yes or no** … **interactive innovative styles** for every reminder — **not in a panicky way**."*
9. *"Every day … a **message/email from me to myself as to what all I have to complete today based on plans.** During the day, it should **ask me if I'm on track or any updates** and accordingly **update the remarks and day-wise statuses** for the task."*
10. *"Maintain … **what I am doing during what time of the day**, and it must **only consider office work or AI project ideas**."*
11. *"An option to **discuss a point or just add a note / voice note**, and it should get **recorded in the dashboard and the sheet** — both updated. … **smart reminder plus notemaker** like product."*
12. *"Whatever uses **local functionalities** and gives complete **data transfer option only to the device it is run on** is best for the user."*
13. *"Add a hook … an **audio message whenever heard** … since it will be on all the time, it should **listen particularly for instructions that it is being given** … **complete transcription so that it can work with it**. … **complete data security and no form of online storage** … unless particularly requested and stored in a particular document (e.g. a **Google Doc**) … the **user will need to give permission — by audio or touch — a 'yes'** — before it can be used ahead."*
14. *"**This idea requires an instant patent and copyright on the idea itself for business use so that no one can copy it ever, with all possible vulnerabilities and liabilities and loopholes covered.**"*

## Appendix B — Where the full conversation transcript lives
The complete working transcript of this build session is retained in the Claude
Code session history for this project. On request, it can be exported to a local
file (or, with consent, to a Google Doc via the connector) — **kept on-device by
default**, per the data principle above.
