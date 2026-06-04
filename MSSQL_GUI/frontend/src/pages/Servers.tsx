import { useEffect, useRef, useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Plus, Server as ServerIcon, RefreshCw, Trash2, Copy, Check, Database, Pencil, Download } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog"
import api from "@/lib/api"
import { getErrorMessage } from "@/lib/errors"

const AGENT_LATEST_FALLBACK = "1.4.1"

function getLatestAgentVersion(): string {
  const cfg = typeof window !== "undefined" ? window.__RESTORIX_CONFIG__ : undefined
  return (cfg as unknown as { latest_agent_version?: string })?.latest_agent_version || AGENT_LATEST_FALLBACK
}

function buildInstallCommand(token: string): string {
  const cfg = typeof window !== "undefined" ? window.__RESTORIX_CONFIG__ : undefined
  const base = (cfg?.agent_endpoint || cfg?.api_url || (typeof window !== "undefined" ? window.location.origin : "")).replace(/\/$/, "")
  return `curl -sSL ${base}/install.sh | sudo bash -s -- --token=${token}`
}

type UpdateStatus = "success" | "failed" | "in_progress" | "rolled_back" | null

interface Server {
  id: string
  name: string
  hostname: string
  agent_token: string
  agent_version: string | null
  status: "never_connected" | "online" | "offline"
  is_active: boolean
  auto_update?: boolean
  update_pending?: boolean
  last_update_at?: string | null
  last_update_status?: UpdateStatus
  last_update_error?: string | null
  last_update_from_version?: string | null
  last_update_to_version?: string | null
}

function UpdateStatusBadge({ server, latestVersion }: { server: Server; latestVersion: string }) {
  if (server.last_update_status === "in_progress") {
    return <Badge className="bg-blue-500/15 text-blue-500 border-blue-500/30">In aggiornamento...</Badge>
  }
  if (server.last_update_status === "failed") {
    return (
      <span title={server.last_update_error ?? ""}>
        <Badge className="bg-red-500/15 text-red-500 border-red-500/30">
          Update fallito
        </Badge>
      </span>
    )
  }
  if (server.agent_version && server.agent_version === latestVersion) {
    return <Badge className="bg-emerald-500/15 text-emerald-500 border-emerald-500/30">Aggiornato</Badge>
  }
  if (server.agent_version) {
    return (
      <Badge className="bg-amber-500/15 text-amber-500 border-amber-500/30">
        Disponibile {latestVersion}
      </Badge>
    )
  }
  return <Badge variant="secondary">Sconosciuto</Badge>
}

function AgentUpdatePanel({
  server,
  latestVersion,
  onRequestUpdate,
  onToggleAutoUpdate,
  isRequestingUpdate,
}: {
  server: Server
  latestVersion: string
  onRequestUpdate: (id: string) => void
  onToggleAutoUpdate: (args: { serverId: string; enabled: boolean }) => void
  isRequestingUpdate: boolean
}) {
  const inProgress = server.last_update_status === "in_progress"
  const upToDate = !!server.agent_version && server.agent_version === latestVersion
  const disabled = inProgress || !!server.update_pending || upToDate || isRequestingUpdate

  const tooltip = [
    server.last_update_at ? `Ultimo update: ${new Date(server.last_update_at).toLocaleString()}` : null,
    server.last_update_status === "failed" && server.last_update_error
      ? `Errore: ${server.last_update_error}`
      : null,
    server.last_update_from_version && server.last_update_to_version
      ? `Da v${server.last_update_from_version} → v${server.last_update_to_version}`
      : null,
  ]
    .filter(Boolean)
    .join("\n")

  return (
    <div className="flex flex-col items-end gap-1.5 min-w-[180px]" title={tooltip || undefined}>
      <div className="flex items-center gap-2">
        <span className="font-mono text-xs text-muted-foreground">v{server.agent_version ?? "—"}</span>
        <UpdateStatusBadge server={server} latestVersion={latestVersion} />
      </div>
      <div className="flex items-center gap-2">
        <Button
          size="sm"
          variant="outline"
          disabled={disabled}
          onClick={() => onRequestUpdate(server.id)}
          title={tooltip || "Richiedi aggiornamento agente"}
        >
          <Download className="h-3 w-3 mr-1" />
          {server.update_pending ? "In coda..." : inProgress ? "Aggiornamento..." : "Aggiorna ora"}
        </Button>
        <label className="flex items-center gap-1.5 text-xs text-muted-foreground cursor-pointer select-none">
          <input
            type="checkbox"
            checked={!!server.auto_update}
            onChange={(e) =>
              onToggleAutoUpdate({ serverId: server.id, enabled: e.target.checked })
            }
            className="rounded"
          />
          Auto-update
        </label>
      </div>
    </div>
  )
}

