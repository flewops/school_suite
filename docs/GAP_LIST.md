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
| Fees on the native v16 flow (Fee Schedule → Sales Invoice) counted on portals, dashboards, TC | integration tests |
| Sibling discount (auto, on new fee invoices) / concession / late-fee calculation | tests: ₹5000 → ₹4500 for a 2nd child; late fee capped |
| Fix: legacy Fees ignored the component discount when totalling | tests: 20% → ₹4000 |
| **School Suite Settings**: every policy value editable by the school | replaces code constants |
| Board-configurable report card compile + UDISE placeholder | verified |
| SMS via native SMS Settings, email via Email Account; log-only until configured | WhatsApp still pluggable |
| Teacher attendance marking + marks entry (native tools, own classes only) | verified by impersonation |
| Same-day absence SMS to guardians (once per child per day) | verified (dummy provider) |
| India / UDISE+ student fields (APAAR, PEN, category, CWSN, RTE, BPL, admission no.) + UDISE code on Company | custom fields |
| UDISE+ export with class × gender, category, CWSN/RTE/BPL + data-gap list | still a placeholder schema |
| Printable Transfer Certificate (`/transfer-certificate`) and report card (`/report-card`) | browser print / Save as PDF |
| Below-75% attendance list on `/principal`; CBSE 9-Point grading scale seed | verified |
| RTE 12(1)(c) fee warning | warns, doesn't block |
| Admission→fee→timetable→quiz→report full flow | 10/10 steps verified |
| Schema in code (no fixtures), module-tagged for clean uninstall; upgrade from the fixtures version tested | `setup/install.py` |
| 21 integration tests + CI (pre-commit lint, server tests) | `bench run-tests --app school_suite` |
| Pinned prod image build + CI + backup/restore + data-protection + deployment docs | files shipped |

## 🔨 BUILD (remaining gaps, worth doing in-house)
| Gap | Why build | Est. (days) |
|---|---|---|
| Real Zoom S2S integration wired end-to-end (create class, pull attendance, match by email) | only the plumbing is done; needs real creds + email-match tuning + teacher override UI | 3–5 |
| Razorpay test→live fee collection (Payment Gateway Account, Payment Request on fee invoices, reconciliation) | v16 fees are Sales Invoices, so native Payment Request works; needs real keys, a pay button on `/parent`, and reconciliation | 2–4 |
| Consent Record doctype + capture flow (DPDP children's data) | legal requirement; not native | 3–4 |
| Retention/purge job + export audit surfacing | legal requirement | 2–3 |
| Real UDISE+ field mapping to the government schema | placeholder only; format is fixed & external | 4–6 |
| Fold parent portal fully into native edu-portal (remove overlap) | reduce duplication flagged in review | 2–3 |
| Board-exact layouts (CBSE / state formats, co-scholastic block) for the printable report card and TC | generic print pages exist; boards prescribe exact formats | 2–3 |
| **Section 80C tuition-fee certificate** for parents' income-tax claim | every parent asks each year; needs a "tuition" flag on Fee Category + paid-in-FY sum from Payment Entries | 1–2 |
| **Guardian login by mobile number + SMS OTP** | many parents have no email. Frappe supports mobile login; needs a user-creation flow. (Mandatory student email can now be switched off in Settings.) | 2–3 |
| **Fee-due reminders + late-fee posting** (scheduler) | `late_fee_amount` computes but nothing posts or reminds; ERPNext Dunning may cover posting; needs DLT templates | 1–2 |
| **RTE reimbursement claim tracking** (per-child per-year claim to the State) | private unaided schools claim this yearly | 2–3 |
| **Transport**: routes, stops, bus fee, vehicle staff | very common in Indian schools; nothing native | 4–6 (or buy) |
| **Co-scholastic grades + NEP 2020 Holistic Progress Card** | CBSE template expects co-scholastic data; no source today | 3–5 |
| **Portal translations** (Hindi / regional) | strings are wrapped in `_()`; needs the translation files | translation only |
| **Restrict sensitive student fields** (religion, caste, disability, BPL) to staff via permlevel | DPDP minimisation | 0.5–1 |

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
| Hostel, library | only boarding / larger schools; integrate when a school asks |
| CBSE board registration (LOC) export | Classes IX–XII only; format changes yearly |

## Rough total for a production-hardened v1
**~30–45 engineering days** across the BUILD items above, plus the school's own
content setup (programmes, courses, fee structures, staff, report-card layouts) and
the legal review. The pilot itself (what's done) is the foundation those build on.
