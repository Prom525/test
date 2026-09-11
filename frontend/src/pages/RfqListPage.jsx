import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import { getRfqList } from "../services/api";

export default function RfqListPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      try {
        setData(await getRfqList());
      } catch (err) {
        setError(err.message);
      }
    }

    load();
  }, []);

  return (
    <div className="page">
      <header>
        <h1>RFQ Overzicht</h1>
        <p>Alle aanvragen, statussen, suppliers en awards</p>
      </header>

      {error && <div className="error">{error}</div>}

      {data && (
        <section className="card">
          <h2>RFQ lijst</h2>

          <table>
            <thead>
              <tr>
                <th>Odoo</th>
                <th>Klant</th>
                <th>Status</th>
                <th>Route</th>
                <th>Product</th>
                <th>Suppliers</th>
                <th>Ontvangen</th>
                <th>Award</th>
                <th>Waarde</th>
              </tr>
            </thead>

            <tbody>
              {data.rfqs?.map((r) => (
                <tr key={r.rfq_id}>
                  <td>
                    <Link to={`/rfq/${r.rfq_id}`}>
                      {r.odoo_reference}
                    </Link>
                  </td>
                  <td>{r.customer_name_internal || "-"}</td>
                  <td>
                    <span className={`badge status-${r.status}`}>
                      {r.status}
                    </span>
                  </td>
                  <td>{r.selected_route}</td>
                  <td>{r.product_types || "-"}</td>
                  <td>{r.supplier_rfq_count}</td>
                  <td>{r.received_count}</td>
                  <td>{r.awarded_supplier || "-"}</td>
                  <td>
                    {r.awarded_amount
                      ? `€ ${r.awarded_amount}`
                      : "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}