import { Link, useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  ArchiveRestore,
  Server,
  Database,
  HardDrive,
  FileText,
  Users,
  Settings,
  Shield,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";

interface NavItem {
  to: string;
  icon: LucideIcon;
  label: string;
  roles?: string[];
}

const navItems: NavItem[] = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/restore-hub", icon: ArchiveRestore, label: "Restore Hub" },
  { to: "/servers", icon: Server, label: "Server" },
  { to: "/jobs", icon: Database, label: "Backup Jobs" },
  { to: "/storage", icon: HardDrive, label: "Storage" },
  { to: "/logs", icon: FileText, label: "Log" },
  { to: "/audit", icon: Shield, label: "Audit", roles: ["superadmin", "admin"] },
  { to: "/users", icon: Users, label: "Utenti" },
  { to: "/settings", icon: Settings, label: "Impostazioni" },
];

export default function Sidebar() {
  const { pathname } = useLocation();
  const { user } = useAuth();

  const visibleItems = navItems.filter(
    (i) => !i.roles || (user?.role && i.roles.includes(user.role))
  );

  return (
    <aside className="w-56 min-h-screen bg-gradient-to-b from-rx-bg to-rx-bg-elevated border-r border-rx-border flex flex-col">
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 py-5 border-b border-rx-border">
        <img src="/logo.svg" alt="Restorix" className="h-8 w-8" />
        <div>
          <span className="text-xl font-extrabold tracking-tight text-rx-ink">
            Restor<span className="text-rx-accent">ix</span>
          </span>
          <p className="text-rx-ink-faint text-[10px] leading-none mt-0.5">Backup Manager</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-2 py-3 space-y-0.5">
        {visibleItems.map(({ to, icon: Icon, label }) => {
          const isActive = pathname === to;
          return (
            <Link
              key={to}
              to={to}
              aria-current={isActive ? "page" : undefined}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-all duration-150",
                isActive
                  ? "bg-gradient-to-r from-rx-accent/15 to-transparent text-rx-accent border-l-[3px] border-rx-accent pl-2"
                  : "text-rx-ink-muted hover:text-rx-ink hover:bg-white/5"
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              <span>{label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-rx-border flex items-center justify-between text-xs text-rx-ink-faint">
        <span>v1.2.0</span>
        <span>Restorix</span>
      </div>
    </aside>
  );
}
