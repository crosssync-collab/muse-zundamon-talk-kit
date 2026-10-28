#!/usr/bin/env bash
# Push a zundamon phrase slug to the standby page via the state spreadsheet.
# Usage: ZUNDAMON_SHEET_ID=<your sheet id> ./push.sh <slug>
# Requires the Google Sheets connector CLI (hatch_gws_cli) on PATH as $SHEETS_CLI.
set -euo pipefail
SID="${ZUNDAMON_SHEET_ID:?set ZUNDAMON_SHEET_ID}"
SLUG="${1:?slug required}"
CLI="${SHEETS_CLI:-/opt/hatch/bin/hatch_gws_cli}"
SEQFILE="${ZUNDAMON_SEQ_FILE:-$HOME/workspace/zundamon-speaker/seq.txt}"
if [ -f "$SEQFILE" ]; then SEQ=$(cat "$SEQFILE"); else SEQ=0; fi
NEWSEQ=$((SEQ+1))
TS=$(date '+%Y-%m-%d %H:%M:%S')
$CLI sheets spreadsheets values update --params "{\"spreadsheetId\":\"$SID\",\"range\":\"シート1!A2:C2\",\"valueInputOption\":\"RAW\"}" --json "{\"values\":[[\"$NEWSEQ\",\"$SLUG\",\"$TS\"]]}" > /dev/null
echo "$NEWSEQ" > "$SEQFILE"
echo "pushed seq=$NEWSEQ slug=$SLUG at $TS"
