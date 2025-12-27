function deleteEmailsBasedOnCriteria(dryRun = false) {
  try {
    Logger.log('Starting deleteEmailsBasedOnCriteria function');
    batchPromotionDelete();
    const sheetId = '1irHlPSUhhJMiy0cRd-X9MxgHG3IWMcodV0saY-36F3o';
    const parametersSheetName = 'Parameters';

    Logger.log('Fetching parameters from sheet');
    const parameters = fetchParameters(sheetId, parametersSheetName);
    const toBeDeletedSheetName = parameters['ToBeDeletedSheet'];

    Logger.log(`Parameters fetched: ${JSON.stringify(parameters)}`);
    
    const spreadsheet = SpreadsheetApp.openById(sheetId);
    const toBeDeletedSheet = spreadsheet.getSheetByName(toBeDeletedSheetName);
    const range = toBeDeletedSheet.getDataRange();
    const values = range.getValues();

    let statusColumnIndex = values[0].indexOf('Status');
    if (statusColumnIndex === -1) {
      statusColumnIndex = values[0].length;
      toBeDeletedSheet.getRange(1, statusColumnIndex + 1).setValue('Status');
    }

    let deletedCountColumnIndex = values[0].indexOf('Deleted Count');
    if (deletedCountColumnIndex === -1) {
      deletedCountColumnIndex = values[0].length + (statusColumnIndex === values[0].length ? 1 : 0);
      toBeDeletedSheet.getRange(1, deletedCountColumnIndex + 1).setValue('Deleted Count');
    }

    let dryRunColumnIndex = values[0].indexOf('Dry Run');
    if (dryRunColumnIndex === -1) {
      dryRunColumnIndex = values[0].length + (statusColumnIndex === values[0].length ? 1 : 0) + (deletedCountColumnIndex === values[0].length + (statusColumnIndex === values[0].length ? 1 : 0) ? 1 : 0);
      toBeDeletedSheet.getRange(1, dryRunColumnIndex + 1).setValue('Dry Run');
    }

    const criteria = values.slice(1).map(row => ({
      email: row[0],
      subdomain: row[1],
      primaryDomain: row[2],
      subject: row[3],
      toEmails: row[4],
      ccEmails: row[5],
      excludeSubject: row[6]
    }));

    //Logger.log(`Criteria to be processed: ${JSON.stringify(criteria)}`);
    
    try {
      const { statuses, deletedCounts, dryRunCounts } = deleteEmailsByCriteria(criteria, dryRun);
    
      for (let i = 1; i < values.length; i++) {
        toBeDeletedSheet.getRange(i + 1, statusColumnIndex + 1).setValue(statuses[i - 1]);
        toBeDeletedSheet.getRange(i + 1, deletedCountColumnIndex + 1).setValue(deletedCounts[i - 1]);
        toBeDeletedSheet.getRange(i + 1, dryRunColumnIndex + 1).setValue(dryRunCounts[i - 1]);
      }
    } catch (error) {
      Logger.log('Error in running query: ' + error.message);
    }

  } catch (error) {
    Logger.log('Error in deleteEmailsBasedOnCriteria: ' + error.message);
    throw new Error('Failed to delete emails based on criteria: ' + error.message);
  }
}

function deleteEmailsByCriteria(criteria, dryRun) {
  const statuses = [];
  const deletedCounts = [];
  const dryRunCounts = [];

  criteria.forEach(criterion => {
    try {
      const query = buildQuery(criterion);
      if (query === '') {
        statuses.push('Failed: Invalid query');
        deletedCounts.push(0);
        dryRunCounts.push(0);
        Logger.log('Invalid query: skipping deletion');
        return;
      }
      const threads = GmailApp.search(query);
      if (threads.length > 0){
      Logger.log('deleteEmailsMatch: ' + threads.length + ' Query: ' + query)};
      
      if (threads.length > 0) {
        if (!dryRun) {
          GmailApp.moveThreadsToTrash(threads);
          statuses.push('Success');
          deletedCounts.push(threads.length);
          dryRunCounts.push('');
        } else {
          statuses.push('Dry Run');
          deletedCounts.push('');
          dryRunCounts.push(threads.length);
        }
      } else {
        statuses.push('No matching emails found');
        deletedCounts.push(0);
        dryRunCounts.push(0);
      }
    } catch (error) {
      statuses.push('Failed: ' + error.message);
      deletedCounts.push(0);
      dryRunCounts.push(0);
    }
    
  });
  return { statuses, deletedCounts, dryRunCounts };
}

function buildQuery(criterion) {
  let query = 'is:unread ';
  if (criterion.email) {
    query += `from:${criterion.email} `;
  }
  if (criterion.subdomain) {
    query += `from:*@${criterion.subdomain} `;
  }
  if (criterion.primaryDomain) {
    query += `from:*@${criterion.primaryDomain} `;
  }
  if (criterion.subject) {
    query += `subject:(${criterion.subject}) `;
  }
  if (criterion.toEmails) {
    query += `to:(${criterion.toEmails}) `;
  }
  if (criterion.ccEmails) {
    query += `cc:(${criterion.ccEmails}) `;
  }
  if (criterion.excludeSubject) {
    query += `-subject:(${criterion.excludeSubject}) `;
  }
  return query.trim();
}


function fetchParameters(sheetId, parametersSheetName) {
  try {
    const spreadsheet = SpreadsheetApp.openById(sheetId);
    const parametersSheet = spreadsheet.getSheetByName(parametersSheetName);
    const range = parametersSheet.getDataRange();
    const values = range.getValues();

    const parameters = {};
    for (let i = 1; i < values.length; i++) {
      parameters[values[i][0]] = values[i][1];
    }
    return parameters;

  } catch (error) {
    Logger.log('Error in fetchParameters: ' + error.message);
    throw error;
  }
}
