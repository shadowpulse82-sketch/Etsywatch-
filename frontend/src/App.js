import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import Landing from "@/pages/Landing";
import Dashboard from "@/pages/Dashboard";
import AlertSettings from "@/pages/AlertSettings";
import EvidenceVault from "@/pages/EvidenceVault";
import { getSession } from "@/lib/api";

const Protected = ({ children }) => {
  if (!getSession()) {
    return <Navigate to="/" replace />;
  }
  return children;
};

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Toaster position="top-right" richColors closeButton />
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route
            path="/dashboard"
            element={
              <Protected>
                <Dashboard />
              </Protected>
            }
          />
          <Route
            path="/settings"
            element={
              <Protected>
                <AlertSettings />
              </Protected>
            }
          />
          <Route
            path="/evidence"
            element={
              <Protected>
                <EvidenceVault />
              </Protected>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </div>
  );
}

export default App;
