from __future__ import annotations
"""Root command runner. Triggered (as root) by a systemd path-unit when the agent
drops /run/restorix-agent/command.json. Executes the whitelisted ROOT actions
(install_deps, restart_agent, repair) and reports the result back to the platform
if the command carries an id (platform-issued); agent-initiated auto-installs
carry no id and are run silently.
"""
import json
import os
import shutil
import subprocess
import sys

CONFIG_PATH = "/etc/restorix-agent/config.json"
VENV = "/opt/restorix-agent/venv"
SERVICE = "restorix-agent"
TRIGGER = "/run/restorix-agent/command.json"
ALLOWED = {"install_deps", "restart_agent", "repair"}


def _run(cmd: list[str], env: dict | None = None, timeout: int = 600) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
        out = (p.stdout or "") + (p.stderr or "")
        return p.returncode, out.strip()
    except Exception as e:
        return 1, str(e)


def _pkg_manager() -> str | None:
    for mgr in ("apt-get", "dnf", "yum"):
        if shutil.which(mgr):
            return mgr
    return None


def _install_mysql_client() -> tuple[bool, str]:
    mgr = _pkg_manager()
    if mgr == "apt-get":
        _run(["apt-get", "update", "-qq"])
        rc, out = _run(["apt-get", "install", "-y", "default-mysql-client"])
    elif mgr in ("dnf", "yum"):
        rc, out = _run([mgr, "install", "-y", "mysql"])
    else:
        return False, "Nessun gestore pacchetti supportato"
    ok = shutil.which("mysqldump") is not None
    return ok, out


def _install_mssql_tools() -> tuple[bool, str]:
    mgr = _pkg_manager()
    if mgr != "apt-get":
        return False, "Installazione sqlcmd automatica supportata solo su Debian/Ubuntu"
    logs = []
    # Microsoft repo (version-specific)
    try:
        import platform  # noqa
        ver = ""
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("VERSION_ID="):
                    ver = line.strip().split("=", 1)[1].strip('"')
        url = f"https://packages.microsoft.com/config/ubuntu/{ver}/packages-microsoft-prod.deb"
        rc, out = _run(["curl", "-sSL", "-o", "/tmp/ms-prod.deb", url]); logs.append(out)
        rc, out = _run(["dpkg", "-i", "/tmp/ms-prod.deb"]); logs.append(out)
        _run(["apt-get", "update", "-qq"])
        env = os.environ.copy(); env["ACCEPT_EULA"] = "Y"; env["DEBIAN_FRONTEND"] = "noninteractive"
        rc, out = _run(["apt-get", "install", "-y", "mssql-tools18", "unixodbc-dev"], env=env); logs.append(out)
        # symlink sqlcmd into PATH
        for cand in ("/opt/mssql-tools18/bin/sqlcmd", "/opt/mssql-tools/bin/sqlcmd"):
            if os.path.exists(cand):
                try:
                    if not os.path.exists("/usr/local/bin/sqlcmd"):
                        os.symlink(cand, "/usr/local/bin/sqlcmd")
                except OSError:
                    pass
    except Exception as e:
        logs.append(str(e))
    ok = shutil.which("sqlcmd") is not None
    return ok, "\n".join(logs)


def _do_install_deps(params: dict) -> tuple[bool, str]:
    deps = params.get("deps") or ["mysql"]
    results = []
    overall = True
    for dep in deps:
        if dep == "mysql":
            ok, out = _install_mysql_client()
        elif dep == "mssql":
            ok, out = _install_mssql_tools()
        else:
            ok, out = False, f"Dipendenza sconosciuta: {dep}"
        results.append(f"[{dep}] {'OK' if ok else 'FALLITO'}\n{out[-2000:]}")
        overall = overall and ok
    return overall, "\n\n".join(results)


def _do_restart() -> tuple[bool, str]:
    rc, out = _run(["systemctl", "restart", SERVICE])
    return rc == 0, out or "restarted"


def _do_repair() -> tuple[bool, str]:
    logs = []
    boot = os.path.join(VENV, "bin", "restorix-agent-bootstrap")
    if os.path.exists(boot):
        rc, out = _run([boot]); logs.append("bootstrap: " + (out or "ok"))
    else:
        logs.append("bootstrap non trovato")
    rc, out = _run(["systemctl", "restart", SERVICE]); logs.append("restart: " + (out or "ok"))
    return True, "\n".join(logs)


def _report(cmd_id: str, success: bool, result: str) -> None:
    try:
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
        api = cfg["api_url"]; token = cfg["agent_token"]
    except Exception:
        return
    try:
        import urllib.request
        import urllib.parse
        url = f"{api}/api/v1/agent/commands/{cmd_id}/result?token={urllib.parse.quote(token)}"
        data = json.dumps({"success": success, "result": result}).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=15).read()
    except Exception as e:
        print(f"[root-runner] could not report result: {e}", file=sys.stderr)


def main() -> int:
    if os.geteuid() != 0:
        print("restorix-agent-root must run as root", file=sys.stderr)
        return 1
    # lock-rename so a failed run doesn't loop
    if os.path.exists(TRIGGER):
        try:
            os.replace(TRIGGER, TRIGGER + ".processing")
        except OSError:
            return 0
    proc = TRIGGER + ".processing"
    if not os.path.exists(proc):
        return 0
    try:
        with open(proc) as f:
            cmd = json.load(f)
    except Exception:
        os.remove(proc)
        return 0
    os.remove(proc)

    action = cmd.get("action")
    cmd_id = cmd.get("id")
    params = cmd.get("params") or {}
    if action not in ALLOWED:
        if cmd_id:
            _report(cmd_id, False, f"Azione root non consentita: {action}")
        return 0

    if action == "install_deps":
        ok, out = _do_install_deps(params)
    elif action == "restart_agent":
        ok, out = _do_restart()
    elif action == "repair":
        ok, out = _do_repair()
    else:
        ok, out = False, "unhandled"

    print(f"[root-runner] {action}: {'OK' if ok else 'FAILED'}")
    if cmd_id:
        _report(cmd_id, ok, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
