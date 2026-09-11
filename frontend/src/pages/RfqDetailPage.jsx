import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  getRfq,
  getSupplierComparison,
  getLatestArtifacts,
  getRfqTimeline,
  API_ROOT,
} from "../services/api";

const API_BASE = API_ROOT;

export default function RfqDetailPage() {
  const { rfqId } = useParams();

  const [rfq, setRfq] = useState(null);
  const [comparison, setComparison] = useState(null);
  const [artifacts, setArtifacts] = useState(null);
  const [timeline, setTimeline] = useState(null);
  const [supplierRouting, setSupplierRouting] = useState(null);
  const [error, setError] = useState("");
  const [quoteSupplierId, setQuoteSupplierId] = useState("");
  const [quoteText, setQuoteText] = useState("");
  const [quotePreview, setQuotePreview] = useState(null);
  const [quoteImporting, setQuoteImporting] = useState(false);
  const [positionDocuments, setPositionDocuments] = useState({});
  const [documentAnalysis, setDocumentAnalysis] = useState({});
  const [ocrEnabled, setOcrEnabled] = useState(false);
  const [ocrEngine, setOcrEngine] = useState("tesseract");
  const [duplicatePreview, setDuplicatePreview] = useState(null);

  const workflowSteps = [
    "INTAKE",
    "ENGINEERING",
    "COMMERCIAL",
    "PACKAGE",
    "SUPPLIER",
    "AWARD",
  ];

  function getActiveStep(status) {
    if (!status) return 0;

    const map = {
      DRAFT: 0,
      INTAKE_APPROVED: 0,

      ENGINEERING_REVIEW: 1,

      COMMERCIAL_GATE: 2,
      READY_FOR_RFQ: 3,

      SUPPLIER_PACKAGE_CREATED: 3,
      PACKAGE_GENERATED: 3,

      SUPPLIER_ROUTED: 4,
      SUPPLIER_RFQ_SENT: 4,
      QUOTATION_RECEIVED: 4,

      AWARDED: 5,
      CLOSED: 5,
    };

    return map[status] ?? 0;
  }

async function loadRfq() {
  try {
    const [
      rfqData,
      comparisonData,
      artifactData,
      timelineData,
      routingResponse,
    ] = await Promise.all([
      getRfq(rfqId),
      getSupplierComparison(rfqId),
      getLatestArtifacts(rfqId),
      getRfqTimeline(rfqId),
      fetch(`${API_BASE}/analysis/rfq/${rfqId}/supplier-routing`),
    ]);

    const routingData = await routingResponse.json();

    setRfq(rfqData);
    setComparison(comparisonData);
    setArtifacts(artifactData);
    setTimeline(timelineData);
    setSupplierRouting(routingData);

    rfqData.positions?.forEach((p) => {
      loadPositionDocuments(p.position_id);
    });
  } catch (err) {
    setError(err.message);
  }
}

useEffect(() => {
  loadRfq();
}, [rfqId]);

async function awardSupplierRfq(supplierRfqId) {
  const ok = window.confirm("Deze leverancier awarderen?");
  if (!ok) return;

  const response = await fetch(
    `${API_BASE}/analysis/rfq/supplier-rfq/${supplierRfqId}/award?awarded_by=John`,
    {
      method: "POST",
    }
  );

  const data = await response.json();

  if (!response.ok) {
    alert(data.detail || "Award failed");
    return;
  }

  alert("Supplier awarded.");
  await loadRfq();
}

async function loadDuplicatePreview() {
  const res = await fetch(`${API_BASE}/analysis/rfq/${rfqId}/positions/duplicates/cleanup-preview`);
  const data = await res.json();
  setDuplicatePreview(data);
}

async function confirmDuplicateCleanup() {
  if (!window.confirm("Weet je zeker dat je duplicate posities wilt verwijderen?")) {
    return;
  }

  await fetch(`${API_BASE}/analysis/rfq/${rfqId}/positions/duplicates/cleanup-confirm?confirm=true`, {
    method: "POST",
  });

  setDuplicatePreview(null);
  await loadRfq();
}

async function deletePositionDocument(positionId, documentId) {
  if (!confirm("Document verwijderen?")) return;

  const response = await fetch(
    `${API_BASE}/analysis/rfq/${rfqId}/positions/${positionId}/documents/${documentId}`,
    {
      method: "DELETE",
    }
  );

  const data = await response.json();

  if (!response.ok) {
    alert(data.detail || "Document verwijderen mislukt");
    return;
  }

  await loadPositionDocuments(positionId);
}

async function forceStatus(newStatus) {
  await fetch(
    `${API_BASE}/analysis/rfq/${rfqId}/workflow/force-status?status=${newStatus}&changed_by=John`,
    { method: "POST" }
  );

  await loadRfq();
}

async function extractDocumentText(positionId, documentId) {
  const response = await fetch(
    `${API_BASE}/analysis/rfq/${rfqId}/positions/${positionId}/documents/${documentId}/extract-text?ocr_enabled=${ocrEnabled}&ocr_engine=${ocrEngine}`,
    {
      method: "POST",
    }
  );

  const data = await response.json();

  if (!response.ok) {
    alert(data.detail || "Text extractie mislukt");
    return;
  }

  alert(
    `Extractie status: ${data.extraction_status}`
  );

  await loadPositionDocuments(positionId);
}

async function loadPositionDocuments(positionId) {
  const response = await fetch(
    `${API_BASE}/analysis/rfq/${rfqId}/positions/${positionId}/documents`
  );

  const data = await response.json();

  if (response.ok) {
    setPositionDocuments((prev) => ({
      ...prev,
      [positionId]: data.documents || [],
    }));
  }
}

async function uploadPositionDocument(positionId, documentType, file) {
  if (!file) return;

  const formData = new FormData();
  formData.append("document_type", documentType);
  formData.append("uploaded_by", "John");
  formData.append("file", file);

  const response = await fetch(
    `${API_BASE}/analysis/rfq/${rfqId}/positions/${positionId}/documents`,
    {
      method: "POST",
      body: formData,
    }
  );

  const data = await response.json();

  if (!response.ok) {
    alert(data.detail || "Document upload mislukt");
    return;
  }

  await loadPositionDocuments(positionId);
}

async function createSupplierRouting() {
  try {
    const response = await fetch(
      `${API_BASE}/analysis/rfq/${rfqId}/supplier-routing/create?limit=3`,
      { method: "POST" }
    );

    const data = await response.json();

    if (!response.ok) {
      alert(data.detail || "Failed to create supplier RFQs");
      return;
    }

    alert(`${data.supplier_rfqs_created} supplier RFQs created`);
    await loadRfq();
  } catch (err) {
    console.error(err);
    alert("Supplier routing failed");
  }
}

async function previewQuoteImport() {
  if (!quoteSupplierId || !quoteText) {
    alert("Kies een leverancier en plak offertetekst.");
    return;
  }

  setQuoteImporting(true);

  try {
    const response = await fetch(
      `${API_BASE}/analysis/rfq/${rfqId}/supplier-quote/import-text`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          supplier_id: quoteSupplierId,
          quote_text: quoteText,
        }),
      }
    );

    const data = await response.json();

    if (!response.ok) {
      alert(data.detail || "Quote import preview failed");
      return;
    }

    setQuotePreview(data);
  } catch (err) {
    console.error(err);
    alert("Quote import failed");
  } finally {
    setQuoteImporting(false);
  }
}

