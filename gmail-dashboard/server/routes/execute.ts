/**
 * Execute Routes
 *
 * Handles email deletion execution.
 */

import { Router, Request, Response } from 'express';
import { findCachedJson, loadCachedEmails } from '../services/cache.js';
import { matchEmail, getCriteriaStats } from '../services/criteria.js';
import { trashEmail } from '../services/gmail.js';
import type { EmailData } from '../types/index.js';

const router = Router();

interface ExecuteRequest {
  criteriaFile?: 'criteria' | 'criteria_1d';
  dryRun?: boolean;
  minAgeDays?: number;
}

interface ExecuteProgress {
  total: number;
  processed: number;
  deleted: number;
  skipped: number;
  errors: number;
  logs: string[];
}

/**
 * POST /api/execute/preview
 * Preview which emails would be deleted.
 */
router.post('/preview', async (req: Request, res: Response) => {
  try {
    const { criteriaFile = 'criteria', minAgeDays = 0 } = req.body as ExecuteRequest;

    // Find cached emails
    const cache = findCachedJson();
    if (!cache) {
      res.status(404).json({
        success: false,
        error: 'No cached emails found'
      });
      return;
    }

    const emails = loadCachedEmails(cache.filepath);

    // Get criteria stats for response
    const criteriaStats = getCriteriaStats();

    // Determine which action type to target
    const targetAction = criteriaFile === 'criteria_1d' ? 'delete_1d' : 'delete';

    // Find matching emails
    const now = Date.now();
    const minAgeMs = minAgeDays * 24 * 60 * 60 * 1000;
    const matches: Array<{ id: string; from: string; subject: string; date: string }> = [];
    const skipped: Array<{ id: string; reason: string }> = [];

    for (const email of emails) {
      const result = matchEmail(email);

      // Only process emails matching the target action
      if (result.action !== targetAction) {
        continue;
      }

      // Check age
      const emailDate = new Date(email.date).getTime();
      const emailAge = now - emailDate;

      if (emailAge < minAgeMs) {
        skipped.push({
          id: email.id,
          reason: `Too recent (${Math.round(emailAge / (24 * 60 * 60 * 1000))} days old)`
        });
        continue;
      }

      matches.push({
        id: email.id,
        from: email.from,
        subject: email.subject,
        date: email.date
      });
    }

    res.json({
      success: true,
      criteriaFile,
      criteriaStats,
      totalEmails: emails.length,
      matchCount: matches.length,
      skippedCount: skipped.length,
      matches: matches.slice(0, 100), // Limit response size
      skipped: skipped.slice(0, 20)
    });
  } catch (error) {
    console.error('Error previewing:', error);
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error'
    });
  }
});

/**
 * POST /api/execute/delete
 * Execute email deletion.
 */
router.post('/delete', async (req: Request, res: Response) => {
  try {
    const { criteriaFile = 'criteria', dryRun = false, minAgeDays = 0 } = req.body as ExecuteRequest;

    console.log(`Executing delete: criteriaFile=${criteriaFile}, dryRun=${dryRun}, minAgeDays=${minAgeDays}`);

    // Find cached emails
    const cache = findCachedJson();
    if (!cache) {
      res.status(404).json({
        success: false,
        error: 'No cached emails found'
      });
      return;
    }

    const emails = loadCachedEmails(cache.filepath);

    // Determine which action type to target
    const targetAction = criteriaFile === 'criteria_1d' ? 'delete_1d' : 'delete';

    // Execute deletion
    const now = Date.now();
    const minAgeMs = minAgeDays * 24 * 60 * 60 * 1000;
    const progress: ExecuteProgress = {
      total: 0,
      processed: 0,
      deleted: 0,
      skipped: 0,
      errors: 0,
      logs: []
    };

    // Find emails to delete
    const toDelete: EmailData[] = [];

    for (const email of emails) {
      const result = matchEmail(email);

      // Only process emails matching the target action
      if (result.action !== targetAction) {
        continue;
      }

      // Check age
      const emailDate = new Date(email.date).getTime();
      const emailAge = now - emailDate;

      if (emailAge < minAgeMs) {
        progress.skipped++;
        progress.logs.push(`[SKIP] Too recent: ${email.from} - ${email.subject.slice(0, 40)}...`);
        continue;
      }

      toDelete.push(email);
    }

    progress.total = toDelete.length;

    // Delete emails
    for (const email of toDelete) {
      progress.processed++;

      if (dryRun) {
        progress.deleted++;
        progress.logs.push(`[DRY-RUN] Would delete: ${email.from} - ${email.subject.slice(0, 40)}...`);
      } else {
        const success = await trashEmail(email.id);
        if (success) {
          progress.deleted++;
          progress.logs.push(`[DELETED] ${email.from} - ${email.subject.slice(0, 40)}...`);
        } else {
          progress.errors++;
          progress.logs.push(`[ERROR] Failed to delete: ${email.from} - ${email.subject.slice(0, 40)}...`);
        }
      }

      // Log progress every 10 emails
      if (progress.processed % 10 === 0) {
        console.log(`Progress: ${progress.processed}/${progress.total}`);
      }
    }

    console.log(`Deletion complete: ${progress.deleted} deleted, ${progress.skipped} skipped, ${progress.errors} errors`);

    res.json({
      success: true,
      dryRun,
      progress,
      summary: {
        total: progress.total,
        deleted: progress.deleted,
        skipped: progress.skipped,
        errors: progress.errors
      }
    });
  } catch (error) {
    console.error('Error executing delete:', error);
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error'
    });
  }
});

export default router;
