"""
Email Review Server

A simple Flask server that serves the interactive email categorization report
and handles button clicks to update criteria files.
"""

import os
import json
import logging
from datetime import datetime
from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# File paths
CRITERIA_FILE = 'criteria.json'
CRITERIA_1DAY_FILE = 'criteria_1day_old.json'
KEEP_CRITERIA_FILE = 'keep_criteria.json'  # Safe list - emails matching these are NEVER deleted
KEEP_LIST_FILE = 'logs/keep_list.json'  # Log of keep decisions
CURRENT_REPORT_FILE = 'logs/current_report.html'


def load_json_file(filepath):
    """Load JSON file, return empty list if not exists."""
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save_json_file(filepath, data):
    """Save data to JSON file."""
    # Ensure directory exists
    os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else '.', exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def create_criteria_entry(domain, subject_pattern=None, exclude_subject=None):
    """Create a criteria entry in the expected format."""
    return {
        "email": "",
        "subdomain": "",
        "primaryDomain": domain,
        "subject": subject_pattern or "",
        "toEmails": "",
        "ccEmails": "",
        "excludeSubject": exclude_subject or ""
    }


def is_duplicate_criteria(criteria_list, new_entry):
    """Check if a similar criteria already exists."""
    for entry in criteria_list:
        if (entry.get('primaryDomain', '').lower() == new_entry.get('primaryDomain', '').lower() and
            entry.get('subject', '').lower() == new_entry.get('subject', '').lower()):
            return True
    return False


def matches_criteria_pattern(entry, domain, subject_pattern):
    """Check if a criteria entry matches the given domain and subject pattern."""
    entry_domain = entry.get('primaryDomain', '').lower()
    entry_subject = entry.get('subject', '').lower()

    domain_lower = domain.lower() if domain else ''
    subject_lower = subject_pattern.lower() if subject_pattern else ''

    # Match if domain matches AND (subject matches OR either subject is empty)
    if entry_domain == domain_lower:
        if not entry_subject or not subject_lower:
            return True
        if entry_subject in subject_lower or subject_lower in entry_subject:
            return True
    return False


def remove_from_criteria(domain, subject_pattern):
    """Remove matching entries from criteria.json. Returns count of removed entries."""
    criteria = load_json_file(CRITERIA_FILE)
    original_count = len(criteria)

    # Filter out matching entries
    criteria = [c for c in criteria if not matches_criteria_pattern(c, domain, subject_pattern)]

    removed_count = original_count - len(criteria)
    if removed_count > 0:
        save_json_file(CRITERIA_FILE, criteria)
        logger.info(f"Removed {removed_count} entries from criteria.json for {domain}")

    return removed_count


@app.route('/')
def serve_report():
    """Serve the current HTML report."""
    if os.path.exists(CURRENT_REPORT_FILE):
        return send_file(CURRENT_REPORT_FILE)
    return "No report generated yet. Run categorize_emails.py first.", 404


