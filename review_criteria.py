#!/usr/bin/env python3
"""
Review Criteria JSON Files

Utility to quickly view and analyze criteria.json, keep_criteria.json, etc.
Groups entries by domain and shows hierarchical view.

Usage:
    python review_criteria.py                     # Show all files summary
    python review_criteria.py --file criteria     # Show criteria.json details
    python review_criteria.py --domain nse.co.in  # Filter by domain
    python review_criteria.py --search alert      # Search in domain/subject
"""

import json
import argparse
import os
from collections import defaultdict
from pathlib import Path

# File paths
SCRIPT_DIR = Path(__file__).parent
CRITERIA_FILE = SCRIPT_DIR / "criteria.json"
CRITERIA_1DAY_FILE = SCRIPT_DIR / "criteria_1day_old.json"
KEEP_CRITERIA_FILE = SCRIPT_DIR / "keep_criteria.json"

# Two-level TLDs (common ones)
TWO_LEVEL_TLDS = {
    'co.in', 'co.uk', 'co.nz', 'co.za', 'com.au', 'com.br', 'com.mx',
    'org.uk', 'org.au', 'net.au', 'gov.uk', 'ac.uk', 'edu.au'
}


def load_json_file(filepath: Path) -> list:
    """Load a JSON file safely."""
    if not filepath.exists():
        return []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def get_primary_domain(domain: str) -> str:
    """Extract primary domain, handling two-level TLDs correctly."""
    if not domain:
        return domain

    parts = domain.split('.')
    if len(parts) < 2:
        return domain

    # Check for two-level TLD
    last_two = '.'.join(parts[-2:])
    if last_two.lower() in TWO_LEVEL_TLDS:
        # For two-level TLD, take last 3 parts
        return '.'.join(parts[-3:]) if len(parts) >= 3 else domain
    else:
        # Standard TLD, take last 2 parts
        return '.'.join(parts[-2:])


def extract_domain_from_entry(entry: dict) -> str:
    """Extract domain from any field that contains domain info."""
    # Try primaryDomain first
    domain = entry.get('primaryDomain', '').strip()
    if domain:
        return domain

    # Try subdomain field (might contain full domain or email)
    subdomain = entry.get('subdomain', '').strip()
    if subdomain:
        if '@' in subdomain:
            return subdomain.split('@')[-1]
        else:
            return subdomain

    # Try email field - might be full email OR just domain
    email = entry.get('email', '').strip()
    if email:
        if '@' in email:
            return email.split('@')[-1]
        elif '.' in email:
            # It's a domain in the email field (common pattern)
            return email

    return ''


def group_by_domain(entries: list) -> dict:
    """Group entries by primary domain with subdomain breakdown."""
    grouped = defaultdict(lambda: {'subdomains': defaultdict(list), 'entries': []})

    for entry in entries:
        domain = extract_domain_from_entry(entry)
        subdomain_field = entry.get('subdomain', '').strip()

        if domain:
            primary = get_primary_domain(domain)
            grouped[primary]['entries'].append(entry)

            # Track subdomain if it's a full domain different from primary
            if subdomain_field and '@' not in subdomain_field:
                subdomain_primary = get_primary_domain(subdomain_field)
                if subdomain_field != subdomain_primary:
                    grouped[primary]['subdomains'][subdomain_field].append(entry)

    return grouped


def format_entry(entry: dict) -> str:
    """Format a single entry for display."""
    parts = []

    email = entry.get('email', '')
    subdomain = entry.get('subdomain', '')
    primary = entry.get('primaryDomain', '')
    subject = entry.get('subject', '')
    exclude = entry.get('excludeSubject', '')

    if email:
        parts.append(f"email: {email}")
    if subdomain and subdomain != primary:
        parts.append(f"subdomain: {subdomain}")
    if subject:
        parts.append(f"subject: \"{subject[:50]}{'...' if len(subject) > 50 else ''}\"")
    if exclude:
        parts.append(f"exclude: {exclude}")

    if not parts:
        parts.append("(domain-level rule)")

    return ', '.join(parts)


