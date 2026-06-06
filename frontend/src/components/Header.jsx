import { Link, useLocation, useNavigate } from "react-router-dom";
import { ShieldCheck, LogOut } from "lucide-react";
import { Button } from "../components/ui/button";
import { clearSession, getSession } from "../lib/api";

export default function Header() {
  const location = useLocation();
  const navigate = useNavigate();
  const email = getSession();

  const NavLink = ({ to, label, testId }) => {
    const active = location.pathname === to;
    return (
      <Link
        to={to}
        data-testid={testId}
        className={`text-sm font-medium px-3 py-2 rounded-sm transition-colors duration-200 ${
          active
            ? "text-primary bg-accent"
            : "text-foreground/70 hover:text-foreground"
        }`}
      >
        {label}
      </Link>
    );
  };

  const handleLogout = () => {
    clearSession();
    navigate("/");
  };

  return (
    <header className="sticky top-0 z-40 bg-background border-b border-border">
      <div className="max-w-6xl mx-auto px-6 lg:px-10 h-16 flex items-center justify-between">
        <Link
          to={email ? "/dashboard" : "/"}
          data-testid="brand-link"
          className="flex items-center gap-2 font-heading text-lg font-semibold tracking-tight"
        >
          <ShieldCheck className="w-5 h-5 text-primary" strokeWidth={2} />
          EtsyWatch
        </Link>

        {email ? (
          <nav className="flex items-center gap-1">
            <NavLink to="/dashboard" label="Dashboard" testId="nav-dashboard" />
            <NavLink to="/evidence" label="Evidence Vault" testId="nav-evidence" />
            <NavLink to="/settings" label="Alert Settings" testId="nav-settings" />
            <div className="brand-rule w-px h-6 mx-3 bg-border" />
            <span className="hidden sm:inline text-xs text-muted-foreground mr-2">
              {email}
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleLogout}
              data-testid="logout-btn"
              className="text-foreground/70 hover:text-foreground"
            >
              <LogOut className="w-4 h-4" />
            </Button>
          </nav>
        ) : (
          <nav className="flex items-center gap-2">
            <Link to="/" data-testid="nav-home" className="text-sm text-foreground/70 hover:text-foreground px-3 py-2">
              Home
            </Link>
          </nav>
        )}
      </div>
    </header>
  );
}
