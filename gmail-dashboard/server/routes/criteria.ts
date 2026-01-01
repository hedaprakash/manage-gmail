/**
 * Criteria Routes
 *
 * CRUD operations for criteria files.
 */

import { Router, Request, Response } from 'express';
import {
  loadJsonFile,
  saveJsonFile,
  createCriteriaEntry,
  isDuplicateCriteria,
  CRITERIA_FILE,
  CRITERIA_1DAY_FILE,
  KEEP_CRITERIA_FILE
} from '../services/criteria.js';
import type { CriteriaEntry } from '../types/index.js';

const router = Router();

type CriteriaType = 'delete' | 'delete1d' | 'keep';

function getFilePath(type: CriteriaType): string {
  switch (type) {
    case 'delete': return CRITERIA_FILE;
    case 'delete1d': return CRITERIA_1DAY_FILE;
    case 'keep': return KEEP_CRITERIA_FILE;
    default: throw new Error(`Unknown criteria type: ${type}`);
  }
}

/**
 * GET /api/criteria
 * Get all criteria from all files.
 */
router.get('/', (_req: Request, res: Response) => {
  try {
    const criteria = loadJsonFile<CriteriaEntry>(CRITERIA_FILE);
    const criteria1d = loadJsonFile<CriteriaEntry>(CRITERIA_1DAY_FILE);
    const keep = loadJsonFile<CriteriaEntry>(KEEP_CRITERIA_FILE);

    res.json({
      success: true,
      delete: criteria,
      delete1d: criteria1d,
      keep
    });
  } catch (error) {
    console.error('Error loading criteria:', error);
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error'
    });
  }
});

/**
 * GET /api/criteria/:type
 * Get criteria from a specific file.
 */
router.get('/:type', (req: Request, res: Response) => {
  try {
    const type = req.params.type as CriteriaType;
    const filepath = getFilePath(type);
    const criteria = loadJsonFile<CriteriaEntry>(filepath);

    res.json({
      success: true,
      type,
      count: criteria.length,
      entries: criteria
    });
  } catch (error) {
    console.error('Error loading criteria:', error);
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error'
    });
  }
});

/**
 * POST /api/criteria/:type
 * Add a new entry to a criteria file.
 */
router.post('/:type', (req: Request, res: Response) => {
  try {
    const type = req.params.type as CriteriaType;
    const { domain, subject, excludeSubject } = req.body;

    if (!domain) {
      res.status(400).json({
        success: false,
        error: 'Domain is required'
      });
      return;
    }

    const filepath = getFilePath(type);
    const criteria = loadJsonFile<CriteriaEntry>(filepath);

    const newEntry = createCriteriaEntry(domain, subject, excludeSubject);

    if (isDuplicateCriteria(criteria, newEntry)) {
      res.status(409).json({
        success: false,
        error: 'Similar criteria already exists'
      });
      return;
    }

    criteria.push(newEntry);
    saveJsonFile(filepath, criteria);

    console.log(`Added to ${type}: ${domain} (subject: ${subject || '(all)'})`);

    res.json({
      success: true,
      message: `Added to ${type} criteria`,
      entry: newEntry,
      totalCount: criteria.length
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
 * DELETE /api/criteria/:type/:index
 * Delete an entry from a criteria file by index.
 */
router.delete('/:type/:index', (req: Request, res: Response) => {
  try {
    const type = req.params.type as CriteriaType;
    const index = parseInt(req.params.index, 10);

    if (isNaN(index)) {
      res.status(400).json({
        success: false,
        error: 'Invalid index'
      });
      return;
    }

    const filepath = getFilePath(type);
    const criteria = loadJsonFile<CriteriaEntry>(filepath);

    if (index < 0 || index >= criteria.length) {
      res.status(404).json({
        success: false,
        error: 'Entry not found'
      });
      return;
    }

    const removed = criteria.splice(index, 1)[0];
    saveJsonFile(filepath, criteria);

    console.log(`Removed from ${type}: ${removed?.primaryDomain} (subject: ${removed?.subject || '(all)'})`);

    res.json({
      success: true,
      message: `Removed from ${type} criteria`,
      removed,
      remainingCount: criteria.length
    });
  } catch (error) {
    console.error('Error deleting criteria:', error);
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error'
    });
  }
});

/**
 * PUT /api/criteria/:type/:index
 * Update an entry in a criteria file.
 */
router.put('/:type/:index', (req: Request, res: Response) => {
  try {
    const type = req.params.type as CriteriaType;
    const index = parseInt(req.params.index, 10);
    const { domain, subject, excludeSubject } = req.body;

    if (isNaN(index)) {
      res.status(400).json({
        success: false,
        error: 'Invalid index'
      });
      return;
    }

    const filepath = getFilePath(type);
    const criteria = loadJsonFile<CriteriaEntry>(filepath);

    if (index < 0 || index >= criteria.length) {
      res.status(404).json({
        success: false,
        error: 'Entry not found'
      });
      return;
    }

    const updated = createCriteriaEntry(
      domain ?? criteria[index]?.primaryDomain ?? '',
      subject ?? criteria[index]?.subject,
      excludeSubject ?? criteria[index]?.excludeSubject
    );

    criteria[index] = updated;
    saveJsonFile(filepath, criteria);

    res.json({
      success: true,
      message: `Updated ${type} criteria`,
      entry: updated
    });
  } catch (error) {
    console.error('Error updating criteria:', error);
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error'
    });
  }
});

/**
 * POST /api/criteria/move
 * Move an entry from one file to another.
 */
router.post('/move', (req: Request, res: Response) => {
  try {
    const { fromType, toType, index } = req.body as {
      fromType: CriteriaType;
      toType: CriteriaType;
      index: number;
    };

    if (!fromType || !toType || typeof index !== 'number') {
      res.status(400).json({
        success: false,
        error: 'fromType, toType, and index are required'
      });
      return;
    }

    const fromPath = getFilePath(fromType);
    const toPath = getFilePath(toType);

    const fromCriteria = loadJsonFile<CriteriaEntry>(fromPath);
    const toCriteria = loadJsonFile<CriteriaEntry>(toPath);

    if (index < 0 || index >= fromCriteria.length) {
      res.status(404).json({
        success: false,
        error: 'Entry not found'
      });
      return;
    }

    const entry = fromCriteria.splice(index, 1)[0];
    if (!entry) {
      res.status(404).json({
        success: false,
        error: 'Entry not found'
      });
      return;
    }

    if (isDuplicateCriteria(toCriteria, entry)) {
      res.status(409).json({
        success: false,
        error: 'Entry already exists in target file'
      });
      return;
    }

    toCriteria.push(entry);

    saveJsonFile(fromPath, fromCriteria);
    saveJsonFile(toPath, toCriteria);

    console.log(`Moved ${entry.primaryDomain} from ${fromType} to ${toType}`);

    res.json({
      success: true,
      message: `Moved from ${fromType} to ${toType}`,
      entry
    });
  } catch (error) {
    console.error('Error moving criteria:', error);
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error'
    });
  }
});

export default router;
