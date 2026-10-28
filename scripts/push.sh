#!/usr/bin/env bash
# Push a zundamon phrase slug to the standby page via the state spreadsheet.
# Usage: ZUNDAMON_SHEET_ID=<your sheet id> ./push.sh <slug>
#
# seq source of truth is the sheet itself (cell A2 of the first sheet):
# read the current value and write back +1, so VM restarts, new machines
# and multiple chats never rewind the counter. If the read fails, fall
# back to epoch milliseconds (always larger than small counters, which is
# all the standby page's `seq > lastSeq` check needs).
# Ranges omit the sheet name on purpose: the API then targets the first
# sheet, whatever its locale name is.
#
# Requires a Sheets writer CLI as $SHEETS_CLI (default: hatch_gws_cli).
# No such CLI? Use push_webapp.py + apps_script.gs instead (see INSTALL.md).
set -euo pipefail
SID="${ZUNDAMON_SHEET_ID:?set ZUNDAMON_SHEET_ID}"
SLUG="${1:?slug required}"
CLI="${SHEETS_CLI:-/opt/hatch/bin/hatch_gws_cli}"
CUR=$($CLI sheets spreadsheets values get --params "{\"spreadsheetId\":\"$SID\",\"range\":\"A2\"}" 2>/dev/null | python3 -c 'import sys, json; d = json.load(sys.stdin); print(int(d.get("values", [[0]])[0][0]))' 2>/dev/null || true)
if [ -n "${CUR:-}" ]; then NEWSEQ=$((CUR + 1)); else NEWSEQ=$(date +%s%3N); fi
TS=$(date '+%Y-%m-%d %H:%M:%S')
$CLI sheets spreadsheets values update --params "{\"spreadsheetId\":\"$SID\",\"range\":\"A2:C2\",\"valueInputOption\":\"RAW\"}" --json "{\"values\":[[\"$NEWSEQ\",\"$SLUG\",\"$TS\"]]}" > /dev/null
echo "pushed seq=$NEWSEQ slug=$SLUG at $TS"
