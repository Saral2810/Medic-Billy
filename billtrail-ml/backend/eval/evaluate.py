"""Score predictions against ground truth: the metrics proposed for the paper.

Usage:  python -m eval.evaluate --truth data/synthetic/truth --pred data/pred_ocr_llm --manifest data/synthetic/manifest.json
Reports:
  * field-level accuracy for each header field (exact match after normalising; money within Rs 0.01)
  * line-item precision / recall / F1 (a predicted line counts if name, qty and amount all match)
  * GSTIN validity rate of predictions, and review rate (share of bills the rule checks send to a person)
  * rule-check detection of planted errors (if a manifest is given)
  * all of the above split by difficulty (clean / faded / tilted / noisy)
"""
import argparse
import csv
import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path

from app.schemas import StandardBill
from app.validate import gstin_problem, run_checks, status_of

HEADER_FIELDS = ["seller.name", "seller.gstin", "seller.drug_licence_no", "invoice.number", "invoice.date",
                 "patient_name", "doctor_name", "tax.cgst", "tax.sgst", "totals.subtotal", "totals.discount",
                 "totals.taxable_value", "totals.grand_total"]
MONEY = {f for f in HEADER_FIELDS if f.startswith(("tax.", "totals."))}
PLANTED_CHECK = {"bad_gstin": "gstin_valid", "expired_item": "not_expired", "wrong_total": "grand_total", "missing_batch": "batch_expiry"}


def get(d, path):
    for k in path.split("."):
        d = (d or {}).get(k)
    return d


def norm_text(v):
    return re.sub(r"[^a-z0-9]", "", str(v).lower()) if v not in (None, "") else ""


def same(field, t, p):
    if field in MONEY:
        if t in (None, "") and p in (None, ""):
            return True
        try:
            return abs(float(t) - float(p)) <= 0.01
        except (TypeError, ValueError):
            return False
    return norm_text(t) == norm_text(p)


def line_key(it):
    try:
        return (norm_text(it.get("name")), float(it.get("qty") or 0), round(float(it.get("amount") or 0), 2))
    except (TypeError, ValueError):
        return (norm_text(it.get("name")), None, None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--truth", required=True); ap.add_argument("--pred", required=True)
    ap.add_argument("--manifest"); ap.add_argument("--csv", default=None)
    a = ap.parse_args()
    meta = {m["id"]: m for m in json.loads(Path(a.manifest).read_text())} if a.manifest else {}
    groups = defaultdict(lambda: defaultdict(list))
    detected = defaultdict(lambda: [0, 0])
    per_bill = []
    for tp in sorted(Path(a.truth).glob("*.json")):
        pp = Path(a.pred) / tp.name
        if not pp.exists():
            continue
        truth, pred = json.loads(tp.read_text()), json.loads(pp.read_text())
        m = meta.get(tp.stem, {})
        diff = m.get("difficulty", "all")
        row = {"id": tp.stem, "difficulty": diff}
        for f in HEADER_FIELDS:
            ok = same(f, get(truth, f), get(pred, f))
            for g in ("ALL", diff):
                groups[g][f].append(ok)
            row[f] = int(ok)
        tl = [line_key(i) for i in truth.get("items", [])]
        pl = [line_key(i) for i in pred.get("items", [])]
        remaining = list(tl)
        hit = 0
        for k in pl:
            if k in remaining:
                remaining.remove(k); hit += 1
        for g in ("ALL", diff):
            groups[g]["_lines_hit"].append(hit); groups[g]["_lines_pred"].append(len(pl)); groups[g]["_lines_true"].append(len(tl))
        sb = StandardBill.model_validate(pred)
        checks = run_checks(sb, today=date(2100, 1, 1))
        st = status_of(checks, sb.confidence)
        for g in ("ALL", diff):
            groups[g]["_gstin_valid"].append(gstin_problem(sb.seller.gstin) is None)
            groups[g]["_review"].append(st == "review")
        if m.get("planted_error"):
            code = PLANTED_CHECK[m["planted_error"]]
            flagged = any(c["code"] == code and c["status"] != "pass" for c in checks)
            detected[m["planted_error"]][0] += int(flagged); detected[m["planted_error"]][1] += 1
        row["lines_hit"], row["lines_true"], row["status"] = hit, len(tl), st
        per_bill.append(row)

    if not per_bill:
        print("No matching prediction files found."); return
    for g, d in sorted(groups.items(), key=lambda x: x[0] != "ALL"):
        n = len(d["_review"])
        print(f"\n=== {g}  (n={n}) ===")
        for f in HEADER_FIELDS:
            print(f"  {f:24s} {100 * sum(d[f]) / len(d[f]):6.1f}%")
        hit, pr, tr = sum(d["_lines_hit"]), sum(d["_lines_pred"]), sum(d["_lines_true"])
        p, r = (hit / pr if pr else 0), (hit / tr if tr else 0)
        f1 = 2 * p * r / (p + r) if p + r else 0
        field_acc = sum(sum(d[f]) for f in HEADER_FIELDS) / sum(len(d[f]) for f in HEADER_FIELDS)
        print(f"  {'header field accuracy':24s} {100 * field_acc:6.1f}%")
        print(f"  line items  P={p:.3f} R={r:.3f} F1={f1:.3f}")
        print(f"  GSTIN valid in output    {100 * sum(d['_gstin_valid']) / n:6.1f}%")
        print(f"  sent to human review     {100 * sum(d['_review']) / n:6.1f}%")
    if detected:
        print("\n=== planted errors caught by rule checks ===")
        for k, (c, t) in detected.items():
            print(f"  {k:15s} {c}/{t}")
    if a.csv:
        with open(a.csv, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(per_bill[0].keys())); w.writeheader(); w.writerows(per_bill)
        print(f"\nPer-bill results written to {a.csv}")


if __name__ == "__main__":
    main()
