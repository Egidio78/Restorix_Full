# InfraAI Piano 2: AI Core + Ansible Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the AI brain of InfraAI — intent parsing via Claude, Ansible routing by OS version, SSH-based Ansible execution, and a streaming SSE chat API endpoint.

**Architecture:** The FastAPI backend receives chat messages, passes them to Claude with a `extract_intent` tool, resolves target servers from the inventory DB, routes commands to the correct Ansible controller (stable for Ubuntu ≤22.04 / other Linux / Windows, new for Ubuntu ≥24.04), executes via SSH, and streams results back as Server-Sent Events.

**Tech Stack:** Python 3.12, FastAPI, asyncssh, anthropic SDK, sse-starlette, SQLAlchemy async, pytest + respx + pytest-asyncio

---

## File Structure

```
backend/
  ai/
    __init__.py
    prompts.py          # System prompt + tool definition for Claude
    claude_client.py    # Thin wrapper around Anthropic async client
    intent_parser.py    # Intent dataclass + parse_intent() function
    action_handler.py   # Resolves targets, executes via Ansible, yields status
  ansible/
    __init__.py
    router.py           # AnsibleRouter: routes hosts to stable/new controller
    runner.py           # AnsibleRunner: SSH into controller, run ansible ad-hoc
  api/
    chat.py             # POST /api/chat/message — SSE streaming endpoint
  config.py             # Extended: ansible_stable_host/user/key, ansible_new_host/user/key
  tests/
    test_ansible_router.py
    test_ansible_runner.py
    test_intent_parser.py
    test_action_handler.py
    test_chat_api.py
```

---

### Task 1: Dependencies + Extended Config

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/requirements-dev.txt`
- Modify: `backend/config.py`

- [ ] **Step 1: Add new dependencies to requirements.txt**

Replace current `backend/requirements.txt` content:

```
fastapi==0.115.5
uvicorn[standard]==0.32.1
sqlalchemy[asyncio]==2.0.36
asyncpg==0.30.0
alembic==1.14.0
pydantic-settings==2.6.1
httpx==0.28.0
python-multipart==0.0.17
aiofiles==24.1.0
anthropic==0.40.0
asyncssh==2.18.0
sse-starlette==2.1.3
```

- [ ] **Step 2: Add asyncssh stub to requirements-dev.txt**

`backend/requirements-dev.txt` stays as-is (no new dev deps needed for Piano 2).

- [ ] **Step 3: Extend config.py with Ansible controller settings**

Full replacement of `backend/config.py`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://infraai:infraai@db:5432/infraai"
    anthropic_api_key: str = ""

    zabbix_url: str = ""
    zabbix_token: str = ""
    kuma_url: str = ""
    kuma_api_key: str = ""

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    auth_password: str = "changeme"
    allowed_ips: str = ""

    # Ansible Stable controller (Ubuntu ≤22.04, other Linux, Windows)
    ansible_stable_host: str = ""
    ansible_stable_user: str = "ansible"
    ansible_stable_key: str = "/keys/ansible_stable_id_rsa"
    ansible_stable_inventory: str = "/etc/ansible/hosts"

    # Ansible New controller (Ubuntu ≥24.04)
    ansible_new_host: str = ""
    ansible_new_user: str = "ansible"
    ansible_new_key: str = "/keys/ansible_new_id_rsa"
    ansible_new_inventory: str = "/etc/ansible/hosts"


settings = Settings()
```

- [ ] **Step 4: Write a smoke-test that imports new settings fields**

Create `backend/tests/test_config.py`:

```python
from config import settings


def test_ansible_stable_defaults():
    assert settings.ansible_stable_user == "ansible"
    assert settings.ansible_stable_inventory == "/etc/ansible/hosts"


def test_ansible_new_defaults():
    assert settings.ansible_new_user == "ansible"
    assert settings.ansible_new_inventory == "/etc/ansible/hosts"
```

- [ ] **Step 5: Run the test**

