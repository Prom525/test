import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { API_ROOT } from "../services/api";

const API_BASE = API_ROOT;

export default function RfqDashboardPage() {
  const { rfqId, positionId } = useParams();

  const [dashboard, setDashboard] = useState(null);
  const [supplierPackage, setSupplierPackage] = useState(null);
  const [error, setError] = useState("");

  async function loadDashboard() {
    setError("");

    try {
      const dashRes = await fetch(
        `${API_BASE}/analysis/context/rfq/dashboard?rfq_id=${rfqId}&position_id=${positionId}`
      );

      if (!dashRes.ok) throw new Error("RFQ dashboard kon niet geladen worden.");

      const dash = await dashRes.json();
      setDashboard(dash);

      const c = dash.context || {};

      const supplierRes = await fetch(
        `${API_BASE}/analysis/context/rfq/supplier-package?product_type=${c.product_type || ""}&bearing_type=${c.bearing_type || ""}&rubber_material=${c.rubber_material || ""}&limit=10`
      );

      if (supplierRes.ok) {
        setSupplierPackage(await supplierRes.json());
      }
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    loadDashboard();
  }, [rfqId, positionId]);

  const summary = dashboard?.summary || {};
  const context = dashboard?.context || {};
  const currentPhase = summary.phase || "ENGINEERING";

  return (
    <div className="odoo-page">
      <div className="odoo-topbar">
        <div>
          <h1 className="odoo-title">RFQ Dashboard</h1>
          <div className="odoo-subtitle">
            {context.product_type || "RFQ"} · {context.drawing_mark || "-"}
          </div>
        </div>

        <div style={{ display: "flex", gap: 10 }}>
          <Link className="odoo-button-secondary" to={`/rfq/${rfqId}`}>
            Terug naar RFQ
          </Link>
          <Link
            className="odoo-button-primary"
            to={`/rfq/${rfqId}/positions/${positionId}/technical`}
          >
            Engineering
          </Link>
        </div>
      </div>

      {error && <div className="error">{error}</div>}

      {!dashboard && !error && <div className="odoo-card">Dashboard laden...</div>}

      {dashboard && (
        <>
          <div className="odoo-stagebar">
            <Stage label="Engineering" active={currentPhase === "ENGINEERING"} danger />
            <Stage label="Supplier Selection" active={currentPhase === "SUPPLIER_SELECTION"} />
            <Stage label="Quotations" active={currentPhase === "QUOTATIONS"} />
            <Stage label="Award" active={currentPhase === "AWARD"} />
          </div>

          <div className="odoo-smart-buttons">
            <SmartButton title="Status" value={humanStatus(summary.status)} />
            <SmartButton
              title="Readiness"
              value={`${summary.readiness_score ?? 0}%`}
              progress={summary.readiness_score ?? 0}
              danger={(summary.readiness_score ?? 0) < 80}
            />
            <SmartButton title="Fase" value={summary.phase} />
            <SmartButton title="OCR Confidence" value={`${summary.confidence_score ?? 0}%`} warning={(summary.confidence_score ?? 0) < 75} />
          </div>

          <div className="odoo-card">
            <h2>Technische kerngegevens</h2>

            <div className="metricGrid">
              <Metric label="Product" value={context.product_type} />
              <Metric label="Trommel Ø" value={context.diameter_mm && `${context.diameter_mm} mm`} />
              <Metric label="Breedte" value={context.drum_width_mm && `${context.drum_width_mm} mm`} />
              <Metric label="As Ø" value={context.shaft_diameter_mm && `${context.shaft_diameter_mm} mm`} />
              <Metric label="Lager" value={context.bearing_type} />
            </div>
          </div>

          <div className="odoo-kanban">
            <Column title="Engineering" badge={`${dashboard.actions?.length || 0} acties`}>
              {dashboard.actions?.map((a, index) => (
                <ActionCard key={index} action={a} />
              ))}
            </Column>

            <Column title="Primary suppliers" badge={`${supplierPackage?.primary_suppliers?.length || 0}`}>
              {supplierPackage?.primary_suppliers?.map((s) => (
                <SupplierCard key={s.supplier_id} supplier={s} primary />
              ))}
            </Column>

            <Column title="Backup suppliers" badge={`${supplierPackage?.backup_suppliers?.length || 0}`}>
              {supplierPackage?.backup_suppliers?.map((s) => (
                <SupplierCard key={s.supplier_id} supplier={s} />
              ))}
            </Column>

            <Column title="Similar RFQ's" badge={`${supplierPackage?.similar_rfqs?.length || 0}`}>
              {supplierPackage?.similar_rfqs?.map((r) => (
                <SimilarCard key={r.position_id} rfq={r} />
              ))}
            </Column>
          </div>
        </>
      )}
    </div>
  );
}

