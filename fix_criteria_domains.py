#!/usr/bin/env python3
"""
Fix Criteria Domain Data

Fixes entries with incorrect primaryDomain (especially for two-level TLDs like .co.in).
Also normalizes entries where domain was stored in wrong field.

Usage:
    python fix_criteria_domains.py --dry-run    # Preview changes
    python fix_criteria_domains.py              # Apply fixes
"""

import json
import argparse
from pathlib import Path
from copy import deepcopy

SCRIPT_DIR = Path(__file__).parent
CRITERIA_FILE = SCRIPT_DIR / "criteria.json"
CRITERIA_1DAY_FILE = SCRIPT_DIR / "criteria_1day_old.json"
KEEP_CRITERIA_FILE = SCRIPT_DIR / "keep_criteria.json"

# Two-level TLDs that require taking 3 parts for primary domain
TWO_LEVEL_TLDS = {
    'co.in', 'co.uk', 'co.nz', 'co.za', 'co.jp', 'co.kr',
    'com.au', 'com.br', 'com.mx', 'com.sg', 'com.hk', 'com.tw',
    'org.uk', 'org.au', 'org.in',
    'net.au', 'net.in',
    'gov.uk', 'gov.in',
    'ac.uk', 'ac.in',
    'edu.au', 'edu.in'
}


def get_primary_domain(full_domain: str) -> str:
    """Extract primary domain, handling two-level TLDs correctly."""
    if not full_domain:
        return ''

    # Remove any email prefix
    if '@' in full_domain:
        full_domain = full_domain.split('@')[-1]

    parts = full_domain.split('.')
    if len(parts) < 2:
        return full_domain

    # Check for two-level TLD
    last_two = '.'.join(parts[-2:]).lower()
    if last_two in TWO_LEVEL_TLDS and len(parts) >= 3:
        return '.'.join(parts[-3:])
    else:
        return '.'.join(parts[-2:])


def extract_domain_from_entry(entry: dict) -> str:
    """Extract domain from any field that contains it."""
    # Try primaryDomain first
    domain = entry.get('primaryDomain', '').strip()
    if domain and domain not in TWO_LEVEL_TLDS:
        return domain

    # Try subdomain field (might contain full domain or email)
    subdomain = entry.get('subdomain', '').strip()
    if subdomain:
        if '@' in subdomain:
            return subdomain.split('@')[-1]
        elif '.' in subdomain:
            return subdomain

    # Try email field - might be full email OR just domain
    email = entry.get('email', '').strip()
    if email:
        if '@' in email:
            return email.split('@')[-1]
        elif '.' in email:
            return email

    # Last resort: if primaryDomain was a two-level TLD, try to find more context
    if domain in TWO_LEVEL_TLDS:
        # Try to find domain in subdomain field
        if subdomain and not '@' in subdomain:
            return subdomain

    return domain


def fix_entry(entry: dict) -> tuple[dict, list[str]]:
    """Fix an entry and return the fixed entry plus list of changes made."""
    changes = []
    fixed = deepcopy(entry)

    # Extract the best domain we can find
    best_domain = extract_domain_from_entry(entry)
    proper_primary = get_primary_domain(best_domain)

    current_primary = entry.get('primaryDomain', '').strip()

    # Fix 1: primaryDomain is a bare two-level TLD (e.g., "co.in")
    if current_primary in TWO_LEVEL_TLDS:
        if best_domain and best_domain != current_primary:
            fixed['primaryDomain'] = proper_primary
            changes.append(f"primaryDomain: '{current_primary}' -> '{proper_primary}'")
        else:
            changes.append(f"WARNING: Could not fix '{current_primary}' - no better domain found")

    # Fix 2: primaryDomain is empty but domain exists in other fields
    elif not current_primary and proper_primary:
        fixed['primaryDomain'] = proper_primary
        changes.append(f"primaryDomain: '' -> '{proper_primary}'")

    # Fix 3: subdomain has email address
    subdomain = entry.get('subdomain', '').strip()
    if '@' in subdomain:
        domain_from_email = subdomain.split('@')[-1]
        fixed['subdomain'] = domain_from_email
        changes.append(f"subdomain: cleaned email '{subdomain}' -> '{domain_from_email}'")

    return fixed, changes


def fix_criteria_file(filepath: Path, dry_run: bool) -> dict:
    """Fix all entries in a criteria file."""
    if not filepath.exists():
        return {'file': filepath.name, 'status': 'not found', 'fixes': 0}

    with open(filepath, 'r', encoding='utf-8') as f:
        entries = json.load(f)

    fixed_entries = []
    all_changes = []
    fixes_count = 0

    for i, entry in enumerate(entries):
        fixed, changes = fix_entry(entry)
        fixed_entries.append(fixed)

        if changes:
            fixes_count += 1
            all_changes.append({
                'index': i,
                'original': entry,
                'changes': changes
            })

    if not dry_run and fixes_count > 0:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(fixed_entries, f, indent=2, ensure_ascii=False)

    return {
        'file': filepath.name,
        'total_entries': len(entries),
        'fixes_needed': fixes_count,
        'changes': all_changes,
        'applied': not dry_run
    }


def main():
    parser = argparse.ArgumentParser(description='Fix criteria domain data')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without applying')
    args = parser.parse_args()

    files = [CRITERIA_FILE, CRITERIA_1DAY_FILE, KEEP_CRITERIA_FILE]

    print(f"\n{'=' * 60}")
    print(f"  FIX CRITERIA DOMAINS {'(DRY RUN)' if args.dry_run else ''}")
    print(f"{'=' * 60}")

    total_fixes = 0

    for filepath in files:
        result = fix_criteria_file(filepath, args.dry_run)
        total_fixes += result.get('fixes_needed', 0)

        print(f"\n{result['file']}:")
        if result.get('status') == 'not found':
            print("  (file not found)")
            continue

        print(f"  Total entries: {result['total_entries']}")
        print(f"  Fixes needed: {result['fixes_needed']}")

        if result.get('changes'):
            print("\n  Changes:")
            for change in result['changes'][:10]:  # Show first 10
                print(f"    Entry {change['index']}:")
                for c in change['changes']:
                    print(f"      - {c}")

            if len(result['changes']) > 10:
                print(f"    ... and {len(result['changes']) - 10} more")

    print(f"\n{'-' * 60}")
    if args.dry_run:
        print(f"  DRY RUN: {total_fixes} entries would be fixed")
        print("  Run without --dry-run to apply changes")
    else:
        print(f"  Applied {total_fixes} fixes")


if __name__ == '__main__':
    main()
