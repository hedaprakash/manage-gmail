/**
 * Email Routes
 *
 * Handles fetching and displaying emails.
 */

import { Router, Request, Response } from 'express';
import {
  findCachedJson,
  loadCachedEmails,
  saveCachedEmails,
  groupEmailsByPattern,
  filterDecidedEmails,
  getCacheStats
} from '../services/cache.js';
import { fetchAllUnreadEmails, getGmailUrl } from '../services/gmail.js';
import { loadJsonFile, CRITERIA_FILE, CRITERIA_1DAY_FILE, KEEP_CRITERIA_FILE, matchesAnyCriteria } from '../services/criteria.js';
import type { CriteriaEntry, EmailData } from '../types/index.js';

const router = Router();

/**
 * GET /api/emails
 * Load all cached emails grouped by domain/pattern, filtered for undecided only.
 */
router.get('/', async (_req: Request, res: Response) => {
  try {
    // Find cached emails
    const cache = findCachedJson();
    if (!cache) {
      res.status(404).json({
        success: false,
        error: 'No cached emails found. Click "Refresh from Gmail" to fetch emails.'
      });
      return;
    }

    // Load emails from cache
    const emails = loadCachedEmails(cache.filepath);

    // Load criteria
    const criteria = loadJsonFile<CriteriaEntry>(CRITERIA_FILE);
    const criteria1d = loadJsonFile<CriteriaEntry>(CRITERIA_1DAY_FILE);
    const keep = loadJsonFile<CriteriaEntry>(KEEP_CRITERIA_FILE);

    // Combine delete criteria for filtering
    const allDeleteCriteria = [...criteria, ...criteria1d];

    // Filter out decided emails
    const { filtered, removedCount } = filterDecidedEmails(emails, allDeleteCriteria, keep);

    // Group by domain and pattern
    const grouped = groupEmailsByPattern(filtered);

    // Add Gmail URLs to each pattern
    for (const domainGroup of grouped) {
      for (const pattern of domainGroup.patterns) {
        (pattern as any).gmailUrl = getGmailUrl(
          pattern.messageIds,
          pattern.domain,
          pattern.subject
        );
      }
    }

    res.json({
      success: true,
      cacheFile: cache.filepath.split(/[\\/]/).pop(),
      cacheAgeHours: Math.round(cache.ageHours * 100) / 100,
      totalEmails: emails.length,
      filteredOut: removedCount,
      undecidedEmails: filtered.length,
      domains: grouped
    });
  } catch (error) {
    console.error('Error loading emails:', error);
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error'
    });
  }
});

/**
 * POST /api/emails/refresh
 * Refresh emails from Gmail API.
 */
router.post('/refresh', async (_req: Request, res: Response) => {
  try {
    console.log('Refreshing emails from Gmail API...');

    const emails = await fetchAllUnreadEmails((count) => {
      console.log(`Progress: ${count} emails processed`);
    });

    // Save to cache
    const cachePath = saveCachedEmails(emails);

    res.json({
      success: true,
      message: `Fetched ${emails.length} emails from Gmail`,
      emailCount: emails.length,
      cacheFile: cachePath.split(/[\\/]/).pop()
    });
  } catch (error) {
    console.error('Error refreshing emails:', error);
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error'
    });
  }
});

/**
 * GET /api/emails/stats
 * Get email statistics without loading full data.
 */
router.get('/stats', async (_req: Request, res: Response) => {
  try {
    const cacheStats = getCacheStats();

    if (!cacheStats.hasCached) {
      res.json({
        success: true,
        hasCached: false,
        message: 'No cached emails. Click refresh to fetch.'
      });
      return;
    }

    // Load emails for detailed stats
    const emails = loadCachedEmails(cacheStats.filepath!);

    // Load criteria
    const criteria = loadJsonFile<CriteriaEntry>(CRITERIA_FILE);
    const criteria1d = loadJsonFile<CriteriaEntry>(CRITERIA_1DAY_FILE);
    const keep = loadJsonFile<CriteriaEntry>(KEEP_CRITERIA_FILE);

    // Categorize each email
    let matchedCriteria = 0;
    let matchedCriteria1d = 0;
    let matchedKeep = 0;
    let undecided = 0;

    const criteriaDomains: Record<string, number> = {};
    const criteria1dDomains: Record<string, number> = {};
    const keepDomains: Record<string, number> = {};

    for (const email of emails) {
      const domain = email.primaryDomain || 'unknown';

      // Check keep first (highest priority)
      if (matchesAnyCriteria(email, keep)) {
        matchedKeep++;
        keepDomains[domain] = (keepDomains[domain] || 0) + 1;
      } else if (matchesAnyCriteria(email, criteria)) {
        matchedCriteria++;
        criteriaDomains[domain] = (criteriaDomains[domain] || 0) + 1;
      } else if (matchesAnyCriteria(email, criteria1d)) {
        matchedCriteria1d++;
        criteria1dDomains[domain] = (criteria1dDomains[domain] || 0) + 1;
      } else {
        undecided++;
      }
    }

    // Sort and limit domain breakdowns
    const sortAndLimit = (obj: Record<string, number>, limit = 10) => {
      return Object.entries(obj)
        .sort(([, a], [, b]) => b - a)
        .slice(0, limit)
        .reduce((acc, [k, v]) => ({ ...acc, [k]: v }), {});
    };

    res.json({
      success: true,
      cacheFile: cacheStats.filepath!.split(/[\\/]/).pop(),
      cacheAgeHours: Math.round((cacheStats.ageHours || 0) * 100) / 100,
      stats: {
        total: emails.length,
        matchedCriteria,
        matchedCriteria1d,
        matchedKeep,
        undecided,
        criteriaDomains: sortAndLimit(criteriaDomains),
        criteria1dDomains: sortAndLimit(criteria1dDomains),
        keepDomains: sortAndLimit(keepDomains)
      },
      criteriaRules: criteria.length,
      criteria1dRules: criteria1d.length,
      keepRules: keep.length
    });
  } catch (error) {
    console.error('Error getting stats:', error);
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error'
    });
  }
});

export default router;
