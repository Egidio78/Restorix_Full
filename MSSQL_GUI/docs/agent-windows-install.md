# Installazione agent Windows

## Prerequisiti

- Windows 10/11 oppure Windows Server 2016/2019/2022/2025
- PowerShell 5.1+ (incluso di default)
- `tar.exe` (incluso da Windows 10 build 1803+)
- Privilegi di Amministratore
- Connessione internet HTTPS verso `backupdb.edminformatica.it`
- `sqlcmd` (ODBC 18+) — vedi sezione dedicata

## Installazione (one-liner)

In una PowerShell aperta **come Amministratore**:

```powershell
$Env:AGENT_TOKEN = "<AGENT_TOKEN>"
irm https://backupdb.edminformatica.it/api/v1/agent/install-script-windows | iex
```

Lo script:
1. Verifica privilegi admin e presenza `tar.exe`
2. Scarica il tarball dell'agent + verifica SHA256
3. Estrae i file in `C:\Program Files\dbshield-agent\`
4. Scrive la config in `C:\ProgramData\dbshield-agent\config.json`
5. Installa NSSM e registra il service `dbshield-agent`
6. Configura auto-restart e log rotation (10 MB)
7. Avvia il service

## Verifica installazione

```powershell
Get-Service dbshield-agent
Get-Content C:\ProgramData\dbshield-agent\logs\agent.log -Tail 50 -Wait
```

## Concessione accessi a SQL Server

L'agent scrive il file `.bak` in `C:\ProgramData\dbshield-agent\temp\` (default).
Il servizio SQL Server (account `NT SERVICE\MSSQLSERVER` o `LocalSystem`) deve
poter scrivere in quella cartella. Comando per concedere accesso:

```powershell
$tempDir = "C:\ProgramData\dbshield-agent\temp"
$sqlAccount = "NT SERVICE\MSSQLSERVER"  # adatta se hai istanza named (es. NT SERVICE\MSSQL$SQLEXPRESS)
icacls $tempDir /grant "${sqlAccount}:(OI)(CI)F" | Out-Null
```

Per SQL Server Express:

```powershell
icacls $tempDir /grant "NT SERVICE\MSSQL`$SQLEXPRESS:(OI)(CI)F" | Out-Null
```

## Esclusione Antivirus

Windows Defender / antivirus possono rallentare significativamente il backup
(scansione real-time del file `.bak` durante writing). Aggiungere exclusion:

```powershell
# Esclusione cartella per Windows Defender
Add-MpPreference -ExclusionPath "C:\ProgramData\dbshield-agent"
Add-MpPreference -ExclusionPath "C:\Program Files\dbshield-agent"

# Esclusione process
Add-MpPreference -ExclusionProcess "sqlservr.exe"
```

## Installazione sqlcmd (richiesto)

L'agent richiede `sqlcmd` (ODBC 18+) nel PATH. Installa con:

```powershell
# Opzione 1 (raccomandata): winget
winget install Microsoft.Sqlcmd

# Opzione 2: MSI manuale
# https://learn.microsoft.com/en-us/sql/tools/sqlcmd/sqlcmd-utility
```

Verifica:

```powershell
sqlcmd -? | Select-Object -First 1
# Atteso: "Microsoft (R) SQL Server Command Line Tool ..."
```

## Aggiornamento agent (auto + manuale)

### Auto-update (default)

Se `auto_update=true` nel pannello (default), l'agent riceve l'aggiornamento
automaticamente al prossimo heartbeat (entro 30 secondi dal rilascio).

L'agent:
1. Scarica nuovo tarball
2. Verifica SHA256
3. Backup install dir corrente in `C:\Program Files\dbshield-agent.bak\`
4. Estrae nuovi file
5. Esce con exit 0 → NSSM riavvia con nuova versione

Su Windows, se l'agent stesso è bloccato (file `.pyd` lockati), l'update fallisce
gracefully e fa rollback. In questo caso: ferma il service e rilancia `install.ps1`
con `-Version <new>`.

### Trigger manuale via UI

Dal pannello Restorix → Servers → bottone "Aggiorna ora" per quel server.

### Reinstall completo

```powershell
# Disinstalla (preserva config)
irm https://backupdb.edminformatica.it/api/v1/agent/install-script-windows-uninstall | iex
# Oppure dal package locale:
& "C:\Program Files\dbshield-agent\uninstall.ps1"

# Reinstalla
$Env:AGENT_TOKEN = "<token>"
irm https://backupdb.edminformatica.it/api/v1/agent/install-script-windows | iex
```

## Troubleshooting

- **`tar.exe non trovato`** → Windows < 10 1803: aggiornare OS, oppure installare Git for Windows (include `tar`).
- **`SmartScreen ha bloccato lo script`** → tasto destro → Run as Administrator, oppure `Set-ExecutionPolicy Bypass -Scope Process -Force`.
- **`Long path > 260 char`** →
  ```powershell
  New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name LongPathsEnabled -Value 1 -PropertyType DWORD -Force
  ```
- **Proxy aziendale** → `$Env:HTTPS_PROXY = "http://proxy:8080"` prima del `irm | iex`.
- **`Service start failed`** → verifica log `C:\ProgramData\dbshield-agent\logs\agent.log`.
- **`sqlcmd not found`** → vedi sezione "Installazione sqlcmd".
- **Backup lentissimi** → vedi sezione "Esclusione Antivirus".

## Disinstallazione

```powershell
& "C:\Program Files\dbshield-agent\uninstall.ps1"
```

Lo script rimuove service, file binari, log e config (se confermato).
