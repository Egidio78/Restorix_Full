import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Download, Send, ArrowRightLeft, Trash2, Folder, ChevronDown, ChevronRight } from 'lucide-react';

import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';

import api from '@/lib/api';
import {
  RestoreHubSummary, TempFolderListResponse,
  formatBytes, formatDuration, formatCountdown, formatRelative, formatVelocity,
} from '@/lib/restore-hub';

interface BackupRun {
  id: string;
  job_id: string;
  job_name: string | null;
  status: string;
  size_bytes: number | null;
  file_path: string | null;
  started_at: string | null;
  finished_at: string | null;
  server_name: string | null;
  storage_name: string | null;
  storage_id?: string | null;
  backup_type: 'mssql' | 'folder' | null;
  database_name: string | null;
  folder_path: string | null;
  velocity_mbps: number | null;
  retention_purged: boolean;
  encryption_enabled?: boolean;
}

const apiBase = (import.meta as any).env?.VITE_API_BASE_URL ?? '/api/v1';

export default function RestoreHubPage() {
  // Summary fetch
  const { data: summary } = useQuery<RestoreHubSummary>({
    queryKey: ['restore-hub-summary'],
    queryFn: () => api.get<RestoreHubSummary>('/restore-hub/summary').then(r => r.data),
    refetchInterval: 30_000,
  });

  // Live countdown
  const [nowMs, setNowMs] = useState(Date.now());
  useEffect(() => {
    const id = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  const secondsUntilNext = useMemo(() => {
    if (!summary?.next_backup) return null;
    const target = new Date(summary.next_backup.next_fire_at).getTime();
    return Math.max(0, Math.floor((target - nowMs) / 1000));
  }, [summary, nowMs]);

  // Filters
  const [filters, setFilters] = useState({ q: '', server_id: '', storage_id: '' });

  // Runs list
  const { data: runs = [] } = useQuery<BackupRun[]>({
    queryKey: ['restore-hub-runs', filters],
    queryFn: async () => {
      const params: any = { status: 'success', limit: 200 };
      if (filters.server_id) params.server_id = filters.server_id;
      if (filters.storage_id) params.storage_id = filters.storage_id;
      const r = await api.get<BackupRun[]>('/runs/', { params });
      return r.data.filter(run => !run.retention_purged && (!filters.q ||
        (run.file_path ?? '').toLowerCase().includes(filters.q.toLowerCase()) ||
        (run.job_name ?? '').toLowerCase().includes(filters.q.toLowerCase()) ||
        (run.database_name ?? '').toLowerCase().includes(filters.q.toLowerCase())));
    },
  });

  // Filter dropdowns data
  const { data: servers = [] } = useQuery<any[]>({
    queryKey: ['servers-for-rh'], queryFn: () => api.get('/servers/').then(r => r.data),
  });
  const { data: storages = [] } = useQuery<any[]>({
    queryKey: ['storage-for-rh'], queryFn: () => api.get('/storage/').then(r => r.data),
  });

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-3xl font-extrabold tracking-tight text-rx-ink">Restore Hub</h1>
        <p className="text-sm text-rx-ink-faint mt-1">
          Tutti i backup pronti per il restore — scarica, invia al server o sposta tra storage
        </p>
      </div>

      {/* KPI Strip */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-5">
          <div className="text-xs uppercase tracking-wider text-rx-ink-faint font-semibold mb-2">Backup totali</div>
          <div className="text-3xl font-extrabold bg-gradient-to-r from-rx-accent to-rx-accent-bright bg-clip-text text-transparent leading-none">
            {summary?.total_backups ?? '—'}
          </div>
          <div className="text-xs text-rx-ink-faint mt-2">{formatBytes(summary?.total_size_bytes ?? 0)} complessivi</div>
        </Card>
        <Card className="p-5">
          <div className="text-xs uppercase tracking-wider text-rx-ink-faint font-semibold mb-2">Success rate (30g)</div>
          <div className="text-3xl font-extrabold bg-gradient-to-r from-rx-accent to-rx-accent-bright bg-clip-text text-transparent leading-none">
            {summary?.success_rate_30d != null ? `${summary.success_rate_30d}%` : '—'}
          </div>
          <div className="text-xs text-rx-ink-faint mt-2">
            {summary?.success_count_30d ?? 0} OK / {(summary?.success_count_30d ?? 0) + (summary?.fail_count_30d ?? 0)} totali
          </div>
        </Card>
        <Card className="p-5">
          <div className="text-xs uppercase tracking-wider text-rx-ink-faint font-semibold mb-2">Ultimo backup</div>
          <div className="text-3xl font-extrabold bg-gradient-to-r from-rx-accent to-rx-accent-bright bg-clip-text text-transparent leading-none">
            {summary?.last_backup ? formatRelative(summary.last_backup.finished_at) : '—'}
          </div>
          <div className="text-xs text-rx-ink-faint mt-2">
            {summary?.last_backup ? `${summary.last_backup.server_name} → ${summary.last_backup.storage_name}` : 'Nessun backup ancora'}
          </div>
        </Card>
        <Card className="p-5 border-amber-500/30">
          <div className="text-xs uppercase tracking-wider text-rx-ink-faint font-semibold mb-2">Prossimo backup</div>
          <div className="text-2xl font-extrabold font-mono bg-gradient-to-r from-amber-400 to-amber-500 bg-clip-text text-transparent leading-none">
            {secondsUntilNext != null ? formatCountdown(secondsUntilNext) : '—'}
          </div>
          <div className="text-xs text-rx-ink-faint mt-2">
            {summary?.next_backup ? `${summary.next_backup.job_name} (cron ${summary.next_backup.schedule_cron})` : 'Nessun job attivo'}
          </div>
        </Card>
      </div>

      {/* Temp Folders Section */}
      <TempFoldersSection />

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <Input
          placeholder="🔍 Cerca per nome, database o job..."
          value={filters.q}
          onChange={e => setFilters(f => ({ ...f, q: e.target.value }))}
          className="max-w-sm"
        />
        <Select value={filters.server_id || 'all'} onValueChange={v => setFilters(f => ({ ...f, server_id: v === 'all' ? '' : v }))}>
          <SelectTrigger className="w-[180px]"><SelectValue placeholder="Server" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tutti i server</SelectItem>
            {servers.map((s: any) => <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={filters.storage_id || 'all'} onValueChange={v => setFilters(f => ({ ...f, storage_id: v === 'all' ? '' : v }))}>
          <SelectTrigger className="w-[180px]"><SelectValue placeholder="Storage" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tutti gli storage</SelectItem>
            {storages.map((s: any) => <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      {/* Cards list */}
      <div className="space-y-3">
        {runs.length === 0 && (
          <Card className="p-8 text-center text-rx-ink-faint">Nessun backup disponibile</Card>
        )}
        {runs.map(run => <BackupCard key={run.id} run={run} />)}
      </div>
    </div>
  );
}

function BackupCard({ run }: { run: BackupRun }) {
  const isFolder = run.backup_type === 'folder';
  const duration = run.started_at && run.finished_at
    ? (new Date(run.finished_at).getTime() - new Date(run.started_at).getTime()) / 1000
    : 0;

  const [sendModal, setSendModal] = useState(false);
  const [sendDecrypt, setSendDecrypt] = useState(false);
  const [sending, setSending] = useState(false);
  const [sendResult, setSendResult] = useState<null | { target_path: string; bytes: number; duration_seconds: number; decrypted: boolean }>(null);

  const [forwardModal, setForwardModal] = useState(false);
  const [forwardTargetId, setForwardTargetId] = useState<string>('');
  const [forwardMode, setForwardMode] = useState<'copy' | 'move'>('copy');
  const [forwarding, setForwarding] = useState(false);

  const { data: allStorages = [] } = useQuery<any[]>({
    queryKey: ['storage-for-forward'],
    queryFn: () => api.get('/storage/').then(r => r.data),
  });
  const availableTargets = allStorages.filter((s: any) => s.id !== run.storage_id);

  const handleDownload = () => {
    window.location.href = `${apiBase}/runs/${run.id}/download?decrypt=false`;
  };
  const handleSendToServer = () => {
    setSendDecrypt(false);
    setSendResult(null);
    setSendModal(true);
  };
  const confirmSend = async () => {
    setSending(true);
    try {
      const r = await api.post(`/runs/${run.id}/send-to-temp`, null, {
        params: { decrypt: sendDecrypt },
      });
      setSendResult(r.data);
    } catch (e: any) {
      alert(`Errore: ${e?.response?.data?.detail ?? e.message}`);
    } finally {
      setSending(false);
    }
  };
  const copyPath = (text: string) => {
    navigator.clipboard?.writeText(text).then(() => alert('Path copiato negli appunti'));
  };
  const handleForward = () => {
    setForwardTargetId('');
    setForwardMode('copy');
    setForwardModal(true);
  };

  const confirmForward = async () => {
    if (!forwardTargetId) {
      alert('Seleziona uno storage di destinazione');
      return;
    }
    setForwarding(true);
    try {
      const r = await api.post(`/runs/${run.id}/forward`, {
        target_storage_id: forwardTargetId,
        mode: forwardMode,
      });
      alert(`✅ Operazione avviata\n\nTask ID: ${r.data.task_id}\nShadow run: ${r.data.shadow_run_id}\n\nIl trasferimento prosegue in background; ricarica la lista tra qualche minuto.`);
      setForwardModal(false);
    } catch (e: any) {
      alert(`Errore: ${e?.response?.data?.detail ?? e.message}`);
    } finally {
      setForwarding(false);
    }
  };

  return (
    <>
      <Card className="p-5 hover:border-rx-accent/40 transition-colors">
        <div className="flex items-center gap-4">
          <div className={`h-12 w-12 rounded-xl flex items-center justify-center font-bold text-rx-bg shadow-rx-glow ${
            isFolder ? 'bg-gradient-to-br from-amber-400 to-amber-500' : 'bg-gradient-to-br from-rx-accent to-rx-accent-bright'
          }`}>
            {isFolder ? 'DIR' : 'DB'}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2">
              <span className="font-bold text-rx-ink truncate">{run.file_path ? run.file_path.split('/').pop() : '—'}</span>
              <Badge variant={isFolder ? 'secondary' : 'default'} className="text-[10px]">
                {isFolder ? 'CARTELLA' : 'MSSQL'}
              </Badge>
              <span className="h-2 w-2 rounded-full bg-rx-accent shadow-[0_0_6px_#34d399]" title="Success" />
            </div>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-xs">
              <MetaItem label="Server" value={run.server_name ?? '—'} />
              <MetaItem label="Storage" value={run.storage_name ?? '—'} />
              <MetaItem label="Orario" value={run.finished_at ? new Date(run.finished_at).toLocaleString('it-IT', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—'} />
              <MetaItem label="Durata" value={duration > 0 ? formatDuration(duration) : '—'} mono />
              <MetaItem label="Velocità" value={formatVelocity(run.velocity_mbps)} mono accent />
            </div>
          </div>
          <div className="flex gap-2">
            <Button variant="restorix" size="sm" title="Scarica .bak" onClick={handleDownload}><Download className="h-4 w-4" /></Button>
            <Button variant="outline" size="sm" title="Invia al server" onClick={handleSendToServer}><Send className="h-4 w-4" /></Button>
            <Button variant="outline" size="sm" title="Copia / Sposta su altro storage" onClick={handleForward}><ArrowRightLeft className="h-4 w-4" /></Button>
          </div>
        </div>
      </Card>

      <Dialog open={sendModal} onOpenChange={setSendModal}>
        <DialogContent
          onPointerDownOutside={(e) => e.preventDefault()}
          onInteractOutside={(e) => e.preventDefault()}
        >
          <DialogHeader>
            <DialogTitle>Invia backup al server piattaforma</DialogTitle>
            <DialogDescription>
              Il backup sarà scaricato dallo storage remoto e salvato sul disco del server in una cartella temporanea, pronta per il restore manuale.
            </DialogDescription>
          </DialogHeader>

          {!sendResult ? (
            <div className="space-y-4 py-2">
              <div className="text-sm text-rx-ink-muted space-y-1">
                <div>File: <span className="font-mono text-rx-ink">{run.file_path?.split('/').pop()}</span></div>
                <div>Storage: <span className="font-mono text-rx-ink">{run.storage_name}</span></div>
                <div>Dimensione: <span className="font-mono text-rx-ink">{formatBytes(run.size_bytes ?? 0)}</span></div>
              </div>

              {run.encryption_enabled && (
                <div className="flex items-center gap-3 p-3 bg-rx-bg-surface/40 rounded-md">
                  <input
                    type="checkbox"
                    id={`dec-${run.id}`}
                    checked={sendDecrypt}
                    onChange={e => setSendDecrypt(e.target.checked)}
                    className="h-4 w-4 accent-rx-accent"
                  />
                  <Label htmlFor={`dec-${run.id}`} className="cursor-pointer flex-1 text-sm text-rx-ink">
                    Decifra il file prima di salvarlo
                    <p className="text-xs text-rx-ink-faint mt-1">
                      Il file finale sarà già utilizzabile per RESTORE DATABASE (nessun decrypt manuale richiesto).
                    </p>
                  </Label>
                </div>
              )}

              <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-md text-xs text-amber-200">
                ⚠️ Ricorda di eliminare la cartella temp dal Restore Hub quando hai finito il restore — altrimenti occupa spazio sul server.
              </div>
            </div>
          ) : (
            <div className="space-y-3 py-2">
              <div className="text-sm text-rx-accent">✅ Backup inviato con successo</div>
              <div className="space-y-2 text-sm">
                <div className="text-rx-ink-muted">Path completo:</div>
                <div className="font-mono text-xs bg-rx-bg-surface p-3 rounded-md break-all flex items-start gap-2">
                  <span className="flex-1">{sendResult.target_path}</span>
                  <Button variant="outline" size="sm" onClick={() => copyPath(sendResult.target_path)}>Copia</Button>
                </div>
                <div className="grid grid-cols-3 gap-3 text-xs">
                  <div>
                    <div className="text-rx-ink-faint uppercase tracking-wider">Dimensione</div>
                    <div className="font-mono text-rx-ink">{formatBytes(sendResult.bytes)}</div>
                  </div>
                  <div>
                    <div className="text-rx-ink-faint uppercase tracking-wider">Decifrato</div>
                    <div className="text-rx-ink">{sendResult.decrypted ? 'Sì' : 'No'}</div>
                  </div>
                  <div>
                    <div className="text-rx-ink-faint uppercase tracking-wider">Durata</div>
                    <div className="font-mono text-rx-ink">{formatDuration(sendResult.duration_seconds)}</div>
                  </div>
                </div>
              </div>
            </div>
          )}

          <DialogFooter>
            {!sendResult ? (
              <>
                <Button variant="outline" onClick={() => setSendModal(false)} disabled={sending}>Annulla</Button>
                <Button variant="restorix" onClick={confirmSend} disabled={sending}>
                  {sending ? 'Invio in corso…' : 'Invia'}
                </Button>
              </>
            ) : (
              <Button variant="restorix" onClick={() => setSendModal(false)}>Chiudi</Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={forwardModal} onOpenChange={setForwardModal}>
        <DialogContent
          onPointerDownOutside={(e) => e.preventDefault()}
          onInteractOutside={(e) => e.preventDefault()}
        >
          <DialogHeader>
            <DialogTitle>Sposta backup tra storage</DialogTitle>
            <DialogDescription>
              Trasferisce il file da <strong>{run.storage_name}</strong> a un altro storage configurato.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div>
              <Label>Storage di destinazione</Label>
              <Select value={forwardTargetId || ''} onValueChange={setForwardTargetId}>
                <SelectTrigger><SelectValue placeholder="Seleziona uno storage..." /></SelectTrigger>
                <SelectContent>
                  {availableTargets.map((s: any) => (
                    <SelectItem key={s.id} value={s.id}>
                      {s.name} ({s.storage_type ?? s.type ?? '?'})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {availableTargets.length === 0 && (
                <p className="text-xs text-amber-400 mt-1">Nessun altro storage configurato. Aggiungine uno in Storage.</p>
              )}
            </div>

            <div>
              <Label>Modalità</Label>
              <div className="flex gap-3 mt-2">
                <label className={`flex-1 cursor-pointer p-3 rounded-md border ${forwardMode === 'copy' ? 'border-rx-accent bg-rx-accent/10' : 'border-rx-border'}`}>
                  <input
                    type="radio"
                    name={`mode-${run.id}`}
                    value="copy"
                    checked={forwardMode === 'copy'}
                    onChange={() => setForwardMode('copy')}
                    className="mr-2 accent-rx-accent"
                  />
                  <strong className="text-rx-ink">Copia</strong>
                  <p className="text-xs text-rx-ink-faint mt-1">L'originale resta dov'è, viene duplicato sul nuovo storage.</p>
                </label>
                <label className={`flex-1 cursor-pointer p-3 rounded-md border ${forwardMode === 'move' ? 'border-rx-accent bg-rx-accent/10' : 'border-rx-border'}`}>
                  <input
                    type="radio"
                    name={`mode-${run.id}`}
                    value="move"
                    checked={forwardMode === 'move'}
                    onChange={() => setForwardMode('move')}
                    className="mr-2 accent-rx-accent"
                  />
                  <strong className="text-rx-ink">Sposta</strong>
                  <p className="text-xs text-rx-ink-faint mt-1">Il file viene cancellato dall'origine dopo l'upload OK.</p>
                </label>
              </div>
            </div>

            {forwardMode === 'move' && (
              <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-md text-xs text-amber-200">
                ⚠️ Modalità "Sposta": il file sarà cancellato dallo storage di origine. L'operazione è irreversibile.
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setForwardModal(false)} disabled={forwarding}>Annulla</Button>
            <Button variant="restorix" onClick={confirmForward} disabled={forwarding || !forwardTargetId}>
              {forwarding ? 'Avvio in corso…' : 'Avvia'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function MetaItem({ label, value, mono = false, accent = false }: { label: string; value: string; mono?: boolean; accent?: boolean }) {
  return (
    <div>
      <div className="text-rx-ink-faint uppercase tracking-wider text-[10px] font-semibold">{label}</div>
      <div className={`${mono ? 'font-mono' : ''} ${accent ? 'text-cyan-400' : 'text-rx-ink'}`}>{value}</div>
    </div>
  );
}

function TempFoldersSection() {
  const [expanded, setExpanded] = useState(false);
  const { data, refetch } = useQuery<TempFolderListResponse>({
    queryKey: ['temp-folders'],
    queryFn: () => api.get<TempFolderListResponse>('/restore-hub/temp-folders').then(r => r.data),
  });

  const hasFolders = (data?.items?.length ?? 0) > 0;

  useEffect(() => { if (hasFolders) setExpanded(true); }, [hasFolders]);

  const handleDelete = async (name: string) => {
    if (!confirm(`Cancellare la cartella ${name}? L'azione è irreversibile.`)) return;
    try {
      await api.delete(`/restore-hub/temp-folders/${encodeURIComponent(name)}`);
      refetch();
    } catch (e: any) {
      alert(`Errore: ${e?.response?.data?.detail ?? e.message}`);
    }
  };

  return (
    <Card className="p-5">
      <button
        type="button"
        onClick={() => setExpanded(v => !v)}
        className="flex items-center gap-2 text-sm font-bold text-rx-ink w-full text-left"
      >
        {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        <Folder className="h-4 w-4 text-rx-accent" />
        <span>Cartelle temp restore</span>
        <Badge variant="secondary" className="ml-2">{data?.items?.length ?? 0}</Badge>
        <span className="ml-auto text-xs text-rx-ink-faint">{formatBytes(data?.total_size_bytes ?? 0)} occupati</span>
      </button>
      {expanded && (
        <div className="mt-4 space-y-2">
          {!hasFolders && <p className="text-sm text-rx-ink-faint">Nessuna cartella temp presente.</p>}
          {data?.items?.map(f => (
            <div key={f.name} className="flex items-center gap-3 p-3 bg-rx-bg-surface/40 rounded-md">
              <Folder className="h-4 w-4 text-rx-ink-muted" />
              <div className="flex-1">
                <div className="text-sm font-medium text-rx-ink">{f.name}</div>
                <div className="text-xs text-rx-ink-faint font-mono">{f.path}</div>
              </div>
              <div className="text-xs text-rx-ink-muted">{f.n_files} file • {formatBytes(f.size_bytes)} • {formatRelative(f.created_at)}</div>
              <Button variant="outline" size="sm" onClick={() => handleDelete(f.name)} title="Cancella cartella">
                <Trash2 className="h-4 w-4 text-red-400" />
              </Button>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
