// Zundamon talk kit - Apps Script Web App receiver (portable push channel).
// Setup: open your state spreadsheet -> Extensions -> Apps Script, paste this
// file, Deploy -> Web app (execute as: Me, access: Anyone). Copy the Web App
// URL into ZUNDAMON_WEBAPP_URL and push with scripts/push_webapp.py.
// The spreadsheet is the seq source of truth here too: A2 is read and +1'd
// under a lock, so concurrent pushes cannot collide.
function doPost(e) {
  var lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    var body = JSON.parse(e.postData.contents || "{}");
    var slug = String(body.slug || "");
    if (!slug) throw new Error("slug required");
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheets()[0];
    var cur = Number(sheet.getRange("A2").getValue()) || 0;
    var seq = cur + 1;
    var ts = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd HH:mm:ss");
    sheet.getRange("A2:C2").setValues([[seq, slug, ts]]);
    return ContentService.createTextOutput(JSON.stringify({ ok: true, seq: seq, slug: slug }))
      .setMimeType(ContentService.MimeType.JSON);
  } finally {
    lock.releaseLock();
  }
}
