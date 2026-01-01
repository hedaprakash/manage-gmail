/**
 * Gmail Service
 *
 * Handles Gmail API authentication and email fetching.
 */

import fs from 'fs';
import path from 'path';
import { google, gmail_v1 } from 'googleapis';
import type { OAuth2Client } from 'google-auth-library';
import type { EmailData } from '../types/index.js';
import { classifyEmail } from './classification.js';

const SCOPES = ['https://mail.google.com/'];
const PROJECT_ROOT = path.resolve(process.cwd(), '..');
const TOKEN_PATH = path.join(PROJECT_ROOT, 'token.json');
const CREDENTIALS_PATH = path.join(PROJECT_ROOT, 'credentials.json');
const BATCH_SIZE = 100;

let gmailService: gmail_v1.Gmail | null = null;

/**
 * Extract email address from a header like 'Name <email@domain.com>'.
 */
function extractEmailAddress(headerValue: string): string {
  if (!headerValue) return '';
  const match = headerValue.match(/<(.+?)>/);
  return match ? match[1] : headerValue.trim();
}

/**
 * Extract subdomain and primary domain from email address.
 */
function extractDomainInfo(email: string): { subdomain: string; primaryDomain: string } {
  if (!email.includes('@')) {
    return { subdomain: '', primaryDomain: '' };
  }
  const subdomain = email.split('@')[1] ?? '';
  const parts = subdomain.split('.');
  const primaryDomain = parts.length >= 2 ? parts.slice(-2).join('.') : subdomain;
  return { subdomain, primaryDomain };
}

/**
 * Get a header value by name from message headers.
 */
function getHeaderValue(headers: gmail_v1.Schema$MessagePartHeader[], name: string): string {
  const header = headers.find(h => h.name?.toLowerCase() === name.toLowerCase());
  return header?.value ?? '';
}

/**
 * Get or create Gmail API service.
 */
export async function getGmailService(): Promise<gmail_v1.Gmail> {
  if (gmailService) {
    return gmailService;
  }

  // Load credentials
  if (!fs.existsSync(CREDENTIALS_PATH)) {
    throw new Error(`credentials.json not found at ${CREDENTIALS_PATH}`);
  }

  const credentials = JSON.parse(fs.readFileSync(CREDENTIALS_PATH, 'utf-8'));
  const { client_id, client_secret, redirect_uris } = credentials.installed || credentials.web;

  const oauth2Client = new google.auth.OAuth2(client_id, client_secret, redirect_uris?.[0]);

  // Load token
  if (fs.existsSync(TOKEN_PATH)) {
    const token = JSON.parse(fs.readFileSync(TOKEN_PATH, 'utf-8'));
    oauth2Client.setCredentials(token);

    // Check if token needs refresh
    if (token.expiry_date && Date.now() >= token.expiry_date) {
      try {
        const { credentials: newCredentials } = await oauth2Client.refreshAccessToken();
        oauth2Client.setCredentials(newCredentials);
        fs.writeFileSync(TOKEN_PATH, JSON.stringify(newCredentials));
        console.log('Token refreshed');
      } catch (error) {
        console.error('Error refreshing token:', error);
        throw new Error('Token expired. Please re-authenticate using the Python scripts first.');
      }
    }
  } else {
    throw new Error('token.json not found. Please authenticate using the Python scripts first.');
  }

  gmailService = google.gmail({ version: 'v1', auth: oauth2Client as unknown as OAuth2Client });
  return gmailService;
}

/**
 * Fetch all unread emails using pagination.
 */
export async function fetchAllUnreadEmails(
  onProgress?: (count: number) => void,
  maxEmails?: number
): Promise<EmailData[]> {
  const gmail = await getGmailService();
  const emailDetails: EmailData[] = [];
  let pageToken: string | undefined;
  let totalFetched = 0;

  console.log('Searching for ALL unread emails (with pagination)...');

  while (true) {
    const response = await gmail.users.messages.list({
      userId: 'me',
      q: 'is:unread',
      maxResults: BATCH_SIZE,
      pageToken
    });

    const messages = response.data.messages;
    if (!messages || messages.length === 0) {
      break;
    }

    console.log(`Fetched batch of ${messages.length} message IDs...`);

    // Process each message
    for (const msgInfo of messages) {
      if (maxEmails && totalFetched >= maxEmails) {
        console.log(`Reached max limit of ${maxEmails} emails.`);
        return emailDetails;
      }

      try {
        const message = await gmail.users.messages.get({
          userId: 'me',
          id: msgInfo.id!,
          format: 'metadata',
          metadataHeaders: ['From', 'To', 'Cc', 'Subject', 'Date']
        });

        const headers = message.data.payload?.headers ?? [];

        const fromHeader = getHeaderValue(headers, 'From');
        const email = extractEmailAddress(fromHeader);
        const { subdomain, primaryDomain } = extractDomainInfo(email);

        const toHeader = getHeaderValue(headers, 'To');
        const toEmails = toHeader
          ? toHeader.split(',').map(e => extractEmailAddress(e.trim())).join(', ')
          : '';

        const ccHeader = getHeaderValue(headers, 'Cc');
        const ccEmails = ccHeader
          ? ccHeader.split(',').map(e => extractEmailAddress(e.trim())).join(', ')
          : '';

        const subject = getHeaderValue(headers, 'Subject');
        const date = getHeaderValue(headers, 'Date');

        // Classify the email by subject
        const classification = classifyEmail(subject);

        emailDetails.push({
          id: msgInfo.id!,
          email,
          from: fromHeader,
          subdomain,
          primaryDomain,
          subject,
          toEmails,
          ccEmails,
          date,
          category: classification.category,
          categoryIcon: classification.icon,
          categoryColor: classification.color,
          categoryBg: classification.bgColor,
          matchedKeyword: classification.matchedKeyword
        });

        totalFetched++;

        if (totalFetched % 100 === 0) {
          console.log(`Processed ${totalFetched} emails...`);
          onProgress?.(totalFetched);
        }
      } catch (error) {
        console.warn(`Error fetching message ${msgInfo.id}:`, error);
        continue;
      }
    }

    // Check for next page
    pageToken = response.data.nextPageToken ?? undefined;
    if (!pageToken) {
      break;
    }
  }

  console.log(`Successfully extracted details for ${emailDetails.length} emails.`);
  return emailDetails;
}

/**
 * Delete emails by moving them to trash.
 */
export async function trashEmail(messageId: string): Promise<boolean> {
  try {
    const gmail = await getGmailService();
    await gmail.users.messages.trash({
      userId: 'me',
      id: messageId
    });
    return true;
  } catch (error) {
    console.error(`Error trashing message ${messageId}:`, error);
    return false;
  }
}

/**
 * Generate Gmail URL for viewing emails.
 */
export function getGmailUrl(
  messageIds: string[],
  domain: string,
  subject: string
): string {
  const baseUrl = 'https://mail.google.com/mail/u/0/';

  if (messageIds.length === 1) {
    // Single email: direct link
    return `${baseUrl}#inbox/${messageIds[0]}`;
  } else {
    // Multiple emails: search query
    const query = `from:${domain} subject:"${subject.slice(0, 50)}"`;
    return `${baseUrl}#search/${encodeURIComponent(query)}`;
  }
}
