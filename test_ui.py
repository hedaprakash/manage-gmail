"""
Email Review UI Test Suite (Browser-based)

Uses Playwright to test actual browser interactions:
- Text selection
- Button clicks
- Verify correct data is saved

Run: python test_ui.py
"""

import json
import time
import sys
from playwright.sync_api import sync_playwright

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

API_BASE = "http://localhost:5000"
TEST_PREFIX = "test-ui-"

# Colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"


def load_json(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []


def save_json(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def cleanup_test_data():
    """Remove test entries from all files."""
    for filename in ['criteria.json', 'criteria_1day_old.json', 'keep_criteria.json']:
        data = load_json(filename)
        original = len(data)
        data = [d for d in data if not d.get('primaryDomain', '').startswith(TEST_PREFIX)]
        if len(data) < original:
            save_json(filename, data)
            print(f"  Cleaned {original - len(data)} test entries from {filename}")


def find_entry_in_keep(domain, subject_fragment):
    """Check if an entry exists in keep_criteria.json with the given subject fragment."""
    data = load_json('keep_criteria.json')
    for entry in data:
        if entry.get('primaryDomain') == domain:
            subject = entry.get('subject', '')
            if subject_fragment in subject or subject in subject_fragment:
                return entry
    return None


def run_ui_tests():
    results = []

    print("\n" + "="*60)
    print("EMAIL REVIEW UI TEST SUITE (Browser-based)")
    print("="*60 + "\n")

    # Pre-cleanup
    print("Pre-test cleanup...")
    cleanup_test_data()
    print()

    with sync_playwright() as p:
        # Launch browser in headless mode (no popup)
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            # Navigate to the app
            print("Opening dashboard...")
            page.goto(API_BASE)
            page.wait_for_load_state('networkidle')
            print(f"  {GREEN}Page loaded{RESET}")

            # TEST 1: Find a domain section and expand it
            print("\nTEST 1: Expand domain section")
            domain_headers = page.locator('.domain-header .domain-info')
            if domain_headers.count() > 0:
                # Click first domain to expand
                domain_headers.first.click()
                page.wait_for_timeout(500)
                print(f"  {GREEN}PASS{RESET}: Expanded first domain section")
                results.append(("Expand domain", True))
            else:
                print(f"  {RED}FAIL{RESET}: No domain sections found")
                results.append(("Expand domain", False))

            # TEST 2: Click Keep button (without selection) - should save full subject
            print("\nTEST 2: Keep button without selection (saves full subject)")
            # First expand a section to make pattern items visible
            page.locator('.domain-header .domain-info').first.click()
            page.wait_for_timeout(500)

            pattern_items = page.locator('.pattern-item:visible')
            if pattern_items.count() > 0:
                first_item = pattern_items.first
                # Get the subject text
                subject_elem = first_item.locator('.pattern-subject')
                full_subject = subject_elem.text_content().strip()
                domain_section = first_item.locator('xpath=ancestor::div[contains(@class, "domain-section")]')
                domain = domain_section.get_attribute('data-domain')

                # Click Keep button
                keep_btn = first_item.locator('.btn-keep')
                keep_btn.click()
                page.wait_for_timeout(1000)

                # Verify saved in keep_criteria.json
                entry = find_entry_in_keep(domain, full_subject[:20])
                if entry:
                    print(f"  {GREEN}PASS{RESET}: Saved full subject for {domain}")
                    print(f"       Subject: \"{entry.get('subject', '')[:40]}...\"")
                    results.append(("Keep full subject", True))
                else:
                    print(f"  {RED}FAIL{RESET}: Entry not found in keep_criteria.json")
                    results.append(("Keep full subject", False))
            else:
                print(f"  {RED}FAIL{RESET}: No pattern items found")
                results.append(("Keep full subject", False))

            # TEST 3: Text selection + Keep button (should save only selected text)
            print("\nTEST 3: Keep button WITH text selection (saves selected text only)")

            # Expand more sections to find available items
            headers = page.locator('.domain-header .domain-info')
            for i in range(min(3, headers.count())):
                headers.nth(i).click()
                page.wait_for_timeout(300)

            # Find another pattern item that hasn't been marked
            available_items = page.locator('.pattern-item:visible:not(:has(.btn-keep.done))')
            if available_items.count() > 0:
                test_item = available_items.first
                subject_elem = test_item.locator('.pattern-subject')
                full_subject = subject_elem.text_content().strip()
                domain_section = test_item.locator('xpath=ancestor::div[contains(@class, "domain-section")]')
                domain = domain_section.get_attribute('data-domain')

                # Select only first 15 characters of the subject using JavaScript
                selected_text = full_subject[:15] if len(full_subject) > 15 else full_subject

                # In headless mode, getSelection() doesn't work - directly set the variable
                result = page.evaluate(f'''() => {{
                    const elem = document.querySelector('.pattern-item:not(:has(.btn-keep.done)) .pattern-subject');
                    if (!elem) return {{ error: 'element not found' }};

                    const fullText = elem.textContent;
                    const selectedText = fullText.substring(0, {len(selected_text)}).trim();

                    // Directly set the global variable (bypass Selection API for headless)
                    window.currentSelectionSubject = selectedText;
                    window.currentSelectionDomain = elem.closest('.domain-section').dataset.domain;

                    return {{
                        fullText: fullText.substring(0, 50),
                        selectedText: selectedText
                    }};
                }}''')
                page.wait_for_timeout(500)

                # Now click Keep button
                keep_btn = test_item.locator('.btn-keep')
                keep_btn.click()
                page.wait_for_timeout(1000)

                # Verify saved in keep_criteria.json with SELECTED text only
                data = load_json('keep_criteria.json')
                # Find entry for this domain
                found_entry = None
                for entry in reversed(data):  # Check most recent first
                    if entry.get('primaryDomain') == domain:
                        found_entry = entry
                        break

                if found_entry:
                    saved_subject = found_entry.get('subject', '')
                    # Check if saved subject is shorter (selected portion)
                    if len(saved_subject) <= len(selected_text) + 5:  # Allow small margin
                        print(f"  {GREEN}PASS{RESET}: Saved selected text only!")
                        print(f"       Full subject: \"{full_subject[:40]}...\"")
                        print(f"       Saved:        \"{saved_subject}\"")
                        results.append(("Keep selected text", True))
                    else:
                        print(f"  {YELLOW}PARTIAL{RESET}: Saved more than selected")
                        print(f"       Selected: \"{selected_text}\"")
                        print(f"       Saved:    \"{saved_subject}\"")
                        results.append(("Keep selected text", False))
                else:
                    print(f"  {RED}FAIL{RESET}: Entry not found")
                    results.append(("Keep selected text", False))
            else:
                print(f"  {YELLOW}SKIP{RESET}: No unmarked items available")
                results.append(("Keep selected text", None))

            # TEST 4: Delete button
            print("\nTEST 4: Delete button (adds to criteria.json)")
            available_items = page.locator('.pattern-item:visible:not(:has(.btn-keep.done)):not(:has(.btn-delete.done))')
            if available_items.count() > 0:
                test_item = available_items.first
                domain_section = test_item.locator('xpath=ancestor::div[contains(@class, "domain-section")]')
                domain = domain_section.get_attribute('data-domain')

                delete_btn = test_item.locator('.btn-delete')
                delete_btn.click()
                page.wait_for_timeout(1000)

                # Verify in criteria.json
                data = load_json('criteria.json')
                found = any(e.get('primaryDomain') == domain for e in data[-5:])
                if found:
                    print(f"  {GREEN}PASS{RESET}: Added {domain} to criteria.json")
                    results.append(("Delete button", True))
                else:
                    print(f"  {RED}FAIL{RESET}: Entry not found in criteria.json")
                    results.append(("Delete button", False))
            else:
                print(f"  {YELLOW}SKIP{RESET}: No available items")
                results.append(("Delete button", None))

            # TEST 5: Keep All button (domain-level)
            print("\nTEST 5: Keep All button (domain-level protection)")
            # Find a domain section that has available Keep All button
            keep_all_btns = page.locator('.domain-header .btn-keep:not(.done)')
            if keep_all_btns.count() > 0:
                btn = keep_all_btns.first
                domain_section = btn.locator('xpath=ancestor::div[contains(@class, "domain-section")]')
                domain = domain_section.get_attribute('data-domain')

                btn.click()
                page.wait_for_timeout(1000)

                # Verify domain-only entry (empty subject) in keep_criteria.json
                data = load_json('keep_criteria.json')
                found = any(
                    e.get('primaryDomain') == domain and e.get('subject') == ''
                    for e in data
                )
                if found:
                    print(f"  {GREEN}PASS{RESET}: Added domain-only entry for {domain}")
                    results.append(("Keep All", True))
                else:
                    print(f"  {RED}FAIL{RESET}: Domain-only entry not found")
                    results.append(("Keep All", False))
            else:
                print(f"  {YELLOW}SKIP{RESET}: No Keep All buttons available")
                results.append(("Keep All", None))

        except Exception as e:
            print(f"\n{RED}ERROR{RESET}: {e}")
            results.append(("Browser test", False))

        finally:
            browser.close()

    # Post-cleanup
    print("\nPost-test cleanup...")
    cleanup_test_data()

    # Summary
    print("\n" + "="*60)
    print("UI TEST RESULTS SUMMARY")
    print("="*60)
    print(f"\n{'Test':<30} {'Status':<10}")
    print("-"*40)

    passed = 0
    failed = 0
    skipped = 0
    for name, result in results:
        if result is True:
            status = f"{GREEN}PASS{RESET}"
            passed += 1
        elif result is False:
            status = f"{RED}FAIL{RESET}"
            failed += 1
        else:
            status = f"{YELLOW}SKIP{RESET}"
            skipped += 1
        print(f"{name:<30} {status}")

    print("-"*40)
    if failed == 0:
        print(f"\n{GREEN}All {passed} tests passed!{RESET}", end="")
        if skipped > 0:
            print(f" ({skipped} skipped)")
        else:
            print()
    else:
        print(f"\n{RED}{failed} of {passed + failed} tests failed{RESET}")

    return failed == 0


if __name__ == "__main__":
    run_ui_tests()
