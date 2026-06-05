import { useState, useRef, useEffect } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Plus, Server as ServerIcon, RefreshCw, Trash2, Copy, Check, Database, Pencil, Wrench } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import api from "@/lib/api"

interface Server {
  id: string
  name: string
  hostname: string
  agent_token: string
  agent_version: string | null
  status: "never_connected" | "online" | "offline"
  is_active: boolean
  engine?: string
  update_requested?: boolean
  latest_version?: string
  update_available?: boolean
  auto_update_enabled?: boolean
  update_status?: string
  update_badge?: "up_to_date" | "available" | "updating" | "failed" | "unknown"
}

interface DbInstance {
  id: string
  server_id: string
  name: string
  connection_string: string
  is_active: boolean
}

function StatusBadge({ status }: { status: Server["status"] }) {
  if (status === "online") return <Badge variant="success" className="bg-rx-accent/15 text-rx-accent border-rx-accent/30">Online</Badge>
  if (status === "offline") return <Badge variant="destructive">Offline</Badge>
  return <Badge variant="secondary">Mai connesso</Badge>
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <button onClick={copy} className="text-muted-foreground hover:text-foreground transition-colors p-1 rounded">
      {copied ? <Check className="h-3.5 w-3.5 text-green-500" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
  )
}

function DatabasesModal({ server, onClose }: { server: Server; onClose: () => void }) {
  const qc = useQueryClient()
  const [showAdd, setShowAdd] = useState(false)
  const [form, setForm] = useState({ name: "", connection_string: "localhost", username: "", password: "" })
  const [error, setError] = useState("")

  const [showDiscover, setShowDiscover] = useState(false)
  const [discoverForm, setDiscoverForm] = useState({ connection_string: "localhost", username: "sa", password: "" })
  const [discovering, setDiscovering] = useState(false)
  const [discovered, setDiscovered] = useState<string[] | null>(null)
  const [discoverError, setDiscoverError] = useState("")
  const [selectedDbs, setSelectedDbs] = useState<Set<string>>(new Set())

  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const mountedRef = useRef(true)

  useEffect(() => () => {
    mountedRef.current = false
    if (pollTimerRef.current) clearTimeout(pollTimerRef.current)
  }, [])

  const { data: dbs = [], isLoading } = useQuery<DbInstance[]>({
    queryKey: ["databases", server.id],
    queryFn: () => api.get(`/servers/${server.id}/databases`).then(r => r.data),
  })

  const addMutation = useMutation({
    mutationFn: (data: typeof form) => api.post(`/servers/${server.id}/databases`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["databases", server.id] })
      setShowAdd(false)
      setForm({ name: "", connection_string: "localhost", username: "", password: "" })
      setError("")
    },
    onError: () => setError("Errore durante l'aggiunta del database"),
  })

  const deleteMutation = useMutation({
    mutationFn: (dbId: string) => api.delete(`/servers/${server.id}/databases/${dbId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["databases", server.id] }),
  })

  const [editDb, setEditDb] = useState<DbInstance | null>(null)
  const [editDbForm, setEditDbForm] = useState({ name: "", connection_string: "", username: "", password: "" })

  const editDbMutation = useMutation({
    mutationFn: ({ id, ...data }: { id: string; name: string; connection_string: string; username: string; password: string }) =>
      api.patch(`/servers/${server.id}/databases/${id}`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["databases", server.id] })
      setEditDb(null)
    },
  })

  const startDiscover = async () => {
    setDiscovering(true)
    setDiscoverError("")
    setDiscovered(null)
    setSelectedDbs(new Set())
    try {
      await api.post(`/servers/${server.id}/discover`, discoverForm)
      const startedAt = Date.now()
      const poll = async () => {
        if (!mountedRef.current) return
        if (Date.now() - startedAt > 90_000) {
          setDiscoverError("Timeout: l'agente non ha risposto entro 90 secondi")
          setDiscovering(false)
          return
        }
        try {
          const res = await api.get(`/servers/${server.id}/discovery`)
          if (!mountedRef.current) return
          if (res.data.status === "ready") {
            if (res.data.error) {
              setDiscoverError(res.data.error)
            } else {
              setDiscovered(res.data.databases ?? [])
            }
            setDiscovering(false)
            return
          }
        } catch {}
        if (!mountedRef.current) return
        pollTimerRef.current = setTimeout(poll, 2000)
      }
      pollTimerRef.current = setTimeout(poll, 2000)
    } catch {
      setDiscoverError("Errore avvio discovery")
      setDiscovering(false)
    }
  }

  const registerSelected = async () => {
    try {
      for (const dbName of selectedDbs) {
        await api.post(`/servers/${server.id}/databases`, {
          name: dbName,
          connection_string: discoverForm.connection_string,
          username: discoverForm.username,
          password: discoverForm.password,
        })
      }
      qc.invalidateQueries({ queryKey: ["databases", server.id] })
      setShowDiscover(false)
      setDiscovered(null)
      setSelectedDbs(new Set())
    } catch (e: any) {
      setDiscoverError(e?.response?.data?.detail ?? "Errore durante la registrazione dei database")
    }
  }

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent
        className="max-w-2xl max-h-[90vh] overflow-y-auto"
        onPointerDownOutside={(e) => e.preventDefault()}
        onInteractOutside={(e) => e.preventDefault()}
        onEscapeKeyDown={(e) => { if (discovering) e.preventDefault(); }}
      >
        <DialogHeader>
          <DialogTitle>Database — {server.name}</DialogTitle>
          <DialogDescription>
            Registra i database {(server.engine ?? "mssql") === "mysql" ? "MySQL / MariaDB" : "MSSQL"} disponibili su questo server.
            Click sulla X o sul pulsante in basso per chiudere — non si chiude più cliccando fuori dalla finestra.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          {isLoading ? (
            <p className="text-sm text-muted-foreground text-center py-4">Caricamento...</p>
          ) : dbs.length === 0 ? (
            <div className="text-center py-8 border-2 border-dashed rounded-lg">
              <Database className="h-10 w-10 text-muted-foreground/30 mx-auto mb-2" />
              <p className="text-sm text-muted-foreground">Nessun database registrato</p>
            </div>
          ) : (
            <div className="divide-y border rounded-lg">
              {dbs.map(db => (
                <div key={db.id} className="flex items-center justify-between p-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <Database className="h-4 w-4 text-primary" />
                      <span className="font-medium">{db.name}</span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5 ml-6">Istanza: {db.connection_string}</p>
                  </div>
                  <div className="flex items-center gap-1">
                    <Button variant="ghost" size="icon" title="Modifica" onClick={() => {
                      setEditDb(db)
                      setEditDbForm({ name: db.name, connection_string: db.connection_string, username: "", password: "" })
                    }}>
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="icon" className="text-destructive hover:text-destructive" onClick={() => {
                      if (confirm("Eliminare " + db.name + "?")) deleteMutation.mutate(db.id)
                    }}>
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {!showAdd && !showDiscover && (
            <div className="grid grid-cols-2 gap-2">
              <Button variant="default" onClick={() => setShowDiscover(true)} disabled={server.status !== "online"}>
                <Database className="h-4 w-4 mr-2" /> Scopri da server
              </Button>
              <Button variant="outline" onClick={() => setShowAdd(true)}>
                <Plus className="h-4 w-4 mr-2" /> Aggiungi manualmente
              </Button>
            </div>
          )}

          {server.status !== "online" && !showAdd && !showDiscover && (
            <p className="text-xs text-yellow-700 bg-yellow-50 border border-yellow-200 rounded p-2">
              ⚠ Lo scopri automatico richiede che l'agente sia online sul server.
            </p>
          )}

          {showDiscover && (
            <div className="border rounded-lg p-4 space-y-3 bg-muted/30">
              <h3 className="font-medium text-sm">Scopri database</h3>
              {!discovered && !discovering && (
                <>
                  {(server.engine ?? "mssql") === "mysql" ? (
                    <p className="text-xs text-muted-foreground">L'agente eseguirà <code className="bg-muted px-1 rounded">SHOW DATABASES</code> e mostrerà la lista.</p>
                  ) : (
                    <p className="text-xs text-muted-foreground">L'agente eseguirà <code className="bg-muted px-1 rounded">SELECT name FROM sys.databases</code> e mostrerà la lista.</p>
                  )}
                  <div className="space-y-1.5">
                    <Label>{(server.engine ?? "mssql") === "mysql" ? "Host:Porta (es. 192.168.1.10:3306)" : "Istanza MSSQL"}</Label>
                    <Input
                      value={discoverForm.connection_string}
                      onChange={e => setDiscoverForm(f => ({ ...f, connection_string: e.target.value }))}
                      placeholder={(server.engine ?? "mssql") === "mysql" ? "localhost:3306" : "localhost o hostname\\istanza"}
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="space-y-1.5">
                      <Label>{(server.engine ?? "mssql") === "mysql" ? "Username" : "Username (sa o lascia vuoto per Win auth)"}</Label>
                      <Input value={discoverForm.username} onChange={e => setDiscoverForm(f => ({ ...f, username: e.target.value }))} />
                    </div>
                    <div className="space-y-1.5">
                      <Label>Password</Label>
                      <Input type="password" value={discoverForm.password} onChange={e => setDiscoverForm(f => ({ ...f, password: e.target.value }))} />
                    </div>
                  </div>
                  {discoverError && <p className="text-destructive text-sm bg-destructive/10 rounded p-2">{discoverError}</p>}
                  <div className="flex justify-end gap-2">
                    <Button variant="outline" size="sm" onClick={() => { setShowDiscover(false); setDiscoverError("") }}>Annulla</Button>
                    <Button size="sm" onClick={startDiscover} disabled={!discoverForm.connection_string}>
                      <Database className="h-3.5 w-3.5 mr-1" /> Avvia Scoperta
                    </Button>
                  </div>
                </>
              )}

              {discovering && (
                <div className="text-center py-6">
                  <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent mx-auto mb-2"></div>
                  <p className="text-sm text-muted-foreground">In attesa della risposta dell'agente...</p>
                  <p className="text-xs text-muted-foreground/70 mt-1">L'agente esegue il polling ogni 30s</p>
                </div>
              )}

              {discovered && (
                <>
                  <p className="text-sm">Trovati <strong>{discovered.length}</strong> database. Seleziona quali registrare:</p>
                  {discovered.length === 0 ? (
                    <p className="text-sm text-muted-foreground text-center py-3">Nessun database utente trovato</p>
                  ) : (
                    <div className="max-h-60 overflow-y-auto space-y-1 border rounded p-2 bg-background">
                      {discovered.map(name => {
                        const already = dbs.some(d => d.name === name)
                        return (
                          <label key={name} className={`flex items-center gap-2 p-2 rounded hover:bg-muted/50 cursor-pointer ${already ? "opacity-50" : ""}`}>
                            <input
                              type="checkbox"
                              disabled={already}
                              checked={selectedDbs.has(name)}
                              onChange={e => {
                                const s = new Set(selectedDbs)
                                if (e.target.checked) s.add(name); else s.delete(name)
                                setSelectedDbs(s)
                              }}
                              className="rounded"
                            />
                            <Database className="h-3.5 w-3.5 text-primary" />
                            <span className="text-sm font-medium">{name}</span>
                            {already && <span className="text-xs text-muted-foreground">(già registrato)</span>}
                          </label>
                        )
                      })}
                    </div>
                  )}
                  <div className="flex justify-end gap-2">
                    <Button variant="outline" size="sm" onClick={() => { setShowDiscover(false); setDiscovered(null) }}>Annulla</Button>
                    <Button size="sm" disabled={selectedDbs.size === 0} onClick={registerSelected}>
                      Registra {selectedDbs.size} database
                    </Button>
                  </div>
                </>
              )}
            </div>
          )}

          {showAdd && (
            <div className="border rounded-lg p-4 space-y-3 bg-muted/30">
              <h3 className="font-medium text-sm">Aggiungi manualmente</h3>
              <div className="space-y-1.5">
                <Label>Nome database</Label>
                <Input placeholder="es. CRM_Production" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
              </div>
              <div className="space-y-1.5">
                <Label>{(server.engine ?? "mssql") === "mysql" ? "Host:Porta (es. 192.168.1.10:3306)" : "Istanza MSSQL"}</Label>
                <Input
                  placeholder={(server.engine ?? "mssql") === "mysql" ? "es. 192.168.1.10:3306" : "es. localhost, 192.168.1.10\\SQLEXPRESS"}
                  value={form.connection_string}
                  onChange={e => setForm(f => ({ ...f, connection_string: e.target.value }))}
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1.5">
                  <Label>Username</Label>
                  <Input
                    placeholder={(server.engine ?? "mssql") === "mysql" ? "root" : "sa o vuoto per Win auth"}
                    value={form.username}
                    onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>Password</Label>
                  <Input type="password" placeholder="••••••••" value={form.password} onChange={e => setForm(f => ({ ...f, password: e.target.value }))} />
                </div>
              </div>
              {error && <p className="text-destructive text-sm">{error}</p>}
              <div className="flex justify-end gap-2">
                <Button variant="outline" size="sm" onClick={() => { setShowAdd(false); setError("") }}>Annulla</Button>
                <Button size="sm" disabled={!form.name || !form.connection_string || addMutation.isPending} onClick={() => addMutation.mutate(form)}>
                  {addMutation.isPending ? "Salvataggio..." : "Salva Database"}
                </Button>
              </div>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button onClick={onClose}>Chiudi</Button>
        </DialogFooter>
      </DialogContent>

      <Dialog open={!!editDb} onOpenChange={() => setEditDb(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Modifica Database</DialogTitle>
            <DialogDescription>Lascia password vuota per non modificarla</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label>Nome database</Label>
              <Input value={editDbForm.name} onChange={e => setEditDbForm(f => ({ ...f, name: e.target.value }))} />
            </div>
            <div className="space-y-1.5">
              <Label>Istanza MSSQL</Label>
              <Input value={editDbForm.connection_string} onChange={e => setEditDbForm(f => ({ ...f, connection_string: e.target.value }))} />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1.5">
                <Label>Username (vuoto = invariato)</Label>
                <Input value={editDbForm.username} onChange={e => setEditDbForm(f => ({ ...f, username: e.target.value }))} placeholder="lascia vuoto" />
              </div>
              <div className="space-y-1.5">
                <Label>Password (vuoto = invariata)</Label>
                <Input type="password" value={editDbForm.password} onChange={e => setEditDbForm(f => ({ ...f, password: e.target.value }))} placeholder="lascia vuoto" />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditDb(null)}>Annulla</Button>
            <Button disabled={!editDbForm.name || !editDbForm.connection_string || editDbMutation.isPending} onClick={() => {
              if (editDb) editDbMutation.mutate({ id: editDb.id, ...editDbForm })
            }}>
              {editDbMutation.isPending ? "Salvataggio..." : "Salva"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Dialog>
  )
}

interface AgentCommand {
  id: string
  action: string
  status: "pending" | "running" | "done" | "failed"
  result: string | null
  created_at: string | null
  finished_at: string | null
}

const ACTION_LABELS: Record<string, string> = {
  healthcheck: "Diagnostica",
  collect_logs: "Log agente",
  test_db: "Test connessione DB",
  install_deps: "Installa dipendenze",
  restart_agent: "Riavvio agente",
  repair: "Riparazione",
  set_config: "Modifica config",
}

function AgentManageModal({ server, onClose }: { server: Server; onClose: () => void }) {
  const qc = useQueryClient()
  const [testDbId, setTestDbId] = useState("")
  const [pollInterval, setPollInterval] = useState("")
  const [logLevel, setLogLevel] = useState("")
  const [tempDir, setTempDir] = useState("")
  const [expanded, setExpanded] = useState<string | null>(null)

  const { data: commands = [] } = useQuery<AgentCommand[]>({
    queryKey: ["agent-commands", server.id],
    queryFn: () => api.get(`/servers/${server.id}/commands`).then(r => r.data),
    refetchInterval: 4000,
  })
  const { data: dbs = [] } = useQuery<DbInstance[]>({
    queryKey: ["databases", server.id],
    queryFn: () => api.get(`/servers/${server.id}/databases`).then(r => r.data),
  })

  const enqueue = useMutation({
    mutationFn: (body: { action: string; params?: any }) => api.post(`/servers/${server.id}/commands`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["agent-commands", server.id] }),
  })

  const isMysql = (server.engine ?? "mssql") === "mysql"

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Gestione agente — {server.name}</DialogTitle>
          <DialogDescription>
            I comandi vengono eseguiti dall'agente entro ~30s. Nessun accesso SSH richiesto.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="border rounded-lg divide-y">
            {[
              { action: "healthcheck", label: "Diagnostica", desc: "Mostra versione agente, sistema operativo, dipendenze installate (mysqldump/sqlcmd), spazio disco e configurazione.", btn: "Esegui", confirm: null, params: undefined as any },
              { action: "collect_logs", label: "Vedi log", desc: "Recupera le ultime righe del log dell'agente per la diagnostica, senza collegarti al server.", btn: "Recupera", confirm: null, params: undefined },
              { action: "install_deps", label: "Installa dipendenze", desc: isMysql ? "Installa sul server gli strumenti MySQL (mysqldump, client) se mancanti." : "Installa sul server gli strumenti SQL Server (sqlcmd) se mancanti.", btn: "Installa", confirm: null, params: { deps: [isMysql ? "mysql" : "mssql"] } },
              { action: "restart_agent", label: "Riavvia agente", desc: "Riavvia il servizio dell'agente sul server. Utile se sembra bloccato.", btn: "Riavvia", confirm: "Riavviare l'agente sul server?", params: undefined },
              { action: "repair", label: "Ripara agente", desc: "Ricrea i file di sistema dell'agente (servizi systemd, updater) e lo riavvia. Da usare se l'agente non risponde più ai comandi.", btn: "Ripara", confirm: "Eseguire la riparazione dell'agente?", params: undefined },
            ].map(a => (
              <div key={a.action} className="flex items-start justify-between gap-3 p-3">
                <div className="min-w-0">
                  <div className="text-sm font-medium">{a.label}</div>
                  <div className="text-[11px] text-muted-foreground/80">{a.desc}</div>
                </div>
                <Button size="sm" variant="outline" className="shrink-0" disabled={enqueue.isPending}
                  onClick={() => { if (!a.confirm || confirm(a.confirm)) enqueue.mutate({ action: a.action, params: a.params }) }}>
                  {a.btn}
                </Button>
              </div>
            ))}
          </div>

          <div className="border rounded-lg p-3 space-y-2">
            <Label className="text-xs font-semibold">Test connessione database</Label>
            <p className="text-[11px] text-muted-foreground/80">Verifica che l'agente riesca a connettersi al database selezionato con le credenziali salvate (senza fare un backup).</p>
            <div className="flex gap-2">
              <Select value={testDbId} onValueChange={setTestDbId}>
                <SelectTrigger className="flex-1"><SelectValue placeholder={dbs.length ? "Seleziona database..." : "Nessun DB registrato"} /></SelectTrigger>
                <SelectContent>
                  {dbs.map(d => <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>)}
                </SelectContent>
              </Select>
              <Button size="sm" disabled={!testDbId || enqueue.isPending} onClick={() => enqueue.mutate({ action: "test_db", params: { db_instance_id: testDbId } })}>Testa</Button>
            </div>
          </div>

          <div className="border rounded-lg p-3 space-y-2">
            <Label className="text-xs font-semibold">Modifica configurazione</Label>
            <p className="text-[11px] text-muted-foreground/80">Cambia i parametri dell'agente da remoto. Polling = ogni quanti secondi contatta la piattaforma; Log level = dettaglio dei log; Cartella temp = dove crea i file di backup prima dell'upload. L'agente si riavvia per applicare.</p>
            <div className="grid grid-cols-3 gap-2">
              <div>
                <Label className="text-[11px]">Polling (s)</Label>
                <Input placeholder="30" value={pollInterval} onChange={e => setPollInterval(e.target.value)} />
              </div>
              <div>
                <Label className="text-[11px]">Log level</Label>
                <Select value={logLevel} onValueChange={setLogLevel}>
                  <SelectTrigger><SelectValue placeholder="—" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="INFO">INFO</SelectItem>
                    <SelectItem value="DEBUG">DEBUG</SelectItem>
                    <SelectItem value="WARNING">WARNING</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-[11px]">Cartella temp</Label>
                <Input placeholder="/tmp/restorix" value={tempDir} onChange={e => setTempDir(e.target.value)} />
              </div>
            </div>
            <Button size="sm" variant="restorix" disabled={enqueue.isPending || (!pollInterval && !logLevel && !tempDir)} onClick={() => {
              const params: any = {}
              if (pollInterval) params.poll_interval_seconds = parseInt(pollInterval)
              if (logLevel) params.log_level = logLevel
              if (tempDir) params.temp_dir = tempDir
              enqueue.mutate({ action: "set_config", params })
            }}>Applica configurazione</Button>
          </div>

          <div>
            <Label className="text-xs font-semibold">Comandi recenti</Label>
            <div className="divide-y border rounded-lg mt-1 max-h-72 overflow-y-auto">
              {commands.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-4">Nessun comando</p>
              ) : commands.map(c => (
                <div key={c.id} className="p-2 text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium">{ACTION_LABELS[c.action] ?? c.action}</span>
                    <div className="flex items-center gap-2">
                      <Badge variant={c.status === "done" ? "success" : c.status === "failed" ? "destructive" : "warning"} className="text-[10px]">
                        {c.status === "done" ? "✓ Completato" : c.status === "failed" ? "✗ Fallito" : c.status === "running" ? "In corso" : "In attesa"}
                      </Badge>
                      {c.result && (
                        <button className="text-xs text-muted-foreground underline" onClick={() => setExpanded(expanded === c.id ? null : c.id)}>
                          {expanded === c.id ? "nascondi" : "output"}
                        </button>
                      )}
                    </div>
                  </div>
                  {expanded === c.id && c.result && (
                    <pre className="mt-2 text-[11px] bg-slate-900 text-slate-100 rounded p-2 overflow-x-auto whitespace-pre-wrap max-h-60">{c.result}</pre>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Chiudi</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default function Servers() {
  const qc = useQueryClient()
  const [showAdd, setShowAdd] = useState(false)
  const [showInstall, setShowInstall] = useState<Server | null>(null)
  const [showDbs, setShowDbs] = useState<Server | null>(null)
  const [showManage, setShowManage] = useState<Server | null>(null)
  const [form, setForm] = useState({ name: "", hostname: "", engine: "mssql" })
  const [error, setError] = useState("")

  const { data: servers = [], isLoading } = useQuery<Server[]>({
    queryKey: ["servers"],
    queryFn: () => api.get("/servers/").then(r => r.data),
    refetchInterval: 5000,
  })

  const updateAgentMutation = useMutation({
    mutationFn: (id: string) => api.post(`/servers/${id}/request-update`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["servers"] }),
  })

  const autoUpdateMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      api.patch(`/servers/${id}/auto-update`, { enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["servers"] }),
  })

  const updateBadge = (s: Server) => {
    const b = s.update_badge ?? "unknown"
    if (b === "updating") return <Badge variant="warning" className="text-[10px] px-1.5 py-0">🔵 In aggiornamento…</Badge>
    if (b === "failed") return <Badge variant="destructive" className="text-[10px] px-1.5 py-0">🔴 Update fallito</Badge>
    if (b === "available") return <Badge variant="warning" className="text-[10px] px-1.5 py-0">🟡 v{s.latest_version} disponibile</Badge>
    if (b === "up_to_date") return <Badge variant="success" className="text-[10px] px-1.5 py-0 bg-rx-accent/15 text-rx-accent border-rx-accent/30">🟢 Aggiornato</Badge>
    return null
  }

  const addMutation = useMutation({
    mutationFn: (data: typeof form) => api.post("/servers/", data),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["servers"] })
      setShowInstall(res.data)
      setShowAdd(false)
      setForm({ name: "", hostname: "", engine: "mssql" })
      setError("")
    },
    onError: () => setError("Errore durante la creazione del server"),
  })

  const rotateMutation = useMutation({
    mutationFn: (id: string) => api.post(`/servers/${id}/rotate-token`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["servers"] }),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/servers/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["servers"] }),
  })

  const [showEdit, setShowEdit] = useState<Server | null>(null)
  const [editForm, setEditForm] = useState({ name: "", hostname: "", engine: "mssql" })

  const editMutation = useMutation({
    mutationFn: ({ id, ...data }: { id: string; name: string; hostname: string; engine: string }) =>
      api.patch(`/servers/${id}`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["servers"] })
      setShowEdit(null)
    },
  })

  const installCmd = (token: string) =>
    "curl -sSL https://restorix.edminformatica.it/install.sh | bash -s -- --token=" + token

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Server</h1>
          <p className="text-muted-foreground text-sm mt-1">Gestisci i server con l&apos;agente Restorix</p>
        </div>
        <Button variant="restorix" onClick={() => setShowAdd(true)}>
          <Plus className="h-4 w-4 mr-2" /> Aggiungi Server
        </Button>
      </div>

      {isLoading ? (
        <div className="text-center py-12 text-muted-foreground">Caricamento...</div>
      ) : servers.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <ServerIcon className="h-12 w-12 text-muted-foreground/30 mb-4" />
            <p className="text-muted-foreground font-medium">Nessun server configurato</p>
            <p className="text-muted-foreground/70 text-sm mt-1">Aggiungi il tuo primo server per iniziare</p>
            <Button className="mt-4" onClick={() => setShowAdd(true)}>
              <Plus className="h-4 w-4 mr-2" /> Aggiungi Server
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4">
          {servers.map(server => (
            <Card key={server.id} className="hover:shadow-md transition-shadow">
              <CardContent className="p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="bg-primary/10 rounded-lg p-2 shrink-0">
                      <ServerIcon className="h-5 w-5 text-primary" />
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold">{server.name}</span>
                        <StatusBadge status={server.status} />
                        <Badge variant="secondary" className="text-xs">
                          {(server.engine ?? "mssql") === "mysql" ? "MySQL" : "MSSQL"}
                        </Badge>
                      </div>
                      <p className="text-sm text-muted-foreground">{server.hostname}</p>
                      {server.agent_version && (
                        <p className="text-xs text-muted-foreground/70 flex items-center gap-1.5 flex-wrap">
                          Agente v{server.agent_version}
                          {updateBadge(server)}
                          <button
                            type="button"
                            title={server.auto_update_enabled ? "Auto-update attivo — click per disattivare" : "Auto-update disattivo — click per attivare"}
                            onClick={() => autoUpdateMutation.mutate({ id: server.id, enabled: !server.auto_update_enabled })}
                            className={`text-[10px] px-1.5 py-0 rounded border ${server.auto_update_enabled ? "border-rx-accent/30 text-rx-accent" : "border-muted-foreground/30 text-muted-foreground"}`}
                          >
                            auto-update: {server.auto_update_enabled ? "ON" : "OFF"}
                          </button>
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <Button variant="outline" size="sm" onClick={() => setShowDbs(server)}>
                      <Database className="h-3.5 w-3.5 mr-1" /> Database
                    </Button>
                    <Button variant="outline" size="sm" title="Gestione agente da remoto" onClick={() => setShowManage(server)}>
                      <Wrench className="h-3.5 w-3.5 mr-1" /> Gestione
                    </Button>
                    <Button variant="ghost" size="icon" title="Modifica" onClick={() => {
                      setShowEdit(server)
                      setEditForm({ name: server.name, hostname: server.hostname, engine: server.engine ?? "mssql" })
                    }}>
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => setShowInstall(server)}>
                      Installa agente
                    </Button>
                    {server.agent_version && server.update_badge !== "up_to_date" && (
                      <Button
                        variant="outline"
                        size="sm"
                        title="Aggiorna l'agente all'ultima versione"
                        disabled={server.update_badge === "updating" || updateAgentMutation.isPending}
                        onClick={() => updateAgentMutation.mutate(server.id)}
                      >
                        <RefreshCw className={`h-3.5 w-3.5 mr-1 ${server.update_badge === "updating" ? "animate-spin" : ""}`} />
                        {server.update_badge === "updating" ? "In corso…" : "Aggiorna ora"}
                      </Button>
                    )}
                    <Button variant="ghost" size="icon" title="Rigenera token" disabled={rotateMutation.isPending} onClick={() => {
                      if (confirm("Rigenerare il token? L'agente attuale si disconnetterà e dovrai reinstallarlo col nuovo token.")) rotateMutation.mutate(server.id)
                    }}>
                      <RefreshCw className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="icon" title="Elimina" className="text-destructive hover:text-destructive" onClick={() => {
                      if (confirm("Eliminare " + server.name + "?")) deleteMutation.mutate(server.id)
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

      <Dialog open={showAdd} onOpenChange={setShowAdd}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Aggiungi Server</DialogTitle>
            <DialogDescription>Inserisci i dati del server da collegare</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label>Nome server</Label>
              <Input placeholder="es. Produzione DB" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
            </div>
            <div className="space-y-1.5">
              <Label>Hostname / IP</Label>
              <Input placeholder="es. 192.168.1.100 o db.azienda.it" value={form.hostname} onChange={e => setForm(f => ({ ...f, hostname: e.target.value }))} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="engine">Tipo database</Label>
              <Select
                value={form.engine ?? "mssql"}
                onValueChange={(v) => setForm((f) => ({ ...f, engine: v }))}
              >
                <SelectTrigger id="engine">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="mssql">SQL Server (MSSQL)</SelectItem>
                  <SelectItem value="mysql">MySQL / MariaDB</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {error && <p className="text-destructive text-sm">{error}</p>}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAdd(false)}>Annulla</Button>
            <Button variant="restorix" disabled={!form.name || !form.hostname || addMutation.isPending} onClick={() => addMutation.mutate(form)}>
              {addMutation.isPending ? "Creazione..." : "Crea Server"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!showInstall} onOpenChange={() => setShowInstall(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Installa Agente &mdash; {showInstall?.name}</DialogTitle>
            <DialogDescription>Esegui questo comando sul server Linux come root</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="bg-slate-900 rounded-lg p-4 flex items-start gap-3">
              <code className="text-green-400 text-sm flex-1 break-all font-mono">
                {showInstall ? installCmd(showInstall.agent_token) : ""}
              </code>
              {showInstall && <CopyButton text={installCmd(showInstall.agent_token)} />}
            </div>
            <div className="bg-muted/50 rounded-lg p-3 text-sm text-muted-foreground">
              <p className="font-medium mb-1">Il comando:</p>
              <ul className="space-y-1 list-disc list-inside">
                <li>Installa Python e le dipendenze necessarie</li>
                <li>Configura il servizio systemd <code className="bg-muted px-1 rounded">dbshield-agent</code></li>
                <li>Avvia automaticamente il monitoraggio</li>
              </ul>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Token agente (non condividere)</Label>
              <div className="flex items-center gap-2 bg-muted rounded p-2">
                <code className="text-xs flex-1 font-mono truncate">{showInstall?.agent_token}</code>
                {showInstall && <CopyButton text={showInstall.agent_token} />}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button onClick={() => setShowInstall(null)}>Chiudi</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {showDbs && <DatabasesModal server={showDbs} onClose={() => setShowDbs(null)} />}
      {showManage && <AgentManageModal server={showManage} onClose={() => setShowManage(null)} />}

      <Dialog open={!!showEdit} onOpenChange={() => setShowEdit(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Modifica Server</DialogTitle>
            <DialogDescription>Aggiorna i dati del server</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label>Nome server</Label>
              <Input value={editForm.name} onChange={e => setEditForm(f => ({ ...f, name: e.target.value }))} />
            </div>
            <div className="space-y-1.5">
              <Label>Hostname / IP</Label>
              <Input value={editForm.hostname} onChange={e => setEditForm(f => ({ ...f, hostname: e.target.value }))} />
            </div>
            <div className="space-y-2">
              <Label>Tipo database</Label>
              <Select
                value={editForm.engine ?? "mssql"}
                onValueChange={(v) => setEditForm((f: typeof editForm) => ({ ...f, engine: v }))}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="mssql">SQL Server (MSSQL)</SelectItem>
                  <SelectItem value="mysql">MySQL / MariaDB</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowEdit(null)}>Annulla</Button>
            <Button disabled={!editForm.name || !editForm.hostname || editMutation.isPending} onClick={() => {
              if (showEdit) editMutation.mutate({ id: showEdit.id, ...editForm })
            }}>
              {editMutation.isPending ? "Salvataggio..." : "Salva"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
