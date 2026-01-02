/**
 * Criteria Service - Unified Format
 *
 * Handles loading, saving, and matching criteria using the new unified format.
 * Single file with domain-grouped rules supporting:
 * - default action (delete, delete_1d, keep)
 * - subject patterns for each action
 * - excludeSubjects for default action
 * - subdomain overrides
 */

import fs from 'fs';
import path from 'path';
import type { EmailData } from '../types/index.js';

// Types for the unified format
export type Action = 'delete' | 'delete_1d' | 'keep';

export interface DomainRules {
  default?: Action | null;
  excludeSubjects?: string[];
  keep?: string[];
  delete?: string[];
  delete_1d?: string[];
  subdomains?: { [subdomain: string]: DomainRules };
}

export interface UnifiedCriteria {
  [primaryDomain: string]: DomainRules;
}

// Result of matching an email against criteria
export interface MatchResult {
  action: Action | null;
  matchedDomain: string;
  matchedSubdomain?: string;
  matchedPattern?: string;
  reason: string;
}

// Resolve paths relative to the gmail project root (parent of gmail-dashboard)
const PROJECT_ROOT = path.resolve(process.cwd(), '..');
export const UNIFIED_CRITERIA_FILE = path.join(PROJECT_ROOT, 'criteria_unified.json');

// Legacy file paths (for backwards compatibility during transition)
export const CRITERIA_FILE = path.join(PROJECT_ROOT, 'criteria.json');
export const CRITERIA_1DAY_FILE = path.join(PROJECT_ROOT, 'criteria_1day_old.json');
export const KEEP_CRITERIA_FILE = path.join(PROJECT_ROOT, 'keep_criteria.json');

// Cache for the unified criteria
let criteriaCache: UnifiedCriteria | null = null;
let criteriaCacheTime: number = 0;
const CACHE_TTL = 5000; // 5 seconds

/**
 * Load the unified criteria file.
 */
export function loadUnifiedCriteria(): UnifiedCriteria {
  const now = Date.now();
  if (criteriaCache && (now - criteriaCacheTime) < CACHE_TTL) {
    return criteriaCache;
  }

  try {
    if (fs.existsSync(UNIFIED_CRITERIA_FILE)) {
      const content = fs.readFileSync(UNIFIED_CRITERIA_FILE, 'utf-8');
      criteriaCache = JSON.parse(content) as UnifiedCriteria;
      criteriaCacheTime = now;
      return criteriaCache;
    }
  } catch (error) {
    console.error(`Error loading ${UNIFIED_CRITERIA_FILE}:`, error);
  }
  return {};
}

/**
 * Save the unified criteria file.
 */
export function saveUnifiedCriteria(criteria: UnifiedCriteria): void {
  // Sort domains alphabetically
  const sorted: UnifiedCriteria = {};
  for (const domain of Object.keys(criteria).sort()) {
    sorted[domain] = criteria[domain];
  }

  fs.writeFileSync(UNIFIED_CRITERIA_FILE, JSON.stringify(sorted, null, 2), 'utf-8');
  criteriaCache = sorted;
  criteriaCacheTime = Date.now();
}

/**
 * Invalidate the criteria cache.
 */
export function invalidateCache(): void {
  criteriaCache = null;
  criteriaCacheTime = 0;
}

/**
 * Check if a subject matches any pattern in a list (case-insensitive contains).
 */
function matchesSubjectPattern(subject: string, patterns: string[]): string | null {
  const subjectLower = subject.toLowerCase();
  for (const pattern of patterns) {
    if (subjectLower.includes(pattern.toLowerCase())) {
      return pattern;
    }
  }
  return null;
}

/**
 * Check if subject contains any excluded term.
 */
function isExcludedSubject(subject: string, excludeSubjects: string[]): boolean {
  const subjectLower = subject.toLowerCase();
  return excludeSubjects.some(term => subjectLower.includes(term.toLowerCase()));
}

/**
 * Get the action for an email based on domain rules.
 * Priority: subject patterns (keep > delete > delete_1d) > excludeSubjects check > default
 */
function getActionFromRules(rules: DomainRules, subject: string): { action: Action | null; pattern?: string; reason: string } {
  // 1. Check explicit subject patterns (keep has highest priority)
  if (rules.keep?.length) {
    const matched = matchesSubjectPattern(subject, rules.keep);
    if (matched) {
      return { action: 'keep', pattern: matched, reason: 'subject matches keep pattern' };
    }
  }

  if (rules.delete?.length) {
    const matched = matchesSubjectPattern(subject, rules.delete);
    if (matched) {
      return { action: 'delete', pattern: matched, reason: 'subject matches delete pattern' };
    }
  }

  if (rules.delete_1d?.length) {
    const matched = matchesSubjectPattern(subject, rules.delete_1d);
    if (matched) {
      return { action: 'delete_1d', pattern: matched, reason: 'subject matches delete_1d pattern' };
    }
  }

  // 2. Check excludeSubjects - if matched, KEEP the email
  if (rules.excludeSubjects?.length && isExcludedSubject(subject, rules.excludeSubjects)) {
    return { action: 'keep', reason: 'subject matches excludeSubjects (protected)' };
  }

  // 3. Apply default action (if set)
  if (rules.default) {
    return { action: rules.default, reason: 'default action' };
  }

  // 4. No match
  return { action: null, reason: 'no matching rule' };
}

