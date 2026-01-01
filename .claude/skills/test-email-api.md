# Skill: test-email-api

Test all Email Review API endpoints and verify correct behavior.

## Instructions

When this skill is invoked, perform the following tests WITHOUT asking any questions:

### Pre-flight Check
1. Check if Flask server is running on port 5000
2. If not running, start it: `cd D:/myprojects/gmail && python email_review_server.py &`
3. Wait 2 seconds for server to start

### Test Execution

Run ALL tests using curl commands. Use test domains prefixed with `test-skill-` to avoid conflicts.

#### Test 1: Delete Button (add to criteria.json)
```bash
curl -s -X POST http://localhost:5000/api/add-criteria \
  -H "Content-Type: application/json" \
  -d '{"domain": "test-skill-delete.com", "subject_pattern": "Newsletter Subject"}'
```
**Expected:** `success: true`, `message` contains "Added to criteria.json"
**Verify:** `grep "test-skill-delete.com" criteria.json` returns 1 match

#### Test 2: Keep Button (removes from delete, adds to keep)
```bash
curl -s -X POST http://localhost:5000/api/mark-keep \
  -H "Content-Type: application/json" \
  -d '{"domain": "test-skill-delete.com", "subject_pattern": "Newsletter Subject", "category": "TEST"}'
```
**Expected:** `removed_from_delete: 1`, `success: true`
**Verify:**
- `grep "test-skill-delete.com" criteria.json` returns 0 matches
- `grep "test-skill-delete.com" keep_criteria.json` returns 1 match

#### Test 3: Del All (domain-level delete)
```bash
curl -s -X POST http://localhost:5000/api/add-criteria \
  -H "Content-Type: application/json" \
  -d '{"domain": "test-skill-delall.com", "subject_pattern": ""}'
```
**Expected:** `success: true`, entry has empty `subject`
**Verify:** Entry in criteria.json has `"subject": ""`

#### Test 4: Del 1d (add to criteria_1day_old.json)
```bash
curl -s -X POST http://localhost:5000/api/add-criteria-1d \
  -H "Content-Type: application/json" \
  -d '{"domain": "test-skill-del1d.com", "subject_pattern": "Daily Digest"}'
```
**Expected:** `success: true`, `message` contains "criteria_1day_old.json"
**Verify:** `grep "test-skill-del1d.com" criteria_1day_old.json` returns 1 match

#### Test 5: Keep after Del 1d (cross-file removal)
```bash
curl -s -X POST http://localhost:5000/api/mark-keep \
  -H "Content-Type: application/json" \
  -d '{"domain": "test-skill-del1d.com", "subject_pattern": "Daily Digest", "category": "TEST"}'
```
**Expected:** `removed_from_delete: 1`, `success: true`
**Verify:**
- `grep "test-skill-del1d.com" criteria_1day_old.json` returns 0 matches
- `grep "test-skill-del1d.com" keep_criteria.json` returns 1 match

#### Test 6: Keep All (domain-level protection)
```bash
curl -s -X POST http://localhost:5000/api/mark-keep \
  -H "Content-Type: application/json" \
  -d '{"domain": "test-skill-keepall.com", "subject_pattern": "", "category": "DOMAIN"}'
```
**Expected:** `success: true`, entry has empty `subject`
**Verify:** Entry in keep_criteria.json has `"primaryDomain": "test-skill-keepall.com"` and `"subject": ""`

#### Test 7: Del 1d All (domain-level 1-day delete)
```bash
curl -s -X POST http://localhost:5000/api/add-criteria-1d \
  -H "Content-Type: application/json" \
  -d '{"domain": "test-skill-del1dall.com", "subject_pattern": ""}'
```
**Expected:** `success: true`, entry has empty `subject`
**Verify:** Entry in criteria_1day_old.json has `"subject": ""`

### Cleanup
After all tests, remove test data:
```python
import json
for filename in ['criteria.json', 'criteria_1day_old.json', 'keep_criteria.json']:
    with open(filename, 'r', encoding='utf-8') as f:
        data = json.load(f)
    data = [d for d in data if not d.get('primaryDomain', '').startswith('test-skill-')]
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
```

### Output Format
Report results as a table:

| Test | API | Expected | Actual | Status |
|------|-----|----------|--------|--------|
| 1. Delete | /api/add-criteria | Added to criteria.json | ... | PASS/FAIL |
| 2. Keep | /api/mark-keep | Removed + Added to keep | ... | PASS/FAIL |
| ... | ... | ... | ... | ... |

End with: "All X tests passed" or "Y of X tests failed: [list failures]"
