import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Download, Filter, Shield } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

import api from '@/lib/api';
import { AUDIT_EVENT_TYPES, CATEGORY_COLORS } from '@/lib/audit-events';

interface AuditLog {
  id: string;
  org_id: string | null;
  user_id: string | null;
  user_email: string | null;
  action: string;
  target_type: string | null;
  target_id: string | null;
  description: string;
  metadata: Record<string, any>;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
}

interface AuditListResponse {
  items: AuditLog[];
  total: number;
  page: number;
  page_size: number;
}

function formatDateTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString('it-IT', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
  } catch {
    return iso;
  }
}

function categoryOf(action: string): string {
  return AUDIT_EVENT_TYPES.find(e => e.value === action)?.category ?? 'system';
}

const apiBase = (import.meta as any).env?.VITE_API_BASE_URL ?? '/api/v1';

export default function AuditPage() {
  const [filters, setFilters] = useState({
    from: '',
    to: '',
    action: '',
    q: '',
    page: 1,
    page_size: 50,
  });

  const { data, isLoading, error } = useQuery<AuditListResponse>({
    queryKey: ['audit', filters],
    queryFn: async () => {
      const params: Record<string, any> = { page: filters.page, page_size: filters.page_size };
      if (filters.from) params.from = filters.from;
      if (filters.to) params.to = filters.to;
      if (filters.action) params.action = filters.action;
      if (filters.q) params.q = filters.q;
      const r = await api.get<AuditListResponse>('/audit/', { params });
      return r.data;
    },
    placeholderData: (prev) => prev,
  });

  const handleExport = () => {
    const qs = new URLSearchParams();
    if (filters.from) qs.set('from', filters.from);
    if (filters.to) qs.set('to', filters.to);
    if (filters.action) qs.set('action', filters.action);
    if (filters.q) qs.set('q', filters.q);
    window.location.href = `${apiBase}/audit/export.csv?${qs.toString()}`;
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Shield className="h-6 w-6 text-rx-accent drop-shadow-[0_0_6px_rgba(52,211,153,0.5)]" />
          <h1 className="text-2xl font-bold">Audit Log</h1>
        </div>
        <Button onClick={handleExport} variant="outline">
          <Download className="mr-2 h-4 w-4" /> Esporta CSV
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Filter className="h-4 w-4" /> Filtri
          </CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div>
            <Label htmlFor="from">Da</Label>
            <Input id="from" type="datetime-local" value={filters.from}
                   onChange={e => setFilters(f => ({ ...f, from: e.target.value, page: 1 }))} />
          </div>
          <div>
            <Label htmlFor="to">A</Label>
            <Input id="to" type="datetime-local" value={filters.to}
                   onChange={e => setFilters(f => ({ ...f, to: e.target.value, page: 1 }))} />
          </div>
          <div>
            <Label>Tipo evento</Label>
            <Select value={filters.action || 'all'}
                    onValueChange={v => setFilters(f => ({ ...f, action: v === 'all' ? '' : v, page: 1 }))}>
              <SelectTrigger><SelectValue placeholder="Tutti" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tutti</SelectItem>
                {AUDIT_EVENT_TYPES.map(e => (
                  <SelectItem key={e.value} value={e.value}>{e.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label htmlFor="q">Ricerca</Label>
            <Input id="q" placeholder="descrizione, metadata..."
                   value={filters.q}
                   onChange={e => setFilters(f => ({ ...f, q: e.target.value, page: 1 }))} />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Quando</TableHead>
                <TableHead>Utente</TableHead>
                <TableHead>Azione</TableHead>
                <TableHead>Target</TableHead>
                <TableHead>IP</TableHead>
                <TableHead>Descrizione</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading && (
                <TableRow><TableCell colSpan={6}>Caricamento...</TableCell></TableRow>
              )}
              {error && (
                <TableRow><TableCell colSpan={6} className="text-red-600">Errore caricamento</TableCell></TableRow>
              )}
              {!isLoading && data && data.items.length === 0 && (
                <TableRow><TableCell colSpan={6}>Nessun evento</TableCell></TableRow>
              )}
              {data?.items?.map((item) => {
                const cat = categoryOf(item.action);
                return (
                  <TableRow key={item.id}>
                    <TableCell className="font-mono text-xs whitespace-nowrap">
                      {formatDateTime(item.created_at)}
                    </TableCell>
                    <TableCell>
                      {item.user_email ?? <em className="text-muted-foreground">Sistema</em>}
                    </TableCell>
                    <TableCell>
                      <Badge className={CATEGORY_COLORS[cat] ?? ''}>{item.action}</Badge>
                    </TableCell>
                    <TableCell className="text-xs">
                      {item.target_type && (
                        <span className="text-muted-foreground">{item.target_type}: </span>
                      )}
                      {item.target_id && <code className="text-xs">{item.target_id.slice(0, 8)}</code>}
                    </TableCell>
                    <TableCell className="font-mono text-xs">{item.ip_address ?? '-'}</TableCell>
                    <TableCell className="text-xs max-w-md truncate" title={item.description}>
                      {item.description || (Object.keys(item.metadata).length ? JSON.stringify(item.metadata).slice(0, 100) : '-')}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <div className="flex items-center justify-between">
        <div className="text-sm text-muted-foreground">
          {data?.total ?? 0} eventi totali — pagina {data?.page ?? 1}
        </div>
        <div className="flex gap-2">
          <Button variant="outline" disabled={filters.page <= 1}
                  onClick={() => setFilters(f => ({ ...f, page: f.page - 1 }))}>
            Prec
          </Button>
          <Button variant="outline" disabled={!data || data.items.length < filters.page_size}
                  onClick={() => setFilters(f => ({ ...f, page: f.page + 1 }))}>
            Succ
          </Button>
        </div>
      </div>
    </div>
  );
}
