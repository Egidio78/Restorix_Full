import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { FileText, CheckCircle, XCircle, Clock, Loader, Filter, Trash2, Folder, Download } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table"
import api from "@/lib/api"
import { useState, useMemo } from "react"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { useAuth } from "@/hooks/useAuth"

interface BackupRun {
  id: string
  job_id: string
  job_name: string | null
  started_at: string | null
  finished_at: string | null
  status: "pending" | "running" | "success" | "failed" | "cancelled"
  size_bytes: number | null
  file_path: string | null
  error_message: string | null
  trigger_type: string
  server_id: string | null
  server_name: string | null
  backup_type: "mssql" | "folder" | null
  database_name: string | null
  folder_path: string | null
  storage_id: string | null
  storage_name: string | null
  storage_type: string | null
  retention_purged: boolean
  encryption_enabled?: boolean
}

interface ServerItem { id: string; name: string }
interface StorageItem { id: string; name: string }

const apiBase = ((import.meta as any).env?.VITE_API_BASE_URL as string | undefined) ?? "/api/v1"
const downloadUrl = (runId: string, decrypt: boolean) =>
  `${apiBase}/runs/${runId}/download?decrypt=${decrypt}`

function formatBytes(n: number | null): string {
  if (!n) return "—"
  if (n < 1024) return `${n} B`
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(1)} KB`
  if (n < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(1)} MB`
  return `${(n / 1024 ** 3).toFixed(2)} GB`
}

function formatDate(dt: string | null): string {
  if (!dt) return "—"
  return new Date(dt).toLocaleString("it-IT", { day: "2-digit", month: "2-digit", year: "2-digit", hour: "2-digit", minute: "2-digit" })
}

function truncate(s: string | null, n = 30): string {
  if (!s) return "—"
  return s.length > n ? s.slice(0, n - 1) + "…" : s
}

const STATUS_ICON: Record<string, React.ReactNode> = {
  success: <CheckCircle className="h-4 w-4 text-rx-accent drop-shadow-[0_0_4px_rgba(52,211,153,0.6)]" />,
  failed: <XCircle className="h-4 w-4 text-destructive" />,
  running: <Loader className="h-4 w-4 text-yellow-500 animate-spin" />,
  pending: <Clock className="h-4 w-4 text-muted-foreground" />,
  cancelled: <Clock className="h-4 w-4 text-muted-foreground" />,
}

const STATUS_VARIANTS: Record<string, "success" | "destructive" | "warning" | "secondary"> = {
  success: "success", failed: "destructive", running: "warning", pending: "secondary", cancelled: "secondary",
}

const STATUS_LABEL: Record<string, string> = {
  success: "Completato", failed: "Fallito", running: "In corso", pending: "In attesa", cancelled: "Annullato",
}

