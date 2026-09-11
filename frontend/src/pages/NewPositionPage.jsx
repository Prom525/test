import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { API_ROOT } from "../services/api";

const API_BASE = API_ROOT;

export default function NewPositionPage() {
  const { rfqId } = useParams();
  const navigate = useNavigate();

  const [productType, setProductType] = useState("TROMMEL");
  const [quantity, setQuantity] = useState(1);
  const [drawingFile, setDrawingFile] = useState(null);
  const [loading, setLoading] = useState(false);

  async function createPosition(e) {
    e.preventDefault();
    setLoading(true);

    try {
      let response;

      if (drawingFile) {
        const formData = new FormData();
        formData.append("product_type", productType);
        formData.append("quantity", quantity);
        formData.append("drawing", drawingFile);

        response = await fetch(
          `${API_BASE}/analysis/rfq/${rfqId}/positions/from-drawing`,
          {
            method: "POST",
            body: formData,
          }
        );
      } else {
        response = await fetch(
          `${API_BASE}/analysis/rfq/${rfqId}/positions`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              product_type: productType,
              quantity,
            }),
          }
        );
      }

      const data = await response.json();

      if (!response.ok) {
        alert(data.detail || "Position create failed");
        return;
      }

      navigate(`/rfq/${rfqId}/positions/${data.position.position_id}/technical`);
    } catch (err) {
      console.error(err);
      alert("Error creating position");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <div className="pageHeader">
        <div>
          <h1>Nieuwe positie</h1>

          <p className="subtitle">
            RFQ {rfqId}
          </p>
        </div>
      </div>

      <section className="card">
        <form onSubmit={createPosition}>
          <div className="formGrid">

            <div>
              <label>Product type</label>

              <select
                value={productType}
                onChange={(e) => setProductType(e.target.value)}
              >
                <option value="TROMMEL">TROMMEL</option>
                <option value="ROL">ROL</option>
                <option value="FRAME">FRAME</option>
              </select>
            </div>

            <div>
              <label>Quantity</label>

              <input
                type="number"
                value={quantity}
                onChange={(e) => setQuantity(Number(e.target.value))}
              />
            </div>

            <div>
              <label>Tekening upload</label>

              <input
                type="file"
                onChange={(e) => setDrawingFile(e.target.files[0])}
              />
            </div>

          </div>

          <button
            type="submit"
            className="buttonPrimary"
            disabled={loading}
          >
            {loading ? "Creating..." : "Create position"}
          </button>
        </form>
      </section>
    </div>
  );
}