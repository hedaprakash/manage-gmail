/**
 * Action Routes
 *
 * Handles Keep/Delete/Delete1d button actions.
 */

import { Router, Request, Response } from 'express';
import {
  loadJsonFile,
  saveJsonFile,
  createCriteriaEntry,
  isDuplicateCriteria,
  removeFromCriteria,
  CRITERIA_FILE,
  CRITERIA_1DAY_FILE,
  KEEP_CRITERIA_FILE,
  KEEP_LIST_FILE
} from '../services/criteria.js';
import type { CriteriaEntry } from '../types/index.js';

const router = Router();

/**
 * POST /api/actions/add-criteria
 * Add an entry to criteria.json (immediate deletion).
 */
router.post('/add-criteria', (req: Request, res: Response) => {
  try {
    const { domain, subject_pattern, exclude_subject } = req.body;

    if (!domain) {
      res.status(400).json({
        success: false,
        error: 'Domain is required'
      });
      return;
    }

    const criteria = loadJsonFile<CriteriaEntry>(CRITERIA_FILE);
    const newEntry = createCriteriaEntry(domain, subject_pattern, exclude_subject);

    if (isDuplicateCriteria(criteria, newEntry)) {
      res.status(409).json({
        success: false,
        error: 'Similar criteria already exists'
      });
      return;
    }

    criteria.push(newEntry);
    saveJsonFile(CRITERIA_FILE, criteria);

    console.log(`Added criteria: ${domain} (subject: ${subject_pattern || '(all)'})`);

    res.json({
      success: true,
      message: 'Added to criteria.json',
      entry: newEntry,
      total_criteria: criteria.length
    });
  } catch (error) {
    console.error('Error adding criteria:', error);
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error'
    });
  }
});

/**
 * POST /api/actions/add-criteria-1d
 * Add an entry to criteria_1day_old.json (delete after 1 day).
 */
router.post('/add-criteria-1d', (req: Request, res: Response) => {
  try {
    const { domain, subject_pattern, exclude_subject } = req.body;

    if (!domain) {
      res.status(400).json({
        success: false,
        error: 'Domain is required'
      });
      return;
    }

    const criteria = loadJsonFile<CriteriaEntry>(CRITERIA_1DAY_FILE);
    const newEntry = createCriteriaEntry(domain, subject_pattern, exclude_subject);

    if (isDuplicateCriteria(criteria, newEntry)) {
      res.status(409).json({
        success: false,
        error: 'Similar criteria already exists'
      });
      return;
    }

    criteria.push(newEntry);
    saveJsonFile(CRITERIA_1DAY_FILE, criteria);

    console.log(`Added 1-day criteria: ${domain} (subject: ${subject_pattern || '(all)'})`);

    res.json({
      success: true,
      message: 'Added to criteria_1day_old.json',
      entry: newEntry,
      total_criteria: criteria.length
    });
  } catch (error) {
    console.error('Error adding 1-day criteria:', error);
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error'
    });
  }
});

/**
 * POST /api/actions/mark-keep
 * Mark an email pattern as 'keep' - removes from delete criteria AND adds to safe list.
 */
router.post('/mark-keep', (req: Request, res: Response) => {
  try {
    const { domain, subject_pattern, category } = req.body;

    if (!domain) {
      res.status(400).json({
        success: false,
        error: 'Domain is required'
      });
      return;
    }

    // 1. Remove from criteria.json AND criteria_1day_old.json if present
    const removedCount = removeFromCriteria(domain, subject_pattern || '');

    // 2. Add to keep_criteria.json (the actual safe list)
    const keepCriteria = loadJsonFile<CriteriaEntry>(KEEP_CRITERIA_FILE);
    const keepEntry = createCriteriaEntry(domain, subject_pattern);

    let addedToKeep = false;
    if (!isDuplicateCriteria(keepCriteria, keepEntry)) {
      keepCriteria.push(keepEntry);
      saveJsonFile(KEEP_CRITERIA_FILE, keepCriteria);
      addedToKeep = true;
      console.log(`Added to safe list: ${domain} (subject: ${subject_pattern || '(all)'})`);
    }

    // 3. Log to keep_list.json for reference with timestamp
    const keepList = loadJsonFile<any>(KEEP_LIST_FILE);
    const logEntry = {
      domain,
      subject_pattern: subject_pattern || '',
      category: category || 'UNKNOWN',
      marked_at: new Date().toISOString(),
      removed_from_delete: removedCount
    };
    keepList.push(logEntry);
    saveJsonFile(KEEP_LIST_FILE, keepList);

    // Build response message
    const messageParts: string[] = [];
    if (removedCount > 0) {
      messageParts.push(`Removed ${removedCount} from delete criteria`);
    }
    if (addedToKeep) {
      messageParts.push(`Added to safe list (${keepCriteria.length} protected)`);
    } else {
      messageParts.push('Already in safe list');
    }

    res.json({
      success: true,
      message: messageParts.join(' | '),
      entry: keepEntry,
      total_protected: keepCriteria.length,
      removed_from_delete: removedCount
    });
  } catch (error) {
    console.error('Error marking keep:', error);
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error'
    });
  }
});

/**
 * POST /api/actions/undo-last
 * Undo the last added criteria.
 */
router.post('/undo-last', (req: Request, res: Response) => {
  try {
    const { file_type } = req.body as { file_type?: 'criteria' | 'criteria_1d' };

    const filepath = file_type === 'criteria_1d' ? CRITERIA_1DAY_FILE : CRITERIA_FILE;
    const criteria = loadJsonFile<CriteriaEntry>(filepath);

    if (criteria.length === 0) {
      res.status(400).json({
        success: false,
        error: 'No criteria to undo'
      });
      return;
    }

    const removed = criteria.pop();
    saveJsonFile(filepath, criteria);

    console.log(`Undid last criteria: ${JSON.stringify(removed)}`);

    res.json({
      success: true,
      message: 'Last criteria removed',
      removed,
      remaining: criteria.length
    });
  } catch (error) {
    console.error('Error undoing:', error);
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error'
    });
  }
});

export default router;
