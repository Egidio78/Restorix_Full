import { useState, useEffect } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { User, Building2, Mail, Webhook, Shield, Save, Plus, Trash2, FolderCheck } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import api from "@/lib/api"
import { useAuth } from "@/hooks/useAuth"
import { useTheme } from "@/hooks/useTheme"

interface OrgInfo {
  id: string
  name: string
  plan: string
  require_2fa: boolean
  user_count: number
}

interface NotificationChannel {
  id: string
  name: string
  channel_type: "email" | "webhook"
  on_success: boolean
  on_failure: boolean
  enabled: boolean
}

type TabKey = "profile" | "security" | "organization" | "notifications"

export default function Settings() {
  const { user } = useAuth()
  const [tab, setTab] = useState<TabKey>("profile")

  const tabs: { key: TabKey; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
    { key: "profile", label: "Profilo", icon: User },
    { key: "security", label: "Sicurezza", icon: Shield },
    { key: "organization", label: "Organizzazione", icon: Building2 },
    { key: "notifications", label: "Notifiche", icon: Mail },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Impostazioni</h1>
        <p className="text-muted-foreground text-sm mt-1">Gestisci profilo, sicurezza e configurazioni</p>
      </div>

      <div className="flex gap-2 border-b">
        {tabs.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === key ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <Icon className="h-4 w-4" />
            {label}
          </button>
        ))}
      </div>

      {tab === "profile" && <ProfileTab />}
      {tab === "security" && <SecurityTab user={user} />}
      {tab === "organization" && <OrganizationTab userRole={user?.role} />}
      {tab === "notifications" && <NotificationsTab />}
    </div>
  )
}

function ProfileTab() {
  const { user } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const [pwForm, setPwForm] = useState({ current_password: "", new_password: "", confirm: "" })
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null)

  const pwMutation = useMutation({
    mutationFn: (data: { current_password: string; new_password: string }) =>
      api.post("/users/me/change-password", data),
    onSuccess: () => {
      setMsg({ type: "success", text: "Password cambiata con successo" })
      setPwForm({ current_password: "", new_password: "", confirm: "" })
    },
    onError: (err: any) => setMsg({ type: "error", text: err.response?.data?.detail ?? "Errore" }),
  })

  const submit = () => {
    setMsg(null)
    if (pwForm.new_password !== pwForm.confirm) {
      setMsg({ type: "error", text: "Le password non coincidono" })
      return
    }
    if (pwForm.new_password.length < 8) {
      setMsg({ type: "error", text: "Minimo 8 caratteri" })
      return
    }
    pwMutation.mutate({ current_password: pwForm.current_password, new_password: pwForm.new_password })
  }

  return (
    <div className="grid gap-4 max-w-2xl">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Dati profilo</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-2 pb-4 border-b">
            <Label>Aspetto</Label>
            <div className="flex items-center gap-3">
              <span className="text-sm text-muted-foreground">Modalità:</span>
              <button
                type="button"
                onClick={toggleTheme}
                className="flex items-center gap-2 px-4 py-2 rounded-md bg-rx-bg-surface border border-rx-border hover:border-rx-accent transition-colors text-rx-ink"
              >
                <span>{theme === 'dark' ? '🌙' : '☀️'}</span>
                <span className="capitalize">{theme}</span>
              </button>
            </div>
            <p className="text-xs text-muted-foreground">
              Il tema è salvato localmente nel tuo browser.
            </p>
          </div>
          <div>
            <Label className="text-xs text-muted-foreground">Email</Label>
            <p className="font-medium">{user?.email}</p>
          </div>
          <div>
            <Label className="text-xs text-muted-foreground">Ruolo</Label>
            <p className="font-medium capitalize">{user?.role}</p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Cambia Password</CardTitle>
          <CardDescription>Minimo 8 caratteri</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-1.5">
            <Label>Password attuale</Label>
            <Input type="password" value={pwForm.current_password} onChange={e => setPwForm(f => ({ ...f, current_password: e.target.value }))} />
          </div>
          <div className="space-y-1.5">
            <Label>Nuova password</Label>
            <Input type="password" value={pwForm.new_password} onChange={e => setPwForm(f => ({ ...f, new_password: e.target.value }))} />
          </div>
          <div className="space-y-1.5">
            <Label>Conferma nuova password</Label>
            <Input type="password" value={pwForm.confirm} onChange={e => setPwForm(f => ({ ...f, confirm: e.target.value }))} />
          </div>
          {msg && (
            <div className={`text-sm rounded p-2 ${msg.type === "success" ? "bg-green-50 text-green-700" : "bg-destructive/10 text-destructive"}`}>
              {msg.text}
            </div>
          )}
          <Button variant="restorix" onClick={submit} disabled={!pwForm.current_password || !pwForm.new_password || pwMutation.isPending}>
            {pwMutation.isPending ? "Salvataggio..." : "Cambia Password"}
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}

