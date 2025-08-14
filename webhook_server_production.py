#!/usr/bin/env python3
"""
Production Webhook Server for Close Apollo Integration
Includes file management, logging, and health monitoring
"""

import os
import json
import time
import logging
from datetime import datetime
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from file_manager import FileManager

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Initialize file manager
fm = FileManager()

# Setup logging
log_file = fm.get_log_path("webhook_server")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# In-memory storage for webhook data (also persisted to files)
webhook_data = []

@app.route('/apollo-webhook', methods=['POST'])
def handle_apollo_webhook():
    """Handle incoming Apollo webhook for phone number enrichment"""
    try:
        data = request.json
        timestamp = datetime.now().isoformat()
        
        # Create webhook entry
        webhook_entry = {
            'timestamp': timestamp,
            'headers': dict(request.headers),
            'data': data
        }
        
        # Add to in-memory storage
        webhook_data.append(webhook_entry)
        
        # Save to persistent storage using file manager
        filepath = fm.save_webhook_response(webhook_entry)
        
        # Log the webhook reception
        logger.info(f"Apollo webhook received: {filepath}")
        
        # Extract and log useful information
        if 'people' in data:
            people = data.get('people', [])
            phone_count = sum(len(person.get('phone_numbers', [])) for person in people)
            logger.info(f"Received phone data for {len(people)} people, {phone_count} phone numbers total")
            
            # Log individual people for debugging
            for person in people:
                person_id = person.get('id', 'unknown')
                status = person.get('status', 'unknown')
                phones = len(person.get('phone_numbers', []))
                logger.info(f"  Person {person_id}: {status}, {phones} phone numbers")
        
        # Update the shared webhook_data.json for backward compatibility
        try:
            with open('webhook_data.json', 'w', encoding='utf-8') as f:
                json.dump(webhook_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Could not update webhook_data.json: {e}")
        
        return jsonify({'status': 'success', 'message': 'Data received'}), 200
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/webhook-health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Get storage usage
        usage = fm.get_storage_usage()
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'total_webhooks_received': len(webhook_data),
            'last_webhook': webhook_data[-1]['timestamp'] if webhook_data else None,
            'storage_usage': usage,
            'uptime_seconds': time.time() - start_time
        })
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/webhook-data', methods=['GET'])
def get_webhook_data():
    """Get all received webhook data"""
    return jsonify(webhook_data)

@app.route('/storage-usage', methods=['GET'])
def get_storage_usage():
    """Get current storage usage"""
    try:
        usage = fm.get_storage_usage()
        return jsonify({
            'status': 'success',
            'storage_usage': usage,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Storage usage error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/cleanup', methods=['POST'])
def cleanup_files():
    """Trigger file cleanup (admin endpoint)"""
    try:
        dry_run = request.args.get('dry_run', 'false').lower() == 'true'
        
        logger.info(f"File cleanup triggered (dry_run={dry_run})")
        stats = fm.cleanup_old_files(dry_run=dry_run)
        
        return jsonify({
            'status': 'success',
            'cleanup_stats': stats,
            'dry_run': dry_run,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Cleanup error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/', methods=['GET'])
def index():
    """Basic info page"""
    return jsonify({
        'service': 'Close Apollo Integration Webhook Server',
        'status': 'running',
        'timestamp': datetime.now().isoformat(),
        'endpoints': {
            'webhook': '/apollo-webhook (POST)',
            'health': '/webhook-health (GET)',
            'data': '/webhook-data (GET)', 
            'storage': '/storage-usage (GET)',
            'cleanup': '/cleanup (POST)'
        }
    })

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'status': 'error', 'message': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({'status': 'error', 'message': 'Internal server error'}), 500

# Startup
start_time = time.time()

if __name__ == '__main__':
    print("🚀 Starting Close Apollo Integration Webhook Server")
    print("=" * 60)
    
    # Setup directories
    fm.setup_directories()
    
    # Log startup
    logger.info("Webhook server starting up")
    logger.info(f"Data directory: {fm.data_dir}")
    
    # Get configuration
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV') != 'production'
    
    print(f"📡 Webhook endpoints:")
    print(f"  POST /apollo-webhook - Receive Apollo phone data")
    print(f"  GET  /webhook-health - Health check")
    print(f"  GET  /webhook-data   - View all received data")
    print(f"  GET  /storage-usage  - Storage usage stats")
    print(f"  POST /cleanup        - Trigger file cleanup")
    print()
    print(f"🌐 Server starting on http://{host}:{port}")
    print(f"📁 Data directory: {fm.data_dir}")
    print(f"🗂️  File retention: 7 days")
    print()
    print("Apollo phone data typically arrives 5-30 minutes after request")
    print("=" * 60)
    
    # Start the server
    if debug:
        app.run(host=host, port=port, debug=True)
    else:
        # Production mode - use gunicorn
        import subprocess
        cmd = [
            'gunicorn',
            '--bind', f'{host}:{port}',
            '--workers', '1',
            '--timeout', '300',
            '--keep-alive', '2',
            '--max-requests', '1000',
            '--access-logfile', str(fm.get_log_path("access")),
            '--error-logfile', str(fm.get_log_path("error")),
            'webhook_server_production:app'
        ]
        subprocess.run(cmd)