def print_domain_hierarchy(grouped: dict, file_name: str, search: str = None):
    """Print domain hierarchy view."""
    print(f"\n{'=' * 60}")
    print(f"  {file_name}")
    print(f"{'=' * 60}")

    if not grouped:
        print("  (empty)")
        return

    # Sort by number of entries
    sorted_domains = sorted(grouped.items(), key=lambda x: len(x[1]['entries']), reverse=True)

    for domain, data in sorted_domains:
        if search and search.lower() not in domain.lower():
            # Check if search matches any entry
            match = any(
                search.lower() in format_entry(e).lower()
                for e in data['entries']
            )
            if not match:
                continue

        entries = data['entries']
        subdomains = data['subdomains']

        print(f"\n  {domain} ({len(entries)} rules)")
        print(f"  {'-' * 40}")

        # Show subdomains if any
        if subdomains:
            for subdomain, sub_entries in sorted(subdomains.items()):
                print(f"    +-- {subdomain}")
                for entry in sub_entries:
                    print(f"    |     +-- {format_entry(entry)}")

        # Show entries without subdomain grouping for simplicity
        for entry in entries[:10]:  # Limit to 10 for readability
            formatted = format_entry(entry)
            if search and search.lower() in formatted.lower():
                # Highlight matching entries
                print(f"    * {formatted}")
            else:
                print(f"      {formatted}")

        if len(entries) > 10:
            print(f"      ... and {len(entries) - 10} more")


def print_summary():
    """Print summary of all criteria files."""
    files = {
        'criteria.json (Delete)': CRITERIA_FILE,
        'criteria_1day_old.json (Delete after 1d)': CRITERIA_1DAY_FILE,
        'keep_criteria.json (Keep/Protect)': KEEP_CRITERIA_FILE
    }

    print("\n" + "=" * 60)
    print("  CRITERIA FILES SUMMARY")
    print("=" * 60)

    total = 0
    for name, filepath in files.items():
        entries = load_json_file(filepath)
        count = len(entries)
        total += count

        # Count unique domains using proper extraction
        domains = set(get_primary_domain(extract_domain_from_entry(e)) for e in entries)
        domains.discard('')  # Remove empty strings

        print(f"\n  {name}")
        print(f"    Rules: {count}")
        print(f"    Unique domains: {len(domains)}")

        if entries:
            # Show top 5 domains by rule count
            domain_counts = defaultdict(int)
            for e in entries:
                d = get_primary_domain(extract_domain_from_entry(e)) or 'unknown'
                domain_counts[d] += 1

            top = sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            print("    Top domains:")
            for domain, count in top:
                print(f"      - {domain}: {count} rules")

    print(f"\n  {'-' * 40}")
    print(f"  Total rules across all files: {total}")


def main():
    parser = argparse.ArgumentParser(description='Review criteria JSON files')
    parser.add_argument('--file', '-f', choices=['criteria', 'keep', '1day', 'all'],
                        default='all', help='Which file to show (default: all)')
    parser.add_argument('--domain', '-d', help='Filter by domain')
    parser.add_argument('--search', '-s', help='Search in domain/subject')
    parser.add_argument('--summary', action='store_true', help='Show summary only')

    args = parser.parse_args()

    if args.summary or (args.file == 'all' and not args.domain and not args.search):
        print_summary()
        if not args.domain and not args.search:
            return

    # Map file choices to paths
    file_map = {
        'criteria': ('criteria.json', CRITERIA_FILE),
        'keep': ('keep_criteria.json', KEEP_CRITERIA_FILE),
        '1day': ('criteria_1day_old.json', CRITERIA_1DAY_FILE)
    }

    files_to_show = list(file_map.values()) if args.file == 'all' else [file_map[args.file]]

    search_term = args.search or args.domain

    for file_name, filepath in files_to_show:
        entries = load_json_file(filepath)

        if args.domain:
            # Filter entries by domain
            entries = [e for e in entries if args.domain.lower() in e.get('primaryDomain', '').lower()]

        grouped = group_by_domain(entries)
        print_domain_hierarchy(grouped, file_name, search_term)


if __name__ == '__main__':
    main()
