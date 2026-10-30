# Gap List — Build / Buy / Skip (with effort estimates)

Status after the pilot build (Phases 1–6). Effort is **engineering person-days**
for one mid-level Frappe developer, excluding the school's own content/config.

## ✅ Done and verified in the pilot
| Capability | Notes |
|---|---|
| v16 stack on one site (ERPNext + Education + HRMS + LMS + India Compliance + Payments) | all `version-16`, Python 3.14 / Node 24 |
| Row-level security (teacher→class; guardian→child via native) | verified by impersonation |
| Unified Education + LMS student dashboard + Principal dashboard | the real cross-app value |
| Parent portal (`/parent`) incl. LMS progress | augments native edu-portal |
| LMS batch ↔ class mapping + auto-enrol | verified |
| "Online mode" attendance (LMS activity; Zoom path documented) | verified (activity path) |
| Sibling discount / concession / late-fee policy | verified |
| Board-configurable report card compile + UDISE placeholder | verified |
| Pluggable SMS/WhatsApp/email (dummy providers) | verified |
| Admission→fee→timetable→quiz→report full flow | 10/10 steps verified |
| Fixtures (roles, custom fields, property setters incl. a v16 Fees bug fix, workflow) | version-controlled |
| Pinned prod image build + CI + backup/restore + data-protection + deployment docs | files shipped |

## 🔨 BUILD (remaining gaps, worth doing in-house)
| Gap | Why build | Est. (days) |
|---|---|---|
| Real Zoom S2S integration wired end-to-end (create class, pull attendance, match by email) | only the plumbing is done; needs real creds + email-match tuning + teacher override UI | 3–5 |
| Razorpay test→live fee collection (Payment Gateway Account, Payment Request from Fees, reconciliation) | native pieces exist but Education Fees ≠ Sales Invoice; needs a clean collection flow | 4–6 |
| Consent Record doctype + capture flow (DPDP children's data) | legal requirement; not native | 3–4 |
| Retention/purge job + export audit surfacing | legal requirement | 2–3 |
| Report-card **print formats** per board (CBSE/State PDF layouts) | compile logic done; needs real PDF templates | 3–5 |
| Real UDISE+ field mapping to the government schema | placeholder only; format is fixed & external | 4–6 |
| Fold parent portal fully into native edu-portal (remove overlap) | reduce duplication flagged in review | 2–3 |
| Teacher attendance-marking + grade-entry UI (desk/portal) | currently read paths; teachers need write flows | 3–5 |

## 💳 BUY / integrate (don't build)
| Gap | Buy instead of build |
|---|---|
| SMS / WhatsApp delivery | a provider (MSG91, Gupshup, Twilio, Meta WhatsApp Cloud) — plug into `notify.PROVIDERS` |
| Payment gateway | Razorpay (already the chosen rail) — just credentials + account |
| Video classes | Zoom (paid plan for reporting API) or Google Meet |
| S3-compatible backup storage | AWS S3 / Wasabi / self-hosted MinIO |
| Managed hosting (India region) | Frappe Cloud (India DC) or a cloud VM in an India region |

## ⏭️ SKIP (for the pilot; revisit later)
| Gap | Why skip now |
|---|---|
| Trust/society **fund accounting** | **open question for the CA** — do not assume a model |
| Separate sites + SSO topology | single site is simpler; only split if AGPL/upgrade cadence forces it |
| Native-dashboard rebuild of `/principal` | the custom page works; migrate to Number Cards only if desired |
| Multi-board report cards beyond CBSE/State | add boards when a school actually needs them |

## Rough total for a production-hardened v1
**~30–45 engineering days** across the BUILD items above, plus the school's own
content setup (programmes, courses, fee structures, staff, report-card layouts) and
the legal review. The pilot itself (what's done) is the foundation those build on.
