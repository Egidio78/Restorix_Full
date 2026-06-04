#!/bin/bash
# Build a versioned agent release tarball.
# Usage: ./scripts/build_agent_release.sh 1.4.1
set -e
VERSION="$1"
if [ -z "$VERSION" ]; then
  echo "Usage: $0 <version>" >&2
  exit 1
fi
OUT_DIR="agent_releases"
TARBALL="$OUT_DIR/dbshield-agent-$VERSION.tar.gz"
mkdir -p "$OUT_DIR"
tar -czf "$TARBALL" -C agent dbshield_agent dbshield-agent.service install.sh 2>/dev/null \
  || tar -czf "$TARBALL" -C agent dbshield_agent install.sh
sha256sum "$TARBALL" | awk '{print $1}' > "$TARBALL.sha256"
echo "Created $TARBALL (sha256: $(cat $TARBALL.sha256))"
