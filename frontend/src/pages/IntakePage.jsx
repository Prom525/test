import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { API_ROOT } from "../services/api";

export default function IntakePage() {
  const [form, setForm] = useState({
    odoo_reference: "",
    customer_name_internal: "",
    verkoper: "",
    request_type: "",
    drawing_text: "",
  });

  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const navigate = useNavigate();

  function updateField(key, value) {
    setForm((prev) => ({
      ...prev,
      [key]: value,
    }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setResult(null);

    try {
      const data = new FormData();

      Object.entries(form).forEach(([key, value]) => {
        data.append(key, value);
      });

      if (file) {
        data.append("drawing_file", file);
      }

      const response = await fetch(`${API_ROOT}/analysis/rfq/assistant/upload-drawing-rfq`, {
        method: "POST",
        body: data,
      });

      const json = await response.json();
      setResult(json);

      if (json.rfq_id) {
        navigate(`/rfq/${json.rfq_id}`);
      }
    } catch (err) {
      console.error(err);
      alert("Upload failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <header>
        <h1>Nieuwe RFQ Intake</h1>
        <p>Upload aanvraag + tekening</p>
      </header>

      <section className="card">
        <form onSubmit={handleSubmit} className="intakeForm">
          <div className="formGrid">
            <div>
              <label>Odoo referentie</label>
              <input
                value={form.odoo_reference}
                onChange={(e) =>
                  updateField("odoo_reference", e.target.value)
                }
              />
            </div>

            <div>
              <label>Klant</label>
              <input
                value={form.customer_name_internal}
                onChange={(e) =>
                  updateField("customer_name_internal", e.target.value)
                }
              />
            </div>

            <div>
              <label>Verkoper</label>
              <input
                value={form.verkoper}
                onChange={(e) => updateField("verkoper", e.target.value)}
              />
            </div>

            <div>
              <label>Aanvraag type</label>
              <input
                value={form.request_type}
                onChange={(e) => updateField("request_type", e.target.value)}
              />
            </div>
          </div>

          <div>
            <label>Aanvraagtekst</label>
            <textarea
              rows="10"
              value={form.drawing_text}
              onChange={(e) => updateField("drawing_text", e.target.value)}
            />
          </div>

          <div>
            <label>PDF upload</label>
            <input
              type="file"
              accept=".pdf"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
          </div>

          <button type="submit" disabled={loading}>
            {loading ? "Processing..." : "Start intake"}
          </button>
        </form>
      </section>

      {result && (
        <section className="card">
          <h2>Resultaat</h2>
          <pre>{JSON.stringify(result, null, 2)}</pre>
        </section>
      )}
    </div>
  );
}