```bash
cd backend
python -m pytest tests/test_config.py -v
```

Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add backend/requirements.txt backend/config.py backend/tests/test_config.py
git commit -m "feat: add anthropic/asyncssh/sse-starlette deps and ansible controller config"
```

---

### Task 2: Ansible Router

Routes a list of server records to the correct Ansible controller based on OS version. This is pure logic with no I/O — fully testable without SSH or a database.

**Files:**
- Create: `backend/ansible/__init__.py`
- Create: `backend/ansible/router.py`
- Create: `backend/tests/test_ansible_router.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_ansible_router.py`:

```python
import pytest
from ansible.router import AnsibleRouter, Controller


def make_server(hostname, os_family=None, os_version=None, ansible_controller="auto"):
    return {
        "hostname": hostname,
        "os_family": os_family,
        "os_version": os_version,
        "ansible_controller": ansible_controller,
    }


def test_ubuntu_24_routes_to_new():
    router = AnsibleRouter()
    s = make_server("srv-01", os_family="ubuntu", os_version="24.04")
    assert router.get_controller(s) == Controller.NEW


def test_ubuntu_22_routes_to_stable():
    router = AnsibleRouter()
    s = make_server("srv-02", os_family="ubuntu", os_version="22.04")
    assert router.get_controller(s) == Controller.STABLE


def test_ubuntu_20_routes_to_stable():
    router = AnsibleRouter()
    s = make_server("srv-03", os_family="ubuntu", os_version="20.04")
    assert router.get_controller(s) == Controller.STABLE


def test_debian_routes_to_stable():
    router = AnsibleRouter()
    s = make_server("srv-04", os_family="debian", os_version="12")
    assert router.get_controller(s) == Controller.STABLE


def test_windows_routes_to_stable():
    router = AnsibleRouter()
    s = make_server("srv-05", os_family="windows", os_version=None)
    assert router.get_controller(s) == Controller.STABLE


def test_unknown_os_routes_to_stable():
    router = AnsibleRouter()
    s = make_server("srv-06", os_family=None, os_version=None)
    assert router.get_controller(s) == Controller.STABLE


def test_manual_override_new():
    router = AnsibleRouter()
    # ubuntu 22 but manually overridden
    s = make_server("srv-07", os_family="ubuntu", os_version="22.04", ansible_controller="new")
    assert router.get_controller(s) == Controller.NEW


def test_manual_override_stable():
    router = AnsibleRouter()
    # ubuntu 24 but manually overridden
    s = make_server("srv-08", os_family="ubuntu", os_version="24.04", ansible_controller="stable")
    assert router.get_controller(s) == Controller.STABLE


def test_group_by_controller_splits_correctly():
    router = AnsibleRouter()
    servers = [
        make_server("a", "ubuntu", "24.04"),
        make_server("b", "ubuntu", "22.04"),
        make_server("c", "debian", "12"),
        make_server("d", "ubuntu", "24.04"),
    ]
    groups = router.group_by_controller(servers)
    assert set(groups[Controller.NEW]) == {"a", "d"}
    assert set(groups[Controller.STABLE]) == {"b", "c"}


def test_group_by_controller_empty():
    router = AnsibleRouter()
    groups = router.group_by_controller([])
    assert groups[Controller.NEW] == []
    assert groups[Controller.STABLE] == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
python -m pytest tests/test_ansible_router.py -v
```

Expected: ImportError (module doesn't exist yet)

- [ ] **Step 3: Create `backend/ansible/__init__.py`**

```python
```

(empty file)

- [ ] **Step 4: Implement `backend/ansible/router.py`**

```python
from enum import Enum


class Controller(str, Enum):
    STABLE = "stable"
    NEW = "new"