export default function Logs() {
  const qc = useQueryClient()
  const { user } = useAuth()
  const isSuperAdmin = user?.role === "superadmin"
  const canDownload = user?.role === "superadmin" || user?.role === "admin" || user?.role === "operator"
  const [statusFilter, setStatusFilter] = useState<string>("all")
  const [serverFilter, setServerFilter] = useState<string>("all")
  const [storageFilter, setStorageFilter] = useState<string>("all")

  const queryParams = useMemo(() => {
    const p = new URLSearchParams({ limit: "100" })
    if (statusFilter !== "all") p.set("status", statusFilter)
    if (serverFilter !== "all") p.set("server_id", serverFilter)
    if (storageFilter !== "all") p.set("storage_id", storageFilter)
    return p.toString()
  }, [statusFilter, serverFilter, storageFilter])

  const { data: runs = [], isLoading } = useQuery<BackupRun[]>({
    queryKey: ["runs", statusFilter, serverFilter, storageFilter],
    queryFn: () => api.get(`/runs/?${queryParams}`).then(r => r.data),
    refetchInterval: 15000,
  })

  const { data: servers = [] } = useQuery<ServerItem[]>({
    queryKey: ["servers"],
    queryFn: () => api.get("/servers/").then(r => r.data),
  })

  const { data: storages = [] } = useQuery<StorageItem[]>({
    queryKey: ["storage"],
    queryFn: () => api.get("/storage/").then(r => r.data),
  })

  const deleteRunMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/runs/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["runs"] }),
  })

  const deleteAllMutation = useMutation({
    mutationFn: () => api.delete("/runs/"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["runs"] }),
  })

  const showActionsCol = isSuperAdmin || canDownload

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Log Backup</h1>
          <p className="text-muted-foreground text-sm mt-1">Storico delle esecuzioni di backup</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {isSuperAdmin && runs.length > 0 && (
            <Button variant="outline" size="sm" className="text-destructive" disabled={deleteAllMutation.isPending} onClick={() => {
              if (confirm("Eliminare TUTTI i log di backup? L'operazione è irreversibile.")) {
                deleteAllMutation.mutate()
              }
            }}>
              <Trash2 className="h-4 w-4 mr-2" /> Elimina tutto
            </Button>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        <Filter className="h-4 w-4 text-muted-foreground" />
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-40"><SelectValue placeholder="Stato" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tutti gli stati</SelectItem>
            <SelectItem value="success">Completati</SelectItem>
            <SelectItem value="failed">Falliti</SelectItem>
            <SelectItem value="running">In corso</SelectItem>
            <SelectItem value="pending">In attesa</SelectItem>
            <SelectItem value="cancelled">Annullati</SelectItem>
          </SelectContent>
        </Select>
        <Select value={serverFilter} onValueChange={setServerFilter}>
          <SelectTrigger className="w-48"><SelectValue placeholder="Server" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tutti i server</SelectItem>
            {servers.map(s => <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={storageFilter} onValueChange={setStorageFilter}>
          <SelectTrigger className="w-48"><SelectValue placeholder="Storage" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tutti gli storage</SelectItem>
            {storages.map(s => <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      {isLoading ? (
        <div className="text-center py-12 text-muted-foreground">Caricamento...</div>
      ) : runs.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <FileText className="h-12 w-12 text-muted-foreground/30 mb-4" />
            <p className="text-muted-foreground font-medium">Nessun backup trovato</p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Quando</TableHead>
                  <TableHead>Stato</TableHead>
                  <TableHead>Server</TableHead>
                  <TableHead>Database</TableHead>
                  <TableHead>Storage</TableHead>
                  <TableHead>Job</TableHead>
                  <TableHead>Dimensione</TableHead>
                  <TableHead>File path</TableHead>
                  {showActionsCol && <TableHead className="text-right">Azioni</TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {runs.map(run => (
                  <TableRow key={run.id}>
                    <TableCell className="whitespace-nowrap text-xs">{formatDate(run.started_at)}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {STATUS_ICON[run.status] ?? STATUS_ICON.pending}
                        <Badge variant={STATUS_VARIANTS[run.status] ?? "default"}>
                          {STATUS_LABEL[run.status] ?? run.status}
                        </Badge>
                      </div>
                      {run.error_message && (
                        <p className="mt-1 text-xs text-destructive font-mono max-w-xs truncate" title={run.error_message}>
                          {run.error_message}
                        </p>
                      )}
                    </TableCell>
                    <TableCell className="text-sm">{run.server_name ?? "—"}</TableCell>
                    <TableCell className="text-sm">
                      {run.backup_type === "folder" ? (
                        <span className="inline-flex items-center gap-1 font-mono text-xs" title={run.folder_path ?? ""}>
                          <Folder className="h-3 w-3" />
                          {truncate(run.folder_path, 28)}
                        </span>
                      ) : (
                        run.database_name ?? "—"
                      )}
                    </TableCell>
                    <TableCell className="text-sm">
                      {run.storage_name ?? "—"}
                      {run.storage_type && (
                        <span className="ml-1 text-xs text-muted-foreground">({run.storage_type})</span>
                      )}
                    </TableCell>
                    <TableCell className="text-sm">
                      <span className="flex items-center gap-1 flex-wrap">
                        {run.job_name ?? "Job rimosso"}
                        {run.trigger_type === "manual" && <Badge variant="secondary" className="text-[10px]">M</Badge>}
                      </span>
                    </TableCell>
                    <TableCell className="text-sm whitespace-nowrap">{formatBytes(run.size_bytes)}</TableCell>
                    <TableCell>
                      {run.retention_purged ? (
                        <span title="Il file è stato cancellato dalla retention policy">
                          <Badge variant="secondary" className="text-[10px]">🗑️ Purgato</Badge>
                        </span>
                      ) : (
                        run.file_path ? (
                          <span className="font-mono text-xs" title={run.file_path}>
                            {truncate(run.file_path, 30)}
                          </span>
                        ) : "—"
                      )}
                    </TableCell>
                    {showActionsCol && (
                      <TableCell className="text-right">
                        <div className="inline-flex items-center gap-1 justify-end">
                          {canDownload && run.status === "success" && !run.retention_purged && (
                            <Button
                              variant="ghost"
                              size="icon"
                              title="Scarica backup"
                              onClick={() => { window.location.href = downloadUrl(run.id, false) }}
                            >
                              <Download className="h-4 w-4" />
                            </Button>
                          )}
                          {isSuperAdmin && (
                            <Button variant="ghost" size="icon" className="text-destructive" title="Elimina log" onClick={() => {
                              if (confirm("Eliminare questo log?")) deleteRunMutation.mutate(run.id)
                            }}>
                              <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
