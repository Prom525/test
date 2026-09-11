import { API_ROOT } from "../config";

export { API_ROOT };

const API_BASE = `${API_ROOT}/analysis/rfq`;
const CONTEXT_API_BASE = `${API_ROOT}/analysis/context/rfq`;

export async function getEngineeringReviewV2(rfqId, positionId) {
  const res = await fetch(
    `${CONTEXT_API_BASE}/${rfqId}/positions/${positionId}/engineering-review-v2`
  );
  if (!res.ok) throw new Error("Engineering review ophalen mislukt");
  return res.json();
}

export async function getOcrPreview(rfqId, positionId) {
  const res = await fetch(
    `${CONTEXT_API_BASE}/${rfqId}/positions/${positionId}/ocr-preview`
  );
  if (!res.ok) throw new Error("OCR preview ophalen mislukt");
  return res.json();
}

export async function runOcrMerge(rfqId, positionId) {
  const res = await fetch(
    `${CONTEXT_API_BASE}/${rfqId}/positions/${positionId}/ocr-merge`,
    { method: "POST" }
  );
  if (!res.ok) throw new Error("OCR merge mislukt");
  return res.json();
}

export async function getTechnicalReviewPreview(rfqId, positionId) {
  const res = await fetch(
    `${CONTEXT_API_BASE}/${rfqId}/positions/${positionId}/technical-review-preview`,
    { method: "POST" }
  );
  if (!res.ok) throw new Error("Technical review preview mislukt");
  return res.json();
}

export async function runTechnicalReviewMerge(rfqId, positionId) {
  const res = await fetch(
    `${CONTEXT_API_BASE}/${rfqId}/positions/${positionId}/technical-review-merge`,
    { method: "POST" }
  );
  if (!res.ok) throw new Error("Technical review merge mislukt");
  return res.json();
}

export async function getSupplierRouting(rfqId) {
  const res = await fetch(`${API_BASE}/${rfqId}/supplier-routing`);

  if (!res.ok) {
    throw new Error("Supplier routing ophalen mislukt");
  }

  return res.json();
}

export async function getAward(rfqId) {
  const res = await fetch(`${API_BASE}/${rfqId}/award`);

  if (!res.ok) {
    throw new Error("Award ophalen mislukt");
  }

  return res.json();
}

export async function getSupplierKpi() {
  const res = await fetch(`${API_BASE}/suppliers/kpi`);

  if (!res.ok) {
    throw new Error("Supplier KPI ophalen mislukt");
  }

  return res.json();
}

export async function getRfqList() {
  const res = await fetch(`${API_BASE}/list`);
  if (!res.ok) throw new Error("RFQ lijst ophalen mislukt");
  return res.json();
}

export async function getRfq(rfqId) {
  const res = await fetch(`${API_BASE}/${rfqId}`);
  if (!res.ok) throw new Error("RFQ detail ophalen mislukt");
  return res.json();
}

export async function getSupplierComparison(rfqId) {
  const res = await fetch(`${API_BASE}/${rfqId}/supplier-comparison`);
  if (!res.ok) throw new Error("Supplier comparison ophalen mislukt");
  return res.json();
}

export async function getLatestArtifacts(rfqId) {
  const res = await fetch(`${API_BASE}/${rfqId}/artifacts/latest`);
  if (!res.ok) throw new Error("Artifacts ophalen mislukt");
  return res.json();
}

export async function getRfqTimeline(rfqId) {
  const res = await fetch(`${API_BASE}/${rfqId}/timeline`);
  if (!res.ok) throw new Error("RFQ timeline ophalen mislukt");
  return res.json();
}

export async function getCustomerEvaluation(customerName) {
  return fetch(`${API_BASE}/analysis/rfq/customer/evaluation?customer_name=${encodeURIComponent(customerName)}`).then(r => r.json());
}

export async function getSalespersonEvaluation(verkoper) {
  return fetch(`${API_BASE}/analysis/rfq/salesperson/evaluation?verkoper=${encodeURIComponent(verkoper)}`).then(r => r.json());
}