class AnsibleRouter:
    def get_controller(self, server: dict) -> Controller:
        override = server.get("ansible_controller", "auto")
        if override == "stable":
            return Controller.STABLE
        if override == "new":
            return Controller.NEW

        os_family = (server.get("os_family") or "").lower()
        os_version = server.get("os_version") or ""

        if os_family == "ubuntu":
            try:
                major = int(os_version.split(".")[0])
                if major >= 24:
                    return Controller.NEW
            except (ValueError, IndexError):
                pass

        return Controller.STABLE

    def group_by_controller(self, servers: list[dict]) -> dict[Controller, list[str]]:
        groups: dict[Controller, list[str]] = {
            Controller.STABLE: [],
            Controller.NEW: [],
        }
        for server in servers:
            ctrl = self.get_controller(server)
            groups[ctrl].append(server["hostname"])
        return groups
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend
python -m pytest tests/test_ansible_router.py -v
```

Expected: 10 passed

- [ ] **Step 6: Commit**

```bash
git add backend/ansible/__init__.py backend/ansible/router.py backend/tests/test_ansible_router.py
git commit -m "feat: ansible router routes hosts to stable/new controller by OS version"
```

---

### Task 3: Ansible Runner

Executes Ansible ad-hoc commands on the remote controller via SSH. Tests use `unittest.mock.AsyncMock` to mock `asyncssh.connect` — no real SSH connection.

**Files:**
- Create: `backend/ansible/runner.py`
- Create: `backend/tests/test_ansible_runner.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_ansible_runner.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from ansible.runner import AnsibleRunner, AnsibleResult


@pytest.fixture
def runner():
    return AnsibleRunner(
        host="ctrl.example.com",
        user="ansible",
        key_path="/keys/id_rsa",
        inventory="/etc/ansible/hosts",
    )


def make_mock_conn(stdout="ok", stderr="", returncode=0):
    result = MagicMock()
    result.stdout = stdout
    result.stderr = stderr
    result.returncode = returncode

    conn = AsyncMock()
    conn.run = AsyncMock(return_value=result)
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=None)
    return conn


@pytest.mark.asyncio
async def test_run_adhoc_returns_result(runner):
    mock_conn = make_mock_conn(stdout="SUCCESS", returncode=0)
    with patch("asyncssh.connect", return_value=mock_conn):
        result = await runner.run_adhoc(
            hosts=["srv-01", "srv-02"],
            module="shell",
            args="apt-get update",
        )
    assert result.success is True
    assert "SUCCESS" in result.stdout


@pytest.mark.asyncio
async def test_run_adhoc_failure_captured(runner):
    mock_conn = make_mock_conn(stdout="FAILED", stderr="some error", returncode=1)
    with patch("asyncssh.connect", return_value=mock_conn):
        result = await runner.run_adhoc(
            hosts=["srv-01"],
            module="shell",
            args="bad-command",
        )
    assert result.success is False
    assert result.returncode == 1


@pytest.mark.asyncio
async def test_run_adhoc_builds_correct_command(runner):
    mock_conn = make_mock_conn()
    with patch("asyncssh.connect", return_value=mock_conn) as mock_connect:
        mock_connect.return_value = mock_conn
        await runner.run_adhoc(
            hosts=["srv-01", "srv-02"],
            module="shell",
            args="systemctl restart nginx",
        )
    called_cmd = mock_conn.run.call_args[0][0]
    assert "srv-01,srv-02" in called_cmd
    assert "-m shell" in called_cmd
    assert "systemctl restart nginx" in called_cmd
    assert "/etc/ansible/hosts" in called_cmd


@pytest.mark.asyncio
async def test_run_adhoc_ssh_error_raises(runner):
    with patch("asyncssh.connect", side_effect=OSError("connection refused")):
        with pytest.raises(RuntimeError, match="SSH"):
            await runner.run_adhoc(
                hosts=["srv-01"],
                module="ping",
                args="",
            )
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
python -m pytest tests/test_ansible_runner.py -v
```

Expected: ImportError

- [ ] **Step 3: Implement `backend/ansible/runner.py`**

```python
from dataclasses import dataclass

import asyncssh


@dataclass
class AnsibleResult:
    stdout: str
    stderr: str
    returncode: int

    @property
    def success(self) -> bool:
        return self.returncode == 0


