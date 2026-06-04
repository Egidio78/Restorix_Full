import { useQuery } from "@tanstack/react-query"
import { ShieldCheck, Server, Database, AlertTriangle, Activity, Clock, CheckCircle, XCircle } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import api from "@/lib/api"

interface ServerItem { id: string; name: string; status: string }
interface JobItem { id: string; name: string; enabled: boolean }
interface RunItem {
  id: string
  job_id: string
  status: "pending" | "running" | "success" | "failed" | "cancelled"
  started_at: string | null
  finished_at: string | null
  size_bytes: number | null
  trigger_type: string
}

function formatBytes(bytes: number | null): string {
  if (bytes === null || bytes === undefined) return "—"
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`
}

function formatDate(dt: string | null): string {
  if (!dt) return "—"
  return new Date(dt).toLocaleString("it-IT", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" })
}

function RunStatusBadge({ status }: { status: RunItem["status"] }) {
  const variants: Record<string, "success" | "destructive" | "warning" | "secondary" | "default"> = {
    success: "success", failed: "destructive", running: "warning", pending: "secondary", cancelled: "secondary",
  }
  const labels: Record<string, string> = {
    success: "Completato", failed: "Fallito", running: "In corso", pending: "In attesa", cancelled: "Annullato",
  }
  return <Badge variant={variants[status] ?? "default"}>{labels[status] ?? status}</Badge>
}

export default function Dashboard() {
  const { data: servers = [] } = useQuery<ServerItem[]>({
    queryKey: ["servers"],
    queryFn: () => api.get("/servers/").then(r => r.data),
    refetchInterval: 30000,
  })

  const { data: jobs = [] } = useQuery<JobItem[]>({
    queryKey: ["jobs"],
    queryFn: () => api.get("/jobs/").then(r => r.data),
    refetchInterval: 30000,
  })

  const { data: runs = [] } = useQuery<RunItem[]>({
    queryKey: ["runs"],
    queryFn: () => api.get("/runs/").then(r => r.data),
    refetchInterval: 15000,
  })

  const onlineServers = servers.filter(s => s.status === "online").length
  const activeJobs = jobs.filter(j => j.enabled).length
  const todayRuns = runs.filter(r => r.started_at && new Date(r.started_at).toDateString() === new Date().toDateString())
  const successToday = todayRuns.filter(r => r.status === "success").length
  const errorJobs = runs.filter(r => r.status === "failed").length
  const recentRuns = runs.slice(0, 10)

  const stats = [
    { label: "Server Online", value: `${onlineServers}/${servers.length}`, icon: Server, iconColor: onlineServers > 0 ? "text-green-500" : "text-muted-foreground", description: servers.length === 0 ? "Nessun server configurato" : `${servers.length - onlineServers} offline` },
    { label: "Job Attivi", value: activeJobs.toString(), icon: Database, iconColor: "text-blue-500", description: `${jobs.length} job totali` },
    { label: "Backup Oggi", value: successToday.toString(), icon: ShieldCheck, iconColor: "text-primary", description: `${todayRuns.length} eseguiti` },
    { label: "Errori Recenti", value: errorJobs.toString(), icon: AlertTriangle, iconColor: errorJobs > 0 ? "text-destructive" : "text-muted-foreground", description: "ultimi backup" },
  ]

  return (
    <div className="space-y-6 max-w-7xl">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground text-sm mt-1">Panoramica del sistema di backup</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map(({ label, value, description, icon: Icon, iconColor }) => (
          <Card key={label} className="hover:shadow-md transition-shadow">
            <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
              <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
              <Icon className={`h-5 w-5 ${iconColor}`} />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-extrabold bg-gradient-to-r from-rx-accent to-rx-accent-bright bg-clip-text text-transparent">{value}</div>
              <p className="text-xs text-muted-foreground mt-1">{description}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-muted-foreground" />
              <CardTitle className="text-base">{"Attività recente"}</CardTitle>
            </div>
            <CardDescription>Ultime esecuzioni di backup</CardDescription>
          </CardHeader>
          <CardContent>
            {recentRuns.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <ShieldCheck className="h-10 w-10 text-muted-foreground/30 mb-3" />
                <p className="text-sm text-muted-foreground">Nessun backup eseguito ancora.</p>
                <p className="text-xs text-muted-foreground/70 mt-1">Configura un job e avvia il primo backup.</p>
              </div>
            ) : (
              <div className="space-y-2">
                {recentRuns.map(run => (
                  <div key={run.id} className="flex items-center justify-between py-2 border-b last:border-0">
                    <div className="flex items-center gap-3 min-w-0">
                      {run.status === "success" ? <CheckCircle className="h-4 w-4 text-green-500 shrink-0" /> :
                       run.status === "failed" ? <XCircle className="h-4 w-4 text-destructive shrink-0" /> :
                       <Clock className="h-4 w-4 text-muted-foreground shrink-0" />}
                      <div className="min-w-0">
                        <p className="text-sm font-medium truncate">{formatDate(run.started_at)}</p>
                        <p className="text-xs text-muted-foreground">{formatBytes(run.size_bytes)}</p>
                      </div>
                    </div>
                    <RunStatusBadge status={run.status} />
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Server className="h-4 w-4 text-muted-foreground" />
              <CardTitle className="text-base">Stato server</CardTitle>
            </div>
            <CardDescription>Server collegati al sistema</CardDescription>
          </CardHeader>
          <CardContent>
            {servers.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <Server className="h-10 w-10 text-muted-foreground/30 mb-3" />
                <p className="text-sm text-muted-foreground">Nessun server configurato.</p>
                <p className="text-xs text-muted-foreground/70 mt-1">Vai in <span className="font-medium">Server</span> per aggiungere il primo server.</p>
              </div>
            ) : (
              <div className="space-y-2">
                {servers.map(server => (
                  <div key={server.id} className="flex items-center justify-between py-2 border-b last:border-0">
                    <div className="flex items-center gap-2">
                      <div className={`h-2 w-2 rounded-full ${server.status === "online" ? "bg-rx-accent shadow-[0_0_6px_#34d399]" : server.status === "offline" ? "bg-red-500" : "bg-muted-foreground"}`} />
                      <span className="text-sm font-medium">{server.name}</span>
                    </div>
                    <Badge variant={server.status === "online" ? "success" : server.status === "offline" ? "destructive" : "secondary"}>
                      {server.status === "online" ? "Online" : server.status === "offline" ? "Offline" : "Mai connesso"}
                    </Badge>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
