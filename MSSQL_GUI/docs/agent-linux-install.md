# Installazione agent Linux

## Prerequisiti

- Linux 64-bit (Ubuntu 20.04+, Debian 11+, RHEL/Rocky 8+, Fedora 38+)
- Python 3.9+ (auto-installato dall'installer)
- `sqlcmd` (mssql-tools18) — l'installer lo cerca, warning se assente
- Connessione internet
- Privilegi root (sudo)

## Installazione

```bash
curl -sSL https://backupdb.edminformatica.it/install.sh | sudo bash -s -- --token=<TOKEN>
```

Lo script:
1. Verifica `tar`, `curl`, `sudo`, `systemctl`
2. Auto-installa Python 3.11 se assente
3. Scarica tarball agent + verifica SHA256
4. Crea user `dbshield`, install in `/opt/dbshield-agent/`
5. Config in `/etc/dbshield-agent/config.json` (perms 640 root:dbshield)
6. Unit systemd `dbshield-agent.service` con `Restart=always`
7. Avvia il service

## Verifica

```bash
systemctl status dbshield-agent
journalctl -u dbshield-agent -f
```

## SQL Server permission

Su Linux, SQL Server gira come user `mssql`. Per permettere all'agent (user `dbshield`) di leggere i file `.bak`:

```bash
sudo usermod -a -G mssql dbshield
sudo chmod g+r /var/opt/mssql/backups/
sudo systemctl restart dbshield-agent
```

## Aggiornamento

Auto-update default. Manuale:

```bash
sudo systemctl stop dbshield-agent
curl -sSL https://backupdb.edminformatica.it/install.sh | sudo bash -s -- --token=<TOKEN>
```

## Disinstallazione

```bash
sudo systemctl stop dbshield-agent
sudo systemctl disable dbshield-agent
sudo rm /etc/systemd/system/dbshield-agent.service
sudo rm -rf /opt/dbshield-agent /etc/dbshield-agent /var/log/dbshield-agent
sudo userdel dbshield
```

## Troubleshooting

- `sqlcmd not found` → installare mssql-tools18 (https://learn.microsoft.com/sql/linux/sql-server-linux-setup-tools)
- `Permission denied su /var/opt/mssql/backups` → vedi sezione "SQL Server permission"
- `Cannot connect to backend` → verificare token + DNS + firewall (porta 443)