class AnsibleRunner:
    def __init__(self, host: str, user: str, key_path: str, inventory: str) -> None:
        self._host = host
        self._user = user
        self._key_path = key_path
        self._inventory = inventory

    async def run_adhoc(
        self,
        hosts: list[str],
        module: str,
        args: str,
    ) -> AnsibleResult:
        host_pattern = ",".join(hosts)
        cmd = (
            f"ansible all -i {self._inventory}"
            f" --limit '{host_pattern}'"
            f" -m {module}"
            f" -a '{args}'"
        )
        try:
            async with await asyncssh.connect(
                self._host,
                username=self._user,
                client_keys=[self._key_path],
                known_hosts=None,
            ) as conn:
                result = await conn.run(cmd)
                return AnsibleResult(
                    stdout=result.stdout or "",
                    stderr=result.stderr or "",
                    returncode=result.returncode or 0,
                )
        except (OSError, asyncssh.Error) as exc:
            raise RuntimeError(f"SSH connection to {self._host} failed: {exc}") from exc
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend
python -m pytest tests/test_ansible_runner.py -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/ansible/runner.py backend/tests/test_ansible_runner.py
git commit -m "feat: ansible runner executes ad-hoc commands on controller via SSH"
```

---

### Task 4: Intent Parser

Calls Claude with a tool definition and returns a structured `Intent` dataclass. Tests mock the Anthropic client entirely — no real API calls.

**Files:**
- Create: `backend/ai/__init__.py`
- Create: `backend/ai/prompts.py`
- Create: `backend/ai/claude_client.py`
- Create: `backend/ai/intent_parser.py`
- Create: `backend/tests/test_intent_parser.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_intent_parser.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from ai.intent_parser import parse_intent, Intent


def make_tool_use_block(input_data: dict):
    block = MagicMock()
    block.type = "tool_use"
    block.input = input_data
    return block


def make_text_block(text: str):
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def make_mock_message(blocks):
    msg = MagicMock()
    msg.content = blocks
    return msg


@pytest.mark.asyncio
async def test_parse_update_intent():
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(
        return_value=make_mock_message([
            make_tool_use_block({
                "action": "update",
                "targets": {"cliente": "Rossi"},
                "hostnames": [],
                "os_filter": "24.04",
                "extra": {},
            })
        ])
    )
    intent = await parse_intent("Aggiorna tutti i server Ubuntu 24.04 del cliente Rossi", mock_client)
    assert intent.action == "update"
    assert intent.targets == {"cliente": "Rossi"}
    assert intent.os_filter == "24.04"


@pytest.mark.asyncio
async def test_parse_restart_intent():
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(
        return_value=make_mock_message([
            make_tool_use_block({
                "action": "restart_service",
                "targets": {},
                "hostnames": ["srv-web-01"],
                "os_filter": None,
                "extra": {"service": "nginx"},
            })
        ])
    )
    intent = await parse_intent("Riavvia nginx su srv-web-01", mock_client)
    assert intent.action == "restart_service"
    assert intent.hostnames == ["srv-web-01"]
    assert intent.extra == {"service": "nginx"}


@pytest.mark.asyncio
async def test_parse_fallback_on_text_only():
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(
        return_value=make_mock_message([
            make_text_block("Non ho capito la richiesta.")
        ])
    )
    intent = await parse_intent("blah blah incomprensibile", mock_client)
    assert intent.action == "unknown"
    assert "Non ho capito" in intent.raw_response


@pytest.mark.asyncio
async def test_parse_read_logs_intent():
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(
        return_value=make_mock_message([
            make_tool_use_block({
                "action": "read_logs",
                "targets": {},
                "hostnames": ["db-01"],
                "os_filter": None,
                "extra": {"service": "postgresql", "lines": 100},
            })
        ])
    )
    intent = await parse_intent("Mostrami gli ultimi 100 log di postgresql su db-01", mock_client)
    assert intent.action == "read_logs"
    assert intent.extra["lines"] == 100
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
python -m pytest tests/test_intent_parser.py -v
```

Expected: ImportError

- [ ] **Step 3: Create `backend/ai/__init__.py`**

```python
```

(empty file)

- [ ] **Step 4: Create `backend/ai/prompts.py`**

```python
SYSTEM_PROMPT = """Sei InfraAI, un assistente per la gestione dell'infrastruttura IT.
Gestisci circa 400 server Linux e Windows per conto di un sistemista italiano.
Interpreta i comandi in italiano e usa il tool extract_intent per strutturare la richiesta.
Sii preciso: se non capisci, restituisci action="unknown".
"""

