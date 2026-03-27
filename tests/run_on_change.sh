#!/bin/bash
# Hook script: run pytest when a .py or .html file is edited
FILE=$(jq -r '.tool_input.file_path // .tool_response.filePath // empty')
if echo "$FILE" | grep -qE '\.(py|html)$'; then
  cd /Users/nealmulnick/Library/CloudStorage/Dropbox/AI/Claude/Ford
  python3 -m pytest tests/ -q --tb=line 2>&1
fi
