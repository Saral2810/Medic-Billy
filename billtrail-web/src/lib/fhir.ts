import type { Bill } from "@/types/bill";

/** Minimal FHIR R4 Invoice bundle. Extend with Claim/NHCX profiles later. */
export function toFhirBundle(bills: Bill[]) {
  return {
    resourceType: "Bundle", type: "collection",
    entry: bills.map((b) => ({
      resource: {
        resourceType: "Invoice", id: b.id, status: "issued", date: b.invoiceDate,
        identifier: [{ system: `urn:gstin:${b.pharmacy.gstin}`, value: b.invoiceNumber }],
        issuer: { display: b.pharmacy.name }, subject: { display: b.patientName },
        lineItem: b.items.map((it, i) => ({
          sequence: i + 1, chargeItemCodeableConcept: { text: it.name },
          priceComponent: [{ type: "base", amount: { value: it.amount, currency: "INR" } }],
        })),
        totalNet: { value: b.totals.subTotal - b.totals.discount, currency: "INR" },
        totalGross: { value: b.totals.grandTotal, currency: "INR" },
      },
    })),
  };
}

export function downloadJson(name: string, data: unknown) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/fhir+json" }));
  a.download = name; a.click(); URL.revokeObjectURL(a.href);
}
