import { Link, useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Server,
  Database,
  HardDrive,
  FileText,
  Users,
  Settings,
  ShieldCheck,
} from "lucide-react";

interface NavItem {
  to: string;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
}

const navItems: NavItem[] = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/servers", icon: Server, label: "Server" },
  { to: "/jobs", icon: Database, label: "Backup Jobs" },
  { to: "/storage", icon: HardDrive, label: "Storage" },
  { to: "/logs", icon: FileText, label: "Log" },
  { to: "/users", icon: Users, label: "Utenti" },
  { to: "/settings", icon: Settings, label: "Impostazioni" },
];

export default function Sidebar() {
  const { pathname } = useLocation();

  return (
    <aside className="w-64 min-h-screen bg-slate-900 text-slate-100 flex flex-col border-r border-slate-800">
      {/* Logo */}
      <div className="flex items-center gap-3 px-6 py-5 border-b border-slate-800">
        <div className="bg-primary rounded-lg p-1.5 shadow-md shadow-primary/25">
          <ShieldCheck className="h-5 w-5 text-white" />
        </div>
        <div>
          <span className="font-bold text-base text-white">DBShield</span>
          <p className="text-slate-500 text-[10px] leading-none mt-0.5">Backup Manager</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 space-y-0.5">
        {navItems.map(({ to, icon: Icon, label }) => {
          const isActive = pathname === to;
          return (
            <Link
              key={to}
              to={to}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-all duration-150",
                isActive
                  ? "bg-primary text-white shadow-sm"
                  : "text-slate-400 hover:text-slate-100 hover:bg-slate-800/70"
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              <span>{label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-slate-800 flex items-center justify-between">
        <span className="text-slate-600 text-xs">v1.0.0</span>
        <span className="text-slate-700 text-xs">DBShield</span>
      </div>
    </aside>
  );
}