async function confirmQuoteImport() {
  if (!quotePreview?.quote_lines?.length) {
    alert("Geen quote regels om te bevestigen.");
    return;
  }

  const lines = quotePreview.quote_lines
    .filter((line) => line.matched_position_id && line.quoted_amount)
    .map((line) => ({
      supplier_id: quotePreview.supplier.supplier_id,
      position_id: line.matched_position_id,
      quoted_amount: line.quoted_amount,
      delivery_time: line.delivery_time,
      technical_deviations: null,
      commercial_deviations: null,
    }));

  if (!lines.length) {
    alert("Geen geldige regels gevonden om op te slaan.");
    return;
  }

  const response = await fetch(
    `${API_BASE}/analysis/rfq/${rfqId}/supplier-quote/confirm`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ lines }),
    }
  );

  const data = await response.json();

  if (!response.ok) {
    alert(data.detail || "Quote confirm failed");
    return;
  }

  alert(`${data.updated_count} offerte regels opgeslagen.`);

  setQuoteText("");
  setQuotePreview(null);

  await loadRfq();
}

async function analyzePositionDocuments(positionId) {
  const response = await fetch(
    `${API_BASE}/analysis/rfq/${rfqId}/positions/${positionId}/documents/analyze`,
    {
      method: "POST",
    }
  );

  const data = await response.json();

  if (!response.ok) {
    alert(data.detail || "Document analysis mislukt");
    return;
  }

  setDocumentAnalysis((prev) => ({
    ...prev,
    [positionId]: data.analysis,
  }));
}

