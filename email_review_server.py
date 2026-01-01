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
KEEP_LIST_FILE = 'logs/keep_list.json'
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
    """Mark an email pattern as 'keep' for future reference."""
    try:
        data = request.json
        domain = data.get('domain')
        subject_pattern = data.get('subject_pattern')
        category = data.get('category')

        if not domain:
            return jsonify({'success': False, 'error': 'Domain is required'}), 400

        # Load existing keep list
        keep_list = load_json_file(KEEP_LIST_FILE)

        # Add entry with timestamp
        keep_entry = {
            'domain': domain,
            'subject_pattern': subject_pattern,
            'category': category,
            'marked_at': datetime.now().isoformat()
        }

        keep_list.append(keep_entry)
        save_json_file(KEEP_LIST_FILE, keep_list)

        logger.info(f"Marked as keep: {domain} (subject: {subject_pattern})")

        return jsonify({
            'success': True,
            'message': 'Marked as keep',
            'entry': keep_entry
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
