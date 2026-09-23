import { Route, Routes } from "react-router";
import { Layout } from "./components/Layout";
import ProgramList from "./pages/ProgramList";
import ProgramDetail from "./pages/ProgramDetail";
import Dashboard from "./pages/Dashboard";
import NotFound from "./pages/NotFound";

export default function App() {
  return (
    <div className="min-h-screen bg-canvas text-ink">
      <Layout>
        <Routes>
          <Route path="/" element={<ProgramList />} />
          <Route path="/programs/:id" element={<ProgramDetail />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Layout>
    </div>
  );
}