interface DbInstance {
  id: string
  server_id: string
  name: string
  mssql_instance: string
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
  const [form, setForm] = useState({ name: "", mssql_instance: "localhost", username: "", password: "" })
  const [error, setError] = useState("")

  const [showDiscover, setShowDiscover] = useState(false)
  const [discoverForm, setDiscoverForm] = useState({ mssql_instance: "localhost", username: "sa", password: "" })
  const [discovering, setDiscovering] = useState(false)
  const [discovered, setDiscovered] = useState<string[] | null>(null)
  const [discoverError, setDiscoverError] = useState("")
  const [selectedDbs, setSelectedDbs] = useState<Set<string>>(new Set())

  // Discovery polling cancel flag — set to true on unmount to stop the recursive setTimeout.
  const cancelledRef = useRef(false)
  useEffect(() => {
    cancelledRef.current = false
    return () => { cancelledRef.current = true }
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
      setForm({ name: "", mssql_instance: "localhost", username: "", password: "" })
      setError("")
    },
    onError: () => setError("Errore durante l'aggiunta del database"),
  })

  const deleteMutation = useMutation({
    mutationFn: (dbId: string) => api.delete(`/servers/${server.id}/databases/${dbId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["databases", server.id] }),
  })

  const [editDb, setEditDb] = useState<DbInstance | null>(null)
  const [editDbForm, setEditDbForm] = useState({ name: "", mssql_instance: "", username: "", password: "" })

  const editDbMutation = useMutation({
    mutationFn: ({ id, ...data }: { id: string; name: string; mssql_instance: string; username: string; password: string }) =>
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
        if (cancelledRef.current) return
        if (Date.now() - startedAt > 90_000) {
          setDiscoverError("Timeout: l'agente non ha risposto entro 90 secondi")
          setDiscovering(false)
          return
        }
        try {
          const res = await api.get(`/servers/${server.id}/discovery`)
          if (cancelledRef.current) return
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
        if (!cancelledRef.current) setTimeout(poll, 2000)
      }
      setTimeout(poll, 2000)
    } catch {
      setDiscoverError("Errore avvio discovery")
      setDiscovering(false)
    }
  }

  const registerSelected = async () => {
    const results = await Promise.allSettled(
      Array.from(selectedDbs).map(dbName =>
        api.post(`/servers/${server.id}/databases`, {
          name: dbName,
          mssql_instance: discoverForm.mssql_instance,
          username: discoverForm.username,
          password: discoverForm.password,
        })
      )
    )
    qc.invalidateQueries({ queryKey: ["databases", server.id] })
    const failed = results.filter(r => r.status === "rejected").length
    if (failed > 0) {
      setError(`${failed} database non registrati. Ricontrolla la lista.`)
      return
    }
    setShowDiscover(false)
    setDiscovered(null)
    setSelectedDbs(new Set())
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
          <DialogDescription>Registra i database MSSQL disponibili su questo server. Click sulla X o sul pulsante in basso per chiudere — non si chiude più cliccando fuori dalla finestra.</DialogDescription>
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
                    <p className="text-xs text-muted-foreground mt-0.5 ml-6">Istanza: {db.mssql_instance}</p>
                  </div>
                  <div className="flex items-center gap-1">
                    <Button variant="ghost" size="icon" title="Modifica" onClick={() => {
                      setEditDb(db)
                      setEditDbForm({ name: db.name, mssql_instance: db.mssql_instance, username: "", password: "" })
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
                  <p className="text-xs text-muted-foreground">L'agente eseguirà <code className="bg-muted px-1 rounded">SELECT name FROM sys.databases</code> e mostrerà la lista.</p>
                  <div className="space-y-1.5">
                    <Label>Istanza MSSQL</Label>
                    <Input value={discoverForm.mssql_instance} onChange={e => setDiscoverForm(f => ({ ...f, mssql_instance: e.target.value }))} placeholder="localhost o hostname\istanza" />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="space-y-1.5">
                      <Label>Username (sa o lascia vuoto per Win auth)</Label>
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
                    <Button size="sm" onClick={startDiscover} disabled={!discoverForm.mssql_instance}>
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
                <Label>Istanza MSSQL</Label>
                <Input placeholder="es. localhost, 192.168.1.10\SQLEXPRESS" value={form.mssql_instance} onChange={e => setForm(f => ({ ...f, mssql_instance: e.target.value }))} />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1.5">
                  <Label>Username</Label>
                  <Input placeholder="sa o vuoto per Win auth" value={form.username} onChange={e => setForm(f => ({ ...f, username: e.target.value }))} />
                </div>
                <div className="space-y-1.5">
                  <Label>Password</Label>
                  <Input type="password" placeholder="••••••••" value={form.password} onChange={e => setForm(f => ({ ...f, password: e.target.value }))} />
                </div>
              </div>
              {error && <p className="text-destructive text-sm">{error}</p>}
              <div className="flex justify-end gap-2">
                <Button variant="outline" size="sm" onClick={() => { setShowAdd(false); setError("") }}>Annulla</Button>
                <Button size="sm" disabled={!form.name || !form.mssql_instance || addMutation.isPending} onClick={() => addMutation.mutate(form)}>
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
              <Input value={editDbForm.mssql_instance} onChange={e => setEditDbForm(f => ({ ...f, mssql_instance: e.target.value }))} />
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
            <Button disabled={!editDbForm.name || !editDbForm.mssql_instance || editDbMutation.isPending} onClick={() => {
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

export default function Servers() {
  const qc = useQueryClient()
  const [showAdd, setShowAdd] = useState(false)
  const [showInstall, setShowInstall] = useState<Server | null>(null)
  const [showDbs, setShowDbs] = useState<Server | null>(null)
  const [form, setForm] = useState({ name: "", hostname: "" })
  const [error, setError] = useState("")

  const { data: servers = [], isLoading } = useQuery<Server[]>({
    queryKey: ["servers"],
    queryFn: () => api.get("/servers/").then(r => r.data),
    refetchInterval: (query) => {
      const data = query.state.data as Server[] | undefined
      const anyInProgress = data?.some(
        s => s.last_update_status === "in_progress" || s.update_pending
      )
      return anyInProgress ? 5000 : 30000
    },
  })

  const latestVersion = getLatestAgentVersion()

  const requestUpdateMutation = useMutation({
    mutationFn: (serverId: string) =>
      api.post(`/servers/${serverId}/request-update`).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["servers"] })
    },
    onError: (e: unknown) => alert(getErrorMessage(e)),
  })

  const toggleAutoUpdateMutation = useMutation({
    mutationFn: ({ serverId, enabled }: { serverId: string; enabled: boolean }) =>
      api.patch(`/servers/${serverId}/auto-update`, { enabled }).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["servers"] }),
    onError: (e: unknown) => alert(getErrorMessage(e)),
  })

  const addMutation = useMutation({
    mutationFn: (data: typeof form) => api.post("/servers/", data),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["servers"] })
      setShowInstall(res.data)
      setShowAdd(false)
      setForm({ name: "", hostname: "" })
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
  const [editForm, setEditForm] = useState({ name: "", hostname: "" })

  const editMutation = useMutation({
    mutationFn: ({ id, ...data }: { id: string; name: string; hostname: string }) =>
      api.patch(`/servers/${id}`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["servers"] })
      setShowEdit(null)
    },
  })

  const installCmd = (token: string) => buildInstallCommand(token)

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
                      </div>
                      <p className="text-sm text-muted-foreground">{server.hostname}</p>
                    </div>
                  </div>
                  <AgentUpdatePanel
                    server={server}
                    latestVersion={latestVersion}
                    onRequestUpdate={(id) => requestUpdateMutation.mutate(id)}
                    onToggleAutoUpdate={(args) => toggleAutoUpdateMutation.mutate(args)}
                    isRequestingUpdate={requestUpdateMutation.isPending}
                  />
                  <div className="flex items-center gap-2 shrink-0">
                    <Button variant="outline" size="sm" onClick={() => setShowDbs(server)}>
                      <Database className="h-3.5 w-3.5 mr-1" /> Database
                    </Button>
                    <Button variant="ghost" size="icon" title="Modifica" onClick={() => {
                      setShowEdit(server)
                      setEditForm({ name: server.name, hostname: server.hostname })
                    }}>
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => setShowInstall(server)}>
                      Installa agente
                    </Button>
                    <Button variant="ghost" size="icon" title="Rigenera token" onClick={() => rotateMutation.mutate(server.id)}>
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