async function analyzePositionDocuments(positionId) {
  const response = await fetch(
    `${API_BASE}/analysis/rfq/${rfqId}/positions/${positionId}/documents/analyze`,
    {
      method: "POST",
    }
  );

  const data = await response.json();

  if (!response.ok) {
    alert(data.detail || "Document analysis mislukt");
    return;
  }

  setDocumentAnalysis((prev) => ({
    ...prev,
    [positionId]: data.analysis,
  }));
}

async function extractPositionSpecs(positionId) {
  const response = await fetch(
    `${API_BASE}/analysis/rfq/${rfqId}/positions/${positionId}/documents/extract-specs`,
    {
      method: "POST",
    }
  );

  const data = await response.json();

  if (!response.ok) {
    alert(data.detail || "Spec extraction mislukt");
    return;
  }

  alert(
    `Specs extracted. Confidence: ${data.structured_specs.confidence_score}%`
  );

  await loadRfq();
}

const intake = rfq?.decision_log?.find(
  (d) => d.step === "INTAKE_EVALUATION"
)?.gpt_suggestion;

const customerScore = intake?.components?.customer_score;
const salespersonScore = intake?.components?.salesperson_score;
const combinedScore = intake?.combined_score;
const comparisonByPosition = {};

comparison?.comparison?.forEach((item) => {
  const key = item.position_id || "UNKNOWN";

  if (!comparisonByPosition[key]) {
    const pos = rfq?.positions?.find((p) => p.position_id === key);

    comparisonByPosition[key] = {
      position: pos,
      suppliers: [],
    };
  }

  comparisonByPosition[key].suppliers.push(item);
});

