export interface LastBackupInfo {
  file_name: string;
  server_name: string | null;
  storage_name: string | null;
  finished_at: string;
}
export interface NextBackupInfo {
  job_name: string;
  server_name: string | null;
  schedule_cron: string;
  next_fire_at: string;
  seconds_until: number;
}
export interface RestoreHubSummary {
  total_backups: number;
  success_count_30d: number;
  fail_count_30d: number;
  success_rate_30d: number;
  total_size_bytes: number;
  last_backup: LastBackupInfo | null;
  next_backup: NextBackupInfo | null;
}
export interface TempFolderInfo {
  name: string;
  path: string;
  size_bytes: number;
  n_files: number;
  created_at: string;
}
export interface TempFolderListResponse {
  items: TempFolderInfo[];
  total_size_bytes: number;
}

export function formatBytes(n: number | null | undefined): string {
  if (!n && n !== 0) return '—';
  if (n < 1024) return `${n} B`;
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(1)} MB`;
  return `${(n / 1024 ** 3).toFixed(2)} GB`;
}

export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.floor(seconds)}s`;
  if (seconds < 3600) {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return s > 0 ? `${m}m ${s}s` : `${m}m`;
  }
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
}

export function formatCountdown(seconds: number): string {
  if (seconds <= 0) return '00:00:00';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

export function formatRelative(iso: string): string {
  const t = new Date(iso).getTime();
  const diff = (Date.now() - t) / 1000;
  if (diff < 60) return `${Math.floor(diff)}s fa`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m fa`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h fa`;
  return `${Math.floor(diff / 86400)}g fa`;
}

export function formatVelocity(mbps: number | null | undefined): string {
  if (mbps == null) return '—';
  return `${mbps.toFixed(1)} MB/s`;
}
