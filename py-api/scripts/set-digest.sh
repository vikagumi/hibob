#!/usr/bin/env bash
set -euo pipefail

FILE=$1
DIGEST=$2

# Replace the 'digest:' line, keeping indentation
sed -E -i.bak 's/^([[:space:]]*digest:).*/\1 "'"$DIGEST"'"/' "$FILE"
rm -f "$FILE.bak"