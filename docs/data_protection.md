# Data Protection Checklist — Children's Data

> **FOR LEGAL REVIEW.** This is an engineering checklist, **not legal advice**. A
> school handling minors' data in India must have this reviewed against the Digital
> Personal Data Protection Act, 2023 (DPDP) and its rules — which treat children's
> data with heightened obligations (verifiable parental consent, no tracking/
> targeted advertising, data-minimisation).

## Consent
- [ ] **Verifiable guardian consent** captured before processing a child's data,
      with purpose, scope and date. (Suggested: a `Consent Record` doctype linked to
      Student + Guardian, storing consent version, timestamp, and channel. Not yet
      built — see gap list.)
- [ ] Consent is **re-collectable / withdrawable**; withdrawal flows to downstream
      processing (LMS enrolment, notifications).
- [ ] Separate consent for optional processing (e.g. WhatsApp messaging, photos).

## Access control & logging
- [x] Row-level access so a guardian sees only their child, a teacher only their
      class (school_suite `permissions.py`, verified).
- [ ] **Access logging / audit trail** for who viewed/exported a child's record.
      Frappe has `Access Log` + version history; confirm it is enabled and retained.
- [ ] Admin/exports (UDISE, report cards) restricted to Principal/School Admin
      (enforced in `reports.py`).

## Hosting & residency
- [ ] **India-region hosting** for DB, files and backups (incl. the S3 bucket).
- [ ] Sub-processors (SMS/WhatsApp/email vendors, Zoom, Razorpay) listed with their
      data-residency and DPAs on file.
- [ ] TLS everywhere; secrets in env/secret store, never in git (enforced in this
      repo — only dummy/placeholder creds are committed).

## Sensitive student fields
- [ ] School Suite adds optional **religion, social category, CWSN/disability and BPL**
      fields (needed for UDISE+ / scholarships). Collect them only where required, and
      restrict who can see them (permlevel) — not yet done; see gap list.
- [x] **Aadhaar is not stored.** UDISE+ identity is covered by **PEN** and **APAAR
      ID**. If a school must record Aadhaar, store only a masked / last-4 value and
      get legal advice first (Aadhaar Act storage rules).

## Retention & minimisation
- [ ] Defined **retention period** per data type (e.g. purge alumni PII after N
      years) and an automated purge job.
- [ ] Collect only what is needed; avoid storing sensitive data (health, biometrics)
      unless justified and consented.
- [ ] Right to **erasure / correction** process for guardians.

## Breach & governance
- [ ] Breach-notification procedure and contact appointed.
- [ ] Backups encrypted at rest; restore tested (see deployment.md).
- [ ] Vendor list + DPAs reviewed annually.

**Known gaps to build if legal confirms:** Consent Record doctype + capture flow;
automated retention/purge job; export audit log surfacing. Estimated in the gap list.
