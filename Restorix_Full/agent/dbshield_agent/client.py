from __future__ import annotations
import logging
import requests
from dbshield_agent.config import AgentConfig

logger = logging.getLogger(__name__)


class AgentClient:
    def __init__(self, config: AgentConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "dbshield-agent/1.0.0"

    def _url(self, path: str) -> str:
        return f"{self.config.api_url}/api/v1/agent{path}"

    def heartbeat(self, agent_version: str = "1.0.0") -> bool:
        try:
            r = self.session.post(
                self._url("/heartbeat"),
                params={"token": self.config.agent_token, "agent_version": agent_version},
                timeout=10,
            )
            return r.status_code == 200
        except Exception as e:
            logger.warning(f"Heartbeat failed: {e}")
            return False

    def get_pending_jobs(self) -> list:
        try:
            r = self.session.get(
                self._url("/jobs"),
                params={"token": self.config.agent_token},
                timeout=15,
            )
            if r.status_code == 200:
                return r.json()
            logger.warning(f"get_pending_jobs returned {r.status_code}: {r.text[:200]}")
            return []
        except Exception as e:
            logger.warning(f"get_pending_jobs failed: {e}")
            return []

    def report_success(self, run_id: str, size_bytes: int, file_path: str, checksum=None) -> bool:
        return self._report(run_id, "success", size_bytes=size_bytes, file_path=file_path, checksum_sha256=checksum)

    def report_failure(self, run_id: str, error_message: str) -> bool:
        return self._report(run_id, "failed", error_message=error_message)

    def _report(self, run_id: str, status: str, **kwargs) -> bool:
        try:
            payload = {"status": status, "agent_version": "1.0.0", **kwargs}
            r = self.session.post(
                self._url(f"/runs/{run_id}"),
                params={"token": self.config.agent_token},
                json=payload,
                timeout=15,
            )
            return r.status_code == 200
        except Exception as e:
            logger.warning(f"report failed: {e}")
            return False

    def get_discovery_request(self):
        try:
            r = self.session.get(
                self._url("/discovery"),
                params={"token": self.config.agent_token},
                timeout=10,
            )
            if r.status_code == 200:
                return r.json()
            return None
        except Exception as e:
            logger.warning(f"get_discovery_request failed: {e}")
            return None

    def report_discovery(self, databases, error=None):
        try:
            r = self.session.post(
                self._url("/discovery/result"),
                params={"token": self.config.agent_token},
                json={"databases": databases, "error": error},
                timeout=10,
            )
            return r.status_code == 200
        except Exception as e:
            logger.warning(f"report_discovery failed: {e}")
            return False