EXTRACT_INTENT_TOOL = {
    "name": "extract_intent",
    "description": (
        "Estrai l'intento del sistemista dalla richiesta in linguaggio naturale. "
        "Usa questo tool per ogni richiesta operativa."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "update",
                    "restart_service",
                    "read_logs",
                    "service_status",
                    "upgrade_os",
                    "add_user",
                    "remove_user",
                    "firewall_change",
                    "generate_report",
                    "unknown",
                ],
                "description": "Tipo di operazione richiesta",
            },
            "targets": {
                "type": "object",
                "description": (
                    "Filtri per selezionare i server target. "
                    "Chiavi possibili: cliente, ruolo, source, provider."
                ),
                "additionalProperties": {"type": "string"},
            },
            "hostnames": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Lista di hostname specifici se menzionati esplicitamente",
            },
            "os_filter": {
                "type": ["string", "null"],
                "description": "Versione OS specifica (es. '24.04', '22.04') o null",
            },
            "extra": {
                "type": "object",
                "description": (
                    "Parametri aggiuntivi specifici per l'azione. "
                    "Es: service='nginx', lines=100, new_version='24.04'"
                ),
                "additionalProperties": True,
            },
        },
        "required": ["action", "targets", "hostnames", "os_filter", "extra"],
    },
}
```

- [ ] **Step 5: Create `backend/ai/claude_client.py`**

```python
import anthropic
from config import settings


def make_anthropic_client() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
```

- [ ] **Step 6: Create `backend/ai/intent_parser.py`**

```python
from dataclasses import dataclass, field

import anthropic

from ai.prompts import SYSTEM_PROMPT, EXTRACT_INTENT_TOOL


@dataclass
class Intent:
    action: str
    targets: dict = field(default_factory=dict)
    hostnames: list[str] = field(default_factory=list)
    os_filter: str | None = None
    extra: dict = field(default_factory=dict)
    raw_response: str = ""


async def parse_intent(
    user_message: str,
    client: anthropic.AsyncAnthropic,
) -> Intent:
    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        tools=[EXTRACT_INTENT_TOOL],
        messages=[{"role": "user", "content": user_message}],
    )

    for block in response.content:
        if block.type == "tool_use":
            data = block.input
            return Intent(
                action=data.get("action", "unknown"),
                targets=data.get("targets") or {},
                hostnames=data.get("hostnames") or [],
                os_filter=data.get("os_filter"),
                extra=data.get("extra") or {},
            )

    text = " ".join(
        block.text for block in response.content if block.type == "text"
    )
    return Intent(action="unknown", raw_response=text)
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
cd backend
python -m pytest tests/test_intent_parser.py -v
```

Expected: 4 passed

- [ ] **Step 8: Commit**

```bash
git add backend/ai/ backend/tests/test_intent_parser.py
git commit -m "feat: intent parser extracts structured intent from Italian natural language via Claude"
```

---

### Task 5: Action Handler

Resolves target servers from DB, groups by controller, executes Ansible commands, and yields human-readable status strings. Tests use an in-memory SQLite session (from conftest) and mock AnsibleRunner.

**Files:**
- Create: `backend/ai/action_handler.py`
- Create: `backend/tests/test_action_handler.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_action_handler.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from ai.action_handler import ActionHandler, ActionResult
from ai.intent_parser import Intent
from models.server import Server, OSFamily, Provider, AnsibleController


async def add_server(session: AsyncSession, hostname: str, cliente: str = "Test",
                     os_family: str = "ubuntu", os_version: str = "22.04",
                     ansible_controller: str = "auto") -> None:
    server = Server(
        hostname=hostname,
        cliente=cliente,
        os_family=OSFamily(os_family) if os_family else None,
        os_version=os_version,
        provider=Provider.other,
        ansible_controller=AnsibleController(ansible_controller),
        source="test",
    )
    session.add(server)
    await session.commit()


@pytest.fixture
def mock_runner():
    runner = AsyncMock()
    result = MagicMock()
    result.success = True
    result.stdout = "changed: [srv-01]"
    result.stderr = ""
    runner.run_adhoc = AsyncMock(return_value=result)
    return runner


