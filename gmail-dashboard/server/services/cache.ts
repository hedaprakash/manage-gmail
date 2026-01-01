/**
 * Cache Service
 *
 * Handles caching of email data to avoid repeated Gmail API calls.
 */

import fs from 'fs';
import path from 'path';
import type { EmailData, DomainGroup, EmailPattern } from '../types/index.js';
import { matchesAnyCriteria, loadJsonFile, CRITERIA_FILE, CRITERIA_1DAY_FILE, KEEP_CRITERIA_FILE } from './criteria.js';
import type { CriteriaEntry } from '../types/index.js';

const PROJECT_ROOT = path.resolve(process.cwd(), '..');
const LOGS_DIR = path.join(PROJECT_ROOT, 'logs');
const CACHE_PATTERN = 'emails_categorized_*.json';
const CACHE_MAX_AGE_HOURS = 5;

/**
 * Find the most recent cached JSON file and check its age.
 */
export function findCachedJson(): { filepath: string; ageHours: number } | null {
  if (!fs.existsSync(LOGS_DIR)) {
    return null;
  }

  const files = fs.readdirSync(LOGS_DIR)
    .filter(f => f.startsWith('emails_categorized_') && f.endsWith('.json'))
    .map(f => ({
      name: f,
      path: path.join(LOGS_DIR, f),
      mtime: fs.statSync(path.join(LOGS_DIR, f)).mtime.getTime()
    }))
    .sort((a, b) => b.mtime - a.mtime);

  if (files.length === 0) {
    return null;
  }

  const mostRecent = files[0];
  if (!mostRecent) return null;

  const ageHours = (Date.now() - mostRecent.mtime) / (1000 * 60 * 60);

  return {
    filepath: mostRecent.path,
    ageHours
  };
}

/**
 * Load emails from cached JSON file.
 */
export function loadCachedEmails(cachePath: string): EmailData[] {
  console.log(`Loading cached data from ${cachePath}`);
  const content = fs.readFileSync(cachePath, 'utf-8');
  return JSON.parse(content) as EmailData[];
}

/**
 * Save emails to cache.
 */
export function saveCachedEmails(emails: EmailData[]): string {
  if (!fs.existsSync(LOGS_DIR)) {
    fs.mkdirSync(LOGS_DIR, { recursive: true });
  }

  const timestamp = new Date().toISOString().replace(/[-:]/g, '').replace('T', '_').slice(0, 15);
  const cachePath = path.join(LOGS_DIR, `emails_categorized_${timestamp}.json`);

  fs.writeFileSync(cachePath, JSON.stringify(emails, null, 2), 'utf-8');
  console.log(`Saved ${emails.length} emails to cache: ${cachePath}`);

  return cachePath;
}

/**
 * Check if cache should be refreshed.
 */
export function shouldRefreshCache(): boolean {
  const cache = findCachedJson();
  if (!cache) {
    return true;
  }
  return cache.ageHours > CACHE_MAX_AGE_HOURS;
}

/**
 * Group emails by domain and subject pattern.
 */
export function groupEmailsByPattern(emailDetails: EmailData[]): DomainGroup[] {
  const grouped: Record<string, Record<string, {
    subject: string;
    category: string;
    categoryIcon: string;
    categoryColor: string;
    categoryBg: string;
    count: number;
    emails: EmailData[];
    minDate: Date;
    maxDate: Date;
    messageIds: string[];
  }>> = {};

  for (const email of emailDetails) {
    const domain = email.primaryDomain || 'unknown';
    const subject = email.subject.slice(0, 50); // First 50 chars as pattern key
    const category = email.category || 'UNKNOWN';
    const patternKey = `${category}:${subject}`;

    if (!grouped[domain]) {
      grouped[domain] = {};
    }

    if (!grouped[domain][patternKey]) {
      grouped[domain][patternKey] = {
        subject,
        category,
        categoryIcon: email.categoryIcon || '🟡',
        categoryColor: email.categoryColor || '#ffc107',
        categoryBg: email.categoryBg || '#fff3cd',
        count: 0,
        emails: [],
        minDate: new Date(email.date),
        maxDate: new Date(email.date),
        messageIds: []
      };
    }

    const group = grouped[domain][patternKey]!;
    group.count++;
    group.emails.push(email);
    group.messageIds.push(email.id);

    // Update date range
    const emailDate = new Date(email.date);
    if (emailDate < group.minDate) {
      group.minDate = emailDate;
    }
    if (emailDate > group.maxDate) {
      group.maxDate = emailDate;
    }
  }

  // Convert to DomainGroup array
  const result: DomainGroup[] = [];

  for (const [domain, patterns] of Object.entries(grouped)) {
    const patternList: EmailPattern[] = [];

    for (const pattern of Object.values(patterns)) {
      patternList.push({
        domain,
        subject: pattern.subject,
        category: pattern.category,
        count: pattern.count,
        minDate: pattern.minDate.toISOString(),
        maxDate: pattern.maxDate.toISOString(),
        messageIds: pattern.messageIds,
        categoryIcon: pattern.categoryIcon,
        categoryColor: pattern.categoryColor,
        categoryBg: pattern.categoryBg
      });
    }

    // Sort patterns by count (descending)
    patternList.sort((a, b) => b.count - a.count);

    result.push({
      domain,
      totalEmails: patternList.reduce((sum, p) => sum + p.count, 0),
      patterns: patternList
    });
  }

  // Sort domains by total email count (descending)
  result.sort((a, b) => b.totalEmails - a.totalEmails);

  return result;
}

/**
 * Filter out emails that already have a decision (in criteria or keep_criteria).
 */
export function filterDecidedEmails(
  emails: EmailData[],
  criteria: CriteriaEntry[],
  keep: CriteriaEntry[]
): { filtered: EmailData[]; removedCount: number } {
  const filtered: EmailData[] = [];
  let removedCount = 0;

  for (const email of emails) {
    const inDelete = matchesAnyCriteria(email, criteria);
    const inKeep = matchesAnyCriteria(email, keep);

    if (inDelete || inKeep) {
      removedCount++;
    } else {
      filtered.push(email);
    }
  }

  return { filtered, removedCount };
}

/**
 * Get cache stats.
 */
export function getCacheStats(): {
  hasCached: boolean;
  filepath?: string;
  ageHours?: number;
  emailCount?: number;
} {
  const cache = findCachedJson();
  if (!cache) {
    return { hasCached: false };
  }

  try {
    const emails = loadCachedEmails(cache.filepath);
    return {
      hasCached: true,
      filepath: cache.filepath,
      ageHours: cache.ageHours,
      emailCount: emails.length
    };
  } catch {
    return {
      hasCached: true,
      filepath: cache.filepath,
      ageHours: cache.ageHours
    };
  }
}
