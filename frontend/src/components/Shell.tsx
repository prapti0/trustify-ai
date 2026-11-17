import { useState, type ReactNode } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { logoutAccount } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { useTheme } from "../context/ThemeContext";
import { Icons } from "./Icons";

const groups = [
  {
    label: "Workspace",
    items: [
      ["/app", "Overview"],
      ["/app/analyze", "New Analysis"],
      ["/app/history", "Analysis History"],
      ["/app/history?status=completed", "Reports"],
    ],
  },
  {
    label: "Investigations",
    items: [
      ["/app/video", "Video Forensics"],
      ["/app/image", "Image Analysis"],
      ["/app/audio", "Audio Analysis"],
      ["/app/documents", "Document Analysis"],
      ["/app/security", "Security Scanner"],
      ["/app/duplicates", "Duplicate Detection"],
      ["/app/scam", "Scam Investigation"],
    ],
  },
  {
    label: "Account",
    items: [
      ["/app/settings", "Settings"],
      ["/app/help", "Help & Support"],
    ],
  },
] as const;

export function AppShell({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const { theme, toggle } = useTheme();
  const { clear } = useAuth();
  const navigate = useNavigate();

  async function signOut() {
    try {
      await logoutAccount();
    } catch {
      // The local session is cleared even if the server is unreachable.
    }
    clear();
    navigate("/login");
  }

  return (
    <div className="min-h-screen md:grid md:grid-cols-[250px_1fr]">
      <aside className={`${open ? "block" : "hidden"} border-b border-[var(--line)] bg-[var(--elevated)] md:block md:border-b-0 md:border-r`}>
        <div className="flex items-center gap-2 px-4 py-5">
          <Icons.shield />
          <Link to="/app" className="font-medium">
            TRUSTIFY AI
          </Link>
        </div>
        <nav className="flex flex-col gap-5 px-3 pb-6" aria-label="Application">
          {groups.map((group) => (
            <div key={group.label}>
              <p className="px-3 text-xs uppercase tracking-wide muted">{group.label}</p>
              <div className="mt-2 flex flex-col">
                {group.items.map(([to, label]) => (
                  <NavLink
                    key={to}
                    to={to}
                    end={to === "/app"}
                    onClick={() => setOpen(false)}
                    className={({ isActive }) => `rounded-lg px-3 py-2 text-sm ${isActive ? "bg-[var(--card)]" : "muted"}`}
                  >
                    {label}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>
      </aside>
      <div>
        <header className="flex flex-wrap items-center gap-3 border-b border-[var(--line)] px-4 py-4 md:px-8">
          <button type="button" className="btn btn-secondary md:hidden" onClick={() => setOpen((value) => !value)}>
            Menu
          </button>
          <div className="min-w-0 flex-1">
            <h1 className="text-xl font-medium">{title}</h1>
            {subtitle ? <p className="text-sm muted">{subtitle}</p> : null}
          </div>
          <button type="button" className="btn btn-secondary px-3" onClick={toggle} aria-label="Toggle color theme">
            {theme === "dark" ? <Icons.sun /> : <Icons.moon />}
          </button>
          <Link to="/app/analyze" className="btn btn-primary">
            New Analysis
          </Link>
          <Link to="/app/history?status=completed" className="btn btn-secondary">
            View Reports
          </Link>
          <button type="button" className="btn btn-secondary" onClick={() => void signOut()}>
            Sign Out
          </button>
        </header>
        <main className="px-4 py-6 md:px-8">{children}</main>
      </div>
    </div>
  );
}
