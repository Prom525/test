import { useState } from "react";
import { getAward, getSupplierRouting } from "../services/api";

export default function DashboardPage() {
  const [rfqId, setRfqId] = useState(
    "2af821f2-da0a-4f39-a143-b291bc42de1e"
  );

  const [routing, setRouting] = useState(null);
  const [award, setAward] = useState(null);
  const [error, setError] = useState("");

  async function loadCockpit() {
    setError("");

    try {
      const [routingData, awardData] = await Promise.all([
        getSupplierRouting(rfqId),
        getAward(rfqId),
      ]);

      setRouting(routingData);
      setAward(awardData);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="page">
      <header>
        <h1>Promati RFQ Dashboard</h1>
        <p>Supplier routing, award status en RFQ workflow</p>
      </header>

      <section className="card">
        <label>RFQ ID</label>

        <div className="row">
          <input
            value={rfqId}
            onChange={(e) => setRfqId(e.target.value)}
          />

          <button onClick={loadCockpit}>
            RFQ cockpit laden
          </button>
        </div>
      </section>

      {error && <div className="error">{error}</div>}

      {award?.awarded && (
        <section className="card">
          <h2>RFQ status</h2>

          <div className="statusGrid">
            <div>
              <strong>Status</strong>
              <span>AWARDED</span>
            </div>

            <div>
              <strong>Supplier</strong>
              <span>{award.award.supplier_name}</span>
            </div>

            <div>
              <strong>Waarde</strong>
              <span>€ {award.award.quoted_amount}</span>
            </div>
          </div>
        </section>
      )}

      {routing && (
        <section className="card">
          <h2>Supplier routing</h2>

          <table>
            <thead>
              <tr>
                <th>Rank</th>
                <th>Supplier</th>
                <th>Classificatie</th>
                <th>Score</th>
              </tr>
            </thead>

            <tbody>
              {routing.recommended_suppliers?.map((s, idx) => (
                <tr key={s.supplier_id}>
                  <td>{idx + 1}</td>
                  <td>{s.supplier_name}</td>
                  <td>{s.classification}</td>
                  <td>{s.total_score}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}