/**
 * Match an email against the unified criteria.
 * Returns the action to take and details about the match.
 */
export function matchEmail(emailData: EmailData): MatchResult {
  const criteria = loadUnifiedCriteria();
  const primaryDomain = emailData.primaryDomain.toLowerCase();
  const subdomain = emailData.subdomain?.toLowerCase() || '';
  const subject = emailData.subject || '';

  // Look up the primary domain
  const domainRules = criteria[primaryDomain];
  if (!domainRules) {
    return { action: null, matchedDomain: primaryDomain, reason: 'domain not in criteria' };
  }

  // Check if there's a subdomain-specific rule
  if (subdomain && domainRules.subdomains) {
    const subdomainRules = domainRules.subdomains[subdomain];
    if (subdomainRules) {
      // Use subdomain rules (completely overrides parent)
      const result = getActionFromRules(subdomainRules, subject);
      return {
        action: result.action,
        matchedDomain: primaryDomain,
        matchedSubdomain: subdomain,
        matchedPattern: result.pattern,
        reason: result.reason
      };
    }
  }

  // Use domain-level rules
  const result = getActionFromRules(domainRules, subject);
  return {
    action: result.action,
    matchedDomain: primaryDomain,
    matchedPattern: result.pattern,
    reason: result.reason
  };
}

/**
 * Check if email matches criteria for a specific action type.
 */
export function matchesAction(emailData: EmailData, action: Action): boolean {
  const result = matchEmail(emailData);
  return result.action === action;
}

/**
 * Legacy compatibility: Check if email matches any "delete" criteria.
 */
export function matchesDeleteCriteria(emailData: EmailData): boolean {
  return matchesAction(emailData, 'delete');
}

/**
 * Legacy compatibility: Check if email matches any "delete_1d" criteria.
 */
export function matchesDelete1dCriteria(emailData: EmailData): boolean {
  return matchesAction(emailData, 'delete_1d');
}

/**
 * Legacy compatibility: Check if email matches any "keep" criteria.
 */
export function matchesKeepCriteria(emailData: EmailData): boolean {
  return matchesAction(emailData, 'keep');
}

/**
 * Add a rule to the criteria.
 */
export function addRule(
  domain: string,
  action: Action,
  subjectPattern?: string,
  subdomain?: string
): void {
  const criteria = loadUnifiedCriteria();
  const domainLower = domain.toLowerCase();

  // Ensure domain exists
  if (!criteria[domainLower]) {
    criteria[domainLower] = {};
  }

  let targetRules = criteria[domainLower];

  // Handle subdomain
  if (subdomain) {
    const subdomainLower = subdomain.toLowerCase();
    if (!targetRules.subdomains) {
      targetRules.subdomains = {};
    }
    if (!targetRules.subdomains[subdomainLower]) {
      targetRules.subdomains[subdomainLower] = {};
    }
    targetRules = targetRules.subdomains[subdomainLower];
  }

  if (subjectPattern) {
    // Add to subject pattern list
    const key = action as 'keep' | 'delete' | 'delete_1d';
    if (!targetRules[key]) {
      targetRules[key] = [];
    }
    const patternLower = subjectPattern.toLowerCase();
    if (!targetRules[key]!.some(p => p.toLowerCase() === patternLower)) {
      targetRules[key]!.push(subjectPattern);
    }
  } else {
    // Set as default action
    targetRules.default = action;
  }

  saveUnifiedCriteria(criteria);
}

/**
 * Remove a rule from the criteria.
 * If removing the last rule for a domain, removes the domain entirely.
 */
