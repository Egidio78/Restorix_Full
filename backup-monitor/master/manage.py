#!/usr/bin/env python3
"""CLI management tool for Backup Monitor."""
import argparse
import getpass
import sys
import os

# Ensure MASTER_SECRET etc. are set (minimal defaults for CLI)
os.environ.setdefault("MASTER_SECRET", "changeme")
os.environ.setdefault("JWT_SECRET", "changeme")
os.environ.setdefault("TOTP_ENCRYPTION_KEY", "dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXQ=")

import db
import bcrypt
from auth.totp import (
    generate_totp_secret,
    encrypt_secret,
    generate_qr_b64,
    generate_recovery_codes,
)


def cmd_init_db(args):
    db.init_db()
    print("✅ Database inizializzato.")


def cmd_create_user(args):
    username = args.username
    password = getpass.getpass(f"Password per {username}: ")
    password2 = getpass.getpass("Conferma password: ")
    if password != password2:
        print("❌ Le password non corrispondono.")
        sys.exit(1)

    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()
    totp_secret = generate_totp_secret()
    totp_enc = encrypt_secret(totp_secret)
    recovery_codes = generate_recovery_codes()
    recovery_json = __import__("json").dumps(recovery_codes)

    with db.get_db() as conn:
        existing = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
        if existing:
            print(f"❌ Utente '{username}' già esistente.")
            sys.exit(1)
        conn.execute(
            "INSERT INTO users (username, password_hash, totp_secret_enc, recovery_codes) VALUES (?,?,?,?)",
            (username, password_hash, totp_enc, recovery_json),
        )

    qr_b64 = generate_qr_b64(username, totp_secret)
    qr_path = f"/tmp/totp-qr-{username}.png"
    import base64
    with open(qr_path, "wb") as f:
        f.write(base64.b64decode(qr_b64))

    print(f"✅ Utente '{username}' creato.")
    print(f"📱 QR code salvato in: {qr_path}")
    print(f"🔑 Segreto TOTP (manuale): {totp_secret}")
    print(f"\n🔒 Codici di recupero (monouso — salvali ora!):")
    for i, code in enumerate(recovery_codes, 1):
        print(f"  {i:2d}. {code}")


def cmd_list_users(args):
    with db.get_db() as conn:
        users = conn.execute("SELECT id, username, role, created_at FROM users").fetchall()
    if not users:
        print("Nessun utente.")
        return
    print(f"{'ID':<4} {'Username':<20} {'Ruolo':<10} {'Creato il'}")
    print("-" * 55)
    for u in users:
        print(f"{u['id']:<4} {u['username']:<20} {u['role']:<10} {u['created_at']}")


def cmd_delete_user(args):
    username = args.username
    confirm = input(f"Eliminare utente '{username}'? [s/N]: ")
    if confirm.lower() != "s":
        print("Annullato.")
        return
    with db.get_db() as conn:
        cur = conn.execute("DELETE FROM users WHERE username=?", (username,))
    if cur.rowcount == 0:
        print(f"❌ Utente '{username}' non trovato.")
    else:
        print(f"✅ Utente '{username}' eliminato.")


def cmd_set_password(args):
    username = args.username
    password = getpass.getpass(f"Nuova password per {username}: ")
    password2 = getpass.getpass("Conferma: ")
    if password != password2:
        print("❌ Le password non corrispondono.")
        sys.exit(1)
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()
    with db.get_db() as conn:
        cur = conn.execute("UPDATE users SET password_hash=? WHERE username=?", (password_hash, username))
    if cur.rowcount == 0:
        print(f"❌ Utente '{username}' non trovato.")
    else:
        print(f"✅ Password aggiornata per '{username}'.")


def main():
    parser = argparse.ArgumentParser(description="Backup Monitor CLI")
    sub = parser.add_subparsers(dest="command")

    p_init = sub.add_parser("init-db", help="Inizializza il database")
    p_init.set_defaults(func=cmd_init_db)

    p_create = sub.add_parser("create-user", help="Crea un nuovo utente")
    p_create.add_argument("--username", required=True)
    p_create.set_defaults(func=cmd_create_user)

    p_list = sub.add_parser("list-users", help="Lista utenti")
    p_list.set_defaults(func=cmd_list_users)

    p_delete = sub.add_parser("delete-user", help="Elimina utente")
    p_delete.add_argument("--username", required=True)
    p_delete.set_defaults(func=cmd_delete_user)

    p_passwd = sub.add_parser("set-password", help="Cambia password utente")
    p_passwd.add_argument("--username", required=True)
    p_passwd.set_defaults(func=cmd_set_password)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
