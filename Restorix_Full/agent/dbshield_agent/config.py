from __future__ import annotations
import json
import os
from dataclasses import dataclass

DEFAULT_CONFIG_PATH = "/etc/dbshield-agent/config.json"


@dataclass
class AgentConfig:
    api_url: str
    agent_token: str
    poll_interval_seconds: int = 30
    log_level: str = "INFO"
    temp_dir: str = "/tmp/dbshield"


def load_config(path: str = DEFAULT_CONFIG_PATH) -> AgentConfig:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path) as f:
        data = json.load(f)
    return AgentConfig(
        api_url=data["api_url"].rstrip("/"),
        agent_token=data["agent_token"],
        poll_interval_seconds=data.get("poll_interval_seconds", 30),
        log_level=data.get("log_level", "INFO"),
        temp_dir=data.get("temp_dir", "/tmp/dbshield"),
    )