function Stage({ label, active, danger }) {
  return (
    <div className={`odoo-stage ${active ? "active" : ""} ${active && danger ? "danger" : ""}`}>
      {label}
    </div>
  );
}

function SmartButton({
  title,
  value,
  danger,
  warning,
  progress
}) {
  return (
    <div className="odoo-smart-button">
      <span>{title}</span>

      <strong className={danger ? "risk-high" : warning ? "risk-medium" : ""}>
        {value || "-"}
      </strong>

      {typeof progress === "number" && (
        <div className="odoo-progress">
          <div
            className="odoo-progress-bar"
            style={{ width: `${progress}%` }}
          />
        </div>
      )}
    </div>
  );
}

function Metric({ label, value }) {
  return (
    <div>
      <strong>{label}</strong>
      <span>{value || "-"}</span>
    </div>
  );
}

function Column({ title, badge, children }) {
  return (
    <div className="odoo-column">
      <div className="odoo-column-header">
        <h3>{title}</h3>
        <span className="odoo-badge">{badge}</span>
      </div>
      <div className="odoo-column-body">{children}</div>
    </div>
  );
}

function ActionCard({ action }) {
  const isHigh = action.priority === "HIGH";

  return (
    <div
      className="odoo-kanban-card"
      style={{ borderLeftColor: isHigh ? "var(--odoo-danger)" : "var(--odoo-warning)" }}
    >
      <h4>{humanField(action.field || action.type)}</h4>
      <p>{action.action}</p>
      <span className={isHigh ? "odoo-badge odoo-badge-danger" : "odoo-badge odoo-badge-warning"}>
        {action.priority}
      </span>
    </div>
  );
}

function SupplierCard({ supplier, primary }) {
  return (
    <div
      className="odoo-kanban-card"
      style={{ borderLeftColor: primary ? "var(--odoo-success)" : "var(--odoo-primary)" }}
    >
      <h4>{supplier.supplier_name}</h4>
      <p>Score: {supplier.recommendation_score}</p>
      <p>Performance: {supplier.performance_score}</p>

      <div>
        {supplier.categories?.map((c) => (
          <span key={c} className="odoo-tag">{c}</span>
        ))}
      </div>
    </div>
  );
}

function SimilarCard({ rfq }) {
  return (
    <div className="odoo-kanban-card" style={{ borderLeftColor: "var(--odoo-info)" }}>
      <h4>{rfq.product_type || "RFQ"}</h4>
      <p>{rfq.drawing_mark || rfq.file_name || "-"}</p>
      <p>
        Ø {rfq.diameter_mm || "-"} · {rfq.bearing_type || "-"} · {rfq.rubber_material || "-"}
      </p>
      <span className="odoo-badge odoo-badge-info">Match {rfq.similarity_score}</span>
    </div>
  );
}

function humanField(field) {
  const labels = {
    balancing_norm: "Bevestig balanceernorm",
    seal_type: "Bevestig afdichting",
    grease_type: "Bevestig vettype",
    surface_roughness: "Bevestig ruwheid",
    tolerance_class: "Bevestig toleranties",
    DATA_QUALITY: "Datakwaliteit",
    ENGINEERING: "Engineering",
  };

  return labels[field] || field;
}

function humanStatus(status) {
  const map = {
    ENGINEERING_REVIEW_REQUIRED: "Engineering review vereist",
    READY_FOR_SUPPLIER_RFQ: "Gereed voor uitvraag",
  };

  return map[status] || status;
}