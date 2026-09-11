import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  getEngineeringReviewV2,
  getOcrPreview,
  runOcrMerge,
  getTechnicalReviewPreview,
  runTechnicalReviewMerge,
  API_ROOT,
} from "../services/api";

export default function RfqTechnicalPage() {
  const { rfqId, positionId } = useParams();
  const navigate = useNavigate();

  const [rfq, setRfq] = useState(null);
  const [loading, setLoading] = useState(true);
  const [editSpecs, setEditSpecs] = useState({});
  const [saving, setSaving] = useState(false);
  const [documentStatus, setDocumentStatus] = useState(null);
  const [engineeringReview, setEngineeringReview] = useState(null);
  const [ocrPreview, setOcrPreview] = useState(null);
  const [technicalReview, setTechnicalReview] = useState(null);
  const [actionBusy, setActionBusy] = useState(false);
  const [actionMessage, setActionMessage] = useState("");

  useEffect(() => {
    loadRfq();
    loadDocumentStatus();
    loadEngineeringReview();
  }, [rfqId, positionId]);

  async function loadRfq() {
    try {
      setLoading(true);

      const response = await fetch(
        `${API_ROOT}/analysis/rfq/${rfqId}`
      );

      const data = await response.json();

      setRfq(data);

      const currentPosition =
        data?.positions?.find((p) => p.position_id === positionId) ||
        data?.positions?.[0];

      if (currentPosition?.extracted_specs) {
        setEditSpecs(currentPosition.extracted_specs);
      }

    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  function updateSpec(key, value) {
    setEditSpecs((prev) => ({
      ...prev,
      [key]: value,
    }));
  }

  async function loadDocumentStatus() {
    const response = await fetch(
      `${API_ROOT}/analysis/rfq/${rfqId}/positions/${positionId}/documents/status`
    );

    const data = await response.json();
    setDocumentStatus(data);
  }

  async function loadEngineeringReview() {
    try {
      const data = await getEngineeringReviewV2(rfqId, positionId);
      setEngineeringReview(data);
    } catch (err) {
      console.error(err);
    }
  }

  async function handleOcrPreview() {
    try {
      setActionBusy(true);
      setActionMessage("OCR preview ophalen...");
      const data = await getOcrPreview(rfqId, positionId);
      setOcrPreview(data);
      setActionMessage("OCR preview opgehaald.");
    } catch (err) {
      console.error(err);
      setActionMessage("OCR preview mislukt.");
    } finally {
      setActionBusy(false);
    }
  }

  async function handleOcrMerge() {
    try {
      setActionBusy(true);
      setActionMessage("OCR merge uitvoeren...");
      const data = await runOcrMerge(rfqId, positionId);
      setOcrPreview(data);
      setActionMessage("OCR merge uitgevoerd.");
      await loadEngineeringReview();
      await loadRfq();
    } catch (err) {
      console.error(err);
      setActionMessage("OCR merge mislukt.");
    } finally {
      setActionBusy(false);
    }
  }

  async function handleTechnicalReviewPreview() {
    try {
      setActionBusy(true);
      setActionMessage("Phi-3 technische review ophalen...");
      const data = await getTechnicalReviewPreview(rfqId, positionId);
      setTechnicalReview(data);
      setActionMessage("Phi-3 technische review opgehaald.");
    } catch (err) {
      console.error(err);
      setActionMessage("Phi-3 technische review mislukt.");
    } finally {
      setActionBusy(false);
    }
  }

  async function handleTechnicalReviewMerge() {
    try {
      setActionBusy(true);
      setActionMessage("Phi-3 technische review opslaan...");
      const data = await runTechnicalReviewMerge(rfqId, positionId);
      setTechnicalReview(data);
      setActionMessage(
        data?.status === "model_fallback_not_saved"
          ? "Fallback niet opgeslagen. Probeer opnieuw."
          : "Phi-3 technische review opgeslagen."
      );
      await loadEngineeringReview();
      await loadRfq();
    } catch (err) {
      console.error(err);
      setActionMessage("Phi-3 technische review opslaan mislukt.");
    } finally {
      setActionBusy(false);
    }
  }

  async function saveTechnicalSpecs() {
    if (!position?.position_id) return;

    setSaving(true);

    try {
      const response = await fetch(
        `${API_ROOT}/analysis/rfq/${rfqId}/positions/${position.position_id}/technical-specs`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            extracted_specs: editSpecs,
            missing_fields: position.missing_fields || [],
            confidence_score: position.confidence_score,
          }),
        }
      );

      const json = await response.json();

      await loadRfq();

      alert("Engineering review opgeslagen. Status en completeness zijn bijgewerkt.");
    } catch (err) {
      console.error(err);
      alert("Opslaan mislukt.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="page">
        <h1>Loading technical review...</h1>
      </div>
    );
  }

  const position =
    rfq?.positions?.find((p) => p.position_id === positionId) ||
    rfq?.positions?.[0];

  const specs = position?.extracted_specs || {};
  const classification = specs?.classification || {};

  const getOcrValue = (key) => {
    return (
      ocrPreview?.extracted?.[key] ??
      ocrPreview?.updated_spec?.[key] ??
      ocrPreview?.updated_spec?.extracted_fields?.[key] ??
      engineeringReview?.context?.extracted_specs?.[key] ??
      engineeringReview?.extracted_specs?.[key] ??
      position?.extracted_specs?.[key] ??
      position?.[key] ??
      "-"
    );
  };

const savedTechnicalReview =
  technicalReview?.updated_spec?.extracted_fields?.technical_review;

const currentTechnicalReview =
  technicalReview?.techreview || savedTechnicalReview || null;

const currentTechnicalReviewData =
  currentTechnicalReview?.review || technicalReview?.review || null;

const technicalProposals =
  currentTechnicalReviewData?.technical_proposals || {};

const supplierQuestions =
  currentTechnicalReviewData?.supplier_questions || [];

const engineeringNotes =
  currentTechnicalReviewData?.engineering_notes || [];

const standardSuggestions =
  engineeringReview?.standard_suggestions || [];

const standardSupplierQuestions =
  engineeringReview?.standard_supplier_questions || [];

const standardEngineeringNotes =
  engineeringReview?.standard_engineering_notes || [];

const currentMissingFields =
  engineeringReview?.missing_fields?.map((item) => {
    if (typeof item === "string") return item;
    return item?.field || item?.label || "";
  }).filter(Boolean) || [];

return (
  <div className="page">

      <div className="pageHeader">
        <div>
          <h1>Engineering Workspace</h1>

          <p className="subtitle">
            RFQ {rfq?.rfq?.odoo_reference}
            {" — "}
            Positie {position?.pos_nr || "-"}
            {" — "}
            {position?.product_type || "-"}
          </p>
        </div>

        <button
          className="backButton"
          onClick={() => navigate(`/rfq/${rfqId}`)}
        >
          Back to RFQ
        </button>
      </div>

      <section className="card technicalHero">
        <div>
          <h2>
            {position?.product_type || "Unknown product"}
          </h2>

          <p className="drawingRef">
            {position?.drawing_mark}
          </p>
        </div>

        {editSpecs?.drawing_number || editSpecs?.doc_number ? (
          <div className="drawingMeta">
            Drawing no: {editSpecs?.drawing_number || editSpecs?.doc_number}
          </div>
        ) : null}

        <div className="confidenceBadge">
          Confidence {position?.confidence_score}%
        </div>
      </section>

      <div className="technicalGrid">

      <section className="card fullWidth">
        <div className="sectionHeader">
          <div>
            <h2>OCR & Phi-3 technische review</h2>
            <p>
              Interne engineering-acties. Phi-3 doet alleen voorstellen; locked fields
              worden niet automatisch ingevuld.
            </p>
          </div>
        </div>

        <div className="positionActionBar">
          <button onClick={handleOcrPreview} disabled={actionBusy}>
            OCR preview
          </button>

          <button onClick={handleOcrMerge} disabled={actionBusy}>
            OCR merge
          </button>

          <button onClick={handleTechnicalReviewPreview} disabled={actionBusy}>
            Phi-3 preview
          </button>

          <button onClick={handleTechnicalReviewMerge} disabled={actionBusy}>
            Phi-3 opslaan
          </button>
        </div>

        {actionMessage ? (
          <div className="documentAnalysisWide">
            <strong>Status</strong>
            <em>{actionMessage}</em>
          </div>
        ) : null}

        <div className="technicalReviewGrid">
          <div className="technicalReviewBox">
            <h3>Engineering review</h3>
            <p>
              <strong>Product:</strong>{" "}
              {engineeringReview?.context?.product_type ||
                engineeringReview?.product_type ||
                position?.product_type ||
                "-"}
            </p>
            <p>
              <strong>Confidence:</strong>{" "}
              {engineeringReview?.context?.confidence_score ||
                position?.confidence_score ||
                "-"}
            </p>
            <p>
              <strong>Missing:</strong>{" "}
              {(engineeringReview?.context?.missing_fields || position?.missing_fields || [])
                .join(", ") || "-"}
            </p>
          </div>

          <div className="technicalReviewBox">
            <h3>OCR extractie</h3>
            <p>
              <strong>Status:</strong> {ocrPreview?.status || "-"}
            </p>
            <p>
              <strong>Tekstlengte:</strong>{" "}
              {ocrPreview?.edocr2?.text_length || ocrPreview?.text_length || "-"}
            </p>
            <p>
              <strong>Diameter:</strong> {getOcrValue("diameter_mm")}
            </p>
            <p>
              <strong>Mantellengte:</strong> {getOcrValue("drum_width_mm")}
            </p>
            <p>
              <strong>Asdiameter:</strong> {getOcrValue("shaft_diameter_mm")}
            </p>
          </div>

          <div className="technicalReviewBox">
            <h3>Phi-3 review</h3>
            <p>
              <strong>Model:</strong> {currentTechnicalReview?.model || "-"}
            </p>
            <p>
              <strong>Runtime:</strong> {currentTechnicalReview?.runtime || "-"}
            </p>
            <p>
              <strong>Assessment:</strong>{" "}
              {currentTechnicalReviewData?.technical_assessment ||
                technicalReview?.technical_assessment ||
                "-"}
            </p>
            <p>
              <strong>Risk:</strong>{" "}
              {currentTechnicalReviewData?.risk_level ||
                technicalReview?.risk_level ||
                "-"}
            </p>
          </div>
        </div>

        {currentTechnicalReviewData ? (
          <div className="technicalReviewDetails">
            <div className="technicalReviewDetailBlock">
              <h3>Technische voorstellen</h3>

              {Object.keys(technicalProposals).length === 0 ? (
                <p>Geen technische voorstellen beschikbaar.</p>
              ) : (
                Object.entries(technicalProposals).map(([field, proposal]) => (
                  <div className="proposalCard" key={field}>
                    <h4>{field}</h4>
                    <p>
                      <strong>Voorstel:</strong>{" "}
                      {proposal?.proposal || "-"}
                    </p>
                    <p>
                      <strong>Risico indien ontbrekend:</strong>{" "}
                      {proposal?.risk_if_missing || "-"}
                    </p>
                    <p>
                      <strong>Leveranciersvraag:</strong>{" "}
                      {proposal?.supplier_question || "-"}
                    </p>
                    <p>
                      <strong>Confidence:</strong>{" "}
                      {proposal?.confidence || "-"}
                    </p>
                  </div>
                ))
              )}
            </div>

            <div className="technicalReviewDetailBlock">
              <h3>Leveranciersvragen</h3>

              {supplierQuestions.length === 0 ? (
                <p>Geen leveranciersvragen beschikbaar.</p>
              ) : (
                <ul>
                  {supplierQuestions.map((question, index) => (
                    <li key={`${question}-${index}`}>{question}</li>
                  ))}
                </ul>
              )}
            </div>

            <div className="technicalReviewDetailBlock">
              <h3>Engineering notes</h3>

              {engineeringNotes.length === 0 ? (
                <p>Geen engineering notes beschikbaar.</p>
              ) : (
                <ul>
                  {engineeringNotes.map((note, index) => (
                    <li key={`${note}-${index}`}>{note}</li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        ) : null}
        {(
          standardSuggestions.length > 0 ||
          standardSupplierQuestions.length > 0 ||
          standardEngineeringNotes.length > 0
        ) ? (
          <div className="technicalReviewDetails standardKnowledgeDetails">
            <div className="technicalReviewDetailBlock">
              <h3>Normvoorstellen</h3>

              {standardSuggestions.length === 0 ? (
                <p>Geen normvoorstellen beschikbaar.</p>
              ) : (
                standardSuggestions.map((suggestion, index) => (
                  <div
                    className="proposalCard"
                    key={`${suggestion.field || "suggestion"}-${index}`}
                  >
                    <h4>{suggestion.label || suggestion.field}</h4>

                    <p>
                      <strong>Voorstel:</strong>{" "}
                      {Array.isArray(suggestion.proposed_values)
                        ? `${suggestion.proposed_values.join(" / ")} ${suggestion.unit || ""}`
                        : suggestion.proposed_value || "-"}
                    </p>

                    <p>
                      <strong>Bron:</strong> {suggestion.source || "-"}
                    </p>

                    <p>
                      <strong>Status:</strong> {suggestion.status || "-"}
                    </p>

                    <p>
                      <strong>Confidence:</strong> {suggestion.confidence || "-"}
                    </p>

                    <p>
                      <strong>Reden:</strong> {suggestion.reason || "-"}
                    </p>

                    {suggestion.match ? (
                      <div className="standardMatchBox">
                        <p>
                          <strong>Match:</strong>{" "}
                          D {suggestion.match.input_diameter_mm} →{" "}
                          {suggestion.match.matched_diameter_mm} mm, bandbreedte{" "}
                          {suggestion.match.input_belt_width_candidate_mm} →{" "}
                          {suggestion.match.matched_belt_width_mm} mm
                        </p>

                        <p>
                          <strong>Afwijking:</strong>{" "}
                          diameter {suggestion.match.diameter_delta_mm} mm,
                          bandbreedte {suggestion.match.belt_width_delta_mm} mm
                        </p>
                      </div>
                    ) : null}
                  </div>
                ))
              )}
            </div>
            <div className="technicalReviewDetailBlock">
              <h3>Standaard leveranciersvragen</h3>

              {standardSupplierQuestions.length === 0 ? (
                <p>Geen standaard leveranciersvragen beschikbaar.</p>
              ) : (
                <ul>
                  {standardSupplierQuestions.map((question, index) => (
                    <li key={`${question}-${index}`}>{question}</li>
                  ))}
                </ul>
              )}
            </div>

            <div className="technicalReviewDetailBlock">
              <h3>Norm engineering notes</h3>

              {standardEngineeringNotes.length === 0 ? (
                <p>Geen norm engineering notes beschikbaar.</p>
              ) : (
                <ul>
                  {standardEngineeringNotes.map((note, index) => (
                    <li key={`${note}-${index}`}>{note}</li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        ) : null}
      </section>

        {/* CORE SPECIFICATIONS */}

        <section className="card">
          <h2>Core specifications</h2>

          <div className="specGrid">

            <div className="specRow">
              <strong>Diameter</strong>
              <input
                className="specInput"
                value={editSpecs?.diameter_mm || ""}
                onChange={(e) => updateSpec("diameter_mm", e.target.value)}
              />
            </div>

            <div className="specRow">
              <strong>Outside diameter</strong>
              <input
                className="specInput"
                value={editSpecs?.outside_diameter_mm || ""}
                onChange={(e) => updateSpec("outside_diameter_mm", e.target.value)}
              />
            </div>

            <div className="specRow">
              <strong>Drum width</strong>
              <input
                className="specInput"
                value={editSpecs?.drum_width_mm || ""}
                onChange={(e) => updateSpec("drum_width_mm", e.target.value)}
              />
            </div>

            <div className="specRow">
              <strong>Total length</strong>
              <input
                className="specInput"
                value={editSpecs?.total_length_mm || ""}
                onChange={(e) => updateSpec("total_length_mm", e.target.value)}
              />
            </div>

            <div className="specRow">
              <strong>Mantellengte</strong>
              <input
                className="specInput"
                value={editSpecs?.mantel_lengte_mm || ""}
                onChange={(e) => updateSpec("mantel_lengte_mm", e.target.value)}
              />
            </div>

            <div className="specRow">
              <strong>Hart-op-hart lagers</strong>
              <input
                className="specInput"
                value={editSpecs?.bearing_center_distance_mm || ""}
                onChange={(e) =>
                  updateSpec("bearing_center_distance_mm", e.target.value)
                }
              />
            </div>

            <div className="specRow">
              <strong>Shaft diameter</strong>
              <input
                className="specInput"
                value={editSpecs?.shaft_diameter_mm || ""}
                onChange={(e) => updateSpec("shaft_diameter_mm", e.target.value)}
              />
            </div>
 
            <div className="specRow">
              <strong>End shaft diameter</strong>
              <input
                className="specInput"
                value={editSpecs?.shaft_end_diameter_mm || ""}
                onChange={(e) =>
                  updateSpec("shaft_end_diameter_mm", e.target.value)
                }
              />
            </div>

            <div className="specRow">
              <strong>Shaft material</strong>
              <input
                className="specInput"
                value={editSpecs?.shaft_material || ""}
                onChange={(e) => updateSpec("shaft_material", e.target.value)}
              />
            </div>

            <div className="specRow">
              <strong>Shell material</strong>
              <input
                className="specInput"
                value={editSpecs?.shell_material || editSpecs?.materiaal_mantel || ""}
                onChange={(e) => updateSpec("shell_material", e.target.value)}
              />
            </div>

            <div className="specRow">
              <strong>Torque</strong>
              <input
                className="specInput"
                value={editSpecs?.motor_torque || ""}
                onChange={(e) => updateSpec("motor_torque", e.target.value)}
              />
            </div>

            <div className="specRow">
              <strong>Belt force</strong>
              <input
                className="specInput"
                value={editSpecs?.belt_pull_force || ""}
                onChange={(e) => updateSpec("belt_pull_force", e.target.value)}
              />
            </div>

            <div className="specRow">
              <strong>Belt speed</strong>
              <input
                className="specInput"
                value={editSpecs?.belt_speed || ""}
                onChange={(e) => updateSpec("belt_speed", e.target.value)}
              />
            </div>

            <div className="specRow">
              <strong>Lagging type</strong>
              <input
                className="specInput"
                value={editSpecs?.lagging_type || ""}
                onChange={(e) => updateSpec("lagging_type", e.target.value)}
              />
            </div>

            <div className="specRow">
              <strong>Lagging thickness</strong>
              <input
                className="specInput"
                value={editSpecs?.lagging_dikte_mm || editSpecs?.rubber_thickness_mm || ""}
                onChange={(e) => updateSpec("lagging_dikte_mm", e.target.value)}
              />
            </div>

            <div className="specRow">
              <strong>Rubber material</strong>
              <input
                className="specInput"
                value={editSpecs?.rubber_material || ""}
                onChange={(e) => updateSpec("rubber_material", e.target.value)}
              />
            </div>

            <div className="specRow">
              <strong>Rubber hardness</strong>
              <input
                className="specInput"
                value={editSpecs?.rubber_hardness_shore_a || ""}
                onChange={(e) => updateSpec("rubber_hardness_shore_a", e.target.value)}
              />
            </div>

            <div className="specRow">
              <strong>Vulcanizing method</strong>
              <input
                className="specInput"
                value={editSpecs?.vulcanizing_method || ""}
                onChange={(e) => updateSpec("vulcanizing_method", e.target.value)}
              />
            </div>

            <div className="specRow">
              <strong>FAT required</strong>
              <input
                className="specInput"
                value={editSpecs?.fat_required || ""}
                onChange={(e) => updateSpec("fat_required", e.target.value)}
              />
            </div>

          </div>

          <button
            className="buttonPrimary"
            onClick={saveTechnicalSpecs}
            disabled={saving}
            style={{ marginTop: "24px" }}
          >
            {saving ? "Opslaan..." : "Save engineering review"}
          </button>
        </section>   

        <section className="card">
          <h2>Bearing set / lagering</h2>

          <div className="specGrid">
            <div className="specRow">
              <strong>Lagerhuizen</strong>
              <input
                className="specInput"
                value={
                  editSpecs?.bearing_housing ||
                  editSpecs?.lagerhuis
                    ? "2"
                    : ""
                }
                onChange={(e) => updateSpec("bearing_housing_qty", e.target.value)}
              />
            </div>

            <div className="specRow">
              <strong>Lagerhuis type</strong>
              <input
                className="specInput"
                value={editSpecs?.bearing_housing || ""}
                onChange={(e) => updateSpec("bearing_housing", e.target.value)}
              />
            </div>

            <div className="specRow">
              <strong>Lagers</strong>
              <input
                className="specInput"
                value={
                  editSpecs?.bearing ||
                  editSpecs?.lagering ||
                  editSpecs?.bearing_type
                    ? "2"
                    : ""
                }
                onChange={(e) => updateSpec("bearing_qty", e.target.value)}
              />
            </div>

            <div className="specRow">
              <strong>Lager type</strong>
              <input
                className="specInput"
                value={editSpecs?.bearing || ""}
                onChange={(e) => updateSpec("bearing", e.target.value)}
              />
            </div>

            <div className="specRow">
              <strong>Klembussen</strong>
              <input
                className="specInput"
                value={
                  editSpecs?.adapter ||
                  editSpecs?.adapter_type
                    ? "2"
                    : ""
                }
                onChange={(e) => updateSpec("adapter_qty", e.target.value)}
              />
            </div>

            <div className="specRow">
              <strong>Klembus type</strong>
              <input
                className="specInput"
                value={editSpecs?.adapter || ""}
                onChange={(e) => updateSpec("adapter", e.target.value)}
              />
            </div>

            <div className="specRow">
              <strong>Afdichtingen</strong>
              <input
                className="specInput"
                value={
                  editSpecs?.seal ||
                  editSpecs?.seal_type
                    ? "2"
                    : ""
                }
                onChange={(e) => updateSpec("seal_qty", e.target.value)}
              />
            </div>

            <div className="specRow">
              <strong>Afdichting type</strong>
              <input
                className="specInput"
                value={editSpecs?.seal || ""}
                onChange={(e) => updateSpec("seal", e.target.value)}
              />
            </div>

            <div className="specRow">
              <strong>FRB ringen</strong>
              <input
                className="specInput"
                value={
                  editSpecs?.frb_ring
                    ? "2"
                    : ""
                }
                onChange={(e) => updateSpec("frb_ring_qty", e.target.value)}
              />
            </div>

            <div className="specRow">
              <strong>FRB type</strong>
              <input
                className="specInput"
                value={editSpecs?.frb_ring || ""}
                onChange={(e) => updateSpec("frb_ring", e.target.value)}
              />
            </div>
          </div>
        </section>

        {/* DRIVE DATA */}

        <section className="card">
          <h2>Drive data</h2>

          <div className="specGrid">
            <div className="specRow">
              <strong>Drum type</strong>
              <input
                className="specInput"
                value={editSpecs?.drum_type || ""}
                onChange={(e) => updateSpec("drum_type", e.target.value)}
              />
            </div>

            <div className="specRow">
              <strong>Rotation type</strong>
              <input
                className="specInput"
                value={editSpecs?.rotation_type || ""}
                onChange={(e) => updateSpec("rotation_type", e.target.value)}
              />
            </div>

            <div className="specRow">
              <strong>Assembly torque</strong>
              <input
                className="specInput"
                value={editSpecs?.assembly_torque_nm || ""}
                onChange={(e) => updateSpec("assembly_torque_nm", e.target.value)}
              />
            </div>

            <div className="specRow">
              <strong>Nominal torque</strong>
              <input
                className="specInput"
                value={editSpecs?.nominal_motor_torque_nm || ""}
                onChange={(e) => updateSpec("nominal_motor_torque_nm", e.target.value)}
              />
            </div>

            <div className="specRow">
              <strong>Belt pull force</strong>
              <input
                className="specInput"
                value={editSpecs?.belt_pull_force_kn || ""}
                onChange={(e) => updateSpec("belt_pull_force_kn", e.target.value)}
              />
            </div>

            <div className="specRow">
              <strong>Belt speed</strong>
              <input
                className="specInput"
                value={editSpecs?.belt_speed_mps || ""}
                onChange={(e) => updateSpec("belt_speed_mps", e.target.value)}
              />
            </div>
          </div>
        </section>

        {/* PRODUCTION & QA */}

        <section className="card">
          <h2>Production & QA</h2>

          <div className="specGrid">
            <div className="specRow">
              <strong>Mass</strong>
              <input
                className="specInput"
                value={editSpecs?.mass_kg || ""}
                onChange={(e) => updateSpec("mass_kg", e.target.value)}
              />
            </div>

            <div className="specRow">
              <strong>Balancing norm</strong>
              <input
                className="specInput"
                value={editSpecs?.balancing_norm || ""}
                onChange={(e) => updateSpec("balancing_norm", e.target.value)}
              />
            </div>

            <div className="specRow">
              <strong>Tolerance class</strong>
              <input
                className="specInput"
                value={editSpecs?.tolerance_class || ""}
                onChange={(e) => updateSpec("tolerance_class", e.target.value)}
              />
            </div>

            <div className="specRow">
              <strong>Surface roughness</strong>
              <input
                className="specInput"
                value={editSpecs?.surface_roughness || ""}
                onChange={(e) => updateSpec("surface_roughness", e.target.value)}
              />
            </div>

            <div className="specRow">
              <strong>FAT required</strong>
              <input
                className="specInput"
                value={editSpecs?.fat_required || ""}
                onChange={(e) => updateSpec("fat_required", e.target.value)}
              />
            </div>
          </div>
        </section>

        {/* LUBRICATION */}

        <section className="card">
          <h2>Lubrication</h2>

          <div className="specGrid">
            <div className="specRow">
              <strong>Grease fill quantity</strong>
              <input
                className="specInput"
                value={editSpecs?.grease_initial_fill_g || ""}
                onChange={(e) => updateSpec("grease_initial_fill_g", e.target.value)}
              />
            </div>

            <div className="specRow">
              <strong>Regreasing quantity</strong>
              <input
                className="specInput"
                value={editSpecs?.grease_regreasing_g || ""}
                onChange={(e) => updateSpec("grease_regreasing_g", e.target.value)}
              />
            </div>

            <div className="specRow">
              <strong>Grease type</strong>
              <input
                className="specInput"
                value={editSpecs?.grease_type || ""}
                onChange={(e) => updateSpec("grease_type", e.target.value)}
              />
            </div>
          </div>
        </section>

        {/* TOLERANCES & NORMS */}

        <section className="card">
          <h2>Passingen & normen</h2>

          <div className="specGrid">

            <div>
              <strong>Aspassing</strong>
              <span>
                {Array.isArray(editSpecs?.shaft_fits) && editSpecs.shaft_fits.length > 0
                  ? editSpecs.shaft_fits
                      .map((fit) => `${fit.diameter_mm} ${fit.fit}`)
                      .join(" / ")
                  : "n.n.b."}
              </span>
            </div>

            <div>
              <strong>Lagerpassing</strong>
              <span>n.n.b.</span>
            </div>

            <div>
              <strong>Tolerance class</strong>
              <span>ISO 2768-mK</span>
            </div>

            <div>
              <strong>Balancing norm</strong>
              <span>ISO 1940</span>
            </div>

            <div>
              <strong>General tolerance</strong>
              <span>ISO 8015</span>
            </div>

            <div>
              <strong>Surface roughness</strong>
              <span>3.2 / 1.6</span>
            </div>

          </div>
        </section>

        {/* ENGINEERING ADVICE */}

        <section className="card">
          <h2>AI engineering advice</h2>

          <ul className="adviceList">
            <li>Controleer lagerpassing en aspassing.</li>

            <li>
              Controleer balancing conform toepassing.
            </li>

            <li>
              Controleer coating / paint specification.
            </li>

            <li>
              Controleer FAT requirement.
            </li>

            <li>
              Controleer lagging toepassing en omgeving.
            </li>
          </ul>
        </section>

        {/* MISSING FIELDS */}

        <section className="card">
          <h2>Missing fields</h2>

          {currentMissingFields.length === 0 ? (
            <p>Geen ontbrekende engineeringvelden.</p>
          ) : (
            <div className="missingFields">
              {currentMissingFields.map((field, index) => (
                <div key={`${field}-${index}`} className="missingTag">
                  {field}
                </div>
              ))}
            </div>
          )}
        </section>

        {/* INTERNAL COMMERCIAL */}

        <section className="card">
          <h2>Internal evaluation</h2>

          <div className="specGrid">

            <div>
              <strong>Customer type</strong>
              <span>{rfq?.rfq?.customer_type}</span>
            </div>

            <div>
              <strong>Route</strong>
              <span>{rfq?.rfq?.selected_route}</span>
            </div>

            <div>
              <strong>Customer score</strong>
              <span>
                {rfq?.decision_log?.[0]?.gpt_suggestion?.components?.customer_score || "-"}
              </span>
            </div>

            <div>
              <strong>Salesperson score</strong>
              <span>
                {rfq?.decision_log?.[0]?.gpt_suggestion?.components?.salesperson_score || "-"}
              </span>
            </div>

            <div>
              <strong>Commercial gate</strong>
              <span>
                {rfq?.rfq?.intake_summary?.intake_decision || "-"}
              </span>
            </div>

            <div>
              <strong>Engineering allowed</strong>
              <span>
                {rfq?.rfq?.intake_summary?.engineering_gate?.allow_technical_review
                  ? "YES"
                  : "NO"}
              </span>
            </div>

          </div>
        </section>

        {/* RAG REFERENCES */}

        <section className="card fullWidth">
          <h2>RAG engineering references</h2>

          <div className="ragGrid">

            <div className="ragCard">
              <strong>Bijlage_Trommels_Selectiecriteria.docx</strong>
              <span>Score: 0.753</span>
            </div>

            <div className="ragCard">
              <strong>Promati_Leveranciersselectie.docx</strong>
              <span>Score: 0.715</span>
            </div>

            <div className="ragCard">
              <strong>Promati_Standaard_Trommels.docx</strong>
              <span>Score: 0.692</span>
            </div>

          </div>
        </section>

        {/* EXTRACTED TEXT */}

        <section className="card fullWidth">
          <h2>Extracted drawing text</h2>

          <pre className="drawingText">
            {documentStatus?.latest_text?.extracted_text || specs?.extracted_text_preview || ""}
          </pre>
        </section>

      </div>
    </div>
  );
}