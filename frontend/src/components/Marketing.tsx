import type { ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";
import { useTheme } from "../context/ThemeContext";
import { Icons } from "./Icons";

const links = [
  { href: "/#features", label: "Features" },
  { href: "/#how-it-works", label: "How It Works" },
  { href: "/#technology", label: "Technology" },
  { href: "/about", label: "About" },
  { href: "/documentation", label: "Documentation" },
];

export function MarketingHeader() {
  const { theme, toggle } = useTheme();
  return (
    <header className="border-b border-[var(--line)]">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-4 px-5 py-4">
        <Link to="/" className="font-medium tracking-wide">
          TRUSTIFY AI
        </Link>
        <nav className="flex flex-wrap gap-4 text-sm muted" aria-label="Marketing">
          <Link to="/" className="hover:text-[var(--text)]">
            Home
          </Link>
          {links.map((link) => (
            <a key={link.href} href={link.href} className="hover:text-[var(--text)]">
              {link.label}
            </a>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <button type="button" className="btn btn-secondary px-3" onClick={toggle} aria-label="Toggle color theme">
            {theme === "dark" ? <Icons.sun /> : <Icons.moon />}
          </button>
          <Link to="/login" className="btn btn-secondary">
            Sign In
          </Link>
          <Link to="/register" className="btn btn-primary">
            Get Started
          </Link>
        </div>
      </div>
    </header>
  );
}

export function MarketingFooter() {
  return (
    <footer className="mt-20 border-t border-[var(--line)]">
      <div className="mx-auto grid max-w-6xl gap-6 px-5 py-10 text-sm md:grid-cols-4">
        <div>
          <p className="font-medium">About TRUSTIFY AI</p>
          <p className="mt-2 muted">Digital forensics for files you are allowed to inspect. Evidence stays separate from guesses.</p>
        </div>
        <div className="flex flex-col gap-2">
          <a href="/#features">Features</a>
          <Link to="/documentation">Documentation</Link>
          <a href="https://github.com">GitHub</a>
        </div>
        <div className="flex flex-col gap-2">
          <Link to="/privacy">Privacy Policy</Link>
          <Link to="/terms">Terms of Service</Link>
          <Link to="/contact">Contact</Link>
        </div>
        <p className="muted">Missing credentials are inconclusive. A detector that did not run is not a clean result.</p>
      </div>
    </footer>
  );
}

export function MarketingFrame({ children }: { children: ReactNode }) {
  return (
    <div>
      <MarketingHeader />
      <main className="mx-auto max-w-6xl px-5 py-10">{children}</main>
      <MarketingFooter />
    </div>
  );
}

export function AppLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <NavLink to={to} className={({ isActive }) => `rounded-lg px-3 py-2 text-sm ${isActive ? "bg-[var(--card)]" : "muted hover:text-[var(--text)]"}`}>
      {children}
    </NavLink>
  );
}
