# BillTrail API — Guide for the Frontend Team

**Base URL:** `process.env.NEXT_PUBLIC_API_URL` (local: `http://localhost:8000`). Full interactive docs: `/docs` when the backend runs.
**Every request** sends the header `X-User: <name typed in the "Your name" box>`. This name goes into the paper trail.
**Data shapes:** `frontend/lib/types.ts` is the source of truth. Use exactly these field names.
**Errors:** non-2xx responses return `{"detail": "message"}`. For a duplicate upload (409): `{"detail": {"message": "...", "bill_id": "..."}}`.

## Bill status (drives the UI)

| `status` | Show as | What the UI does |
|---|---|---|
| `queued` | Waiting in queue | Poll; show `queue_position` ("number 2 in line") |
| `processing` | Being read | Poll |
| `verified` | Verified (green) | Show form + checks |
| `review` | Needs review (red) | Show form + checks; user corrects and saves |
| `failed` | Could not read | Show `job_error` + "Read again" button; the user can also type the fields and save |

## Page 1 — Add a bill

| Call | Send | Get back |
|---|---|---|
| `POST /api/bills/upload` | `multipart/form-data`: `file` (PDF/JPG/PNG/WebP, ≤ 15 MB), optional `patient_name` | `BillDetail` with `status: "queued"`. Errors: 415 wrong type, 413 too big, 409 duplicate |
| `GET /api/bills/{id}?track=false` | — | `BillDetail`. **Poll every 3 s while status is `queued`/`processing`.** `track=false` stops polling from filling the paper trail |
| `PUT /api/bills/{id}` | JSON `StandardBill` (the edited `record`) | Updated `BillDetail` (checks re-run). 409 if still being read |
| `POST /api/bills/{id}/reprocess` | — | `BillDetail` back to `queued` ("Read again") |
| `GET /api/bills/{id}/original` | — | The original file. Use `API + bill.original.url` as `<img src>` or `<iframe src>` for PDFs |

## Page 2 — Bills & summary

| Call | Send | Get back |
|---|---|---|
| `GET /api/summary` | optional `?patient_id=` | `{bills, by_status{…}, total_amount, total_gst, pharmacies, queue{waiting, processing}}` |
| `GET /api/bills` | optional `q`, `status`, `patient_id`, `date_from`, `date_to` (YYYY-MM-DD), `limit` | `BillSummary[]`, newest first. `q` searches pharmacy, GSTIN, patient, invoice no., doctor, medicine |
| `GET /api/bills/{id}` | — | `BillDetail` (logs a "viewed" entry; use when a person opens a bill) |
| `GET /api/patients` | — | `[{id, name, bills}]` for the patient filter |
| `GET /api/patients/{id}/recent-medicines?days=90` | — | `[{date, name, qty, batch, from, bill_id}]` (emergency lookup) |
| `POST /api/claims/bundle` | `{"bill_ids": ["…"]}` (same patient, already read) | FHIR bundle JSON. Save it as a `.json` download. 400 if the bills are mixed or unread |

## Page 3 — Paper trail

| Call | Send | Get back |
|---|---|---|
| `GET /api/audit` | optional `limit` (≤ 2000), `bill_id`, `action` | `AuditEntry[]`, newest first, each with `bill_label` ("Pharmacy · invoice no.") |
| `GET /api/audit/verify` | — | `{ok, broken_at, checked}`. Show "All N entries are intact" or "Broken at entry #X" |

**`action` values:** `uploaded`, `queued`, `processing_started`, `ai_extracted`, `ai_failed`, `saved`, `human_corrected`,
`re-verified`, `viewed`, `claim_bundle_created`. The entry's `details` holds specifics, e.g. `human_corrected` → `{field, from, to}`.

## Key fields at a glance

- **`BillSummary`**: `id, status, patient_name, seller_name, gstin, invoice_number, invoice_date, grand_total, total_tax, ai_confidence, human_corrections, file_name, queued_at`
- **`BillDetail`** = BillSummary + `record` (StandardBill), `checks[]` (`{code, label, status: pass|warn|fail, detail, ref}`),
  `model_name, processing_seconds, job_error, queue_position, original{file_name, content_type, sha256, uploaded_at, url}, audit[]`
- **`StandardBill`**: `bill_type, seller{name, address, gstin, drug_licence_no, phone}, invoice{number, date}, patient_name, doctor_name, items[{name, hsn, batch, expiry, qty, mrp, rate, discount, amount}], tax{gst_rate, cgst, sgst, igst}, totals{subtotal, discount, taxable_value, total_tax, grand_total}`.
  A failed bill may have an empty `record` (`{}`), so start the form from blank defaults.

*Not for the frontend:* `/api/worker/*` (used only by the GPU worker, protected by a secret token).
