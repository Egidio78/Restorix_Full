import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Plus, Users as UsersIcon, Trash2, Copy, Check, ShieldCheck } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import api from "@/lib/api"

interface User {
  id: string
  email: string
  role: "superadmin" | "admin" | "operator" | "viewer"
  two_fa_enabled: boolean
  is_active: boolean
}

interface InviteResult {
  user: User
  temporary_password: string
}

const ROLE_LABELS: Record<string, string> = {
  superadmin: "Super Admin",
  admin: "Admin",
  operator: "Operatore",
  viewer: "Visualizzatore",
}

const ROLE_DESCRIPTIONS: Record<string, string> = {
  superadmin: "Accesso completo, gestione organizzazione",
  admin: "Gestione server, job, storage, utenti",
  operator: "Crea e modifica job di backup",
  viewer: "Solo lettura: dashboard, log",
}

function RoleBadge({ role }: { role: User["role"] }) {
  const variants: Record<string, "default" | "success" | "warning" | "secondary"> = {
    superadmin: "warning",
    admin: "default",
    operator: "success",
    viewer: "secondary",
  }
  return <Badge variant={variants[role] ?? "secondary"}>{ROLE_LABELS[role] ?? role}</Badge>
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      onClick={() => {
        navigator.clipboard.writeText(text)
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
      }}
      className="text-muted-foreground hover:text-foreground p-1 rounded"
    >
      {copied ? <Check className="h-3.5 w-3.5 text-green-500" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
  )
}

export default function Users() {
  const qc = useQueryClient()
  const [showInvite, setShowInvite] = useState(false)
  const [inviteForm, setInviteForm] = useState({ email: "", role: "viewer" as User["role"] })
  const [inviteResult, setInviteResult] = useState<InviteResult | null>(null)
  const [error, setError] = useState("")

  const { data: users = [], isLoading, error: queryError } = useQuery<User[]>({
    queryKey: ["users"],
    queryFn: () => api.get("/users/").then(r => r.data),
  })

  const inviteMutation = useMutation({
    mutationFn: (data: typeof inviteForm) => api.post("/users/invite", data).then(r => r.data),
    onSuccess: (data: InviteResult) => {
      qc.invalidateQueries({ queryKey: ["users"] })
      setInviteResult(data)
      setShowInvite(false)
      setInviteForm({ email: "", role: "viewer" })
      setError("")
    },
    onError: (err: any) => setError(err.response?.data?.detail ?? "Errore durante l'invito"),
  })

  const updateRoleMutation = useMutation({
    mutationFn: ({ id, role }: { id: string; role: string }) => api.patch(`/users/${id}`, { role }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/users/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  })

  if (queryError) {
    return (
      <div className="bg-destructive/10 border border-destructive/30 rounded-lg p-4 text-destructive">
        Non hai i permessi per visualizzare gli utenti
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Utenti & Ruoli</h1>
          <p className="text-muted-foreground text-sm mt-1">Gestisci gli utenti della tua organizzazione</p>
        </div>
        <Button variant="restorix" onClick={() => setShowInvite(true)}>
          <Plus className="h-4 w-4 mr-2" /> Invita Utente
        </Button>
      </div>

      {isLoading ? (
        <div className="text-center py-12 text-muted-foreground">Caricamento...</div>
      ) : (
        <Card>
          <CardContent className="p-0">
            <div className="divide-y">
              {users.map(user => (
                <div key={user.id} className="flex items-center justify-between p-4 hover:bg-muted/30 transition-colors">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="bg-primary/10 rounded-full p-2">
                      <UsersIcon className="h-4 w-4 text-primary" />
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium truncate">{user.email}</span>
                        <RoleBadge role={user.role} />
                        {!user.is_active && <Badge variant="secondary">Disattivato</Badge>}
                        {user.two_fa_enabled && (
                          <span title="2FA attivo" className="text-green-600">
                            <ShieldCheck className="h-4 w-4" />
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground">{ROLE_DESCRIPTIONS[user.role]}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Select value={user.role} onValueChange={(v) => updateRoleMutation.mutate({ id: user.id, role: v })}>
                      <SelectTrigger className="w-36 h-8 text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="superadmin">Super Admin</SelectItem>
                        <SelectItem value="admin">Admin</SelectItem>
                        <SelectItem value="operator">Operatore</SelectItem>
                        <SelectItem value="viewer">Visualizzatore</SelectItem>
                      </SelectContent>
                    </Select>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="text-destructive hover:text-destructive"
                      onClick={() => {
                        if (confirm(`Disattivare ${user.email}?`)) deleteMutation.mutate(user.id)
                      }}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <Dialog open={showInvite} onOpenChange={setShowInvite}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Invita Nuovo Utente</DialogTitle>
            <DialogDescription>Verra' generata una password temporanea da comunicare all'utente</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label>Email</Label>
              <Input type="email" placeholder="nome@azienda.com" value={inviteForm.email} onChange={e => setInviteForm(f => ({ ...f, email: e.target.value }))} />
            </div>
            <div className="space-y-1.5">
              <Label>Ruolo</Label>
              <Select value={inviteForm.role} onValueChange={v => setInviteForm(f => ({ ...f, role: v as User["role"] }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="viewer">Visualizzatore</SelectItem>
                  <SelectItem value="operator">Operatore</SelectItem>
                  <SelectItem value="admin">Admin</SelectItem>
                  <SelectItem value="superadmin">Super Admin</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">{ROLE_DESCRIPTIONS[inviteForm.role]}</p>
            </div>
            {error && <p className="text-destructive text-sm">{error}</p>}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowInvite(false)}>Annulla</Button>
            <Button variant="restorix" disabled={!inviteForm.email || inviteMutation.isPending} onClick={() => inviteMutation.mutate(inviteForm)}>
              {inviteMutation.isPending ? "Invio..." : "Invita"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!inviteResult} onOpenChange={() => setInviteResult(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Utente Creato</DialogTitle>
            <DialogDescription>Salva e comunica la password temporanea all'utente</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="bg-muted rounded-lg p-3">
              <Label className="text-xs text-muted-foreground">Email</Label>
              <div className="flex items-center justify-between mt-1">
                <code className="text-sm">{inviteResult?.user.email}</code>
                {inviteResult && <CopyButton text={inviteResult.user.email} />}
              </div>
            </div>
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
              <Label className="text-xs text-yellow-800 font-semibold">Password temporanea (mostrata solo ora)</Label>
              <div className="flex items-center justify-between mt-1">
                <code className="text-sm font-mono">{inviteResult?.temporary_password}</code>
                {inviteResult && <CopyButton text={inviteResult.temporary_password} />}
              </div>
              <p className="text-xs text-yellow-700 mt-2">L'utente dovra' cambiarla al primo accesso.</p>
            </div>
          </div>
          <DialogFooter>
            <Button onClick={() => setInviteResult(null)}>Chiudi</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
