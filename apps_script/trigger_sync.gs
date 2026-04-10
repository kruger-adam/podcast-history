/**
 * Installable onEdit trigger that watches the Controls tab.
 * When the "Sync Now" checkbox (A2) is checked, it triggers
 * a GitHub Actions workflow_dispatch and resets the checkbox.
 *
 * Setup:
 * 1. Open the spreadsheet, go to Extensions > Apps Script
 * 2. Paste this code into Code.gs (replace any existing content)
 * 3. Click the gear icon (Project Settings) on the left sidebar
 * 4. Scroll to "Script Properties" and add:
 *    - GITHUB_TOKEN: a personal access token with "actions:write" scope
 *    - GITHUB_REPO: your repo in "owner/repo" format (e.g. "kruger-adam/podcast-history")
 * 5. Back in the editor, run the "installTrigger" function once
 *    (click the function dropdown, select installTrigger, click Run)
 *    Grant permissions when prompted.
 * 6. Done! The checkbox on the Controls tab will now trigger syncs.
 */

function installTrigger() {
  // Remove any existing onEdit triggers to avoid duplicates
  var triggers = ScriptApp.getProjectTriggers();
  for (var i = 0; i < triggers.length; i++) {
    if (triggers[i].getHandlerFunction() === 'onSyncCheckbox') {
      ScriptApp.deleteTrigger(triggers[i]);
    }
  }
  ScriptApp.newTrigger('onSyncCheckbox')
    .forSpreadsheet(SpreadsheetApp.getActive())
    .onEdit()
    .create();
  Logger.log('Trigger installed successfully.');
}

function onSyncCheckbox(e) {
  var sheet = e.source.getActiveSheet();
  var range = e.range;

  // Only respond to the checkbox in Controls!A2
  if (sheet.getName() !== 'Controls') return;
  if (range.getA1Notation() !== 'A2') return;
  if (range.getValue() !== true) return;

  // Reset the checkbox immediately
  range.setValue(false);

  var props = PropertiesService.getScriptProperties();
  var token = props.getProperty('GITHUB_TOKEN');
  var repo = props.getProperty('GITHUB_REPO');

  if (!token || !repo) {
    SpreadsheetApp.getActiveSpreadsheet().toast(
      'Missing GITHUB_TOKEN or GITHUB_REPO in Script Properties.',
      'Sync Error', 5
    );
    return;
  }

  var url = 'https://api.github.com/repos/' + repo + '/actions/workflows/sync.yml/dispatches';
  var options = {
    method: 'post',
    headers: {
      'Authorization': 'Bearer ' + token,
      'Accept': 'application/vnd.github.v3+json',
    },
    contentType: 'application/json',
    payload: JSON.stringify({ ref: 'main' }),
    muteHttpExceptions: true,
  };

  var response = UrlFetchApp.fetch(url, options);
  var code = response.getResponseCode();

  if (code === 204) {
    SpreadsheetApp.getActiveSpreadsheet().toast(
      'Sync triggered! New episodes should appear in a minute or two.',
      'Syncing', 5
    );
  } else {
    SpreadsheetApp.getActiveSpreadsheet().toast(
      'GitHub API returned ' + code + ': ' + response.getContentText(),
      'Sync Error', 10
    );
  }
}
