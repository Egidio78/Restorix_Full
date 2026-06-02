import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Plus, Database, Play, Pause, Trash2, Clock, PlayCircle, Pencil, FolderArchive } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import api from "@/lib/api"

interface BackupJob {
  id: string
  name: string
  server_id: string
  backup_type: "mssql" | "mysql" | "folder"
  db_instance_id: string | null
  folder_path: string | null
  storage_destination_id: string
  schedule_cron: string
  compression_enabled: boolean
  mssql_native_compression: boolean
  encryption_enabled: boolean
  retention_days: number
  enabled: boolean
}

interface Server { id: string; name: string; hostname: string; engine?: string }
interface DbInstance { id: string; name: string; connection_string: string }
interface StorageDest { id: string; name: string; storage_type: string }

const CRON_PRESETS = [
  { label: "Ogni giorno alle 02:00", value: "0 2 * * *" },
  { label: "Ogni giorno alle 00:00", value: "0 0 * * *" },
  { label: "Ogni 6 ore", value: "0 */6 * * *" },
  { label: "Ogni lunedi alle 03:00", value: "0 3 * * 1" },
  { label: "Ogni ora", value: "0 * * * *" },
  { label: "Personalizzato", value: "custom" },
]

export default function Jobs() {
  const qc = useQueryClient()
  const [showAdd, setShowAdd] = useState(false)
  const [selectedServer, setSelectedServer] = useState("")
  const [cronPreset, setCronPreset] = useState("")
  const [customCron, setCustomCron] = useState("")
  const [backupType, setBackupType] = useState<"mssql" | "mysql" | "folder">("mssql")
  const [folderPath, setFolderPath] = useState("")
  const [form, setForm] = useState({
    name: "", db_instance_id: "", storage_destination_id: "",
    compression_enabled: false, mssql_native_compression: true, encryption_enabled: false,
    retention_days: 30, enabled: true,
  })
  const [error, setError] = useState("")

  // Edit state
  const [editJob, setEditJob] = useState<BackupJob | null>(null)
  const [editForm, setEditForm] = useState<any>({})
  const [editCronPreset, setEditCronPreset] = useState("")
  const [editCustomCron, setEditCustomCron] = useState("")

  const { data: jobs = [], isLoading } = useQuery<BackupJob[]>({
    queryKey: ["jobs"],
    queryFn: () => api.get("/jobs/").then(r => r.data),
  })

  const { data: servers = [] } = useQuery<Server[]>({
    queryKey: ["servers"],
    queryFn: () => api.get("/servers/").then(r => r.data),
  })

  const { data: dbInstances = [] } = useQuery<DbInstance[]>({
    queryKey: ["db-instances", selectedServer],
    queryFn: () => selectedServer ? api.get(`/servers/${selectedServer}/databases`).then(r => r.data) : Promise.resolve([]),
    enabled: !!selectedServer,
  })

  const { data: editDbInstances = [] } = useQuery<DbInstance[]>({
    queryKey: ["db-instances", editJob?.server_id],
    queryFn: () => editJob ? api.get(`/servers/${editJob.server_id}/databases`).then(r => r.data) : Promise.resolve([]),
    enabled: !!editJob && (editJob.backup_type === "mssql" || editJob.backup_type === "mysql"),
  })

  const { data: storages = [] } = useQuery<StorageDest[]>({
    queryKey: ["storage"],
    queryFn: () => api.get("/storage/").then(r => r.data),
  })

  const cronValue = cronPreset === "custom" ? customCron : cronPreset
  const editCronValue = editCronPreset === "custom" ? editCustomCron : editCronPreset

  const resetAddForm = () => {
    setForm({
      name: "", db_instance_id: "", storage_destination_id: "",
      compression_enabled: false, mssql_native_compression: true, encryption_enabled: false,
      retention_days: 30, enabled: true,
    })
    setSelectedServer("")
    setCronPreset("")
    setCustomCron("")
    setBackupType("mssql" as "mssql" | "mysql" | "folder")
    setFolderPath("")
  }

  const addMutation = useMutation({
    mutationFn: () => api.post("/jobs/", {
      name: form.name,
      server_id: selectedServer,
      storage_destination_id: form.storage_destination_id,
      schedule_cron: cronValue,
      compression_enabled: form.compression_enabled,
      mssql_native_compression: form.mssql_native_compression,
      encryption_enabled: form.encryption_enabled,
      retention_days: form.retention_days,
      enabled: form.enabled,
      backup_type: backupType,
      db_instance_id: (backupType === "mssql" || backupType === "mysql") ? form.db_instance_id : null,
      folder_path: backupType === "folder" ? folderPath : null,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["jobs"] })
      setShowAdd(false)
      resetAddForm()
      setError("")
    },
    onError: () => setError("Errore durante la creazione"),
  })

  const editMutation = useMutation({
    mutationFn: ({ id, ...data }: any) => api.patch(`/jobs/${id}`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["jobs"] })
      setEditJob(null)
    },
    onError: () => setError("Errore durante la modifica"),
  })

  const toggleMutation = useMutation({
    mutationFn: (id: string) => api.patch(`/jobs/${id}/toggle`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs"] }),
  })

  const [runFeedback, setRunFeedback] = useState<string | null>(null)
  const runMutation = useMutation({
    mutationFn: (id: string) => api.post(`/jobs/${id}/run`),
    onSuccess: (_, jobId) => {
      const job = jobs.find(j => j.id === jobId)
      setRunFeedback(`✓ Backup "${job?.name ?? jobId}" avviato! L'agente lo prenderà entro 30 secondi.`)
      setTimeout(() => setRunFeedback(null), 5000)
      qc.invalidateQueries({ queryKey: ["jobs"] })
      qc.invalidateQueries({ queryKey: ["runs"] })
    },
    onError: () => {
      setRunFeedback("✗ Errore nell'avvio del backup")
      setTimeout(() => setRunFeedback(null), 5000)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/jobs/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs"] }),
  })

  const getServerName = (id: string) => servers.find(s => s.id === id)?.name ?? id
  const getStorageName = (id: string) => storages.find(s => s.id === id)?.name ?? id
  const getDbName = (id: string | null) => id ? (dbInstances.find(d => d.id === id)?.name ?? id) : "—"

  const openEdit = (job: BackupJob) => {
    setEditJob(job)
    setEditForm({
      name: job.name,
      storage_destination_id: job.storage_destination_id,
      retention_days: job.retention_days,
      compression_enabled: job.compression_enabled,
      mssql_native_compression: job.mssql_native_compression,
      encryption_enabled: job.encryption_enabled,
      encryption_password: "",
      db_instance_id: job.db_instance_id,
      folder_path: job.folder_path ?? "",
    })
    const preset = CRON_PRESETS.find(p => p.value === job.schedule_cron)
    if (preset) {
      setEditCronPreset(preset.value)
      setEditCustomCron("")
    } else {
      setEditCronPreset("custom")
      setEditCustomCron(job.schedule_cron)
    }
  }

  return (
    <div className="space-y-6">
      {runFeedback && (
        <div className={`fixed top-4 right-4 z-[200] rounded-lg px-4 py-3 shadow-lg border ${runFeedback.startsWith("✓") ? "bg-green-50 border-green-200 text-green-800" : "bg-destructive/10 border-destructive/30 text-destructive"}`}>
          {runFeedback}
        </div>
      )}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Backup Jobs</h1>
          <p className="text-muted-foreground text-sm mt-1">Gestisci i job di backup automatico</p>
        </div>
        <Button variant="restorix" onClick={() => setShowAdd(true)} disabled={servers.length === 0 || storages.length === 0}>
          <Plus className="h-4 w-4 mr-2" /> Nuovo Job
        </Button>
      </div>

      {servers.length === 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-sm text-yellow-800">
          Aggiungi almeno un <strong>server</strong> e una <strong>destinazione storage</strong> prima di creare un job.
        </div>
      )}

      {isLoading ? (
        <div className="text-center py-12 text-muted-foreground">Caricamento...</div>
      ) : jobs.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Database className="h-12 w-12 text-muted-foreground/30 mb-4" />
            <p className="text-muted-foreground font-medium">Nessun backup job configurato</p>
            <Button className="mt-4" onClick={() => setShowAdd(true)} disabled={servers.length === 0}>
              <Plus className="h-4 w-4 mr-2" /> Nuovo Job
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4">
          {jobs.map(job => (
            <Card key={job.id} className={`hover:shadow-md transition-shadow ${!job.enabled ? "opacity-60" : ""}`}>
              <CardContent className="p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold">{job.name}</span>
                      <Badge variant={job.enabled ? "success" : "secondary"}>
                        {job.enabled ? "Attivo" : "Disabilitato"}
                      </Badge>
                      <Badge variant="default">
                        {job.backup_type === "folder" ? "Cartella" : job.backup_type === "mysql" ? "MySQL" : "MSSQL"}
                      </Badge>
                      {job.compression_enabled && <Badge variant="default">Compresso</Badge>}
                      {job.encryption_enabled && <Badge variant="warning">Cifrato</Badge>}
                    </div>
                    <div className="flex items-center gap-4 mt-1 text-sm text-muted-foreground flex-wrap">
                      <span>Server: {getServerName(job.server_id)}</span>
                      {job.backup_type === "folder" ? (
                        <span className="flex items-center gap-1">
                          <FolderArchive className="h-3.5 w-3.5" />
                          <code className="text-xs">{job.folder_path}</code>
                        </span>
                      ) : (
                        <span>DB: {getDbName(job.db_instance_id)}</span>
                      )}
                      {job.backup_type === "mysql" && (
                        <span className="text-xs text-muted-foreground/70">.sql.gz</span>
                      )}
                      <span>Storage: {getStorageName(job.storage_destination_id)}</span>
                    </div>
                    <div className="flex items-center gap-1 mt-1 text-xs text-muted-foreground">
                      <Clock className="h-3 w-3" />
                      <code className="bg-muted px-1 rounded">{job.schedule_cron}</code>
                      <span>&mdash; Retention: {job.retention_days} giorni</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <Button variant="restorix" size="sm" disabled={runMutation.isPending} onClick={() => runMutation.mutate(job.id)} title="Avvia subito un backup">
                      <PlayCircle className="h-3.5 w-3.5 mr-1" /> Backup ora
                    </Button>
                    <Button variant="ghost" size="icon" title="Modifica" onClick={() => openEdit(job)}>
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="icon" onClick={() => toggleMutation.mutate(job.id)}>
                      {job.enabled ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                    </Button>
                    <Button variant="ghost" size="icon" className="text-destructive hover:text-destructive" onClick={() => {
                      if (confirm("Eliminare " + job.name + "?")) deleteMutation.mutate(job.id)
                    }}>
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Create Dialog */}
      <Dialog open={showAdd} onOpenChange={(o) => { setShowAdd(o); if (!o) resetAddForm() }}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Nuovo Backup Job</DialogTitle>
            <DialogDescription>Configura un job di backup automatico</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label>Nome job</Label>
              <Input placeholder="es. Backup DB Produzione Notturno" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
            </div>
            <div className="space-y-1.5">
              <Label>Server</Label>
              <Select value={selectedServer} onValueChange={v => {
                setSelectedServer(v)
                setForm(f => ({ ...f, db_instance_id: "" }))
                // Auto-set backup type based on server engine
                const engine = servers.find(s => s.id === v)?.engine ?? "mssql"
                setBackupType(engine === "mysql" ? "mysql" : "mssql")
              }}>
                <SelectTrigger><SelectValue placeholder="Seleziona server..." /></SelectTrigger>
                <SelectContent>
                  {servers.map(s => <SelectItem key={s.id} value={s.id}>{s.name} ({s.hostname})</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Tipo di backup</Label>
              {(() => {
                const selectedServerEngine = servers.find(s => s.id === selectedServer)?.engine ?? "mssql"
                const mssqlDisabled = selectedServerEngine === "mysql"
                const mysqlDisabled = selectedServerEngine === "mssql"
                return (
                  <Select value={backupType} onValueChange={v => setBackupType(v as "mssql" | "mysql" | "folder")}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="mssql" disabled={mssqlDisabled}>Database MSSQL {mssqlDisabled ? "(server MySQL)" : ""}</SelectItem>
                      <SelectItem value="mysql" disabled={mysqlDisabled}>Database MySQL / MariaDB {mysqlDisabled ? "(server MSSQL)" : ""}</SelectItem>
                      <SelectItem value="folder">Cartella filesystem</SelectItem>
                    </SelectContent>
                  </Select>
                )
              })()}
            </div>
            {(backupType === "mssql" || backupType === "mysql") ? (
              <div className="space-y-1.5">
                <Label>Database</Label>
                <Select value={form.db_instance_id} onValueChange={v => setForm(f => ({ ...f, db_instance_id: v }))} disabled={!selectedServer || dbInstances.length === 0}>
                  <SelectTrigger>
                    <SelectValue placeholder={selectedServer ? (dbInstances.length === 0 ? "Nessun DB configurato" : "Seleziona database...") : "Prima seleziona un server"} />
                  </SelectTrigger>
                  <SelectContent>
                    {dbInstances.map(d => <SelectItem key={d.id} value={d.id}>{d.name} ({d.connection_string})</SelectItem>)}
                  </SelectContent>
                </Select>
                {backupType === "mysql" && (
                  <p className="text-xs text-muted-foreground">Output: <code>.sql.gz</code></p>
                )}
              </div>
            ) : (
              <div className="space-y-1.5">
                <Label>Percorso cartella sul server</Label>
                <Input placeholder="es. /var/www/html, C:\Dati o /home/user/documenti" value={folderPath} onChange={e => setFolderPath(e.target.value)} />
                <p className="text-xs text-muted-foreground">Verrà compressa in tar.gz e caricata sullo storage</p>
              </div>
            )}
            <div className="space-y-1.5">
              <Label>Destinazione Storage</Label>
              <Select value={form.storage_destination_id} onValueChange={v => setForm(f => ({ ...f, storage_destination_id: v }))}>
                <SelectTrigger><SelectValue placeholder="Seleziona storage..." /></SelectTrigger>
                <SelectContent>
                  {storages.map(s => <SelectItem key={s.id} value={s.id}>{s.name} ({s.storage_type})</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Schedulazione</Label>
              <Select value={cronPreset} onValueChange={setCronPreset}>
                <SelectTrigger><SelectValue placeholder="Seleziona frequenza..." /></SelectTrigger>
                <SelectContent>
                  {CRON_PRESETS.map(p => <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}
                </SelectContent>
              </Select>
              {cronPreset === "custom" && (
                <Input placeholder="es. 0 3 * * *" value={customCron} onChange={e => setCustomCron(e.target.value)} className="font-mono text-sm mt-2" />
              )}
            </div>
            <div className="space-y-1.5">
              <Label>Retention (giorni)</Label>
              <Input type="number" min={1} value={form.retention_days} onChange={e => setForm(f => ({ ...f, retention_days: parseInt(e.target.value) || 30 }))} />
            </div>
            <div className="flex gap-4">
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input type="checkbox" checked={form.compression_enabled} onChange={e => setForm(f => ({ ...f, compression_enabled: e.target.checked }))} className="rounded" />
                Comprimi (gzip)
              </label>
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input type="checkbox" checked={form.encryption_enabled} onChange={e => setForm(f => ({ ...f, encryption_enabled: e.target.checked }))} className="rounded" />
                Cifra (AES-256)
              </label>
            </div>
            {backupType === 'mssql' && (
              <div className="rounded-md border p-3 bg-muted/30">
                <label className="flex items-start gap-2 text-sm cursor-pointer">
                  <input type="checkbox" checked={form.mssql_native_compression} onChange={e => setForm(f => ({ ...f, mssql_native_compression: e.target.checked }))} className="rounded mt-0.5" />
                  <span>
                    <span className="font-medium">Compressione MSSQL nativa (consigliato)</span>
                    <p className="text-xs text-muted-foreground mt-0.5">Usa BACKUP DATABASE ... WITH COMPRESSION. Il file .bak è già compresso, viene saltato il gzip esterno. ~10-20× più veloce su DB grandi.</p>
                  </span>
                </label>
              </div>
            )}
            {backupType === 'mysql' && (
              <div className="rounded-md border p-3 bg-muted/30 text-sm text-muted-foreground">
                I backup MySQL vengono sempre compressi in <code>.sql.gz</code> (gzip). La compressione nativa MSSQL non è applicabile.
              </div>
            )}
            {error && <p className="text-destructive text-sm">{error}</p>}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAdd(false)}>Annulla</Button>
            <Button
              variant="restorix"
              disabled={!form.name || !selectedServer || !form.storage_destination_id || !cronValue ||
                ((backupType === "mssql" || backupType === "mysql") && !form.db_instance_id) ||
                (backupType === "folder" && !folderPath) ||
                addMutation.isPending}
              onClick={() => addMutation.mutate()}
            >
              {addMutation.isPending ? "Creazione..." : "Crea Job"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog open={!!editJob} onOpenChange={(o) => { if (!o) setEditJob(null) }}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Modifica Backup Job</DialogTitle>
            <DialogDescription>
              Tipo: <strong>{editJob?.backup_type === "folder" ? "Cartella filesystem" : editJob?.backup_type === "mysql" ? "Database MySQL / MariaDB" : "Database MSSQL"}</strong> (non modificabile)
            </DialogDescription>
          </DialogHeader>
          {editJob && (
            <div className="space-y-4">
              <div className="space-y-1.5">
                <Label>Nome job</Label>
                <Input value={editForm.name ?? ""} onChange={e => setEditForm((f: any) => ({ ...f, name: e.target.value }))} />
              </div>
              {(editJob.backup_type === "mssql" || editJob.backup_type === "mysql") ? (
                <div className="space-y-1.5">
                  <Label>Database</Label>
                  <Select value={editForm.db_instance_id ?? ""} onValueChange={v => setEditForm((f: any) => ({ ...f, db_instance_id: v }))}>
                    <SelectTrigger><SelectValue placeholder="Seleziona database..." /></SelectTrigger>
                    <SelectContent>
                      {editDbInstances.map(d => <SelectItem key={d.id} value={d.id}>{d.name} ({d.connection_string})</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              ) : (
                <div className="space-y-1.5">
                  <Label>Percorso cartella</Label>
                  <Input value={editForm.folder_path ?? ""} onChange={e => setEditForm((f: any) => ({ ...f, folder_path: e.target.value }))} />
                </div>
              )}
              <div className="space-y-1.5">
                <Label>Destinazione Storage</Label>
                <Select value={editForm.storage_destination_id ?? ""} onValueChange={v => setEditForm((f: any) => ({ ...f, storage_destination_id: v }))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {storages.map(s => <SelectItem key={s.id} value={s.id}>{s.name} ({s.storage_type})</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Schedulazione</Label>
                <Select value={editCronPreset} onValueChange={setEditCronPreset}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {CRON_PRESETS.map(p => <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}
                  </SelectContent>
                </Select>
                {editCronPreset === "custom" && (
                  <Input value={editCustomCron} onChange={e => setEditCustomCron(e.target.value)} className="font-mono text-sm mt-2" />
                )}
              </div>
              <div className="space-y-1.5">
                <Label>Retention (giorni)</Label>
                <Input type="number" min={1} value={editForm.retention_days ?? 30} onChange={e => setEditForm((f: any) => ({ ...f, retention_days: parseInt(e.target.value) || 30 }))} />
              </div>
              <div className="flex gap-4">
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="checkbox" checked={!!editForm.compression_enabled} onChange={e => setEditForm((f: any) => ({ ...f, compression_enabled: e.target.checked }))} className="rounded" />
                  Comprimi (gzip)
                </label>
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="checkbox" checked={!!editForm.encryption_enabled} onChange={e => setEditForm((f: any) => ({ ...f, encryption_enabled: e.target.checked }))} className="rounded" />
                  Cifra (AES-256)
                </label>
              </div>
              {editJob.backup_type === 'mssql' && (
                <div className="rounded-md border p-3 bg-muted/30">
                  <label className="flex items-start gap-2 text-sm cursor-pointer">
                    <input type="checkbox" checked={!!editForm.mssql_native_compression} onChange={e => setEditForm((f: any) => ({ ...f, mssql_native_compression: e.target.checked }))} className="rounded mt-0.5" />
                    <span>
                      <span className="font-medium">Compressione MSSQL nativa (consigliato)</span>
                      <p className="text-xs text-muted-foreground mt-0.5">Usa BACKUP DATABASE ... WITH COMPRESSION. Salta il gzip esterno, ~10-20× più veloce.</p>
                    </span>
                  </label>
                </div>
              )}
              {editJob.backup_type === 'mysql' && (
                <div className="rounded-md border p-3 bg-muted/30 text-sm text-muted-foreground">
                  I backup MySQL vengono sempre compressi in <code>.sql.gz</code> (gzip). La compressione nativa MSSQL non è applicabile.
                </div>
              )}
              {editForm.encryption_enabled && (
                <div className="space-y-1.5">
                  <Label>Nuova password cifratura (lascia vuoto per non cambiarla)</Label>
                  <Input type="password" value={editForm.encryption_password ?? ""} onChange={e => setEditForm((f: any) => ({ ...f, encryption_password: e.target.value }))} />
                </div>
              )}
              {error && <p className="text-destructive text-sm">{error}</p>}
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditJob(null)}>Annulla</Button>
            <Button
              disabled={editMutation.isPending}
              onClick={() => {
                if (!editJob) return
                const payload: any = {
                  name: editForm.name,
                  storage_destination_id: editForm.storage_destination_id,
                  schedule_cron: editCronValue,
                  retention_days: editForm.retention_days,
                  compression_enabled: editForm.compression_enabled,
                  mssql_native_compression: editForm.mssql_native_compression,
                  encryption_enabled: editForm.encryption_enabled,
                }
                if (editJob.backup_type === "mssql" && editForm.db_instance_id) {
                  payload.db_instance_id = editForm.db_instance_id
                }
                if (editJob.backup_type === "folder" && editForm.folder_path) {
                  payload.folder_path = editForm.folder_path
                }
                if (editForm.encryption_enabled && editForm.encryption_password) {
                  payload.encryption_password = editForm.encryption_password
                }
                editMutation.mutate({ id: editJob.id, ...payload })
              }}
            >
              {editMutation.isPending ? "Salvataggio..." : "Salva modifiche"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
