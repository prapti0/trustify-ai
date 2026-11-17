import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import { LoginPage, RegisterPage } from "./pages/AuthPages";
import { AnalyzePage } from "./pages/AnalyzePage";
import { DashboardPage } from "./pages/DashboardPage";
import { HistoryPage } from "./pages/HistoryPage";
import { LandingPage } from "./pages/LandingPage";
import { ProcessingPage } from "./pages/ProcessingPage";
import { ReportPage } from "./pages/ReportPage";
import { SettingsPage } from "./pages/SettingsPage";
import { AboutPage, ContactPage, DocumentationPage, HelpPage, PrivacyPage, TermsPage } from "./pages/StaticPages";
import { DuplicatesPage, ScamPage, WorkspacePage } from "./pages/WorkspacePage";
import { AppShell } from "./components/Shell";
import type { ReactNode } from "react";

function Protected({ children }: { children: ReactNode }) {
  const { session } = useAuth();
  if (!session) return <Navigate to="/login" replace />;
  return children;
}

export function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/about" element={<AboutPage />} />
      <Route path="/documentation" element={<DocumentationPage />} />
      <Route path="/privacy" element={<PrivacyPage />} />
      <Route path="/terms" element={<TermsPage />} />
      <Route path="/contact" element={<ContactPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/app" element={<Protected><DashboardPage /></Protected>} />
      <Route path="/app/analyze" element={<Protected><AnalyzePage /></Protected>} />
      <Route path="/app/jobs/:jobId" element={<Protected><ProcessingPage /></Protected>} />
      <Route path="/app/reports/:jobId" element={<Protected><ReportPage /></Protected>} />
      <Route path="/app/history" element={<Protected><HistoryPage /></Protected>} />
      <Route path="/app/video" element={<Protected><WorkspacePage kind="video" /></Protected>} />
      <Route path="/app/image" element={<Protected><WorkspacePage kind="image" /></Protected>} />
      <Route path="/app/audio" element={<Protected><WorkspacePage kind="audio" /></Protected>} />
      <Route path="/app/documents" element={<Protected><WorkspacePage kind="documents" /></Protected>} />
      <Route path="/app/security" element={<Protected><WorkspacePage kind="security" /></Protected>} />
      <Route path="/app/duplicates" element={<Protected><DuplicatesPage /></Protected>} />
      <Route path="/app/scam" element={<Protected><ScamPage /></Protected>} />
      <Route path="/app/settings" element={<Protected><SettingsPage /></Protected>} />
      <Route path="/app/help" element={<Protected><AppShell title="Help & Support" subtitle="What the messages on this deployment mean."><HelpPage /></AppShell></Protected>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