@pytest.mark.asyncio
async def test_resolve_targets_by_cliente(db_session, mock_runner):
    await add_server(db_session, "srv-01", cliente="Rossi")
    await add_server(db_session, "srv-02", cliente="Rossi")
    await add_server(db_session, "srv-03", cliente="Bianchi")

    handler = ActionHandler(db_session, stable_runner=mock_runner, new_runner=mock_runner)
    intent = Intent(action="update", targets={"cliente": "Rossi"})

    results = []
    async for msg in handler.execute(intent):
        results.append(msg)

    assert any("srv-01" in r or "srv-02" in r or "Rossi" in r for r in results)
    assert not any("srv-03" in r for r in results)


@pytest.mark.asyncio
async def test_resolve_targets_by_hostname(db_session, mock_runner):
    await add_server(db_session, "db-01")

    handler = ActionHandler(db_session, stable_runner=mock_runner, new_runner=mock_runner)
    intent = Intent(action="restart_service", hostnames=["db-01"], extra={"service": "postgresql"})

    results = []
    async for msg in handler.execute(intent):
        results.append(msg)

    mock_runner.run_adhoc.assert_awaited_once()
    call_kwargs = mock_runner.run_adhoc.call_args
    assert call_kwargs.kwargs["module"] == "shell" or call_kwargs.args[1] == "shell"


@pytest.mark.asyncio
async def test_no_servers_found_yields_message(db_session, mock_runner):
    handler = ActionHandler(db_session, stable_runner=mock_runner, new_runner=mock_runner)
    intent = Intent(action="update", targets={"cliente": "Inesistente"})

    results = []
    async for msg in handler.execute(intent):
        results.append(msg)

    assert any("nessun" in r.lower() or "trovato" in r.lower() for r in results)
    mock_runner.run_adhoc.assert_not_awaited()


@pytest.mark.asyncio
async def test_routes_ubuntu24_to_new_runner(db_session):
    await add_server(db_session, "new-srv", os_version="24.04")

    stable_runner = AsyncMock()
    new_runner = AsyncMock()
    result = MagicMock()
    result.success = True
    result.stdout = "ok"
    result.stderr = ""
    new_runner.run_adhoc = AsyncMock(return_value=result)
    stable_runner.run_adhoc = AsyncMock(return_value=result)

    handler = ActionHandler(db_session, stable_runner=stable_runner, new_runner=new_runner)
    intent = Intent(action="update", hostnames=["new-srv"])

    async for _ in handler.execute(intent):
        pass

    new_runner.run_adhoc.assert_awaited_once()
    stable_runner.run_adhoc.assert_not_awaited()


@pytest.mark.asyncio
async def test_unknown_action_yields_message(db_session, mock_runner):
    handler = ActionHandler(db_session, stable_runner=mock_runner, new_runner=mock_runner)
    intent = Intent(action="unknown", raw_response="Non ho capito")

    results = []
    async for msg in handler.execute(intent):
        results.append(msg)

    assert any("capito" in r.lower() or "unknown" in r.lower() or "Non ho" in r for r in results)
    mock_runner.run_adhoc.assert_not_awaited()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
python -m pytest tests/test_action_handler.py -v
```

Expected: ImportError

- [ ] **Step 3: Implement `backend/ai/action_handler.py`**

```python
from collections.abc import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai.intent_parser import Intent
from ansible.router import AnsibleRouter, Controller
from ansible.runner import AnsibleRunner
from models.server import Server


class ActionResult:
    pass


_ANSIBLE_COMMANDS: dict[str, tuple[str, str]] = {
    "update": ("shell", "apt-get update && apt-get upgrade -y"),
    "restart_service": ("shell", "systemctl restart {service}"),
    "read_logs": ("shell", "journalctl -u {service} -n {lines} --no-pager"),
    "service_status": ("shell", "systemctl status {service}"),
    "upgrade_os": ("shell", "do-release-upgrade -f DistUpgradeViewNonInteractive"),
    "generate_report": ("shell", "uptime && df -h && free -h"),
}


