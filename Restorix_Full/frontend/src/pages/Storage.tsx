import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Plus, HardDrive, Trash2, TestTube, Pencil } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import api from "@/lib/api"

interface StorageDestination {
  id: string
  name: string
  storage_type: string
  last_tested_at: string | null
  last_test_ok: boolean | null
  is_active: boolean
}

const STORAGE_TYPES = [
  { value: "s3", label: "Amazon S3 / Compatibile" },
  { value: "sftp", label: "SFTP" },
  { value: "ftp", label: "FTP" },
  { value: "ftps", label: "FTPS" },
  { value: "gdrive", label: "Google Drive" },
  { value: "onedrive", label: "OneDrive" },
  { value: "nextcloud", label: "Nextcloud / WebDAV" },
]

const TYPE_ICONS: Record<string, string> = {
  s3: "S3", sftp: "SFTP", ftp: "FTP", ftps: "FTPS",
  gdrive: "GDrive", onedrive: "OneDrive", nextcloud: "NC", webdav: "WebDAV",
}

const CONFIG_FIELDS: Record<string, { key: string; label: string; type?: string; placeholder?: string }[]> = {
  s3: [
    { key: "bucket", label: "Nome bucket (solo il nome, NO URL)", placeholder: "es. my-backup-bucket" },
    { key: "region", label: "Region", placeholder: "es. eu-west-1, eu2, default" },
    { key: "access_key", label: "Access Key ID", placeholder: "AKIAIOSFODNN7EXAMPLE" },
    { key: "secret_key", label: "Secret Access Key", type: "password" },
    { key: "endpoint", label: "Endpoint (lascia vuoto per AWS, compila per MinIO/Contabo/Wasabi)", placeholder: "es. https://eu2.contabostorage.com" },
    { key: "prefix", label: "Prefisso (opzionale, cartella dentro il bucket)", placeholder: "dbshield/" },
  ],
  sftp: [
    { key: "host", label: "Host", placeholder: "backup.azienda.it" },
    { key: "port", label: "Porta", placeholder: "22" },
    { key: "username", label: "Username", placeholder: "backupuser" },
    { key: "password", label: "Password", type: "password" },
    { key: "path", label: "Percorso remoto", placeholder: "/backups/dbshield" },
  ],
  ftp: [
    { key: "host", label: "Host", placeholder: "ftp.azienda.it" },
    { key: "port", label: "Porta", placeholder: "21" },
    { key: "username", label: "Username", placeholder: "ftpuser" },
    { key: "password", label: "Password", type: "password" },
    { key: "path", label: "Percorso remoto", placeholder: "/backups" },
  ],
  ftps: [
    { key: "host", label: "Host", placeholder: "ftp.azienda.it" },
    { key: "port", label: "Porta", placeholder: "990" },
    { key: "username", label: "Username", placeholder: "ftpuser" },
    { key: "password", label: "Password", type: "password" },
    { key: "path", label: "Percorso remoto", placeholder: "/backups" },
  ],
  gdrive: [
    { key: "folder_id", label: "ID Cartella Google Drive" },
    { key: "credentials_json", label: "Service Account JSON", type: "password" },
  ],
  onedrive: [
    { key: "client_id", label: "Client ID App Azure" },
    { key: "client_secret", label: "Client Secret", type: "password" },
    { key: "folder_path", label: "Percorso cartella", placeholder: "/Backups/Restorix" },
  ],
  nextcloud: [
    { key: "url", label: "URL WebDAV" },
    { key: "username", label: "Username" },
    { key: "password", label: "Password", type: "password" },
  ],
  webdav: [
    { key: "url", label: "URL WebDAV" },
    { key: "username", label: "Username" },
    { key: "password", label: "Password", type: "password" },
  ],
}

