"""Generate synthetic Indian pharmacy bills (image + ground-truth JSON) for testing and the paper.

Usage:  python -m scripts.make_synthetic_bills --n 100 --out data/synthetic --seed 7
Each bill gets a difficulty: clean, faded (thermal paper), tilted, or noisy. About 20% have a
planted error (bad GSTIN check digit, expired item, wrong total, missing batch) so the rule
checks can be evaluated too. All names and numbers are made up.
"""
import argparse
import json
import random
from datetime import date, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app.validate import CHARS, gstin_check_digit

SHOPS = ["Shri Balaji Medical Store", "New Life Chemists", "Apollo Care Pharmacy", "Sai Ram Medicos", "Gupta Medical Hall",
         "Janta Drug House", "City Care Chemist", "Arogya Medicals", "Krishna Pharma", "Wellness Plus Pharmacy"]
AREAS = [("Rohini, Delhi 110085", "07"), ("Lajpat Nagar, New Delhi 110024", "07"), ("Andheri East, Mumbai 400069", "27"),
         ("Kothrud, Pune 411038", "27"), ("MP Nagar, Bhopal 462011", "23"), ("Indiranagar, Bengaluru 560038", "29"),
         ("Salt Lake, Kolkata 700091", "19"), ("Gomti Nagar, Lucknow 226010", "09")]
DRUGS = [("Paracetamol 650mg Tab", 32.5), ("Azithromycin 500mg Tab", 119.5), ("Pantoprazole 40mg Tab", 145.0),
         ("ORS Sachet 21g", 21.0), ("Cetirizine 10mg Tab", 42.0), ("Amoxicillin 500mg Cap", 98.0),
         ("Metformin 500mg Tab", 38.0), ("Vitamin D3 60K Cap", 60.0), ("Montelukast 10mg Tab", 185.0),
         ("Ibuprofen 400mg Tab", 24.0), ("Cough Syrup 100ml", 115.0), ("Omeprazole 20mg Cap", 72.0)]
PATIENTS = ["Ramesh Kumar", "Sunita Sharma", "Anil Verma", "Priya Nair", "Mohd. Imran", "Kavita Joshi", "Rahul Das", "Meena Iyer"]
DOCTORS = ["Dr. A. Mehta", "Dr. R. Khanna", "Dr. S. Rao", "Dr. P. Banerjee", "Dr. N. Gupta"]


def rand_gstin(state: str, rng: random.Random) -> str:
    L = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    pan = "".join(rng.choice(L) for _ in range(5)) + f"{rng.randint(0, 9999):04d}" + rng.choice(L)
    first14 = state + pan + "1Z"
    return first14 + gstin_check_digit(first14)


def font(size, bold=False):
    for name in (["DejaVuSansMono-Bold.ttf", "courbd.ttf"] if bold else ["DejaVuSansMono.ttf", "cour.ttf"]):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def make_bill(i: int, rng: random.Random) -> tuple[dict, dict]:
    shop = rng.choice(SHOPS)
    area, state = rng.choice(AREAS)
    gstin = rand_gstin(state, rng)
    d = date(2026, 1, 1) + timedelta(days=rng.randint(0, 260))
    items = []
    for name, mrp in rng.sample(DRUGS, rng.randint(2, 6)):
        qty = rng.randint(1, 4)
        exp = d + timedelta(days=rng.randint(120, 900))
        items.append({"name": name, "hsn": "3004", "batch": f"{name[:2].upper()}{rng.randint(1000, 9999)}",
                      "expiry": f"{exp.year}-{exp.month:02d}", "qty": qty, "mrp": mrp, "rate": mrp, "discount": 0.0,
                      "amount": round(qty * mrp, 2)})
    sub = round(sum(x["amount"] for x in items), 2)
    disc = round(sub * rng.choice([0, 0, 0.05, 0.1]), 2)
    grand = round(sub - disc, 2)
    taxable = round(grand / 1.12, 2)
    gst = round(grand - taxable, 2)
    cgst = round(gst / 2, 2)
    sgst = round(gst - cgst, 2)
    truth = {"bill_type": "pharmacy",
             "seller": {"name": shop, "address": f"Shop {rng.randint(1, 99)}, {area}", "gstin": gstin,
                        "drug_licence_no": f"{state}-{rng.randint(10000, 99999)}/20B", "phone": f"0{rng.randint(11, 99)}-{rng.randint(20000000, 99999999)}"},
             "invoice": {"number": f"INV/{d.year % 100}-{d.year % 100 + 1}/{rng.randint(100, 9999)}", "date": d.isoformat()},
             "patient_name": rng.choice(PATIENTS), "doctor_name": rng.choice(DOCTORS), "items": items,
             "tax": {"gst_rate": 12.0, "cgst": cgst, "sgst": sgst, "igst": None},
             "totals": {"subtotal": sub, "discount": disc, "taxable_value": taxable, "total_tax": gst, "grand_total": grand}}
    meta = {"id": f"bill_{i:04d}", "difficulty": rng.choice(["clean", "clean", "faded", "tilted", "noisy"]), "planted_error": None}
    if rng.random() < 0.2:
        err = rng.choice(["bad_gstin", "expired_item", "wrong_total", "missing_batch"])
        meta["planted_error"] = err
        if err == "bad_gstin":
            g = truth["seller"]["gstin"]
            truth["seller"]["gstin"] = g[:14] + CHARS[(CHARS.index(g[14]) + 5) % 36]
        elif err == "expired_item":
            old = d - timedelta(days=40)
            truth["items"][0]["expiry"] = f"{old.year}-{old.month:02d}"
        elif err == "wrong_total":
            truth["totals"]["grand_total"] = round(grand + rng.choice([20, 50, 100]), 2)
        else:
            truth["items"][-1]["batch"] = None
    return truth, meta