@app.route('/api/add-criteria', methods=['POST'])
def add_criteria():
    """Add an entry to criteria.json (immediate deletion)."""
    try:
        data = request.json
        domain = data.get('domain')
        subject_pattern = data.get('subject_pattern')
        exclude_subject = data.get('exclude_subject')

        if not domain:
            return jsonify({'success': False, 'error': 'Domain is required'}), 400

        # Load existing criteria
        criteria = load_json_file(CRITERIA_FILE)

        # Create new entry
        new_entry = create_criteria_entry(domain, subject_pattern, exclude_subject)

        # Check for duplicates
        if is_duplicate_criteria(criteria, new_entry):
            return jsonify({
                'success': False,
                'error': 'Similar criteria already exists'
            }), 409

        # Add and save
        criteria.append(new_entry)
        save_json_file(CRITERIA_FILE, criteria)

        logger.info(f"Added criteria: {domain} (subject: {subject_pattern})")

        return jsonify({
            'success': True,
            'message': f'Added to {CRITERIA_FILE}',
            'entry': new_entry,
            'total_criteria': len(criteria)
        })

    except Exception as e:
        logger.error(f"Error adding criteria: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/add-criteria-1d', methods=['POST'])
def add_criteria_1day():
    """Add an entry to criteria_1day_old.json (delete after 1 day)."""
    try:
        data = request.json
        domain = data.get('domain')
        subject_pattern = data.get('subject_pattern')
        exclude_subject = data.get('exclude_subject')

        if not domain:
            return jsonify({'success': False, 'error': 'Domain is required'}), 400

        # Load existing criteria
        criteria = load_json_file(CRITERIA_1DAY_FILE)

        # Create new entry
        new_entry = create_criteria_entry(domain, subject_pattern, exclude_subject)

        # Check for duplicates
        if is_duplicate_criteria(criteria, new_entry):
            return jsonify({
                'success': False,
                'error': 'Similar criteria already exists'
            }), 409

        # Add and save
        criteria.append(new_entry)
        save_json_file(CRITERIA_1DAY_FILE, criteria)

        logger.info(f"Added 1-day criteria: {domain} (subject: {subject_pattern})")

        return jsonify({
            'success': True,
            'message': f'Added to {CRITERIA_1DAY_FILE}',
            'entry': new_entry,
            'total_criteria': len(criteria)
        })

    except Exception as e:
        logger.error(f"Error adding 1-day criteria: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/mark-keep', methods=['POST'])
def mark_keep():
    """Mark an email pattern as 'keep' - removes from delete criteria AND adds to safe list."""
    try:
        data = request.json
        domain = data.get('domain')
        subject_pattern = data.get('subject_pattern')
        category = data.get('category')

        if not domain:
            return jsonify({'success': False, 'error': 'Domain is required'}), 400

        # 1. FIRST: Remove from criteria.json if present (undo auto-add for PROMO)
        removed_count = remove_from_criteria(domain, subject_pattern)

        # 2. Add to keep_criteria.json (the actual safe list used by delete_gmails.py)
        keep_criteria = load_json_file(KEEP_CRITERIA_FILE)

        # Create criteria entry in same format as delete criteria
        keep_entry = create_criteria_entry(domain, subject_pattern)

        # Check for duplicates
        added_to_keep = False
        if not is_duplicate_criteria(keep_criteria, keep_entry):
            keep_criteria.append(keep_entry)
            save_json_file(KEEP_CRITERIA_FILE, keep_criteria)
            added_to_keep = True
            logger.info(f"Added to safe list: {domain} (subject: {subject_pattern})")

        # 3. Also log to keep_list.json for reference with timestamp
        keep_list = load_json_file(KEEP_LIST_FILE)
        log_entry = {
            'domain': domain,
            'subject_pattern': subject_pattern,
            'category': category,
            'marked_at': datetime.now().isoformat(),
            'removed_from_delete': removed_count
        }
        keep_list.append(log_entry)
        save_json_file(KEEP_LIST_FILE, keep_list)

        # Build response message
        message_parts = []
        if removed_count > 0:
            message_parts.append(f'Removed {removed_count} from delete criteria')
        if added_to_keep:
            message_parts.append(f'Added to safe list ({len(keep_criteria)} protected)')
        else:
            message_parts.append('Already in safe list')

        return jsonify({
            'success': True,
            'message': ' | '.join(message_parts),
            'entry': keep_entry,
            'total_protected': len(keep_criteria),
            'removed_from_delete': removed_count
        })

    except Exception as e:
        logger.error(f"Error marking keep: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get current criteria statistics."""
    try:
        criteria = load_json_file(CRITERIA_FILE)
        criteria_1d = load_json_file(CRITERIA_1DAY_FILE)
        keep_list = load_json_file(KEEP_LIST_FILE)

        return jsonify({
            'success': True,
            'stats': {
                'criteria_count': len(criteria),
                'criteria_1day_count': len(criteria_1d),
                'keep_count': len(keep_list)
            }
        })

    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/undo-last', methods=['POST'])
def undo_last():
    """Undo the last added criteria."""
    try:
        data = request.json
        file_type = data.get('file_type', 'criteria')  # 'criteria' or 'criteria_1d'

        filepath = CRITERIA_FILE if file_type == 'criteria' else CRITERIA_1DAY_FILE
        criteria = load_json_file(filepath)

        if not criteria:
            return jsonify({'success': False, 'error': 'No criteria to undo'}), 400

        removed = criteria.pop()
        save_json_file(filepath, criteria)

        logger.info(f"Undid last criteria: {removed}")

        return jsonify({
            'success': True,
            'message': 'Last criteria removed',
            'removed': removed,
            'remaining': len(criteria)
        })

    except Exception as e:
        logger.error(f"Error undoing: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


def run_server(port=5000):
    """Start the Flask server."""
    logger.info(f"Starting email review server on http://localhost:{port}")
    app.run(host='localhost', port=port, debug=False)


if __name__ == '__main__':
    run_server()