export function removeRule(
  domain: string,
  action?: Action,
  subjectPattern?: string,
  subdomain?: string
): boolean {
  const criteria = loadUnifiedCriteria();
  const domainLower = domain.toLowerCase();

  if (!criteria[domainLower]) {
    return false;
  }

  let targetRules = criteria[domainLower];
  let parentRules = criteria[domainLower];

  // Handle subdomain
  if (subdomain) {
    const subdomainLower = subdomain.toLowerCase();
    if (!targetRules.subdomains?.[subdomainLower]) {
      return false;
    }
    targetRules = targetRules.subdomains[subdomainLower];
  }

  let removed = false;

  if (subjectPattern && action) {
    // Remove specific subject pattern
    const key = action as 'keep' | 'delete' | 'delete_1d';
    if (targetRules[key]) {
      const patternLower = subjectPattern.toLowerCase();
      const idx = targetRules[key]!.findIndex(p => p.toLowerCase() === patternLower);
      if (idx >= 0) {
        targetRules[key]!.splice(idx, 1);
        if (targetRules[key]!.length === 0) {
          delete targetRules[key];
        }
        removed = true;
      }
    }
  } else if (action) {
    // Remove all patterns for an action or clear default
    const key = action as 'keep' | 'delete' | 'delete_1d';
    if (targetRules[key]) {
      delete targetRules[key];
      removed = true;
    }
    if (targetRules.default === action) {
      delete targetRules.default;
      removed = true;
    }
  } else {
    // Remove entire domain or subdomain
    if (subdomain) {
      const subdomainLower = subdomain.toLowerCase();
      delete parentRules.subdomains![subdomainLower];
      if (Object.keys(parentRules.subdomains!).length === 0) {
        delete parentRules.subdomains;
      }
    } else {
      delete criteria[domainLower];
    }
    removed = true;
  }

  // Clean up empty domain entries
  if (criteria[domainLower]) {
    const rules = criteria[domainLower];
    const isEmpty = !rules.default &&
      !rules.keep?.length &&
      !rules.delete?.length &&
      !rules.delete_1d?.length &&
      !rules.excludeSubjects?.length &&
      !rules.subdomains;
    if (isEmpty) {
      delete criteria[domainLower];
    }
  }

  if (removed) {
    saveUnifiedCriteria(criteria);
  }
  return removed;
}

/**
 * Add exclude subjects to a domain.
 */
export function addExcludeSubjects(domain: string, terms: string[]): void {
  const criteria = loadUnifiedCriteria();
  const domainLower = domain.toLowerCase();

  if (!criteria[domainLower]) {
    criteria[domainLower] = {};
  }

  if (!criteria[domainLower].excludeSubjects) {
    criteria[domainLower].excludeSubjects = [];
  }

  for (const term of terms) {
    const termLower = term.toLowerCase();
    if (!criteria[domainLower].excludeSubjects!.some(t => t.toLowerCase() === termLower)) {
      criteria[domainLower].excludeSubjects!.push(term);
    }
  }

  saveUnifiedCriteria(criteria);
}

/**
 * Get all criteria (returns the unified criteria object).
 */
export function getAllCriteria(): UnifiedCriteria {
  return loadUnifiedCriteria();
}

/**
 * Get criteria for a specific domain.
 */
export function getDomainCriteria(domain: string): DomainRules | null {
  const criteria = loadUnifiedCriteria();
  return criteria[domain.toLowerCase()] || null;
}

/**
 * Get statistics about the criteria.
 */
export function getCriteriaStats(): {
  totalDomains: number;
  withDefault: { delete: number; delete_1d: number; keep: number };
  withSubjectPatterns: number;
  withSubdomains: number;
  withExcludeSubjects: number;
} {
  const criteria = loadUnifiedCriteria();
  const stats = {
    totalDomains: 0,
    withDefault: { delete: 0, delete_1d: 0, keep: 0 },
    withSubjectPatterns: 0,
    withSubdomains: 0,
    withExcludeSubjects: 0
  };

  for (const rules of Object.values(criteria)) {
    stats.totalDomains++;
    if (rules.default === 'delete') stats.withDefault.delete++;
    if (rules.default === 'delete_1d') stats.withDefault.delete_1d++;
    if (rules.default === 'keep') stats.withDefault.keep++;
    if (rules.keep?.length || rules.delete?.length || rules.delete_1d?.length) {
      stats.withSubjectPatterns++;
    }
    if (rules.subdomains && Object.keys(rules.subdomains).length > 0) {
      stats.withSubdomains++;
    }
    if (rules.excludeSubjects?.length) {
      stats.withExcludeSubjects++;
    }
  }

  return stats;
}

// Legacy exports for backwards compatibility
export type CriteriaEntry = {
  email: string;
  subdomain: string;
  primaryDomain: string;
  subject: string;
  toEmails: string;
  ccEmails: string;
  excludeSubject: string;
};

/**
 * Legacy: Check if email matches any criteria (for delete or delete_1d).
 */
export function matchesAnyCriteria(emailData: EmailData, _criteriaList?: CriteriaEntry[]): boolean {
  const result = matchEmail(emailData);
  return result.action === 'delete' || result.action === 'delete_1d';
}

/**
 * Legacy: Check if email is in keep criteria.
 */
export function matchesKeepList(emailData: EmailData): boolean {
  return matchesKeepCriteria(emailData);
}
