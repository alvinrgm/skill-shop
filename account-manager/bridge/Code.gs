// ===========================================
// Document Bridge — Google Apps Script (Docs/Sheets/Slides/Drive)
// ===========================================
// Deploy this as a Web App in Google Apps Script. It lets an automated client
// (e.g. the account-manager runtime / deck engine) natively create and edit
// Google Docs, Sheets, Slides, and Drive files that the deploying account owns
// — no per-file sharing dance, no browser in the loop.
//
// SECURITY: Every request must include a shared secret passphrase. Even if
// someone discovers the URL, they can't do anything without the passphrase.
// SET YOUR OWN SECRET below before deploying, and never commit it anywhere
// public. The same value goes into your `.env` as the bridge secret.
//
// Full deploy walkthrough: see bridge/SETUP.md.
// ===========================================

// >>> SET YOUR OWN SECRET HERE before deploying (any long random string). <<<
// The exec URL you get on deploy + this secret go into your .env as the
// bridge URL and bridge secret. Treat the pair like a credential.
const SECRET = 'CHANGE-ME-set-your-own-long-random-secret';

// --- MAIN REQUEST HANDLER ---

function doPost(e) {
  try {
    const payload = JSON.parse(e.postData.contents);

    // Auth check — every request must include the secret
    if (payload.secret !== SECRET) {
      return ContentService
        .createTextOutput(JSON.stringify({ error: 'Unauthorized. Invalid or missing secret.' }))
        .setMimeType(ContentService.MimeType.JSON);
    }

    const action = payload.action;

    let result;
    switch (action) {
      case 'create_doc':
        result = createDoc(payload);
        break;
      case 'update_doc':
        result = updateDoc(payload);
        break;
      case 'read_doc':
        result = readDoc(payload);
        break;
      case 'read_comments':
        result = readComments(payload);
        break;
      case 'create_comment':
        result = createComment(payload);
        break;
      case 'reply_comment':
        result = replyComment(payload);
        break;
      case 'resolve_comment':
        result = resolveComment(payload);
        break;
      case 'delete_comment':
        result = deleteComment(payload);
        break;
      case 'create_sheet':
        result = createSheet(payload);
        break;
      case 'update_sheet':
        result = updateSheet(payload);
        break;
      case 'read_sheet':
        result = readSheet(payload);
        break;
      case 'find_row':
        result = findRow(payload);
        break;
      // --- Drive file management (delete / move / rename / copy / list / share) ---
      case 'delete_file':
        result = deleteFile(payload);
        break;
      case 'move_file':
        result = moveFile(payload);
        break;
      case 'rename_file':
        result = renameFile(payload);
        break;
      case 'copy_file':
        result = copyFile(payload);
        break;
      case 'list_files':
        result = listFiles(payload);
        break;
      case 'file_info':
        result = fileInfo(payload);
        break;
      case 'share_file':
        result = shareFile(payload);
        break;
      // --- Docs surgical editing ---
      case 'doc_find_replace':
        result = docFindReplace(payload);
        break;
      case 'doc_insert_image':
        result = docInsertImage(payload);
        break;
      // --- Sheets richer ops (range write / format / tabs / structure) ---
      case 'sheet_write_range':
        result = sheetWriteRange(payload);
        break;
      case 'sheet_clear_range':
        result = sheetClearRange(payload);
        break;
      case 'sheet_format':
        result = sheetFormat(payload);
        break;
      case 'sheet_freeze':
        result = sheetFreeze(payload);
        break;
      case 'add_tab':
        result = addTab(payload);
        break;
      case 'delete_tab':
        result = deleteTab(payload);
        break;
      case 'rename_tab':
        result = renameTab(payload);
        break;
      // --- Generic escape hatch: any Docs/Sheets/Drive/Slides REST method ---
      case 'google_api':
        result = googleApi(payload);
        break;
      default:
        result = { error: 'Unknown action: ' + action };
    }

    return ContentService
      .createTextOutput(JSON.stringify(result))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({ error: err.message }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

// GET returns nothing useful — no info leakage
function doGet(e) {
  return ContentService
    .createTextOutput(JSON.stringify({ status: 'ok' }))
    .setMimeType(ContentService.MimeType.JSON);
}

// --- GOOGLE DOCS ---

// --- RICH RENDERING HELPERS (shared by createDoc + updateDoc) ---
//
// Block types supported:
//   { type: 'heading1' | 'heading2' | 'heading3', text | runs }
//   { type: 'paragraph', text | runs, align?: 'LEFT'|'CENTER'|'RIGHT' }
//   { type: 'bullet'  | 'numbered', text | runs, nesting?: 0-3 }
//   { type: 'divider' }
//   { type: 'table',  rows: [[cell, ...], ...], headerRow?: bool, headerBg?: '#hex' }
//        cell can be a plain string, or { text | runs, bold?, italic?, color?, bg? }
//   { type: 'callout', text | runs, bg?: '#hex' }   — a single-cell shaded block
//
// 'runs' lets you mix formatting in one paragraph:
//   runs: [
//     { text: 'Hook (first 2s): ', bold: true },
//     { text: 'macro shot of the bag stamp.' }
//   ]
// Each run supports: text, bold, italic, color (hex), link (url), size (pt).

function renderBlocks_(body, blocks) {
  for (var i = 0; i < blocks.length; i++) {
    renderBlock_(body, blocks[i]);
  }
}

function renderBlock_(body, block) {
  if (!block || !block.type) {
    return;
  }
  switch (block.type) {
    case 'heading1':
    case 'heading2':
    case 'heading3': {
      var hMap = {
        heading1: DocumentApp.ParagraphHeading.HEADING1,
        heading2: DocumentApp.ParagraphHeading.HEADING2,
        heading3: DocumentApp.ParagraphHeading.HEADING3
      };
      var hPara = body.appendParagraph('');
      hPara.setHeading(hMap[block.type]);
      applyRuns_(hPara, block);
      break;
    }
    case 'bullet':
    case 'numbered': {
      var glyph = block.type === 'numbered'
        ? DocumentApp.GlyphType.NUMBER
        : DocumentApp.GlyphType.BULLET;
      var item = body.appendListItem('');
      item.setGlyphType(glyph);
      if (typeof block.nesting === 'number') {
        item.setNestingLevel(block.nesting);
      }
      applyRuns_(item, block);
      break;
    }
    case 'divider':
      body.appendHorizontalRule();
      break;
    case 'table': {
      var rows = block.rows || [];
      // Build a 2D string array first (Apps Script requires this for appendTable)
      var stringRows = rows.map(function (row) {
        return row.map(function (cell) {
          if (typeof cell === 'string') return cell;
          if (cell && cell.runs) return cell.runs.map(function (r) { return r.text || ''; }).join('');
          if (cell && cell.text != null) return cell.text;
          return '';
        });
      });
      var table = body.appendTable(stringRows);
      // Re-style each cell if it had formatting
      for (var r = 0; r < rows.length; r++) {
        for (var c = 0; c < rows[r].length; c++) {
          var cellSpec = rows[r][c];
          if (typeof cellSpec === 'object' && cellSpec !== null) {
            var tableCell = table.getCell(r, c);
            if (cellSpec.bg) tableCell.setBackgroundColor(cellSpec.bg);
            if (cellSpec.runs || cellSpec.bold || cellSpec.italic || cellSpec.color) {
              tableCell.clear();
              var cellPara = tableCell.appendParagraph('');
              applyRuns_(cellPara, cellSpec);
            }
          }
        }
      }
      // Header row styling
      if (block.headerRow && rows.length > 0) {
        var headerBg = block.headerBg || '#D94127'; // default header fill (override via headerBg)
        var headerFg = block.headerFg || '#FFFFFF';
        for (var hc = 0; hc < rows[0].length; hc++) {
          var hCell = table.getCell(0, hc);
          hCell.setBackgroundColor(headerBg);
          var hChild = hCell.getChild(0);
          if (hChild && hChild.editAsText) {
            var hTxt = hChild.editAsText();
            var hLen = hTxt.getText().length;
            if (hLen > 0) {
              hTxt.setBold(0, hLen - 1, true);
              hTxt.setForegroundColor(0, hLen - 1, headerFg);
            }
          }
        }
      }
      break;
    }
    case 'callout': {
      // Single-cell shaded block — useful for highlighting key benefits or guardrails
      var coTable = body.appendTable([['']]);
      var coCell = coTable.getCell(0, 0);
      coCell.setBackgroundColor(block.bg || '#FBF3E2'); // cream default
      coCell.clear();
      var coPara = coCell.appendParagraph('');
      applyRuns_(coPara, block);
      break;
    }
    case 'paragraph':
    default: {
      var pPara = body.appendParagraph('');
      pPara.setHeading(DocumentApp.ParagraphHeading.NORMAL);
      if (block.align) {
        var alignMap = {
          LEFT: DocumentApp.HorizontalAlignment.LEFT,
          CENTER: DocumentApp.HorizontalAlignment.CENTER,
          RIGHT: DocumentApp.HorizontalAlignment.RIGHT
        };
        if (alignMap[block.align]) pPara.setAlignment(alignMap[block.align]);
      }
      applyRuns_(pPara, block);
      break;
    }
  }
}

function applyRuns_(paraOrItem, block) {
  // Accept either runs:[{text,bold,italic,color,link,size}] or plain block.text
  var runs;
  if (block.runs && block.runs.length) {
    runs = block.runs;
  } else if (block.text !== undefined && block.text !== null) {
    runs = [{
      text: block.text,
      bold: block.bold,
      italic: block.italic,
      color: block.color,
      link: block.link,
      size: block.size
    }];
  } else {
    return;
  }

  // Assemble full string + offset table
  var fullText = '';
  var offsets = [];
  for (var i = 0; i < runs.length; i++) {
    var t = runs[i].text || '';
    offsets.push({ start: fullText.length, end: fullText.length + t.length - 1, run: runs[i] });
    fullText += t;
  }
  if (!fullText) return;

  paraOrItem.setText(fullText);
  var txt = paraOrItem.editAsText();

  for (var j = 0; j < offsets.length; j++) {
    var o = offsets[j];
    if (o.end < o.start) continue;
    var run = o.run;
    if (run.bold)          txt.setBold(o.start, o.end, true);
    if (run.italic)        txt.setItalic(o.start, o.end, true);
    if (run.strikethrough) txt.setStrikethrough(o.start, o.end, true);
    if (run.color)         txt.setForegroundColor(o.start, o.end, run.color);
    if (run.bg)            txt.setBackgroundColor(o.start, o.end, run.bg);
    if (run.link)          txt.setLinkUrl(o.start, o.end, run.link);
    if (run.size)          txt.setFontSize(o.start, o.end, run.size);
  }
}

function createDoc(payload) {
  // payload: { title, content (plain text) | contentBlocks (rich blocks), folderId? }
  // See renderBlocks_ above for the supported block schema.
  const doc = DocumentApp.create(payload.title || 'Untitled Doc');
  const body = doc.getBody();

  // Clear default empty paragraph
  body.clear();

  if (payload.contentBlocks) {
    renderBlocks_(body, payload.contentBlocks);
  } else if (payload.content) {
    // Plain text content — just dump it in
    body.appendParagraph(payload.content);
  }

  // Move to folder if specified
  if (payload.folderId) {
    try {
      const folder = DriveApp.getFolderById(payload.folderId);
      const file = DriveApp.getFileById(doc.getId());
      folder.addFile(file);
      DriveApp.getRootFolder().removeFile(file);
    } catch (e) {
      // Folder move failed, doc stays in root — not a big deal
    }
  }

  doc.saveAndClose();

  return {
    success: true,
    docId: doc.getId(),
    url: doc.getUrl(),
    title: doc.getName()
  };
}

function updateDoc(payload) {
  // payload: { docId, contentBlocks? (replaces body), appendBlocks? (adds to end) }
  // Both use the rich block schema documented above renderBlocks_.
  const doc = DocumentApp.openById(payload.docId);
  const body = doc.getBody();

  if (payload.contentBlocks) {
    body.clear();
    renderBlocks_(body, payload.contentBlocks);
  }
  if (payload.appendBlocks) {
    renderBlocks_(body, payload.appendBlocks);
  }

  doc.saveAndClose();

  return {
    success: true,
    docId: doc.getId(),
    url: doc.getUrl()
  };
}

function readDoc(payload) {
  // payload: { docId }
  const doc = DocumentApp.openById(payload.docId);
  const body = doc.getBody();
  const text = body.getText();

  return {
    success: true,
    docId: doc.getId(),
    title: doc.getName(),
    text: text,
    url: doc.getUrl()
  };
}

function readComments(payload) {
  // payload: { docId, includeResolved? (default false) }
  // Uses Drive v3 REST API via UrlFetchApp + ScriptApp OAuth token.
  // Returns: { success, comments: [{author, text, quoted, resolved, replies:[], createdTime, id}] }
  const docId = payload.docId;
  const includeResolved = payload.includeResolved === true;

  const url = 'https://www.googleapis.com/drive/v3/files/' + encodeURIComponent(docId)
    + '/comments?fields=' + encodeURIComponent('comments(id,author/displayName,content,quotedFileContent/value,resolved,createdTime,replies(id,author/displayName,content,createdTime))')
    + '&pageSize=100&includeDeleted=false';

  const resp = UrlFetchApp.fetch(url, {
    method: 'get',
    headers: { Authorization: 'Bearer ' + ScriptApp.getOAuthToken() },
    muteHttpExceptions: true
  });

  const code = resp.getResponseCode();
  if (code !== 200) {
    return { error: 'Drive API error ' + code + ': ' + resp.getContentText() };
  }

  const data = JSON.parse(resp.getContentText());
  const out = [];
  for (var i = 0; i < (data.comments || []).length; i++) {
    var c = data.comments[i];
    if (!includeResolved && c.resolved) continue;
    out.push({
      id: c.id,
      author: (c.author && c.author.displayName) || 'unknown',
      text: c.content || '',
      quoted: (c.quotedFileContent && c.quotedFileContent.value) || '',
      resolved: !!c.resolved,
      createdTime: c.createdTime || '',
      replies: (c.replies || []).map(function (r) {
        return {
          author: (r.author && r.author.displayName) || 'unknown',
          text: r.content || '',
          createdTime: r.createdTime || ''
        };
      })
    });
  }

  return { success: true, docId: docId, count: out.length, comments: out };
}

// ===========================================
// COMMENTS — create / reply / resolve / delete
// Drive REST API (comments + replies), on the already-granted `drive` scope
// (same as read_comments) — so no re-auth. Does what you'd do in the comment pane.
//
// NOTE on anchoring: file-level (general) comments are reliable. Anchoring a NEW
// comment to a specific text range is not reliably supported by the public Drive
// API for Docs — so to "comment on X", quote X in `content` (e.g. "Re: '<quote>' …"),
// or reply to an existing (already-anchored) comment. Replies/resolves are exact.
// (Also: the Docs API cannot CREATE tracked "Suggesting"-mode edits — only direct
// edits. Direct edits + comments cover everything else.)
// ===========================================

function driveCommentRequest_(method, path, body) {
  var options = {
    method: method,
    headers: { Authorization: 'Bearer ' + ScriptApp.getOAuthToken() },
    muteHttpExceptions: true
  };
  if (body) { options.contentType = 'application/json'; options.payload = JSON.stringify(body); }
  var resp = UrlFetchApp.fetch('https://www.googleapis.com' + path, options);
  var code = resp.getResponseCode();
  var text = resp.getContentText();
  var parsed;
  try { parsed = JSON.parse(text); } catch (e) { parsed = text; }
  return { code: code, body: parsed };
}

function createComment(payload) {
  // payload: { docId|fileId, content }  — a file-level comment
  var fileId = payload.fileId || payload.docId;
  if (!fileId || !payload.content) return { error: 'fileId/docId and content are required' };
  var r = driveCommentRequest_('post',
    '/drive/v3/files/' + encodeURIComponent(fileId) + '/comments?fields=' +
    encodeURIComponent('id,content,author/displayName,createdTime'),
    { content: payload.content });
  if (r.code < 200 || r.code >= 300) return { error: 'createComment failed ' + r.code + ': ' + JSON.stringify(r.body) };
  return { success: true, fileId: fileId, commentId: r.body.id, content: r.body.content };
}

function replyComment(payload) {
  // payload: { docId|fileId, commentId, content?, resolve?, reopen? }
  var fileId = payload.fileId || payload.docId;
  if (!fileId || !payload.commentId) return { error: 'fileId/docId and commentId are required' };
  var body = {};
  if (payload.content != null) body.content = payload.content;
  if (payload.resolve === true) body.action = 'resolve';
  else if (payload.reopen === true) body.action = 'reopen';
  if (body.content == null && !body.action) return { error: 'Provide content and/or resolve/reopen' };
  // A resolve/reopen reply still wants non-empty content in the UI — default it.
  if (body.action && body.content == null) body.content = (body.action === 'resolve') ? 'Resolved.' : 'Reopened.';
  var r = driveCommentRequest_('post',
    '/drive/v3/files/' + encodeURIComponent(fileId) + '/comments/' + encodeURIComponent(payload.commentId) +
    '/replies?fields=' + encodeURIComponent('id,content,action,author/displayName,createdTime'),
    body);
  if (r.code < 200 || r.code >= 300) return { error: 'replyComment failed ' + r.code + ': ' + JSON.stringify(r.body) };
  return { success: true, fileId: fileId, commentId: payload.commentId, replyId: r.body.id,
    action: r.body.action || null, content: r.body.content };
}

function resolveComment(payload) {
  // convenience: { docId|fileId, commentId, content? } — replies with action:resolve
  payload.resolve = true;
  return replyComment(payload);
}

function deleteComment(payload) {
  // payload: { docId|fileId, commentId }
  var fileId = payload.fileId || payload.docId;
  if (!fileId || !payload.commentId) return { error: 'fileId/docId and commentId are required' };
  var r = driveCommentRequest_('delete',
    '/drive/v3/files/' + encodeURIComponent(fileId) + '/comments/' + encodeURIComponent(payload.commentId), null);
  if (r.code !== 204 && r.code !== 200) return { error: 'deleteComment failed ' + r.code + ': ' + JSON.stringify(r.body) };
  return { success: true, fileId: fileId, deletedCommentId: payload.commentId };
}

// --- GOOGLE SHEETS ---

function createSheet(payload) {
  // payload: { title, sheets: [{ name, data: [[row1col1, row1col2], [row2col1, row2col2]] }] }
  const ss = SpreadsheetApp.create(payload.title || 'Untitled Sheet');

  if (payload.sheets && payload.sheets.length > 0) {
    for (let i = 0; i < payload.sheets.length; i++) {
      const sheetDef = payload.sheets[i];
      let sheet;

      if (i === 0) {
        // Rename the default sheet
        sheet = ss.getSheets()[0];
        sheet.setName(sheetDef.name);
      } else {
        sheet = ss.insertSheet(sheetDef.name);
      }

      if (sheetDef.data && sheetDef.data.length > 0) {
        const range = sheet.getRange(1, 1, sheetDef.data.length, sheetDef.data[0].length);
        range.setValues(sheetDef.data);

        // Bold the header row
        if (sheetDef.data.length > 1) {
          sheet.getRange(1, 1, 1, sheetDef.data[0].length).setFontWeight('bold');
        }

        // Auto-resize columns
        for (let c = 1; c <= sheetDef.data[0].length; c++) {
          sheet.autoResizeColumn(c);
        }
      }
    }
  }

  return {
    success: true,
    spreadsheetId: ss.getId(),
    url: ss.getUrl(),
    title: ss.getName()
  };
}

function updateSheet(payload) {
  // payload: { spreadsheetId, sheetName, data (replaces all), appendRows (adds to end), updateCell: {row, col, value} }
  const ss = SpreadsheetApp.openById(payload.spreadsheetId);
  const sheet = ss.getSheetByName(payload.sheetName);

  if (!sheet) {
    return { error: 'Sheet not found: ' + payload.sheetName };
  }

  if (payload.data) {
    sheet.clear();
    if (payload.data.length > 0) {
      sheet.getRange(1, 1, payload.data.length, payload.data[0].length).setValues(payload.data);
      sheet.getRange(1, 1, 1, payload.data[0].length).setFontWeight('bold');
    }
  }

  if (payload.appendRows) {
    for (const row of payload.appendRows) {
      sheet.appendRow(row);
    }
  }

  if (payload.updateCell) {
    sheet.getRange(payload.updateCell.row, payload.updateCell.col).setValue(payload.updateCell.value);
  }

  return {
    success: true,
    spreadsheetId: ss.getId(),
    url: ss.getUrl()
  };
}

// --- GOOGLE SHEETS (READ) ---

function readSheet(payload) {
  // payload: { spreadsheetId, sheetName, range (optional, e.g. "A1:H10") }
  const ss = SpreadsheetApp.openById(payload.spreadsheetId);
  const sheet = ss.getSheetByName(payload.sheetName);

  if (!sheet) {
    return { error: 'Sheet not found: ' + payload.sheetName };
  }

  let data;
  if (payload.range) {
    data = sheet.getRange(payload.range).getValues();
  } else {
    // Return all data (up to last row/col with content)
    const lastRow = sheet.getLastRow();
    const lastCol = sheet.getLastColumn();
    if (lastRow === 0 || lastCol === 0) {
      return { success: true, spreadsheetId: ss.getId(), sheetName: payload.sheetName, data: [], headers: [] };
    }
    data = sheet.getRange(1, 1, lastRow, lastCol).getValues();
  }

  return {
    success: true,
    spreadsheetId: ss.getId(),
    sheetName: payload.sheetName,
    headers: data.length > 0 ? data[0] : [],
    data: data,
    rowCount: data.length,
    url: ss.getUrl()
  };
}

function findRow(payload) {
  // payload: { spreadsheetId, sheetName, searchCol (1-indexed), searchValue }
  // Returns the first row where searchCol matches searchValue (case-insensitive partial match)
  const ss = SpreadsheetApp.openById(payload.spreadsheetId);
  const sheet = ss.getSheetByName(payload.sheetName);

  if (!sheet) {
    return { error: 'Sheet not found: ' + payload.sheetName };
  }

  const lastRow = sheet.getLastRow();
  const lastCol = sheet.getLastColumn();
  if (lastRow === 0) {
    return { success: true, found: false, message: 'Sheet is empty' };
  }

  const data = sheet.getRange(1, 1, lastRow, lastCol).getValues();
  const searchLower = String(payload.searchValue).toLowerCase();

  for (let i = 1; i < data.length; i++) { // skip header row
    const cellValue = String(data[i][payload.searchCol - 1]).toLowerCase();
    if (cellValue.includes(searchLower)) {
      return {
        success: true,
        found: true,
        rowIndex: i + 1, // 1-indexed for Sheets API
        rowData: data[i],
        headers: data[0]
      };
    }
  }

  return { success: true, found: false, message: 'No matching row found for: ' + payload.searchValue };
}

// ===========================================
// DRIVE FILE MANAGEMENT
// Native DriveApp — uses scopes already granted (drive). No re-auth needed.
// ===========================================

function deleteFile(payload) {
  // payload: { fileId, permanent? (default false = move to Trash, recoverable ~30 days) }
  if (!payload.fileId) return { error: 'fileId is required' };
  try {
    if (payload.permanent === true) {
      // Hard delete via Drive REST (DriveApp has no permanent-delete method).
      var resp = UrlFetchApp.fetch(
        'https://www.googleapis.com/drive/v3/files/' + encodeURIComponent(payload.fileId) + '?supportsAllDrives=true',
        { method: 'delete', headers: { Authorization: 'Bearer ' + ScriptApp.getOAuthToken() }, muteHttpExceptions: true });
      var code = resp.getResponseCode();
      if (code !== 204 && code !== 200) return { error: 'Drive permanent-delete failed ' + code + ': ' + resp.getContentText() };
      return { success: true, fileId: payload.fileId, permanent: true };
    }
    var file = DriveApp.getFileById(payload.fileId);
    var name = file.getName();
    file.setTrashed(true);
    return { success: true, fileId: payload.fileId, name: name, trashed: true,
      note: 'Moved to Trash (recoverable). Pass permanent:true to hard-delete.' };
  } catch (e) {
    return { error: 'deleteFile failed: ' + e.message };
  }
}

function moveFile(payload) {
  // payload: { fileId, folderId, keepInOthers? (default false = remove from all other folders) }
  if (!payload.fileId || !payload.folderId) return { error: 'fileId and folderId are required' };
  try {
    var file = DriveApp.getFileById(payload.fileId);
    var target = DriveApp.getFolderById(payload.folderId);
    target.addFile(file);
    if (payload.keepInOthers !== true) {
      var parents = file.getParents();
      while (parents.hasNext()) {
        var p = parents.next();
        if (p.getId() !== payload.folderId) p.removeFile(file);
      }
    }
    return { success: true, fileId: payload.fileId, movedTo: payload.folderId, url: file.getUrl() };
  } catch (e) {
    return { error: 'moveFile failed: ' + e.message };
  }
}

function renameFile(payload) {
  // payload: { fileId, name }
  if (!payload.fileId || !payload.name) return { error: 'fileId and name are required' };
  try {
    var file = DriveApp.getFileById(payload.fileId);
    var old = file.getName();
    file.setName(payload.name);
    return { success: true, fileId: payload.fileId, oldName: old, newName: payload.name, url: file.getUrl() };
  } catch (e) {
    return { error: 'renameFile failed: ' + e.message };
  }
}

function copyFile(payload) {
  // payload: { fileId, name?, folderId? }
  if (!payload.fileId) return { error: 'fileId is required' };
  try {
    var file = DriveApp.getFileById(payload.fileId);
    var copy = payload.name ? file.makeCopy(payload.name) : file.makeCopy();
    if (payload.folderId) {
      var folder = DriveApp.getFolderById(payload.folderId);
      folder.addFile(copy);
      DriveApp.getRootFolder().removeFile(copy);
    }
    return { success: true, newFileId: copy.getId(), url: copy.getUrl(), name: copy.getName() };
  } catch (e) {
    return { error: 'copyFile failed: ' + e.message };
  }
}

function listFiles(payload) {
  // payload: { folderId?, nameContains?, mimeType?, limit? (default 50) }
  // mimeType examples: 'application/vnd.google-apps.document', '...spreadsheet', '...folder'
  try {
    var limit = payload.limit || 50;
    var out = [];
    var iter;
    if (payload.folderId) {
      var folder = DriveApp.getFolderById(payload.folderId);
      iter = payload.mimeType ? folder.getFilesByType(payload.mimeType) : folder.getFiles();
    } else if (payload.mimeType) {
      iter = DriveApp.getFilesByType(payload.mimeType);
    } else if (payload.nameContains) {
      iter = DriveApp.searchFiles('title contains "' + String(payload.nameContains).replace(/"/g, '\\"') + '" and trashed = false');
    } else {
      iter = DriveApp.getFiles();
    }
    while (iter.hasNext() && out.length < limit) {
      var f = iter.next();
      if (payload.nameContains && f.getName().toLowerCase().indexOf(String(payload.nameContains).toLowerCase()) === -1) continue;
      out.push({ id: f.getId(), name: f.getName(), mimeType: f.getMimeType(), url: f.getUrl(), lastUpdated: f.getLastUpdated() });
    }
    return { success: true, count: out.length, files: out };
  } catch (e) {
    return { error: 'listFiles failed: ' + e.message };
  }
}

function fileInfo(payload) {
  // payload: { fileId }
  if (!payload.fileId) return { error: 'fileId is required' };
  try {
    var f = DriveApp.getFileById(payload.fileId);
    return { success: true, id: f.getId(), name: f.getName(), mimeType: f.getMimeType(),
      url: f.getUrl(), size: f.getSize(), lastUpdated: f.getLastUpdated(),
      owner: f.getOwner() ? f.getOwner().getEmail() : null, trashed: f.isTrashed() };
  } catch (e) {
    return { error: 'fileInfo failed: ' + e.message };
  }
}

function shareFile(payload) {
  // payload: { fileId, email?, role?: 'view'|'edit'|'comment', anyoneWithLink?: bool }
  // OUTWARD-FACING: grants access to others. Use deliberately.
  if (!payload.fileId) return { error: 'fileId is required' };
  try {
    var file = DriveApp.getFileById(payload.fileId);
    var role = (payload.role || 'view').toLowerCase();
    var perm = role === 'edit' ? DriveApp.Permission.EDIT
             : role === 'comment' ? DriveApp.Permission.COMMENT
             : DriveApp.Permission.VIEW;
    if (payload.anyoneWithLink === true) {
      file.setSharing(DriveApp.Access.ANYONE_WITH_LINK, perm);
    }
    if (payload.email) {
      if (role === 'edit') file.addEditor(payload.email);
      else if (role === 'comment') file.addCommenter(payload.email);
      else file.addViewer(payload.email);
    }
    return { success: true, fileId: payload.fileId, url: file.getUrl(),
      sharedWith: payload.email || null, anyoneWithLink: payload.anyoneWithLink === true, role: role };
  } catch (e) {
    return { error: 'shareFile failed: ' + e.message };
  }
}

// ===========================================
// DOCS — SURGICAL EDITING
// find/replace + image insert. For arbitrary structural edits, use the
// google_api passthrough -> Docs documents.batchUpdate.
// ===========================================

function docFindReplace(payload) {
  // payload: { docId, replacements: [{ find, replace }] }
  // `find` is an RE2 regex string. Use (?i) prefix for case-insensitive; escape metachars for literals.
  if (!payload.docId || !payload.replacements) return { error: 'docId and replacements[] are required' };
  try {
    var doc = DocumentApp.openById(payload.docId);
    var body = doc.getBody();
    var applied = 0;
    for (var i = 0; i < payload.replacements.length; i++) {
      var rep = payload.replacements[i];
      if (rep.find == null) continue;
      body.replaceText(rep.find, rep.replace != null ? rep.replace : '');
      applied++;
    }
    doc.saveAndClose();
    return { success: true, docId: payload.docId, replacementsApplied: applied, url: doc.getUrl() };
  } catch (e) {
    return { error: 'docFindReplace failed: ' + e.message };
  }
}

function docInsertImage(payload) {
  // payload: { docId, imageUrl, position? ('start'|'end', default 'end'), width?, height? }
  if (!payload.docId || !payload.imageUrl) return { error: 'docId and imageUrl are required' };
  try {
    var resp = UrlFetchApp.fetch(payload.imageUrl, { muteHttpExceptions: true });
    if (resp.getResponseCode() !== 200) return { error: 'Could not fetch image: HTTP ' + resp.getResponseCode() };
    var blob = resp.getBlob();
    var doc = DocumentApp.openById(payload.docId);
    var body = doc.getBody();
    var img;
    if (payload.position === 'start') {
      img = body.insertParagraph(0, '').appendInlineImage(blob);
    } else {
      img = body.appendImage(blob);
    }
    if (payload.width && payload.height) { img.setWidth(payload.width); img.setHeight(payload.height); }
    doc.saveAndClose();
    return { success: true, docId: payload.docId, url: doc.getUrl() };
  } catch (e) {
    return { error: 'docInsertImage failed: ' + e.message };
  }
}

// ===========================================
// SHEETS — RANGE WRITE / FORMAT / TABS / STRUCTURE
// Native SpreadsheetApp. For conditional formatting / charts / advanced ops,
// use the google_api passthrough -> Sheets spreadsheets.batchUpdate.
// ===========================================

function sheetWriteRange(payload) {
  // payload: { spreadsheetId, sheetName, range (A1), values (2D array), asFormulas? }
  if (!payload.spreadsheetId || !payload.sheetName || !payload.range) return { error: 'spreadsheetId, sheetName, range required' };
  try {
    var ss = SpreadsheetApp.openById(payload.spreadsheetId);
    var sheet = ss.getSheetByName(payload.sheetName);
    if (!sheet) return { error: 'Tab not found: ' + payload.sheetName };
    var rng = sheet.getRange(payload.range);
    if (payload.values) {
      if (payload.asFormulas === true) rng.setFormulas(payload.values);
      else rng.setValues(payload.values);
    }
    return { success: true, spreadsheetId: payload.spreadsheetId, range: payload.range, url: ss.getUrl() };
  } catch (e) {
    return { error: 'sheetWriteRange failed: ' + e.message };
  }
}

function sheetClearRange(payload) {
  // payload: { spreadsheetId, sheetName, range? (omit to clear whole tab) }
  if (!payload.spreadsheetId || !payload.sheetName) return { error: 'spreadsheetId and sheetName required' };
  try {
    var ss = SpreadsheetApp.openById(payload.spreadsheetId);
    var sheet = ss.getSheetByName(payload.sheetName);
    if (!sheet) return { error: 'Tab not found: ' + payload.sheetName };
    if (payload.range) sheet.getRange(payload.range).clear();
    else sheet.clear();
    return { success: true, spreadsheetId: payload.spreadsheetId, cleared: payload.range || 'all' };
  } catch (e) {
    return { error: 'sheetClearRange failed: ' + e.message };
  }
}

function sheetFormat(payload) {
  // payload: { spreadsheetId, sheetName, range, background?, fontColor?, bold?, italic?,
  //            fontSize?, numberFormat?, horizontalAlignment?, verticalAlignment?, wrap?, merge? }
  if (!payload.spreadsheetId || !payload.sheetName || !payload.range) return { error: 'spreadsheetId, sheetName, range required' };
  try {
    var ss = SpreadsheetApp.openById(payload.spreadsheetId);
    var sheet = ss.getSheetByName(payload.sheetName);
    if (!sheet) return { error: 'Tab not found: ' + payload.sheetName };
    var rng = sheet.getRange(payload.range);
    if (payload.background) rng.setBackground(payload.background);
    if (payload.fontColor) rng.setFontColor(payload.fontColor);
    if (payload.bold !== undefined) rng.setFontWeight(payload.bold ? 'bold' : 'normal');
    if (payload.italic !== undefined) rng.setFontStyle(payload.italic ? 'italic' : 'normal');
    if (payload.fontSize) rng.setFontSize(payload.fontSize);
    if (payload.numberFormat) rng.setNumberFormat(payload.numberFormat);
    if (payload.horizontalAlignment) rng.setHorizontalAlignment(payload.horizontalAlignment);
    if (payload.verticalAlignment) rng.setVerticalAlignment(payload.verticalAlignment);
    if (payload.wrap !== undefined) rng.setWrap(payload.wrap);
    if (payload.merge === true) rng.merge();
    return { success: true, spreadsheetId: payload.spreadsheetId, range: payload.range, url: ss.getUrl() };
  } catch (e) {
    return { error: 'sheetFormat failed: ' + e.message };
  }
}

function sheetFreeze(payload) {
  // payload: { spreadsheetId, sheetName, rows?, cols? }
  if (!payload.spreadsheetId || !payload.sheetName) return { error: 'spreadsheetId and sheetName required' };
  try {
    var ss = SpreadsheetApp.openById(payload.spreadsheetId);
    var sheet = ss.getSheetByName(payload.sheetName);
    if (!sheet) return { error: 'Tab not found: ' + payload.sheetName };
    if (payload.rows !== undefined) sheet.setFrozenRows(payload.rows);
    if (payload.cols !== undefined) sheet.setFrozenColumns(payload.cols);
    return { success: true, spreadsheetId: payload.spreadsheetId };
  } catch (e) {
    return { error: 'sheetFreeze failed: ' + e.message };
  }
}

function addTab(payload) {
  // payload: { spreadsheetId, name, index? }
  if (!payload.spreadsheetId || !payload.name) return { error: 'spreadsheetId and name required' };
  try {
    var ss = SpreadsheetApp.openById(payload.spreadsheetId);
    if (ss.getSheetByName(payload.name)) return { error: 'Tab already exists: ' + payload.name };
    if (payload.index !== undefined) ss.insertSheet(payload.name, payload.index);
    else ss.insertSheet(payload.name);
    return { success: true, spreadsheetId: payload.spreadsheetId, tab: payload.name };
  } catch (e) {
    return { error: 'addTab failed: ' + e.message };
  }
}

function deleteTab(payload) {
  // payload: { spreadsheetId, sheetName }
  if (!payload.spreadsheetId || !payload.sheetName) return { error: 'spreadsheetId and sheetName required' };
  try {
    var ss = SpreadsheetApp.openById(payload.spreadsheetId);
    var sheet = ss.getSheetByName(payload.sheetName);
    if (!sheet) return { error: 'Tab not found: ' + payload.sheetName };
    ss.deleteSheet(sheet);
    return { success: true, spreadsheetId: payload.spreadsheetId, deletedTab: payload.sheetName };
  } catch (e) {
    return { error: 'deleteTab failed: ' + e.message };
  }
}

function renameTab(payload) {
  // payload: { spreadsheetId, sheetName, newName }
  if (!payload.spreadsheetId || !payload.sheetName || !payload.newName) return { error: 'spreadsheetId, sheetName, newName required' };
  try {
    var ss = SpreadsheetApp.openById(payload.spreadsheetId);
    var sheet = ss.getSheetByName(payload.sheetName);
    if (!sheet) return { error: 'Tab not found: ' + payload.sheetName };
    sheet.setName(payload.newName);
    return { success: true, spreadsheetId: payload.spreadsheetId, oldName: payload.sheetName, newName: payload.newName };
  } catch (e) {
    return { error: 'renameTab failed: ' + e.message };
  }
}

// ===========================================
// GENERIC GOOGLE API PASSTHROUGH — the unrestricted escape hatch.
// Calls any Docs / Sheets / Drive / Slides REST method with the script's
// OAuth token (runs as the deploying account). Covers anything the
// convenience actions above don't (structural doc edits, conditional
// formatting, charts, permissions listing, revisions, exports, etc.).
//
// payload: {
//   api:   'docs' | 'sheets' | 'drive' | 'slides',
//   method:'GET'|'POST'|'PUT'|'PATCH'|'DELETE'  (default GET),
//   path:  e.g. '/v1/documents/{id}:batchUpdate'       (docs)
//               '/v4/spreadsheets/{id}:batchUpdate'    (sheets)
//               '/drive/v3/files/{id}?fields=...'      (drive)
//   body?: object (sent as JSON),
//   query?: object (appended as ?k=v)
// }
// Returns: { success, status, body }
//
// Scopes already granted via DocumentApp/SpreadsheetApp/DriveApp/UrlFetchApp:
//   documents, spreadsheets, drive, script.external_request — so docs/sheets/
//   drive work with NO re-auth. 'slides' needs the presentations scope added
//   to the manifest first (it will prompt to re-authorize once).
// ===========================================

function googleApi(payload) {
  var hosts = {
    docs: 'https://docs.googleapis.com',
    sheets: 'https://sheets.googleapis.com',
    drive: 'https://www.googleapis.com',
    slides: 'https://slides.googleapis.com'
  };
  var host = hosts[payload.api];
  if (!host) return { error: 'Unknown api: ' + payload.api + ' (use docs|sheets|drive|slides)' };
  if (!payload.path) return { error: 'path is required, e.g. /v1/documents/{id}:batchUpdate' };

  var url = host + payload.path;
  if (payload.query) {
    var qs = [];
    for (var k in payload.query) {
      if (payload.query.hasOwnProperty(k)) qs.push(encodeURIComponent(k) + '=' + encodeURIComponent(payload.query[k]));
    }
    if (qs.length) url += (url.indexOf('?') === -1 ? '?' : '&') + qs.join('&');
  }

  var options = {
    method: (payload.method || 'GET').toLowerCase(),
    headers: { Authorization: 'Bearer ' + ScriptApp.getOAuthToken() },
    muteHttpExceptions: true
  };
  if (payload.body !== undefined && payload.body !== null) {
    options.contentType = 'application/json';
    options.payload = JSON.stringify(payload.body);
  }

  var resp = UrlFetchApp.fetch(url, options);
  var code = resp.getResponseCode();
  var text = resp.getContentText();
  var parsed;
  try { parsed = JSON.parse(text); } catch (e) { parsed = text; }
  return { success: code >= 200 && code < 300, status: code, body: parsed };
}