export default function Storage() {
  const qc = useQueryClient()
  const [showAdd, setShowAdd] = useState(false)
  const [selectedType, setSelectedType] = useState("")
  const [formName, setFormName] = useState("")
  const [configValues, setConfigValues] = useState<Record<string, string>>({})
  const [error, setError] = useState("")
  const [testResults, setTestResults] = useState<Record<string, { ok: boolean; message: string }>>({})

  const { data: destinations = [], isLoading } = useQuery<StorageDestination[]>({
    queryKey: ["storage"],
    queryFn: () => api.get("/storage/").then(r => r.data),
  })

  const addMutation = useMutation({
    mutationFn: () => {
      // Auto-fix S3 bucket: se l'utente ha incollato un URL nel campo bucket, separalo
      const cfg = { ...configValues }
      if (selectedType === "s3" && cfg.bucket) {
        const m = cfg.bucket.match(/^https?:\/\/([^/]+)\/(.+)$/)
        if (m) {
          if (!cfg.endpoint) cfg.endpoint = `https://${m[1]}`
          cfg.bucket = m[2].replace(/\/$/, "")
        }
        // Verifica regex bucket
        if (!/^[a-zA-Z0-9.\-_]{1,255}$/.test(cfg.bucket)) {
          throw new Error("Nome bucket non valido: usa solo lettere, numeri, punti, trattini")
        }
      }
      return api.post("/storage/", {
        name: formName,
        storage_type: selectedType,
        config: cfg,
      })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["storage"] })
      setShowAdd(false)
      setFormName("")
      setSelectedType("")
      setConfigValues({})
      setError("")
    },
    onError: (err: any) => setError(err.message || err.response?.data?.detail || "Errore durante la creazione"),
  })

  const testMutation = useMutation({
    mutationFn: (id: string) => api.post(`/storage/${id}/test`).then(r => r.data),
    onSuccess: (data, id) => {
      setTestResults(prev => ({ ...prev, [id]: data }))
      qc.invalidateQueries({ queryKey: ["storage"] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/storage/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["storage"] }),
  })

  const [showEdit, setShowEdit] = useState<StorageDestination | null>(null)
  const [editConfigValues, setEditConfigValues] = useState<Record<string, string>>({})
  const [editName, setEditName] = useState("")

  const editMutation = useMutation({
    mutationFn: (data: { id: string; name: string; config: Record<string, string> }) => {
      const cfg = { ...data.config }
      if (showEdit?.storage_type === "s3" && cfg.bucket) {
        const m = cfg.bucket.match(/^https?:\/\/([^/]+)\/(.+)$/)
        if (m) {
          if (!cfg.endpoint) cfg.endpoint = `https://${m[1]}`
          cfg.bucket = m[2].replace(/\/$/, "")
        }
      }
      for (const k of ["secret_key", "password", "client_secret", "credentials_json"]) {
        if (cfg[k] === "") delete cfg[k]
      }
      return api.patch(`/storage/${data.id}`, { name: data.name, config: cfg })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["storage"] })
      setShowEdit(null)
    },
  })

  const openEdit = async (dest: StorageDestination) => {
    try {
      const res = await api.get(`/storage/${dest.id}/config`)
      setEditConfigValues(res.data)
      setEditName(dest.name)
      setShowEdit(dest)
    } catch {
      alert("Errore caricamento configurazione")
    }
  }

  const fields = selectedType ? CONFIG_FIELDS[selectedType] ?? [] : []

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Storage</h1>
          <p className="text-muted-foreground text-sm mt-1">Destinazioni dove inviare i backup</p>
        </div>
        <Button variant="restorix" onClick={() => setShowAdd(true)}>
          <Plus className="h-4 w-4 mr-2" /> Aggiungi Destinazione
        </Button>
      </div>

      {isLoading ? (
        <div className="text-center py-12 text-muted-foreground">Caricamento...</div>
      ) : destinations.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <HardDrive className="h-12 w-12 text-muted-foreground/30 mb-4" />
            <p className="text-muted-foreground font-medium">Nessuna destinazione configurata</p>
            <Button className="mt-4" onClick={() => setShowAdd(true)}>
              <Plus className="h-4 w-4 mr-2" /> Aggiungi Destinazione
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4">
          {destinations.map(dest => {
            const testResult = testResults[dest.id]
            return (
              <Card key={dest.id} className="hover:shadow-md transition-shadow">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between gap-4">
                    <div className="flex items-center gap-3 min-w-0">
                      <span className="text-sm font-mono bg-muted px-2 py-1 rounded">{TYPE_ICONS[dest.storage_type] ?? "?"}</span>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-semibold">{dest.name}</span>
                          <Badge variant="secondary">{dest.storage_type.toUpperCase()}</Badge>
                          {dest.last_test_ok === true && <Badge variant="success" className="bg-rx-accent/15 text-rx-accent border-rx-accent/30">Verificato</Badge>}
                          {dest.last_test_ok === false && <Badge variant="destructive">Errore</Badge>}
                        </div>
                        {testResult && (
                          <p className={`text-xs mt-0.5 ${testResult.ok ? "text-green-600" : "text-red-600"}`}>
                            {testResult.message}
                          </p>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <Button variant="outline" size="sm" disabled={testMutation.isPending} onClick={() => testMutation.mutate(dest.id)}>
                        <TestTube className="h-3.5 w-3.5 mr-1" /> Testa
                      </Button>
                      <Button variant="ghost" size="icon" title="Modifica" onClick={() => openEdit(dest)}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="icon" className="text-destructive hover:text-destructive" onClick={() => {
                        if (confirm("Eliminare " + dest.name + "?")) deleteMutation.mutate(dest.id)
                      }}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}

      <Dialog open={showAdd} onOpenChange={setShowAdd}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Aggiungi Destinazione Storage</DialogTitle>
            <DialogDescription>Configura una nuova destinazione per i backup</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label>Nome</Label>
              <Input placeholder="es. S3 Produzione" value={formName} onChange={e => setFormName(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Tipo di storage</Label>
              <Select value={selectedType} onValueChange={v => { setSelectedType(v); setConfigValues({}) }}>
                <SelectTrigger>
                  <SelectValue placeholder="Seleziona tipo..." />
                </SelectTrigger>
                <SelectContent>
                  {STORAGE_TYPES.map(t => (
                    <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {fields.map(f => (
              <div key={f.key} className="space-y-1.5">
                <Label>{f.label}</Label>
                <Input
                  type={f.type ?? "text"}
                  placeholder={f.placeholder}
                  value={configValues[f.key] ?? ""}
                  onChange={e => setConfigValues(prev => ({ ...prev, [f.key]: e.target.value }))}
                />
              </div>
            ))}
            {error && <p className="text-destructive text-sm">{error}</p>}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAdd(false)}>Annulla</Button>
            <Button variant="restorix" disabled={!formName || !selectedType || addMutation.isPending} onClick={() => addMutation.mutate()}>
              {addMutation.isPending ? "Salvataggio..." : "Salva"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!showEdit} onOpenChange={() => setShowEdit(null)}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Modifica {showEdit?.storage_type.toUpperCase()}</DialogTitle>
            <DialogDescription>Lascia vuoti i campi password per non modificarli</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label>Nome</Label>
              <Input value={editName} onChange={e => setEditName(e.target.value)} />
            </div>
            {showEdit && (CONFIG_FIELDS[showEdit.storage_type] ?? []).map(f => (
              <div key={f.key} className="space-y-1.5">
                <Label>{f.label}</Label>
                <Input
                  type={f.type ?? "text"}
                  placeholder={f.placeholder}
                  value={editConfigValues[f.key] ?? ""}
                  onChange={e => setEditConfigValues(prev => ({ ...prev, [f.key]: e.target.value }))}
                />
              </div>
            ))}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowEdit(null)}>Annulla</Button>
            <Button disabled={!editName || editMutation.isPending} onClick={() => {
              if (showEdit) editMutation.mutate({ id: showEdit.id, name: editName, config: editConfigValues })
            }}>
              {editMutation.isPending ? "Salvataggio..." : "Salva"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