return (
  <div className="page">
    <header className="pageHeader">
      <div>
        <h1>RFQ Detail</h1>
        <p>{rfqId}</p>
      </div>
    </header>

    {rfq && (
      <section className="card">
        <div className="workflowStatus">
          Huidige status: <strong>{rfq?.rfq?.status || "-"}</strong>
        </div>

        <div className="workflow">
          {workflowSteps.map((step, index) => {
            const activeIndex = getActiveStep(rfq?.rfq?.status);

            return (
              <div
                key={step}
                className={`workflowStep ${index <= activeIndex ? "active" : ""}`}
              >
                <div className="workflowDot">
                  {index <= activeIndex ? "✓" : index + 1}
                </div>
                <span>{step}</span>
              </div>
            );
          })}
        </div>
      </section>
    )}


    <div className="workflow-test-panel">
      <h3>Workflow test</h3>

      <button onClick={() => forceStatus("DRAFT")}>
        Draft
      </button>

      <button onClick={() => forceStatus("ENGINEERING_REVIEW")}>
        Engineering review
      </button>

      <button onClick={() => forceStatus("COMMERCIAL_GATE")}>
        Commercial gate
      </button>

      <button onClick={() => forceStatus("READY_FOR_RFQ")}>
        Ready for RFQ
      </button>

      <button onClick={() => forceStatus("SUPPLIER_PACKAGE_CREATED")}>
        Package created
      </button>

      <button onClick={() => forceStatus("SUPPLIER_ROUTED")}>
        Supplier routed
      </button>

      <button onClick={() => forceStatus("SUPPLIER_RFQ_SENT")}>
        Supplier sent
      </button>

      <button onClick={() => forceStatus("CLOSED")}>
        Closed
      </button>

      <button onClick={loadDuplicatePreview}>
        Duplicate check
      </button>
    </div>

      {rfq && (
        <section className="card">
          <h2>RFQ informatie</h2>

          <div className="rfq-grid">
            <div className="rfq-box">
              <h3>Odoo</h3>
              <p>{rfq?.rfq?.odoo_reference || "-"}</p>
            </div>

            <div className="rfq-box">
              <h3>Klant</h3>
              <p>{rfq?.rfq?.customer_name_internal || "-"}</p>
            </div>

            <div className="rfq-box">
              <h3>Status</h3>
              <p>{rfq?.rfq?.status || "-"}</p>
            </div>

            <div className="rfq-box">
              <h3>Route</h3>
              <p>{rfq?.rfq?.selected_route || "-"}</p>
            </div>

            <div className="rfq-box">
              <h3>Verkoper</h3>
              <p>{rfq?.rfq?.verkoper || "-"}</p>
            </div>

            <div className="rfq-box">
              <h3>Klanttype</h3>
              <p>{rfq?.rfq?.customer_type || "-"}</p>
            </div>
          </div>
        </section>
      )}

      {duplicatePreview && (
        <div className="card">
          <h3>Duplicate cleanup preview</h3>
          <p>{duplicatePreview.cleanup_group_count} duplicate groepen gevonden</p>

          {duplicatePreview.cleanup_plan?.map((group) => (
            <div key={group.duplicate_key}>
              <strong>{group.duplicate_key}</strong>
              <p>Behouden: {group.keep_pos_nr}</p>
              <p>Verwijderen: {group.remove_pos_nrs?.join(", ") || "-"}</p>
            </div>
          ))}

          <button className="dangerButton" onClick={confirmDuplicateCleanup}>
            Cleanup
          </button>
        </div>
      )}

      {rfq?.positions?.length > 0 && (
        <section className="card">
          <div className="sectionHeader">
            <h2>Posities</h2>

            <label className="ocrToggle">
              <input
                type="checkbox"
                checked={ocrEnabled}
                onChange={(e) => setOcrEnabled(e.target.checked)}
              />
              OCR fallback inschakelen
            </label>

            <select
              className="ocrEngineSelect"
              value={ocrEngine}
              onChange={(e) => setOcrEngine(e.target.value)}
              disabled={!ocrEnabled}
            >
              <option value="tesseract">Tesseract</option>
              <option value="openai">OpenAI Vision</option>
            </select>

            <Link
              to={`/rfq/${rfqId}/positions/new`}
              className="buttonPrimary"
            >
              + Add position
            </Link>
          </div>

          <table className="positionsTable">
            <thead>
              <tr>
                <th>Positie</th>
                <th>Type</th>
                <th>Aantal</th>
                <th>Tekening</th>
                <th>Diameter</th>
                <th>Breedte</th>
                <th>Status</th>
                <th>Completeness</th>
                <th>Confidence</th>
                <th>Acties</th>
              </tr>
            </thead>

            
              <tbody>
                {rfq.positions.map((p) => {
                  const specs = p.extracted_specs || {};
                  const docs = positionDocuments[p.position_id] || [];
                  const analysis = documentAnalysis[p.position_id];

                  return [
                    <tr key={`${p.position_id}-main`}>
                      <td>{p.pos_nr}</td>
                      <td>{p.product_type}</td>
                      <td>{p.quantity}</td>
                      <td>{p.drawing_mark || "-"}</td>
                      <td>{specs.diameter_de_mm || specs.diameter_mm || "-"}</td>
                      <td>{specs.drum_width_mm || specs.mantel_lengte_mm || "-"}</td>
                      <td>
                        <span className={`statusBadge status-${(p.position_status || "").toLowerCase()}`}>
                          {p.position_status || "-"}
                        </span>
                      </td>
                      <td>{p.completeness_score ?? 0}%</td>
                      <td>{p.confidence_score ?? "-"}</td>
                      <td></td>
                    </tr>,

                    <tr key={`${p.position_id}-details`} className="positionDetailRow">
                      <td colSpan="10">
                        <div className="positionDetailPanel">
                          <div className="positionDocumentsPanel">
                            <strong>Documents</strong>

                            {docs.length === 0 && (
                              <span className="emptyDocuments">Geen documenten</span>
                            )}

                            {docs.map((doc) => (
                              <span className="documentBadge documentBadgeWithDelete" key={doc.document_id}>
                                {doc.document_type}: {doc.file_name}

                                <button
                                  type="button"
                                  className="documentDeleteButton"
                                  onClick={() => deletePositionDocument(p.position_id, doc.document_id)}
                                >
                                  🗑
                                </button>
                              </span>
                            ))}
                          </div>

                          <div className="positionActionBar">
                            <label className="uploadButton">
                              Upload DRAWING
                              <input
                                type="file"
                                accept=".pdf,.png,.jpg,.jpeg"
                                hidden
                                onChange={(e) =>
                                  uploadPositionDocument(
                                    p.position_id,
                                    "DRAWING",
                                    e.target.files?.[0]
                                  )
                                }
                              />
                            </label>

                            <label className="uploadButton">
                              Upload TECH SPEC
                              <input
                                type="file"
                                accept=".pdf,.doc,.docx,.txt"
                                hidden
                                onChange={(e) =>
                                  uploadPositionDocument(
                                    p.position_id,
                                    "TECH_SPEC",
                                    e.target.files?.[0]
                                  )
                                }
                              />
                            </label>

                            <button
                              className="secondaryButton"
                              onClick={() => analyzePositionDocuments(p.position_id)}
                            >
                              Analyze documents
                            </button>

                            <button
                              className="secondaryButton"
                              onClick={() => extractPositionSpecs(p.position_id)}
                            >
                              Extract specs
                            </button>

                            <button
                              className="secondaryButton"
                              onClick={() => {
                                const docs = positionDocuments[p.position_id] || [];
                                docs.forEach((doc) => extractDocumentText(p.position_id, doc.document_id));
                              }}
                            >
                              Extract text
                            </button>

                            <Link
                              to={`/rfq/${rfqId}/positions/${p.position_id}/dashboard`}
                              className="secondaryButton"
                            >
                              RFQ Dashboard
                            </Link>

                            <Link
                              to={`/rfq/${rfqId}/positions/${p.position_id}/technical`}
                              className="tableLink"
                            >
                              Technical Review
                            </Link>

                            <a
                              href={`${API_BASE}/analysis/rfq/${rfqId}/positions/${p.position_id}/datasheet/pdf?view_mode=supplier`}
                              target="_blank"
                              rel="noreferrer"
                              className="secondaryButton"
                            >
                              Supplier PDF
                            </a>

                            <button
                              className="dangerButton"
                              onClick={() => deletePosition(p.position_id)}
                            >
                              Delete
                            </button>
                          </div>

                          {analysis && (
                            <div className="documentAnalysisWide">
                              <strong>{analysis.completeness_score}% complete</strong>
                              <span>
                                {analysis.missing_document_types?.length
                                  ? `Missing: ${analysis.missing_document_types.join(", ")}`
                                  : "Ready for analysis"}
                              </span>
                              <em>{analysis.recommendation}</em>
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>,
                  ];
                })}
              </tbody>
          </table>
        </section>
      )}

        {supplierRouting?.recommended_suppliers?.length > 0 && (
          <section className="card">
            <div className="sectionHeader">
              <h2>Recommended suppliers</h2>

              <button
                className="buttonPrimary"
                onClick={createSupplierRouting}
              >
                Create supplier RFQs
              </button>
            </div>

            <div className="supplierGrid">
              {supplierRouting.recommended_suppliers.map((s) => (
                <div className="supplierCard" key={s.supplier_id}>
                  <h3>{s.supplier_name}</h3>
                  <p><strong>{s.classification}</strong></p>
                  <p>Total score: {s.total_score}</p>
                  <p>{s.reason}</p>

                  <div className="supplierTags">
                    {s.approved_for?.map((tag) => (
                      <span className="supplierTag" key={tag}>
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {supplierRouting?.recommended_suppliers?.length > 0 && (
          <section className="card">
            <h2>Import supplier quote</h2>

            <div className="formGrid">
              <div>
                <label>Supplier</label>

                <select
                  value={quoteSupplierId}
                  onChange={(e) => setQuoteSupplierId(e.target.value)}
                >
                  <option value="">Select supplier</option>

                  {supplierRouting.recommended_suppliers.map((s) => (
                    <option key={s.supplier_id} value={s.supplier_id}>
                      {s.supplier_name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label>Quote text</label>

                <textarea
                  value={quoteText}
                  onChange={(e) => setQuoteText(e.target.value)}
                  rows={8}
                  placeholder="Plak hier de offertetekst..."
                />
              </div>
            </div>

            <button
              className="buttonPrimary"
              onClick={previewQuoteImport}
              disabled={quoteImporting}
            >
              {quoteImporting ? "Importing..." : "Preview quote import"}
            </button>

            {quotePreview?.quote_lines?.length > 0 && (
              <div className="quotePreview">
                <h3>Preview</h3>

                <table className="positionsTable">
                  <thead>
                    <tr>
                      <th>Regel</th>
                      <th>Match</th>
                      <th>Confidence</th>
                      <th>Prijs</th>
                      <th>Levertijd</th>
                      <th>Review</th>
                    </tr>
                  </thead>

                  <tbody>
                    {quotePreview.quote_lines.map((line, index) => (
                      <tr key={index}>
                        <td>{line.raw_line}</td>
                        <td>{line.matched_pos_nr || "-"}</td>
                        <td>{line.match_confidence}%</td>
                        <td>{line.quoted_amount ? `€ ${line.quoted_amount}` : "-"}</td>
                        <td>{line.delivery_time || "-"}</td>
                        <td>{line.needs_review ? "YES" : "NO"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                <button
                  className="buttonPrimary"
                  onClick={confirmQuoteImport}
                >
                  Confirm quote import
                </button>
              </div>
            )}
          </section>
        )}

        <section className="card ai-card">
          <h2>AI beoordeling</h2>

          <div className="ai-grid">
            <div><strong>RFQ completeness</strong><span>{combinedScore ? `${combinedScore}%` : "82%"}</span></div>
            <div><strong>Supplier fit</strong><span>Premium advised</span></div>
            <div><strong>Technical risk</strong><span className="risk-medium">Medium</span></div>
            <div><strong>Missing fields</strong><span>Balancing class</span></div>
            <div><strong>Recommended route</strong><span>{rfq?.rfq?.selected_route || "-"}</span></div>
            <div><strong>AI confidence</strong><span>High</span></div>
          </div>
        </section>

    {comparison && (
      <>
        <section className="card">
  <h2>Supplier comparison by position</h2>

  {Object.values(comparisonByPosition).map((group) => {
    const validQuotes = group.suppliers.filter((s) => s.quoted_amount != null);

    const lowestPrice = validQuotes.length
      ? Math.min(...validQuotes.map((s) => s.quoted_amount))
      : null;

    const cheapestSupplier = validQuotes.length
      ? validQuotes.reduce((prev, curr) =>
          curr.quoted_amount < prev.quoted_amount ? curr : prev
        )
      : null;

    const suppliersWithLeadtime = validQuotes.filter((s) => s.delivery_time);

    const fastestSupplier = suppliersWithLeadtime.length
      ? suppliersWithLeadtime.reduce((prev, curr) => {
          const prevWeeks = parseInt(prev.delivery_time);
          const currWeeks = parseInt(curr.delivery_time);
          return currWeeks < prevWeeks ? curr : prev;
        })
      : null;

    const bestCommercialOption = cheapestSupplier || fastestSupplier;

    return (
      <div className="positionComparison" key={group.position?.position_id || "unknown"}>
        <h3>
          {group.position?.pos_nr || "Unknown position"} —{" "}
          {group.position?.product_type || "-"} —{" "}
          {group.position?.drawing_mark || "-"}
        </h3>

        <div className="comparisonGrid">
          {group.suppliers.map((s) => (
            <div className="comparisonCard" key={s.supplier_rfq_id}>
              <h4>{s.supplier_name}</h4>

              <div className="supplierBadgeRow">
                {s.classification && (
                  <span className={`supplierBadge classification-${s.classification.toLowerCase()}`}>
                    {s.classification}
                  </span>
                )}

                {s.risk_flags?.length > 0 && (
                  <span className="supplierBadge risk-badge">RISK</span>
                )}

                {lowestPrice != null && s.quoted_amount === lowestPrice && (
                  <span className="supplierBadge best-price">BEST PRICE</span>
                )}

                {fastestSupplier?.supplier_rfq_id === s.supplier_rfq_id && (
                  <span className="supplierBadge fastest-option">FASTEST</span>
                )}

                {bestCommercialOption?.supplier_rfq_id === s.supplier_rfq_id && (
                  <span className="supplierBadge best-option">BEST OPTION</span>
                )}
              </div>

              <p>
                <strong>Status:</strong>{" "}
                <span className={`statusBadge status-${s.status?.toLowerCase()}`}>
                  {s.status}
                </span>
              </p>

              <p>
                <strong>Prijs:</strong>{" "}
                {s.quoted_amount != null ? `€ ${s.quoted_amount}` : "Nog niet ontvangen"}
              </p>

              <p><strong>Levertijd:</strong> {s.delivery_time || "-"}</p>
              <p><strong>Score:</strong> {s.supplier_score}</p>
              <p><strong>Risico:</strong> {s.risk_flags?.length ? s.risk_flags.join(", ") : "Geen"}</p>

              {s.status === "RECEIVED" && (
                <button
                  className="buttonPrimary"
                  onClick={() => awardSupplierRfq(s.supplier_rfq_id)}
                >
                  Award
                </button>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  })}
</section>

        <section className="card">
          <h2>Commercial evaluation</h2>

          {(() => {
            const groups = Object.values(comparisonByPosition);

            const quotedPositions = groups.filter((g) =>
              g.suppliers.some((s) => s.quoted_amount != null)
            ).length;

            const awardedPositions = groups.filter((g) =>
              g.suppliers.some((s) => s.status === "AWARDED")
            ).length;

            const totalAwardedValue = groups.reduce((sum, g) => {
              const awarded = g.suppliers.find((s) => s.status === "AWARDED");
              return sum + (awarded?.quoted_amount || 0);
            }, 0);

            const openQuotedValue = groups.reduce((sum, g) => {
              const awarded = g.suppliers.find((s) => s.status === "AWARDED");
              if (awarded) return sum;

              const quotes = g.suppliers.filter((s) => s.quoted_amount != null);
              if (!quotes.length) return sum;

              return sum + Math.min(...quotes.map((s) => s.quoted_amount));
            }, 0);

            const lowestPossibleValue = groups.reduce((sum, g) => {
              const quotes = g.suppliers.filter((s) => s.quoted_amount != null);
              if (!quotes.length) return sum;

              return sum + Math.min(...quotes.map((s) => s.quoted_amount));
            }, 0);

            const awardDelta = totalAwardedValue - lowestPossibleValue;

            const commercialDecisionQuality =
              awardedPositions === 0
                ? "Pending"
                : awardDelta <= 0
                  ? "Best price selected"
                  : "Higher price selected";

            const commercialRecommendation =
              awardDelta <= 0
                ? "ACCEPTABLE"
                : awardDelta < 250
                  ? "REVIEW"
                  : "HIGH COST";

            const commercialReason =
              awardDelta <= 0
                ? "Awarded supplier is the cheapest option"
                : awardDelta < 250
                  ? "Awarded supplier is above cheapest but within acceptable range"
                  : "Awarded supplier significantly exceeds cheapest quotation";

            const positionsWithoutQuote = groups.filter(
              (g) => !g.suppliers.some((s) => s.quoted_amount != null)
            ).length;

            const singleQuotePositions = groups.filter(
              (g) =>
                g.suppliers.filter((s) => s.quoted_amount != null).length === 1
            ).length;

            const overallRiskLevel =
              positionsWithoutQuote > 0
                ? "HIGH"
                : singleQuotePositions > 0
                  ? "MEDIUM"
                  : "LOW";

            const riskReasoning =
              positionsWithoutQuote > 0
                ? `${positionsWithoutQuote} positions still have no quotation`
                : singleQuotePositions > 0
                  ? `${singleQuotePositions} positions have only one quotation`
                  : "All positions have competitive quote coverage";

            return (
              <div className="commercialSummary">
                <div>
                  <strong>Quoted positions</strong>
                  <span>{quotedPositions} / {groups.length}</span>
                </div>

                <div>
                  <strong>Awarded positions</strong>
                  <span>{awardedPositions} / {groups.length}</span>
                </div>

                <div>
                  <strong>Total awarded value</strong>
                  <span>€ {totalAwardedValue}</span>
                </div>

                <div>
                  <strong>Open quoted value</strong>
                  <span>€ {openQuotedValue}</span>
                </div>

                <div>
                  <strong>Decision quality</strong>
                  <span>{commercialDecisionQuality}</span>
                </div>

                <div>
                  <strong>AI recommendation</strong>
                  <span
                    className={
                      commercialRecommendation === "ACCEPTABLE"
                        ? "recommendation-good"
                        : commercialRecommendation === "REVIEW"
                          ? "recommendation-review"
                          : "recommendation-bad"
                    }
                  >
                    {commercialRecommendation}
                  </span>
                </div>

                <div>
                  <strong>AI reasoning</strong>
                  <span>{commercialReason}</span>
                </div>

                <div>
                  <strong>Risk level</strong>
                  <span
                    className={
                      overallRiskLevel === "LOW"
                        ? "risk-low"
                        : overallRiskLevel === "MEDIUM"
                          ? "risk-medium"
                          : "risk-high"
                    }
                  >
                    {overallRiskLevel}
                  </span>
                </div>

                <div>
                  <strong>Risk reasoning</strong>
                  <span>{riskReasoning}</span>
                </div>
              </div>
            );
          })()}

          <div className="commercialGrid">
            {Object.values(comparisonByPosition).map((group) => {
              const validQuotes = group.suppliers.filter(
                (s) => s.quoted_amount != null
              );

              const lowestPrice = validQuotes.length
                ? Math.min(...validQuotes.map((s) => s.quoted_amount))
                : null;

              const awardedSupplier = group.suppliers.find(
                (s) => s.status === "AWARDED"
              );

              const cheapestSupplier = validQuotes.length
                ? validQuotes.reduce((prev, curr) =>
                    curr.quoted_amount < prev.quoted_amount ? curr : prev
                  )
                : null;

              const suppliersWithLeadtime = validQuotes.filter(
                (s) => s.delivery_time
              );

              const fastestSupplier = suppliersWithLeadtime.length
                ? suppliersWithLeadtime.reduce((prev, curr) => {
                    const prevWeeks = parseInt(prev.delivery_time);
                    const currWeeks = parseInt(curr.delivery_time);

                    return currWeeks < prevWeeks ? curr : prev;
                  })
                : null;

              const bestCommercialOption = cheapestSupplier || fastestSupplier;

              const savingsAmount =
                awardedSupplier &&
                cheapestSupplier &&
                awardedSupplier.quoted_amount != null
                  ? cheapestSupplier.quoted_amount - awardedSupplier.quoted_amount
                  : null;

              const savingsPercent =
                savingsAmount !== null && cheapestSupplier?.quoted_amount
                  ? ((savingsAmount / cheapestSupplier.quoted_amount) * 100).toFixed(1)
                  : null;

              return (
                <div
                  className="commercialCard"
                  key={group.position?.position_id || "unknown"}
                >
                  <h3>
                    {group.position?.pos_nr || "-"} —{" "}
                    {group.position?.product_type || "-"}
                  </h3>

                  <p>
                    <strong>Quoted suppliers:</strong> {validQuotes.length}
                  </p>

                  <p>
                    <strong>Lowest price:</strong>{" "}
                    {lowestPrice != null ? `€ ${lowestPrice}` : "-"}
                  </p>

                  <p>
                    <strong>Awarded supplier:</strong>{" "}
                    {awardedSupplier?.supplier_name || "-"}
                  </p>

                  <p>
                    <strong>Cheapest supplier:</strong>{" "}
                    {cheapestSupplier?.supplier_name || "-"}
                  </p>

                  <p>
                    <strong>Fastest supplier:</strong>{" "}
                    {fastestSupplier?.supplier_name || "-"}
                  </p>

                  <p>
                    <strong>Best commercial option:</strong>{" "}
                    {bestCommercialOption?.supplier_name || "-"}
                  </p>

                  <p>
                    <strong>Savings vs cheapest:</strong>{" "}
                    {savingsAmount !== null
                      ? `€ ${Math.abs(savingsAmount)} (${Math.abs(savingsPercent)}%)`
                      : "-"}
                  </p>

                  <p>
                    <strong>AI advice:</strong>{" "}
                    {lowestPrice != null
                      ? "Commercially acceptable"
                      : "Waiting for quotations"}
                  </p>
                </div>
              );
            })}
          </div>
        </section>
      </>
    )}

      {timeline && (
        <section className="card">
          <h2>RFQ timeline</h2>

          <div className="timeline">
            {timeline.events.map((e, index) => (
              <div className="timelineItem" key={index}>
                <div className="timelineDot" />

                <div className="timelineContent">
                  <strong>{e.event_type}</strong>

                  <p>{e.description}</p>

                  <span>
                    {new Date(e.event_time).toLocaleString()} — {e.actor}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
