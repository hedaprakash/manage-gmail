# Session Log - Gmail Dashboard

## Current State (2026-01-03)

### What's Been Built

#### 1. SQL Server Database (Complete)
- **Container:** `gmail-sqlserver` running on port 1433
- **Database:** `GmailCriteria`
- **Tables:**
  - `criteria` - 435 entries (425 domains, 9 subdomains, 1 email)
  - `patterns` - 81 subject patterns
  - `email_patterns` - For fromEmails/toEmails rules

#### 2. Stored Procedure: `EvaluateEmails` (Complete)
Batch evaluates emails against all criteria rules. Returns action for each email.

**Location:** `scripts/db/03-create-evaluate-procedure.sql`

**Usage:**
```sql
DECLARE @Emails dbo.EmailInputType;
INSERT INTO @Emails (EmailId, FromEmail, ToEmail, Subject, PrimaryDomain, Subdomain, EmailDate)
VALUES ('E001', 'news@example.com', 'me@gmail.com', 'Newsletter', 'example.com', NULL, GETDATE());

EXEC dbo.EvaluateEmails @Emails = @Emails, @Verbose = 1;
```

**Matching Priority (implemented):**
1. Email address as top-level key (highest)
2. fromEmails keep rules
3. fromEmails delete rules
4. toEmails keep rules
5. toEmails delete rules
6. Subject keep patterns
7. Subject delete patterns
8. Subject delete_1d patterns
9. Default action
10. No match = undecided (lowest)

#### 3. Comprehensive Test Suite (Complete)
**Location:** `scripts/db/05-comprehensive-test.sql`

Covers 37 test cases:
- Group A: Default delete domain (8 tests)
- Group B: Default keep domain (5 tests)
- Group C: Mixed domain - no default (5 tests)
- Group D: Parent/subdomain hierarchy (9 tests)
- Group E: Email key override (3 tests)
- Group F: delete_1d default (2 tests)
- Group G: Unknown domains (2 tests)
- Group H: Priority conflicts (3 tests)

#### 4. Environment Configuration (Complete)
- `.env` and `.env.example` created
- `docker-compose.yaml` uses environment variables
- `setup.sh` reads from `.env`
- `.gitignore` protects secrets

#### 5. Node.js Integration (Complete)
- `server/config/database.ts` - SQL Server connection config
- `server/services/database.ts` - Connection pool and query utilities
- `server/services/criteria.ts` - Updated with SQL support and fromEmails/toEmails
- `server/scripts/sync-criteria.ts` - Sync between JSON and SQL

### File Structure

```
gmail-dashboard/
├── .env                              # Environment variables (gitignored)
├── .env.example                      # Template for .env
├── .gitignore                        # Ignores .env, node_modules, etc.
├── docker-compose.yaml               # SQL Server container config
├── CRITERIA_SPEC.md                  # Complete criteria specification
├── package.json                      # Includes mssql dependency
│
├── scripts/db/
│   ├── README.md                     # Database documentation
│   ├── setup.sh                      # One-command setup script
│   ├── 01-init-schema.sql           # Creates database and tables
│   ├── 02-migrate-data.sql          # Migrates JSON data to SQL
│   ├── 03-create-evaluate-procedure.sql  # EvaluateEmails stored procedure
│   ├── 04-test-evaluate-procedure.sql    # Basic tests
│   ├── 05-comprehensive-test.sql         # Full test suite (37 cases)
│   └── generate-migration.cjs       # Regenerates 02-migrate-data.sql
│
├── server/
│   ├── config/
│   │   └── database.ts              # SQL Server connection config
│   ├── services/
│   │   ├── database.ts              # Connection pool, query utilities
│   │   └── criteria.ts              # Criteria matching (JSON + SQL)
│   └── scripts/
│       └── sync-criteria.ts         # JSON <-> SQL sync utility
```

### NPM Scripts Available

```bash
npm run dev              # Start dev server (Vite + Express)
npm run db:compare       # Compare JSON and SQL data
npm run db:export        # Export SQL to JSON
npm run db:import        # Import JSON to SQL
```

### Quick Start Commands

```bash
# Start SQL Server
docker-compose up -d

# Run full setup (schema + data + procedures)
./scripts/db/setup.sh

# Run comprehensive tests
docker cp scripts/db/05-comprehensive-test.sql gmail-sqlserver:/tmp/
docker exec gmail-sqlserver /opt/mssql-tools18/bin/sqlcmd \
  -S localhost -U sa -P "MyPass@word123" -C -d GmailCriteria \
  -i /tmp/05-comprehensive-test.sql

# Start Node.js server with SQL enabled
USE_SQL_DATABASE=true npm run dev
```

### What's Next (Suggested)

1. **Connect Python delete script to SQL**
   - Update `delete_gmails.py` to call `EvaluateEmails` stored procedure
   - This ensures Python and Node.js use the exact same logic

2. **Add validation stored procedure**
   - Create procedure to detect "oxymoron" violations
   - Validate criteria before allowing inserts

3. **Build criteria management UI**
   - CRUD operations for criteria via the dashboard
   - Real-time validation feedback

4. **Add audit logging**
   - Log every delete decision with the matched rule
   - Track what was deleted and why

### Key Design Decisions

1. **SQL is the source of truth** - JSON kept as backup only
2. **Dual-write strategy** - Writes go to both JSON and SQL
3. **Set-based processing** - No loops/cursors in stored procedure
4. **Priority-based matching** - Higher priority rules win (email > fromEmails > pattern > default)
5. **Subdomain isolation** - Subdomain rules completely override parent

### Database Connection

```
Host: localhost
Port: 1433
Database: GmailCriteria
User: sa
Password: (see .env file)
```

### Test Results Summary

All 37 test cases pass. Key scenarios verified:
- Default actions (delete, delete_1d, keep)
- Subject pattern matching (keep > delete > delete_1d)
- fromEmails/toEmails rules (highest priority)
- Subdomain overrides parent
- Email address keys override domain
- Unknown domains = undecided
- Priority conflicts resolved correctly
