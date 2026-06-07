import db

def test_init_db_creates_tables(fresh_db, tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    conn = db.get_db()
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert {"servers", "backup_runs", "restore_runs", "users", "sessions"} <= tables
    finally:
        conn.close()
