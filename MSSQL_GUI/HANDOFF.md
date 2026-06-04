# Restorix — Handoff

## v1.5.x — Windows agent support (alpha → beta)

**Stato:** Alpha — testato in dev, NON ancora promosso come stable.

**Cosa funziona:**
- One-liner PowerShell installer (`irm | iex`)
- NSSM service con auto-restart, log rotation 10 MB
- Auto-update SHA256-verified (stesso `updater.py` cross-platform)
- OS detection (PowerShell `Get-CimInstance`, fallback `wmic`)
- Heartbeat protocol v3 con `os_type` / `os_version`
- Path platform-aware (config in `%ProgramData%`, install in `%ProgramFiles%`)

**Gap noti / TODO:**
- `sqlcmd` non auto-installato (utente deve `winget install Microsoft.Sqlcmd` separato)
- ACL grant a `NT SERVICE\MSSQLSERVER` sulla temp_dir non automatica
- Long path support (>260 char) richiede registry `LongPathsEnabled=1`
- AV exclusion non automatica (rallentamenti su file `.bak` grandi)
- Shadow update pattern non implementato (`rmtree` fallisce se agent gira da install dir)

**Cosa testare prima di promuovere a stable:**
- Install fresh su Windows Server 2022 + SQL Server Express
- Install fresh su Windows 11 + SQL Server Developer
- Auto-update da v1.5.0 → v1.5.1 con file lockati
- Backup DB con `[name]` contenente caratteri speciali
- Restore via download (server-side, lato backend)
- Disinstallazione completa

**Roadmap v1.6.x:**
- `sqlcmd` auto-install via winget (se assente)
- Shadow update pattern (extract `.new` + rename)
- AV exclusion automatica con `Add-MpPreference`
- Documentazione completa SQL Server ACL grant
