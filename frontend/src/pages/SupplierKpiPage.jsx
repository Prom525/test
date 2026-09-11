import { useEffect, useState } from "react";
import { getSupplierKpi } from "../services/api";

export default function SupplierKpiPage() {
  const [kpi, setKpi] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      try {
        setKpi(await getSupplierKpi());
      } catch (err) {
        setError(err.message);
      }
    }

    load();
  }, []);

  return (
    <div className="page">
      <header>
        <h1>Supplier KPI Dashboard</h1>
        <p>Response rate, award rate en supplier performance</p>
      </header>

      {error && <div className="error">{error}</div>}

      {kpi && (
        <section className="card">
          <h2>Supplier performance</h2>

          <table>
            <thead>
              <tr>
                <th>Supplier</th>
                <th>Classificatie</th>
                <th>Score</th>
                <th>RFQs</th>
                <th>Responses</th>
                <th>Awards</th>
                <th>Response %</th>
                <th>Award %</th>
                <th>Gem. response dagen</th>
              </tr>
            </thead>

            <tbody>
              {kpi.suppliers?.map((s) => (
                <tr key={s.supplier_id}>
                  <td>{s.supplier_name}</td>
                  <td>{s.classification || "-"}</td>
                  <td>{s.qualification_score}</td>
                  <td>{s.rfq_count}</td>
                  <td>{s.quote_received_count}</td>
                  <td>{s.award_count}</td>
                  <td>{s.response_rate_pct}%</td>
                  <td>{s.award_rate_pct}%</td>
                  <td>{s.avg_response_days ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}