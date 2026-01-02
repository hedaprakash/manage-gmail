/**
 * Criteria Service
 *
 * Handles loading, saving, and matching criteria files.
 */

import fs from 'fs';
import path from 'path';
import type { CriteriaEntry, EmailData } from '../types/index.js';

// Resolve paths relative to the gmail project root (parent of gmail-dashboard)
const PROJECT_ROOT = path.resolve(process.cwd(), '..');

export const CRITERIA_FILE = path.join(PROJECT_ROOT, 'criteria.json');
export const CRITERIA_1DAY_FILE = path.join(PROJECT_ROOT, 'criteria_1day_old.json');
export const KEEP_CRITERIA_FILE = path.join(PROJECT_ROOT, 'keep_criteria.json');

/**
 * Load a JSON file, return empty array if not exists.
 */
export function loadJsonFile<T>(filepath: string): T[] {
  try {
    if (fs.existsSync(filepath)) {
      const content = fs.readFileSync(filepath, 'utf-8');
      return JSON.parse(content) as T[];
    }
  } catch (error) {
    console.error(`Error loading ${filepath}:`, error);
  }
  return [];
}

/**
 * Save data to a JSON file.
 */
export function saveJsonFile<T>(filepath: string, data: T[]): void {
  const dir = path.dirname(filepath);
  if (dir && !fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  fs.writeFileSync(filepath, JSON.stringify(data, null, 2), 'utf-8');
}

/**
 * Create a criteria entry in the expected format.
 */
export function createCriteriaEntry(
  domain: string,
  subjectPattern?: string,
  excludeSubject?: string
): CriteriaEntry {
  return {
    email: '',
    subdomain: '',
    primaryDomain: domain,
    subject: subjectPattern ?? '',
    toEmails: '',
    ccEmails: '',
    excludeSubject: excludeSubject ?? ''
  };
}

/**
 * Check if a similar criteria already exists.
 */
export function isDuplicateCriteria(criteriaList: CriteriaEntry[], newEntry: CriteriaEntry): boolean {
  return criteriaList.some(
    entry =>
      entry.primaryDomain.toLowerCase() === newEntry.primaryDomain.toLowerCase() &&
      entry.subject.toLowerCase() === newEntry.subject.toLowerCase()
  );
}

/**
 * Find an existing entry with matching domain and subject.
 */
export function findExistingEntry(
  criteriaList: CriteriaEntry[],
  domain: string,
  subject: string
): CriteriaEntry | undefined {
  const domainLower = domain.toLowerCase();
  const subjectLower = subject.toLowerCase();
  return criteriaList.find(
    entry =>
      entry.primaryDomain.toLowerCase() === domainLower &&
      entry.subject.toLowerCase() === subjectLower
  );
}

/**
 * Merge exclusion terms into an existing entry.
 * Returns true if exclusions were added, false if already present.
 */
export function mergeExclusions(entry: CriteriaEntry, newExclusions: string): boolean {
  if (!newExclusions) return false;

  const existingTerms = entry.excludeSubject
    ? entry.excludeSubject.split(',').map(t => t.trim().toLowerCase()).filter(t => t)
    : [];

  const newTerms = newExclusions.split(',').map(t => t.trim()).filter(t => t);
  const newTermsLower = newTerms.map(t => t.toLowerCase());

  // Find terms that don't already exist
  const termsToAdd = newTerms.filter((_, i) => !existingTerms.includes(newTermsLower[i]));

  if (termsToAdd.length === 0) {
    return false; // All terms already exist
  }

  // Merge: keep existing + add new
  const merged = entry.excludeSubject
    ? `${entry.excludeSubject},${termsToAdd.join(',')}`
    : termsToAdd.join(',');

  entry.excludeSubject = merged;
  return true;
}

/**
 * Check if a criteria entry matches the given domain and subject pattern.
 */
export function matchesCriteriaPattern(
  entry: CriteriaEntry,
  domain: string,
  subjectPattern: string
): boolean {
  const entryDomain = entry.primaryDomain.toLowerCase();
  const entrySubject = entry.subject.toLowerCase();
  const domainLower = domain?.toLowerCase() ?? '';
  const subjectLower = subjectPattern?.toLowerCase() ?? '';

  // Match if domain matches AND (subject matches OR either subject is empty)
  if (entryDomain === domainLower) {
    if (!entrySubject || !subjectLower) {
      return true;
    }
    if (entrySubject.includes(subjectLower) || subjectLower.includes(entrySubject)) {
      return true;
    }
  }
  return false;
}

/**
 * Remove matching entries from BOTH criteria.json and criteria_1day_old.json.
 * Returns total count of removed entries.
 */
export function removeFromCriteria(domain: string, subjectPattern: string): number {
  let totalRemoved = 0;

  // Remove from criteria.json
  const criteria = loadJsonFile<CriteriaEntry>(CRITERIA_FILE);
  const originalCount = criteria.length;
  const filteredCriteria = criteria.filter(
    c => !matchesCriteriaPattern(c, domain, subjectPattern)
  );
  const removedCount = originalCount - filteredCriteria.length;
  if (removedCount > 0) {
    saveJsonFile(CRITERIA_FILE, filteredCriteria);
    console.log(`Removed ${removedCount} entries from criteria.json for ${domain}`);
  }
  totalRemoved += removedCount;

  // Also remove from criteria_1day_old.json
  const criteria1d = loadJsonFile<CriteriaEntry>(CRITERIA_1DAY_FILE);
  const originalCount1d = criteria1d.length;
  const filteredCriteria1d = criteria1d.filter(
    c => !matchesCriteriaPattern(c, domain, subjectPattern)
  );
  const removedCount1d = originalCount1d - filteredCriteria1d.length;
  if (removedCount1d > 0) {
    saveJsonFile(CRITERIA_1DAY_FILE, filteredCriteria1d);
    console.log(`Removed ${removedCount1d} entries from criteria_1day_old.json for ${domain}`);
  }
  totalRemoved += removedCount1d;

  return totalRemoved;
}

/**
 * Check if an email is explicitly excluded by any criteria.
 * Returns true if the email's domain matches a criteria AND the subject is in excludeSubject.
 * This means a decision was made: "don't delete emails with this subject from this domain".
 */
export function isExcludedByCriteria(emailData: EmailData, criteriaList: CriteriaEntry[]): boolean {
  const domain = emailData.primaryDomain.toLowerCase();
  const subdomain = emailData.subdomain?.toLowerCase() ?? '';
  const subject = emailData.subject.toLowerCase();

  for (const c of criteriaList) {
    const cDomain = c.primaryDomain.toLowerCase();
    const excludeSubject = c.excludeSubject?.toLowerCase() ?? '';

    if (!excludeSubject) continue; // No exclusions on this entry

    // Check if domain matches
    const domainMatches = cDomain && (
      domain.includes(cDomain) ||
      subdomain.includes(cDomain) ||
      subdomain === cDomain
    );

    if (domainMatches) {
      // Check if subject matches any excluded term
      const excludeTerms = excludeSubject.split(',').map(t => t.trim()).filter(t => t);
      const hasExcludedTerm = excludeTerms.some(term => subject.includes(term));
      if (hasExcludedTerm) {
        return true; // This email is explicitly excluded
      }
    }
  }
  return false;
}

/**
 * Check if an email matches any criteria in the list.
 * Also respects excludeSubject - if the subject contains any excluded term, it won't match.
 * Supports matching against both primaryDomain and subdomain (full domain like alerts.sbi.co.in).
 */
export function matchesAnyCriteria(emailData: EmailData, criteriaList: CriteriaEntry[]): boolean {
  const domain = emailData.primaryDomain.toLowerCase();
  const subdomain = emailData.subdomain?.toLowerCase() ?? '';
  const subject = emailData.subject.toLowerCase();

  for (const c of criteriaList) {
    const cDomain = c.primaryDomain.toLowerCase();
    const cSubject = c.subject.toLowerCase();
    const excludeSubject = c.excludeSubject?.toLowerCase() ?? '';

    // Match if criteria domain matches either primaryDomain or subdomain
    const domainMatches = cDomain && (
      domain.includes(cDomain) ||
      subdomain.includes(cDomain) ||
      subdomain === cDomain
    );

    if (domainMatches) {
      // Check excludeSubject first - if any excluded term matches, skip this criteria
      if (excludeSubject) {
        const excludeTerms = excludeSubject.split(',').map(t => t.trim()).filter(t => t);
        const hasExcludedTerm = excludeTerms.some(term => subject.includes(term));
        if (hasExcludedTerm) {
          continue; // Skip this criteria, email subject contains excluded term
        }
      }

      // Domain matches and no excluded terms found
      if (!cSubject) {
        // No subject filter = matches all from domain
        return true;
      }
      if (subject.includes(cSubject)) {
        // Subject also matches
        return true;
      }
    }
  }
  return false;
}

/**
 * Get all criteria from all three files.
 */
export function getAllCriteria(): {
  criteria: CriteriaEntry[];
  criteria1d: CriteriaEntry[];
  keep: CriteriaEntry[];
} {
  return {
    criteria: loadJsonFile<CriteriaEntry>(CRITERIA_FILE),
    criteria1d: loadJsonFile<CriteriaEntry>(CRITERIA_1DAY_FILE),
    keep: loadJsonFile<CriteriaEntry>(KEEP_CRITERIA_FILE)
  };
}
