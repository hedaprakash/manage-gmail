// Embedding js-yaml library functions
var YAML = (function () {
  function safeLoad(str) {
    return JSON.parse(JSON.stringify(str)); // Simplified YAML parser for the demo purpose
  }
  function safeDump(obj) {
    return JSON.stringify(obj, null, 2); // Simplified YAML stringifier for the demo purpose
  }
  return {
    parse: safeLoad,
    stringify: safeDump
  };
})();

function myFunc() {
 cleanupEmailsProcessedFiles();
// removeProcessedLabelFromAllEmails();
//  batchPromotionDelete();
  processEmailsBatch();
  createSummaryHTMLFromCSV();
}

function processEmailsBatch() {
  const processedLabelName = 'Processed'; 
  const batchSize = 99;
  const maxSearchIterations = 3; 
  const maxBatchesPerDay = 10;
  const delayBetweenBatches = 5000; 

  try {
    Logger.log('Starting email processing...');

    let batchNumber = 0;
    let searchIteration = 0; 

    const processedLabel = GmailApp.getUserLabelByName(processedLabelName) || GmailApp.createLabel(processedLabelName);

    // Perform initial search
    let threads = GmailApp.search('is:unread NOT label:' + processedLabelName, 0, 498); // Search up to the maximum allowed by the API
    Logger.log(`New email search found count is ${threads.length}`);
    
    while (batchNumber < maxBatchesPerDay && threads.length > 0) {
      const batch = threads.splice(0, batchSize); // Get the next batch of threads
      Logger.log(`Processing batch number: ${batchNumber + 1}`);
      
      try {
        const emailDetails = extractEmailDetails(batch);
        Logger.log(`Extracted email details successfully`);
        
        saveEmailsToJSON(emailDetails);
        Logger.log(`saveEmailsToJSON completed for batch number: ${batchNumber + 1}`);
      } catch (e) {
        Logger.log(`Error in processing batch ${batchNumber + 1}: ${e.message}`);
        Logger.log(`Error stack: ${e.stack}`);
        continue; // Skip to the next batch
      }

      // Label processed threads
      try {
        Logger.log(`Labeling processed threads for batch number: ${batchNumber + 1}`);
        processedLabel.addToThreads(batch);
      } catch (labelError) {
        Logger.log(`Error in labeling threads for batch ${batchNumber + 1}: ${labelError.message}`);
        Logger.log(`Error stack: ${labelError.stack}`);
        continue; // Skip to the next batch
      }

      batchNumber++;

      if (threads.length === 0) {
        // If there are no more threads left in the initial search, perform another search
        searchIteration++;
        if (searchIteration >= maxSearchIterations) {
          Logger.log('Max search iterations reached.');
          break; // Exit if max search iterations are reached
        }

        Utilities.sleep(delayBetweenBatches);
        threads = GmailApp.search('is:unread NOT label:' + processedLabelName, 0, 498);
        Logger.log(`Subsequent email search found count is ${threads.length}`);
      }
    }

    Logger.log(`Processed emails in ${batchNumber} batches.`);
  } catch (error) {
    Logger.log(`Error in processEmailsBatch: ${error.message}`);
    Logger.log(`Error stack: ${error.stack}`);
    throw error;
  }
}


function extractEmailDetails(threads) {
  try {
    Logger.log('Extracting email details from threads.');
    const emailDetails = [];
    const emailRegex = /<(.+?)>/;

    threads.forEach(thread => {
      thread.getMessages().forEach(message => {
        const from = message.getFrom();
        let email = from;
        const emailMatch = from.match(emailRegex);
        if (emailMatch) {
          email = emailMatch[1];
        }
        const subdomain = email.split('@')[1];
        const primaryDomain = subdomain.split('.').slice(-2).join('.');
        const subject = message.getSubject();

        let toEmails = "";
        if (message.getTo()) {
          toEmails = message.getTo().split(',').map(to => {
            const match = to.match(emailRegex);
            return match ? match[1] : to;
          }).join(', ');
        }
        let ccEmails = "";
        if (message.getCc()) {
          ccEmails = message.getCc().split(',').map(cc => {
            const match = cc.match(emailRegex);
            return match ? match[1] : cc;
          }).join(', ');
        }
        
        emailDetails.push({
          email: email,
          subdomain: subdomain,
          primaryDomain: primaryDomain,
          subject: subject,
          toEmails: toEmails,
          ccEmails: ccEmails
        });
      });
    });

    Logger.log(`Extracted details for ${emailDetails.length} emails.`);
    return emailDetails;
  } catch (error) {
    Logger.log('Error in extractEmailDetails: ' + error.message);
    throw error;
  }
}
function saveEmailsToJSON(emailDetails, folderId = '10OJTkl0g9ZDU6QmiRCQG54_V6hk6r6yd') { 
  try {
    // 1. Get the folder
    const folder = DriveApp.getFolderById(folderId);
    if (!folder) {
      throw new Error(`Folder not found with ID: ${folderId}`);
    }

    // 2. Generate filename with timestamp
    const timestamp = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), "yyyyMMdd_HHmmss");
    const fileName = `emails_processed_${timestamp}.json`;

    // 3. Create new file with JSON content
    const jsonData = JSON.stringify(emailDetails, null, 2);
    folder.createFile(fileName, jsonData, MimeType.PLAIN_TEXT);

    Logger.log(`Created new file: ${fileName} in folder ${folderId}`);

  } catch (error) {
    Logger.log(`Error in saveEmailsToJSON: ${error.message}`);
    throw error;
  }
}


function batchPromotionDelete() {
  // Fetch unread emails from promotions and social categories
  const threads = GmailApp.search('category:promotions OR category:social is:unread');
  Logger.log('Promotion batch size is: ' + threads.length);

  // Check if any emails were found
  if (threads.length > 0) {
    // Move threads to trash, effectively deleting them
    threads.forEach(thread => thread.moveToTrash());
    Logger.log(`Successfully deleted ${threads.length} emails.`);
  } else {
    Logger.log('No unread emails found in promotions or social categories.');
  }
}


function removeProcessedLabelFromAllEmails() {
  const processedLabelName = 'Processed';

  try {
    Logger.log('Starting to remove processed label from all emails...');

    // Get the label
    const processedLabel = GmailApp.getUserLabelByName(processedLabelName);

    if (!processedLabel) {
      Logger.log(`Label "${processedLabelName}" does not exist.`);
      return;
    }

    // Search for all emails with the processed label
    let threads = GmailApp.search('label:' + processedLabelName);
    Logger.log(`Found ${threads.length} threads with the label "${processedLabelName}".`);


    // Remove label from threads in batches of 99
    const batchSize = 99;
    for (let i = 0; i < threads.length; i += batchSize) {
      const batch = threads.slice(i, i + batchSize);
      Logger.log(`batchSize: ${batchSize}`);
      processedLabel.removeFromThreads(batch);
      Logger.log(`Removed label from batch no ${i+1}`);
    }

    Logger.log('Finished removing processed label from all emails.');
  } catch (error) {
    Logger.log(`Error: ${error.message}`);
    throw error;
  }
}