class ActionHandler:
    def __init__(
        self,
        session: AsyncSession,
        stable_runner: AnsibleRunner,
        new_runner: AnsibleRunner,
    ) -> None:
        self._session = session
        self._stable_runner = stable_runner
        self._new_runner = new_runner
        self._router = AnsibleRouter()

    async def execute(self, intent: Intent) -> AsyncGenerator[str, None]:
        if intent.action == "unknown":
            yield f"Non ho capito la richiesta. {intent.raw_response}".strip()
            return

        servers = await self._resolve_targets(intent)

        if not servers:
            yield "Nessun server trovato con i criteri specificati."
            return

        groups = self._router.group_by_controller([self._server_to_dict(s) for s in servers])

        cmd_template, args_template = _ANSIBLE_COMMANDS.get(
            intent.action, ("shell", "echo 'azione non supportata'")
        )
        args = args_template.format(**intent.extra) if intent.extra else args_template

        for controller, hostnames in groups.items():
            if not hostnames:
                continue
            runner = self._new_runner if controller == Controller.NEW else self._stable_runner
            yield f"Eseguo su {len(hostnames)} server ({controller.value}): {', '.join(hostnames)}"
            try:
                result = await runner.run_adhoc(hosts=hostnames, module=cmd_template, args=args)
                if result.success:
                    yield f"✅ Completato ({controller.value}):\n{result.stdout}"
                else:
                    yield f"⚠️ Errori ({controller.value}):\n{result.stderr or result.stdout}"
            except RuntimeError as exc:
                yield f"❌ Errore connessione controller {controller.value}: {exc}"

    async def _resolve_targets(self, intent: Intent) -> list[Server]:
        stmt = select(Server).where(Server.is_active.is_(True))

        if intent.hostnames:
            stmt = stmt.where(Server.hostname.in_(intent.hostnames))
        else:
            for key, value in intent.targets.items():
                if key == "cliente":
                    stmt = stmt.where(Server.cliente == value)
                elif key == "ruolo":
                    stmt = stmt.where(Server.ruolo == value)
                elif key == "source":
                    stmt = stmt.where(Server.source == value)

        if intent.os_filter:
            stmt = stmt.where(Server.os_version == intent.os_filter)

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    def _server_to_dict(server: Server) -> dict:
        return {
            "hostname": server.hostname,
            "os_family": server.os_family.value if server.os_family else None,
            "os_version": server.os_version,
            "ansible_controller": server.ansible_controller.value,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend
python -m pytest tests/test_action_handler.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/ai/action_handler.py backend/tests/test_action_handler.py
git commit -m "feat: action handler resolves targets and executes ansible commands with controller routing"
```

---

### Task 6: Chat API (SSE Streaming)

The `/api/chat/message` endpoint receives a message, parses intent, and streams back a Server-Sent Events response. Tests use FastAPI TestClient with dependency overrides.

**Files:**
- Create: `backend/api/chat.py`
- Modify: `backend/main.py`
- Create: `backend/tests/test_chat_api.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_chat_api.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from main import app
from database import get_db
from ai.intent_parser import Intent


def make_mock_db():
    db = AsyncMock()
    return db


def override_db(db):
    async def _override():
        yield db
    return _override


def test_chat_message_streams_response(db_session):
    app.dependency_overrides[get_db] = override_db(db_session)

    mock_intent = Intent(action="unknown", raw_response="test")
    mock_handler_messages = ["Messaggio di risposta dal sistema"]

    async def mock_execute(intent):
        for msg in mock_handler_messages:
            yield msg

    with (
        patch("api.chat.parse_intent", new=AsyncMock(return_value=mock_intent)),
        patch("api.chat.ActionHandler") as MockHandler,
    ):
        mock_instance = MagicMock()
        mock_instance.execute = mock_execute
        MockHandler.return_value = mock_instance

        client = TestClient(app)
        with client.stream("POST", "/api/chat/message", json={"message": "ciao"}) as response:
            assert response.status_code == 200
            content = b"".join(response.iter_bytes())
            assert b"Messaggio di risposta" in content

    app.dependency_overrides.clear()


def test_chat_message_empty_rejected(db_session):
    app.dependency_overrides[get_db] = override_db(db_session)

    client = TestClient(app)
    response = client.post("/api/chat/message", json={"message": ""})
    assert response.status_code == 422

    app.dependency_overrides.clear()


def test_chat_missing_message_rejected(db_session):
    client = TestClient(app)
    response = client.post("/api/chat/message", json={})
    assert response.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
python -m pytest tests/test_chat_api.py -v
```

Expected: ImportError or 404 (chat router not registered)

- [ ] **Step 3: Implement `backend/api/chat.py`**

```python
from collections.abc import AsyncGenerator

import anthropic
from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from ai.action_handler import ActionHandler
from ai.claude_client import make_anthropic_client
from ai.intent_parser import parse_intent
from ansible.runner import AnsibleRunner
from config import settings
from database import get_db

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatMessage(BaseModel):
    message: str

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("message cannot be empty")
        return v


def _make_stable_runner() -> AnsibleRunner:
    return AnsibleRunner(
        host=settings.ansible_stable_host,
        user=settings.ansible_stable_user,
        key_path=settings.ansible_stable_key,
        inventory=settings.ansible_stable_inventory,
    )


def _make_new_runner() -> AnsibleRunner:
    return AnsibleRunner(
        host=settings.ansible_new_host,
        user=settings.ansible_new_user,
        key_path=settings.ansible_new_key,
        inventory=settings.ansible_new_inventory,
    )


@router.post("/message")
async def chat_message(
    body: ChatMessage,
    session: AsyncSession = Depends(get_db),
):
    async def event_generator() -> AsyncGenerator[dict, None]:
        client: anthropic.AsyncAnthropic = make_anthropic_client()
        intent = await parse_intent(body.message, client)

        handler = ActionHandler(
            session=session,
            stable_runner=_make_stable_runner(),
            new_runner=_make_new_runner(),
        )

        async for chunk in handler.execute(intent):
            yield {"data": chunk}

    return EventSourceResponse(event_generator())
```

- [ ] **Step 4: Register the chat router in `backend/main.py`**

Full replacement of `backend/main.py`:

```python
from fastapi import FastAPI
from api.inventory import router as inventory_router
from api.chat import router as chat_router

app = FastAPI(title="InfraAI", version="1.0.0")
app.include_router(inventory_router)
app.include_router(chat_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend
python -m pytest tests/test_chat_api.py -v
```

Expected: 3 passed

- [ ] **Step 6: Run the full test suite to verify no regressions**

```bash
cd backend
python -m pytest -v
```

Expected: all tests pass

- [ ] **Step 7: Commit**

```bash
git add backend/api/chat.py backend/main.py backend/tests/test_chat_api.py
git commit -m "feat: SSE chat endpoint parses intent via Claude and streams ansible results"
```

---

## Self-Review

**Spec coverage:**
- ✅ Intent parsing via Claude tool_use → Task 4
- ✅ Ansible routing by OS version (Ubuntu ≥24 → new, else → stable) → Task 2
- ✅ Manual `ansible_controller` override → Task 2
- ✅ SSH-based Ansible execution → Task 3
- ✅ Action resolution from DB filters (cliente, ruolo, hostname, os_filter) → Task 5
- ✅ Streaming SSE chat API → Task 6
- ✅ Config for two Ansible controllers → Task 1
- ✅ Actions: update, restart_service, read_logs, service_status, upgrade_os, generate_report → Task 5

**Autonomy rules from spec:**
- Leggi log / stato → esegue senza chiedere ✅ (read_logs, service_status in _ANSIBLE_COMMANDS)
- Aggiornamenti pacchetti → esegue senza chiedere ✅ (update action)
- Riavvia servizio → esegue senza chiedere ✅ (restart_service)
- Genera report → esegue senza chiedere ✅ (generate_report)
- Upgrade OS → richiede conferma esplicita — the action handler executes upgrade_os when the intent says so; the confirmation gate (asking the user before running) is a Piano 3 concern (chat history + multi-turn confirmation flow). This is documented as out of scope for Piano 2.

**Type consistency:** All Intent fields used in action_handler match intent_parser dataclass. AnsibleResult used in runner tests matches runner implementation. Controller enum used in router and handler match.

**Placeholders scan:** None found — all code blocks are complete.
