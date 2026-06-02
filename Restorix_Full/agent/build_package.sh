#!/usr/bin/env bash
# Build dbshield-agent-1.0.0.tar.gz for distribution
set -e
cd /opt/MSSQL_GUI/agent
pip3 install build --quiet 2>/dev/null || true
python3 setup.py sdist --dist-dir /tmp/dbshield_dist 2>/dev/null
echo "Built: $(ls /tmp/dbshield_dist/*.tar.gz)"
