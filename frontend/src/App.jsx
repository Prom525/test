import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import DashboardPage from "./pages/DashboardPage";
import SupplierKpiPage from "./pages/SupplierKpiPage";
import RfqListPage from "./pages/RfqListPage";
import RfqDetailPage from "./pages/RfqDetailPage";
import IntakePage from "./pages/IntakePage";
import RfqTechnicalPage from "./pages/RfqTechnicalPage";
import NewPositionPage from "./pages/NewPositionPage";
import RfqDashboardPage from "./pages/RfqDashboardPage";
import "./App.css";

export default function App() {
  return (
    <BrowserRouter>
      <nav className="nav">
        <Link to="/">RFQ Dashboard</Link>
        <Link to="/rfqs">RFQ Overzicht</Link>
        <Link to="/suppliers/kpi">Supplier KPI</Link>
        <Link to="/intake">Nieuwe intake</Link>
      </nav>

      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/rfqs" element={<RfqListPage />} />
        <Route path="/suppliers/kpi" element={<SupplierKpiPage />} />
        <Route path="/rfq/:rfqId" element={<RfqDetailPage />} />
        <Route path="/intake" element={<IntakePage />} />
        <Route path="/rfq/:rfqId/technical" element={<RfqTechnicalPage />} />
        <Route
          path="/rfq/:rfqId/positions/:positionId/technical"
          element={<RfqTechnicalPage />}
        />
        <Route
          path="/rfq/:rfqId/positions/:positionId/dashboard"
          element={<RfqDashboardPage />}
        />
        <Route
          path="/rfq/:rfqId/positions/new"
          element={<NewPositionPage />}
        />
      </Routes>
    </BrowserRouter>
  );
}