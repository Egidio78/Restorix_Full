import {
  ShieldCheck,
  Server,
  Database,
  AlertTriangle,
  Activity,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface StatCard {
  label: string;
  value: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  iconColor: string;
  trend?: "up" | "down" | "neutral";
}

const stats: StatCard[] = [
  {
    label: "Server Online",
    value: "—",
    description: "Server connessi e attivi",
    icon: Server,
    iconColor: "text-green-500",
  },
  {
    label: "Backup Jobs",
    value: "—",
    description: "Job di backup configurati",
    icon: Database,
    iconColor: "text-blue-500",
  },
  {
    label: "Backup Completati",
    value: "—",
    description: "Nelle ultime 24 ore",
    icon: ShieldCheck,
    iconColor: "text-primary",
  },
  {
    label: "Errori Attivi",
    value: "—",
    description: "Job in stato di errore",
    icon: AlertTriangle,
    iconColor: "text-destructive",
  },
];

export default function Dashboard() {
  return (
    <div className="space-y-6 max-w-7xl">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Panoramica dello stato del sistema di backup
        </p>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map(({ label, value, description, icon: Icon, iconColor }) => (
          <Card key={label} className="hover:shadow-md transition-shadow">
            <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {label}
              </CardTitle>
              <div className={cn("p-2 rounded-lg bg-muted/50", iconColor)}>
                <Icon className="h-4 w-4" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{value}</div>
              <p className="text-xs text-muted-foreground mt-1">{description}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Activity placeholder */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-muted-foreground" />
              <CardTitle className="text-base">Attività recente</CardTitle>
            </div>
            <CardDescription>
              Ultime esecuzioni di backup
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <ShieldCheck className="h-10 w-10 text-muted-foreground/30 mb-3" />
              <p className="text-sm text-muted-foreground">
                Nessun backup eseguito ancora.
              </p>
              <p className="text-xs text-muted-foreground/70 mt-1">
                Aggiungi un server e configura un job per iniziare.
              </p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Server className="h-4 w-4 text-muted-foreground" />
              <CardTitle className="text-base">Stato server</CardTitle>
            </div>
            <CardDescription>
              Server collegati al sistema
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <Server className="h-10 w-10 text-muted-foreground/30 mb-3" />
              <p className="text-sm text-muted-foreground">
                Nessun server configurato.
              </p>
              <p className="text-xs text-muted-foreground/70 mt-1">
                Vai in <span className="font-medium">Server</span> per aggiungere il primo server.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