def render(truth: dict, meta: dict, rng: random.Random) -> Image.Image:
    W, H = 900, 340 + 38 * len(truth["items"]) + 330
    img = Image.new("L", (W, H), 255)
    dr = ImageDraw.Draw(img)
    f, fb, fh = font(19), font(19, True), font(28, True)
    s, inv = truth["seller"], truth["invoice"]
    y = 30
    for text, fnt in [(s["name"].upper(), fh), (s["address"], f), (f"GSTIN: {s['gstin']}   D.L. No: {s['drug_licence_no']}", f), (f"Ph: {s['phone']}", f)]:
        w = dr.textlength(text, font=fnt)
        dr.text(((W - w) / 2, y), text, font=fnt, fill=0)
        y += 36 if fnt is fh else 28
    y += 8; dr.line([(30, y), (W - 30, y)], fill=0); y += 14
    dd = date.fromisoformat(inv["date"]).strftime("%d/%m/%Y")
    dr.text((40, y), f"Bill No: {inv['number']}", font=f, fill=0); dr.text((560, y), f"Date: {dd}", font=f, fill=0); y += 30
    dr.text((40, y), f"Patient: {truth['patient_name']}", font=f, fill=0); dr.text((560, y), truth["doctor_name"], font=f, fill=0); y += 34
    dr.line([(30, y), (W - 30, y)], fill=0); y += 10
    cols = [40, 350, 420, 530, 630, 690, 790]
    for c, h in zip(cols, ["Item", "HSN", "Batch", "Exp", "Qty", "MRP", "Amount"]):
        dr.text((c, y), h, font=fb, fill=0)
    y += 32
    for it in truth["items"]:
        exp = it["expiry"][5:] + "/" + it["expiry"][:4] if it["expiry"] else ""
        for c, v in zip(cols, [it["name"], it["hsn"], it["batch"] or "", exp, str(it["qty"]), f"{it['mrp']:.2f}", f"{it['amount']:.2f}"]):
            dr.text((c, y), v, font=font(17), fill=0)
        y += 38
    dr.line([(30, y), (W - 30, y)], fill=0); y += 14
    t, tx = truth["totals"], truth["tax"]
    for k, v in [("Sub Total", t["subtotal"]), ("Discount", t["discount"]), ("Taxable Value", t["taxable_value"]),
                 ("CGST @6%", tx["cgst"]), ("SGST @6%", tx["sgst"]), ("NET AMOUNT (Rs)", t["grand_total"])]:
        dr.text((520, y), k, font=fb if k.startswith("NET") else f, fill=0)
        dr.text((760, y), f"{v:.2f}", font=fb if k.startswith("NET") else f, fill=0)
        y += 30
    y += 16
    dr.text((140, y), "Prices inclusive of GST. Goods once sold will not be taken back.", font=font(15), fill=0)

    diff = meta["difficulty"]
    if diff == "faded":            # thermal paper fading: low contrast + blur
        img = img.point(lambda p: 150 + p * 105 // 255).filter(ImageFilter.GaussianBlur(0.8))
    elif diff == "tilted":
        img = img.rotate(rng.uniform(-6, 6), expand=True, fillcolor=235)
    elif diff == "noisy":
        px = img.load()
        for _ in range(W * H // 40):
            x, yy = rng.randrange(img.width), rng.randrange(img.height)
            px[x, yy] = rng.randint(80, 200)
        img = img.filter(ImageFilter.GaussianBlur(0.5))
    return img.convert("RGB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--out", default="data/synthetic")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    out = Path(a.out)
    (out / "images").mkdir(parents=True, exist_ok=True)
    (out / "truth").mkdir(parents=True, exist_ok=True)
    manifest = []
    for i in range(1, a.n + 1):
        truth, meta = make_bill(i, rng)
        render(truth, meta, rng).save(out / "images" / f"{meta['id']}.png")
        (out / "truth" / f"{meta['id']}.json").write_text(json.dumps(truth, indent=2))
        manifest.append(meta)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"Wrote {a.n} bills to {out}")


if __name__ == "__main__":
    main()