function SecurityTab({ user }: { user: any }) {
  const qc = useQueryClient()
  const [showSetup, setShowSetup] = useState(false)
  const [setupData, setSetupData] = useState<{ secret: string; qr_code: string } | null>(null)
  const [verifyCode, setVerifyCode] = useState("")
  const [disablePassword, setDisablePassword] = useState("")
  const [showDisable, setShowDisable] = useState(false)
  const [backupCodes, setBackupCodes] = useState<string[] | null>(null)
  const [error, setError] = useState("")

  const setupMutation = useMutation({
    mutationFn: () => api.post("/auth/2fa/setup").then(r => r.data),
    onSuccess: (data) => { setSetupData(data); setShowSetup(true); setError("") },
  })

  const verifyMutation = useMutation({
    mutationFn: (code: string) => api.post("/auth/2fa/verify", { code }).then(r => r.data),
    onSuccess: (data) => {
      setBackupCodes(data.backup_codes)
      setShowSetup(false)
      setVerifyCode("")
      qc.invalidateQueries({ queryKey: ["me"] })
    },
    onError: (err: any) => setError(err.response?.data?.detail ?? "Codice errato"),
  })

  const disableMutation = useMutation({
    mutationFn: (password: string) => api.post("/auth/2fa/disable", { password }),
    onSuccess: () => {
      setShowDisable(false)
      setDisablePassword("")
      qc.invalidateQueries({ queryKey: ["me"] })
    },
    onError: (err: any) => setError(err.response?.data?.detail ?? "Password errata"),
  })

  return (
    <div className="grid gap-4 max-w-2xl">
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            Autenticazione a due fattori (2FA)
            {user?.two_fa_enabled && <Badge variant="success" className="bg-rx-accent/15 text-rx-accent border-rx-accent/30">Attivo</Badge>}
          </CardTitle>
          <CardDescription>
            Proteggi il tuo account con un codice TOTP da app di autenticazione
          </CardDescription>
        </CardHeader>
        <CardContent>
          {user?.two_fa_enabled ? (
            <Button variant="destructive" onClick={() => setShowDisable(true)}>
              Disabilita 2FA
            </Button>
          ) : (
            <Button variant="restorix" onClick={() => setupMutation.mutate()} disabled={setupMutation.isPending}>
              {setupMutation.isPending ? "Generazione..." : "Abilita 2FA"}
            </Button>
          )}
        </CardContent>
      </Card>

      <Dialog open={showSetup} onOpenChange={setShowSetup}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Configura 2FA</DialogTitle>
            <DialogDescription>Scansiona il QR code con la tua app di autenticazione</DialogDescription>
          </DialogHeader>
          {setupData && (
            <div className="space-y-4">
              <div className="bg-white p-4 rounded-lg flex justify-center">
                <img src={`data:image/png;base64,${setupData.qr_code}`} alt="QR Code 2FA" className="w-48 h-48" />
              </div>
              <div className="bg-muted rounded-lg p-3">
                <Label className="text-xs text-muted-foreground">Oppure inserisci manualmente</Label>
                <code className="text-xs font-mono block mt-1 break-all">{setupData.secret}</code>
              </div>
              <div className="space-y-1.5">
                <Label>Inserisci il codice generato dall'app</Label>
                <Input maxLength={6} placeholder="000000" value={verifyCode} onChange={e => setVerifyCode(e.target.value)} className="text-center text-2xl tracking-widest font-mono" />
              </div>
              {error && <p className="text-destructive text-sm">{error}</p>}
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowSetup(false)}>Annulla</Button>
            <Button disabled={verifyCode.length !== 6 || verifyMutation.isPending} onClick={() => verifyMutation.mutate(verifyCode)}>
              {verifyMutation.isPending ? "Verifica..." : "Verifica e Abilita"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={showDisable} onOpenChange={setShowDisable}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Disabilita 2FA</DialogTitle>
            <DialogDescription>Inserisci la tua password per confermare</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <Input type="password" placeholder="Password" value={disablePassword} onChange={e => setDisablePassword(e.target.value)} />
            {error && <p className="text-destructive text-sm">{error}</p>}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDisable(false)}>Annulla</Button>
            <Button variant="destructive" disabled={!disablePassword || disableMutation.isPending} onClick={() => disableMutation.mutate(disablePassword)}>
              Disabilita
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!backupCodes} onOpenChange={() => setBackupCodes(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>2FA Abilitato</DialogTitle>
            <DialogDescription>Conserva questi codici di backup in un posto sicuro</DialogDescription>
          </DialogHeader>
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
            <p className="text-xs text-yellow-800 mb-3">Mostrati solo ora. Usali se perdi l'accesso all'app.</p>
            <div className="grid grid-cols-2 gap-2">
              {backupCodes?.map((code, i) => (
                <code key={i} className="bg-white border rounded px-2 py-1 text-sm font-mono text-center text-slate-900 select-all">{code}</code>
              ))}
            </div>
          </div>
          <DialogFooter>
            <Button onClick={() => setBackupCodes(null)}>Ho salvato i codici</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

interface OrgSettings {
  id: string
  audit_retention_days: number
  schedule_cleanup_cron: string
  require_2fa: boolean
  restore_temp_dir: string
}

interface TempdirCheck {
  ok: boolean
  free_gb: number | null
  message: string
}

const CRON_PRESETS: { value: string; label: string }[] = [
  { value: "0 3 * * *", label: "Ogni giorno alle 03:00 (default)" },
  { value: "0 4 * * *", label: "Ogni giorno alle 04:00" },
  { value: "0 2 * * 0", label: "Ogni domenica alle 02:00" },
  { value: "custom", label: "Personalizzato..." },
]

function OrganizationTab({ userRole }: { userRole?: string }) {
  const qc = useQueryClient()
  const [name, setName] = useState("")
  const [require2fa, setRequire2fa] = useState(false)
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null)

  // Retention/schedule state
  const [retentionDays, setRetentionDays] = useState<number>(365)
  const [cronPreset, setCronPreset] = useState<string>("0 3 * * *")
  const [cronCustom, setCronCustom] = useState<string>("")
  const [settingsMsg, setSettingsMsg] = useState<{ type: "success" | "error"; text: string } | null>(null)

  // Restore tempdir state
  const [tempDirInput, setTempDirInput] = useState<string>("/var/lib/dbshield/restore-tmp")
  const [tempdirCheck, setTempdirCheck] = useState<TempdirCheck | null>(null)
  const [verifying, setVerifying] = useState(false)

  const { data: org, isLoading } = useQuery<OrgInfo>({
    queryKey: ["org-info"],
    queryFn: () => api.get("/users/org/info").then(r => r.data),
  })

  const { data: orgSettings } = useQuery<OrgSettings>({
    queryKey: ["org-settings"],
    queryFn: () => api.get("/organizations/me/settings").then(r => r.data),
  })

  useEffect(() => {
    if (org) {
      setName(org.name)
      setRequire2fa(org.require_2fa)
    }
  }, [org])

  useEffect(() => {
    if (orgSettings) {
      setRetentionDays(orgSettings.audit_retention_days)
      const cron = orgSettings.schedule_cleanup_cron
      const known = CRON_PRESETS.find(p => p.value === cron && p.value !== "custom")
      if (known) {
        setCronPreset(cron)
        setCronCustom("")
      } else {
        setCronPreset("custom")
        setCronCustom(cron)
      }
      if (orgSettings.restore_temp_dir) {
        setTempDirInput(orgSettings.restore_temp_dir)
      }
    }
  }, [orgSettings])

  const settingsMutation = useMutation({
    mutationFn: (data: { audit_retention_days?: number; schedule_cleanup_cron?: string; restore_temp_dir?: string }) =>
      api.patch("/organizations/me/settings", data).then(r => r.data),
    onSuccess: () => {
      setSettingsMsg({ type: "success", text: "Impostazioni salvate" })
      qc.invalidateQueries({ queryKey: ["org-settings"] })
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      const text = Array.isArray(detail)
        ? detail.map((d: any) => d.msg).join("; ")
        : (detail ?? "Errore salvataggio impostazioni")
      setSettingsMsg({ type: "error", text })
    },
  })

  const saveSettings = () => {
    setSettingsMsg(null)
    const cron = cronPreset === "custom" ? cronCustom.trim() : cronPreset
    if (!cron) {
      setSettingsMsg({ type: "error", text: "Espressione cron obbligatoria" })
      return
    }
    if (retentionDays < 90 || retentionDays > 3650) {
      setSettingsMsg({ type: "error", text: "La retention deve essere tra 90 e 3650 giorni" })
      return
    }
    const tempDir = tempDirInput.trim()
    if (tempDir && (!tempDir.startsWith("/") || tempDir.includes(".."))) {
      setSettingsMsg({ type: "error", text: "Cartella temporanea: path assoluto e senza '..'" })
      return
    }
    settingsMutation.mutate({
      audit_retention_days: retentionDays,
      schedule_cleanup_cron: cron,
      restore_temp_dir: tempDir || undefined,
    })
  }

  const handleVerifyTempdir = async () => {
    setVerifying(true)
    try {
      const r = await api.post<TempdirCheck>(
        "/organizations/me/settings/verify-tempdir",
        { path: tempDirInput }
      )
      setTempdirCheck(r.data)
    } catch (e: any) {
      const detail = e.response?.data?.detail
      const text = Array.isArray(detail)
        ? detail.map((d: any) => d.msg).join("; ")
        : (detail ?? e.message ?? "Errore verifica")
      setTempdirCheck({ ok: false, free_gb: null, message: text })
    } finally {
      setVerifying(false)
    }
  }

  const updateMutation = useMutation({
    mutationFn: (data: { name?: string; require_2fa?: boolean }) => api.patch("/users/org", data),
    onSuccess: () => {
      setMsg({ type: "success", text: "Organizzazione aggiornata" })
      qc.invalidateQueries({ queryKey: ["org-info"] })
    },
    onError: () => setMsg({ type: "error", text: "Errore aggiornamento" }),
  })

  if (isLoading) return <div className="text-center py-12 text-muted-foreground">Caricamento...</div>

  const canEdit = userRole === "superadmin" || userRole === "admin"

  return (
    <div className="grid gap-4 max-w-2xl">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Dati Organizzazione</CardTitle>
          <CardDescription>{org?.user_count} utenti - Piano: <Badge>{org?.plan}</Badge></CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-1.5">
            <Label>Nome organizzazione</Label>
            <Input value={name} onChange={e => setName(e.target.value)} disabled={!canEdit} />
          </div>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={require2fa} onChange={e => setRequire2fa(e.target.checked)} disabled={!canEdit} className="rounded" />
            <span className="text-sm">Richiedi 2FA per tutti gli utenti dell'organizzazione</span>
          </label>
          {msg && (
            <div className={`text-sm rounded p-2 ${msg.type === "success" ? "bg-green-50 text-green-700" : "bg-destructive/10 text-destructive"}`}>
              {msg.text}
            </div>
          )}
          {canEdit && (
            <Button variant="restorix" onClick={() => updateMutation.mutate({ name, require_2fa: require2fa })} disabled={updateMutation.isPending}>
              <Save className="h-4 w-4 mr-2" />
              {updateMutation.isPending ? "Salvataggio..." : "Salva Modifiche"}
            </Button>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Retention & Pulizia Audit</CardTitle>
          <CardDescription>
            Configura quanto a lungo conservare gli audit log e quando eseguire la pulizia automatica
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label>Giorni di retention audit</Label>
            <Input
              type="number"
              min={90}
              max={3650}
              value={retentionDays}
              onChange={e => setRetentionDays(Number(e.target.value))}
              disabled={!canEdit}
            />
            <p className="text-xs text-muted-foreground">Minimo 90 giorni, massimo 3650</p>
          </div>

          <div className="space-y-1.5">
            <Label>Schedulazione pulizia (cron)</Label>
            <Select value={cronPreset} onValueChange={setCronPreset} disabled={!canEdit}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {CRON_PRESETS.map(p => (
                  <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            {cronPreset === "custom" && (
              <Input
                placeholder="es. 30 2 * * *"
                value={cronCustom}
                onChange={e => setCronCustom(e.target.value)}
                disabled={!canEdit}
                className="font-mono"
              />
            )}
            <p className="text-xs text-muted-foreground">
              Formato: minuto ora giorno-mese mese giorno-settimana
            </p>
          </div>

          {/* Restore tempdir */}
          <div className="space-y-2 pt-2 border-t">
            <Label htmlFor="temp-dir">Cartella temporanea per restore / cifratura</Label>
            <div className="flex gap-2">
              <Input
                id="temp-dir"
                value={tempDirInput}
                onChange={(e) => {
                  setTempDirInput(e.target.value)
                  setTempdirCheck(null)
                }}
                placeholder="/var/lib/dbshield/restore-tmp"
                disabled={!canEdit}
                className="font-mono"
              />
              <Button
                type="button"
                variant="outline"
                onClick={handleVerifyTempdir}
                disabled={!canEdit || verifying || !tempDirInput}
              >
                <FolderCheck className="h-4 w-4 mr-2" />
                {verifying ? "Verifica..." : "Verifica cartella"}
              </Button>
            </div>
            {tempdirCheck && (
              <div className={`text-sm rounded p-2 ${tempdirCheck.ok ? "bg-green-50 text-green-700" : "bg-destructive/10 text-destructive"}`}>
                {tempdirCheck.ok ? "✓" : "✗"} {tempdirCheck.message}
              </div>
            )}
            <p className="text-xs text-muted-foreground">
              Cartella usata per file temporanei durante restore/cifratura. Per file enormi monta un disco
              esterno (es. <code>/mnt/usb-restore</code>) impostando <code>RESTORE_TEMP_HOST_PATH</code> in
              <code> .env</code> sul server, poi inserisci qui lo stesso path container-side.
            </p>
          </div>

          {settingsMsg && (
            <div className={`text-sm rounded p-2 ${settingsMsg.type === "success" ? "bg-green-50 text-green-700" : "bg-destructive/10 text-destructive"}`}>
              {settingsMsg.text}
            </div>
          )}

          {canEdit && (
            <Button variant="restorix" onClick={saveSettings} disabled={settingsMutation.isPending}>
              <Save className="h-4 w-4 mr-2" />
              {settingsMutation.isPending ? "Salvataggio..." : "Salva Retention"}
            </Button>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function NotificationsTab() {
  const qc = useQueryClient()
  const [showAdd, setShowAdd] = useState(false)
  const [type, setType] = useState<"email" | "webhook">("email")
  const [form, setForm] = useState<any>({ name: "", to: "", url: "", secret: "", on_success: true, on_failure: true })
  const [error, setError] = useState("")

  const { data: channels = [], isLoading } = useQuery<NotificationChannel[]>({
    queryKey: ["notifications"],
    queryFn: () => api.get("/notifications/").then(r => r.data),
  })

  const addMutation = useMutation({
    mutationFn: () => {
      const config = type === "email" ? { to: form.to } : { url: form.url, secret: form.secret }
      return api.post("/notifications/", {
        name: form.name,
        channel_type: type,
        config,
        on_success: form.on_success,
        on_failure: form.on_failure,
        enabled: true,
      })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notifications"] })
      setShowAdd(false)
      setForm({ name: "", to: "", url: "", secret: "", on_success: true, on_failure: true })
      setError("")
    },
    onError: () => setError("Errore durante la creazione"),
  })

  const toggleMutation = useMutation({
    mutationFn: (id: string) => api.patch(`/notifications/${id}/toggle`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/notifications/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  })

  return (
    <div className="grid gap-4 max-w-3xl">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">Canali di notifica per backup completati o falliti</p>
        <Button variant="restorix" size="sm" onClick={() => setShowAdd(true)}>
          <Plus className="h-4 w-4 mr-2" /> Aggiungi Canale
        </Button>
      </div>

      {isLoading ? (
        <div className="text-center py-8 text-muted-foreground">Caricamento...</div>
      ) : channels.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Mail className="h-10 w-10 text-muted-foreground/30 mb-3" />
            <p className="text-muted-foreground text-sm">Nessun canale configurato</p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <div className="divide-y">
              {channels.map(ch => (
                <div key={ch.id} className="flex items-center justify-between p-4">
                  <div className="flex items-center gap-3">
                    {ch.channel_type === "email" ? <Mail className="h-4 w-4 text-blue-500" /> : <Webhook className="h-4 w-4 text-purple-500" />}
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{ch.name}</span>
                        <Badge variant="secondary">{ch.channel_type}</Badge>
                        {ch.enabled ? <Badge variant="success" className="bg-rx-accent/15 text-rx-accent border-rx-accent/30">Attivo</Badge> : <Badge variant="secondary">Disabilitato</Badge>}
                      </div>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        Notifica: {ch.on_success && "successo"} {ch.on_failure && "fallimento"}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <Button variant="ghost" size="sm" onClick={() => toggleMutation.mutate(ch.id)}>
                      {ch.enabled ? "Disabilita" : "Abilita"}
                    </Button>
                    <Button variant="ghost" size="icon" className="text-destructive" onClick={() => {
                      if (confirm(`Eliminare "${ch.name}"?`)) deleteMutation.mutate(ch.id)
                    }}>
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <Dialog open={showAdd} onOpenChange={setShowAdd}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Aggiungi Canale Notifiche</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label>Nome</Label>
              <Input placeholder="es. Email Admin" value={form.name} onChange={e => setForm((f: any) => ({ ...f, name: e.target.value }))} />
            </div>
            <div className="space-y-1.5">
              <Label>Tipo</Label>
              <Select value={type} onValueChange={v => setType(v as any)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="email">Email (SMTP)</SelectItem>
                  <SelectItem value="webhook">Webhook (Slack, Teams, ecc.)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {type === "email" ? (
              <div className="space-y-1.5">
                <Label>Indirizzo destinatario</Label>
                <Input type="email" placeholder="admin@azienda.com" value={form.to} onChange={e => setForm((f: any) => ({ ...f, to: e.target.value }))} />
                <p className="text-xs text-muted-foreground">Usera' l'SMTP configurato nell'app</p>
              </div>
            ) : (
              <>
                <div className="space-y-1.5">
                  <Label>URL Webhook</Label>
                  <Input placeholder="https://hooks.slack.com/services/..." value={form.url} onChange={e => setForm((f: any) => ({ ...f, url: e.target.value }))} />
                </div>
                <div className="space-y-1.5">
                  <Label>Secret (opzionale, per firma HMAC)</Label>
                  <Input placeholder="signing secret" value={form.secret} onChange={e => setForm((f: any) => ({ ...f, secret: e.target.value }))} />
                </div>
              </>
            )}
            <div className="flex gap-4">
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input type="checkbox" checked={form.on_success} onChange={e => setForm((f: any) => ({ ...f, on_success: e.target.checked }))} className="rounded" />
                Notifica successo
              </label>
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input type="checkbox" checked={form.on_failure} onChange={e => setForm((f: any) => ({ ...f, on_failure: e.target.checked }))} className="rounded" />
                Notifica fallimento
              </label>
            </div>
            {error && <p className="text-destructive text-sm">{error}</p>}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAdd(false)}>Annulla</Button>
            <Button onClick={() => addMutation.mutate()} disabled={!form.name || addMutation.isPending}>
              {addMutation.isPending ? "Salvataggio..." : "Salva"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
