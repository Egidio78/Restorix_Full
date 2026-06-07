import sqlite3
import config

DDL = """
CREATE TABLE IF NOT EXISTS servers (
    vps_id      TEXT PRIMARY KEY,
    hostname    TEXT NOT NULL,
    cliente     TEXT NOT NULL DEFAULT '',
    os_name     TEXT NOT NULL DEFAULT '',
    os_version  TEXT NOT NULL DEFAULT '',
    folders     TEXT NOT NULL DEFAULT '',
    backup_hour INTEGER NOT NULL DEFAULT 2,
    api_key     TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS backup_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    vps_id      TEXT NOT NULL REFERENCES servers(vps_id),
    status      TEXT NOT NULL,
    snapshot_id TEXT,
    size_gb     REAL,
    duration_s  INTEGER,
    downtime_s  INTEGER,
    error_msg   TEXT,
    folders     TEXT,
    disk_free_pct REAL,
    reported_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS restore_runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    vps_id       TEXT NOT NULL REFERENCES servers(vps_id),
    backup_run_id INTEGER REFERENCES backup_runs(id),
    status       TEXT NOT NULL,
    checksum_ok  INTEGER,
    duration_s   INTEGER,
    error_msg    TEXT,
    reported_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS users (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    username         TEXT NOT NULL UNIQUE,
    password_hash    TEXT NOT NULL,
    totp_secret_enc  TEXT,
    recovery_codes   TEXT,
    passkey_creds    TEXT NOT NULL DEFAULT '[]',
    role             TEXT NOT NULL DEFAULT 'admin',
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessions (
    token       TEXT PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    expires_at  TEXT NOT NULL,
    revoked     INTEGER NOT NULL DEFAULT 0
);
"""

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    with get_db() as conn:
        conn.executescript(DDL)
