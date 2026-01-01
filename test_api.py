"""
Email Review API Test Suite

Run all API endpoint tests and verify correct behavior.
Usage: python test_api.py
"""

import json
import time
import subprocess
import requests
import sys

API_BASE = "http://localhost:5000"
TEST_PREFIX = "test-skill-"

# Colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

def check_server():
    """Check if Flask server is running, start if not."""
    try:
        requests.get(f"{API_BASE}/", timeout=2)
        print(f"{GREEN}Server already running on port 5000{RESET}")
        return True
    except:
        print(f"{YELLOW}Starting Flask server...{RESET}")
        subprocess.Popen(
            ["python", "email_review_server.py"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(2)
        try:
            requests.get(f"{API_BASE}/", timeout=2)
            print(f"{GREEN}Server started successfully{RESET}")
            return True
        except:
            print(f"{RED}Failed to start server{RESET}")
            return False

def load_json(filename):
    """Load JSON file."""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def save_json(filename, data):
    """Save JSON file."""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def count_matches(filename, domain):
    """Count entries matching domain in file."""
    data = load_json(filename)
    return sum(1 for d in data if d.get('primaryDomain', '') == domain)

def cleanup():
    """Remove all test entries from files."""
    for filename in ['criteria.json', 'criteria_1day_old.json', 'keep_criteria.json']:
        data = load_json(filename)
        original = len(data)
        data = [d for d in data if not d.get('primaryDomain', '').startswith(TEST_PREFIX)]
        if len(data) < original:
            save_json(filename, data)
            print(f"  Cleaned {original - len(data)} test entries from {filename}")

def run_tests():
    """Run all API tests."""
    results = []

    print("\n" + "="*60)
    print("EMAIL REVIEW API TEST SUITE")
    print("="*60 + "\n")

    # Pre-cleanup
    print("Pre-test cleanup...")
    cleanup()
    print()

    # Test 1: Delete button
    print("TEST 1: Delete button (add to criteria.json)")
    domain = f"{TEST_PREFIX}delete.com"
    try:
        r = requests.post(f"{API_BASE}/api/add-criteria", json={
            "domain": domain,
            "subject_pattern": "Newsletter Subject"
        })
        data = r.json()
        in_file = count_matches("criteria.json", domain)
        passed = data.get("success") and in_file == 1
        results.append(("Delete", "/api/add-criteria", passed,
                       f"success={data.get('success')}, in_file={in_file}"))
        print(f"  {'PASS' if passed else 'FAIL'}: {data.get('message', 'No message')}")
    except Exception as e:
        results.append(("Delete", "/api/add-criteria", False, str(e)))
        print(f"  FAIL: {e}")

    # Test 2: Keep button (should remove from criteria.json, add to keep)
    print("\nTEST 2: Keep button (removes from delete, adds to keep)")
    try:
        r = requests.post(f"{API_BASE}/api/mark-keep", json={
            "domain": domain,
            "subject_pattern": "Newsletter Subject",
            "category": "TEST"
        })
        data = r.json()
        in_criteria = count_matches("criteria.json", domain)
        in_keep = count_matches("keep_criteria.json", domain)
        passed = data.get("success") and data.get("removed_from_delete", 0) >= 1 and in_criteria == 0 and in_keep == 1
        results.append(("Keep", "/api/mark-keep", passed,
                       f"removed={data.get('removed_from_delete')}, in_criteria={in_criteria}, in_keep={in_keep}"))
        print(f"  {'PASS' if passed else 'FAIL'}: {data.get('message', 'No message')}")
    except Exception as e:
        results.append(("Keep", "/api/mark-keep", False, str(e)))
        print(f"  FAIL: {e}")

    # Test 3: Del All (domain-level)
    print("\nTEST 3: Del All (domain-level delete)")
    domain = f"{TEST_PREFIX}delall.com"
    try:
        r = requests.post(f"{API_BASE}/api/add-criteria", json={
            "domain": domain,
            "subject_pattern": ""
        })
        data = r.json()
        entry = data.get("entry", {})
        passed = data.get("success") and entry.get("subject") == ""
        results.append(("Del All", "/api/add-criteria", passed,
                       f"success={data.get('success')}, subject='{entry.get('subject')}'"))
        print(f"  {'PASS' if passed else 'FAIL'}: {data.get('message', 'No message')}")
    except Exception as e:
        results.append(("Del All", "/api/add-criteria", False, str(e)))
        print(f"  FAIL: {e}")

    # Test 4: Del 1d
    print("\nTEST 4: Del 1d (add to criteria_1day_old.json)")
    domain = f"{TEST_PREFIX}del1d.com"
    try:
        r = requests.post(f"{API_BASE}/api/add-criteria-1d", json={
            "domain": domain,
            "subject_pattern": "Daily Digest"
        })
        data = r.json()
        in_file = count_matches("criteria_1day_old.json", domain)
        passed = data.get("success") and in_file == 1
        results.append(("Del 1d", "/api/add-criteria-1d", passed,
                       f"success={data.get('success')}, in_file={in_file}"))
        print(f"  {'PASS' if passed else 'FAIL'}: {data.get('message', 'No message')}")
    except Exception as e:
        results.append(("Del 1d", "/api/add-criteria-1d", False, str(e)))
        print(f"  FAIL: {e}")

    # Test 5: Keep after Del 1d (cross-file removal)
    print("\nTEST 5: Keep after Del 1d (cross-file removal)")
    try:
        r = requests.post(f"{API_BASE}/api/mark-keep", json={
            "domain": domain,
            "subject_pattern": "Daily Digest",
            "category": "TEST"
        })
        data = r.json()
        in_1d = count_matches("criteria_1day_old.json", domain)
        in_keep = count_matches("keep_criteria.json", domain)
        passed = data.get("success") and data.get("removed_from_delete", 0) >= 1 and in_1d == 0 and in_keep == 1
        results.append(("Keep after Del 1d", "/api/mark-keep", passed,
                       f"removed={data.get('removed_from_delete')}, in_1d={in_1d}, in_keep={in_keep}"))
        print(f"  {'PASS' if passed else 'FAIL'}: {data.get('message', 'No message')}")
    except Exception as e:
        results.append(("Keep after Del 1d", "/api/mark-keep", False, str(e)))
        print(f"  FAIL: {e}")

    # Test 6: Keep All (domain-level protection)
    print("\nTEST 6: Keep All (domain-level protection)")
    domain = f"{TEST_PREFIX}keepall.com"
    try:
        r = requests.post(f"{API_BASE}/api/mark-keep", json={
            "domain": domain,
            "subject_pattern": "",
            "category": "DOMAIN"
        })
        data = r.json()
        entry = data.get("entry", {})
        passed = data.get("success") and entry.get("subject") == ""
        results.append(("Keep All", "/api/mark-keep", passed,
                       f"success={data.get('success')}, subject='{entry.get('subject')}'"))
        print(f"  {'PASS' if passed else 'FAIL'}: {data.get('message', 'No message')}")
    except Exception as e:
        results.append(("Keep All", "/api/mark-keep", False, str(e)))
        print(f"  FAIL: {e}")

    # Test 7: Del 1d All
    print("\nTEST 7: Del 1d All (domain-level 1-day delete)")
    domain = f"{TEST_PREFIX}del1dall.com"
    try:
        r = requests.post(f"{API_BASE}/api/add-criteria-1d", json={
            "domain": domain,
            "subject_pattern": ""
        })
        data = r.json()
        entry = data.get("entry", {})
        passed = data.get("success") and entry.get("subject") == ""
        results.append(("Del 1d All", "/api/add-criteria-1d", passed,
                       f"success={data.get('success')}, subject='{entry.get('subject')}'"))
        print(f"  {'PASS' if passed else 'FAIL'}: {data.get('message', 'No message')}")
    except Exception as e:
        results.append(("Del 1d All", "/api/add-criteria-1d", False, str(e)))
        print(f"  FAIL: {e}")

    # Test 8: Load Emails API (filtering statistics)
    print("\nTEST 8: Load Emails API (filtering statistics)")
    try:
        r = requests.get(f"{API_BASE}/api/load-emails")
        data = r.json()
        summary = data.get("summary", {})
        passed = data.get("success") and "total_emails" in summary
        results.append(("Load Emails", "/api/load-emails", passed,
                       f"total={summary.get('total_emails', 0)}"))
        if passed:
            print(f"  {GREEN}PASS{RESET}: Loaded email statistics")
            print(f"\n  {YELLOW}=== EMAIL FILTERING REPORT ==={RESET}")
            print(f"  Cache file: {data.get('cache_file')} ({data.get('cache_age_hours')}h old)")
            print(f"  Rules: {data.get('criteria_rules')} delete | {data.get('criteria_1d_rules')} del-1d | {data.get('keep_rules')} keep")
            print(f"\n  {'-'*40}")
            print(f"  {'Category':<25} {'Count':>10}")
            print(f"  {'-'*40}")
            print(f"  {'Total Unread Emails':<25} {summary.get('total_emails', 0):>10}")
            print(f"  {'Will Delete (criteria)':<25} {summary.get('will_delete_now', 0):>10}")
            print(f"  {'Will Delete 1d (criteria_1d)':<25} {summary.get('will_delete_1d', 0):>10}")
            print(f"  {'Protected (keep)':<25} {summary.get('protected', 0):>10}")
            print(f"  {'Need Review (undecided)':<25} {summary.get('need_review', 0):>10}")
            print(f"  {'-'*40}")

            # Show top domains for each category
            stats = data.get("stats", {})
            if stats.get("criteria_domains"):
                print(f"\n  Top domains to DELETE:")
                for domain, count in list(stats["criteria_domains"].items())[:5]:
                    print(f"    - {domain}: {count}")
            if stats.get("criteria_1d_domains"):
                print(f"\n  Top domains to DELETE after 1 day:")
                for domain, count in list(stats["criteria_1d_domains"].items())[:5]:
                    print(f"    - {domain}: {count}")
            if stats.get("keep_domains"):
                print(f"\n  Top PROTECTED domains:")
                for domain, count in list(stats["keep_domains"].items())[:5]:
                    print(f"    - {domain}: {count}")
        else:
            print(f"  FAIL: {data.get('error', 'Unknown error')}")
    except Exception as e:
        results.append(("Load Emails", "/api/load-emails", False, str(e)))
        print(f"  FAIL: {e}")

    # Cleanup
    print("\nPost-test cleanup...")
    cleanup()

    # Summary
    print("\n" + "="*60)
    print("TEST RESULTS SUMMARY")
    print("="*60)
    print(f"\n{'Test':<25} {'API':<25} {'Status':<10}")
    print("-"*60)

    passed_count = 0
    for name, api, passed, detail in results:
        status = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
        print(f"{name:<25} {api:<25} {status}")
        if passed:
            passed_count += 1

    print("-"*60)
    total = len(results)
    if passed_count == total:
        print(f"\n{GREEN}All {total} tests passed!{RESET}")
    else:
        print(f"\n{RED}{total - passed_count} of {total} tests failed{RESET}")

    return passed_count == total

if __name__ == "__main__":
    if not check_server():
        sys.exit(1)

    success = run_tests()
    sys.exit(0 if success else 1)
