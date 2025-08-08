from flask import Flask, request, jsonify
import json
import datetime
import os

app = Flask(__name__)
webhook_data = []

@app.route('/apollo-webhook', methods=['POST'])
def handle_apollo_webhook():
    try:
        data = request.json
        timestamp = datetime.datetime.now().isoformat()
        
        webhook_entry = {
            'timestamp': timestamp,
            'headers': dict(request.headers),
            'data': data
        }
        
        webhook_data.append(webhook_entry)
        
        with open('webhook_logs.json', 'a', encoding='utf-8') as f:
            json.dump(webhook_entry, f, indent=2)
            f.write('\n' + '='*50 + '\n')
        
        print(f"[{timestamp}] APOLLO PHONE DATA RECEIVED!")
        print("=" * 50)
        
        if 'person' in data and 'phone_numbers' in data['person']:
            person = data['person']
            name = f"{person.get('first_name', '')} {person.get('last_name', '')}".strip()
            email = person.get('email', 'No email')
            phones = person.get('phone_numbers', [])
            
            print(f"Person: {name}")
            print(f"Email: {email}")
            print(f"Phone numbers found: {len(phones)}")
            for phone in phones:
                print(f"  - {phone.get('raw_number')} (type: {phone.get('type', 'unknown')})")
        else:
            print("Raw data:")
            print(json.dumps(data, indent=2))
        
        print("=" * 50)
        return jsonify({'status': 'success', 'message': 'Data received'}), 200
        
    except Exception as e:
        print(f"ERROR: Error processing webhook: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/webhook-health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.datetime.now().isoformat(),
        'total_webhooks_received': len(webhook_data),
        'last_webhook': webhook_data[-1]['timestamp'] if webhook_data else None
    })

@app.route('/webhook-data', methods=['GET'])
def get_webhook_data():
    return jsonify(webhook_data)

@app.route('/test-webhook', methods=['POST'])
def test_webhook():
    """Test endpoint to simulate Apollo sending data"""
    test_data = {
        'person': {
            'id': 'test_123',
            'email': '[email protected]',
            'phone_numbers': [
                {'raw_number': '+1234567890', 'sanitized_phone': '+11234567890', 'type': 'mobile'},
                {'raw_number': '+1987654321', 'sanitized_phone': '+11987654321', 'type': 'work'}
            ],
            'first_name': 'Test',
            'last_name': 'Person'
        }
    }
    
    # Directly call the webhook handler with test data
    timestamp = datetime.datetime.now().isoformat()
    webhook_entry = {
        'timestamp': timestamp,
        'headers': {'Content-Type': 'application/json'},
        'data': test_data
    }
    
    webhook_data.append(webhook_entry)
    
    with open('webhook_logs.json', 'a', encoding='utf-8') as f:
        json.dump(webhook_entry, f, indent=2)
        f.write('\n' + '='*50 + '\n')
    
    print(f"[{timestamp}] TEST WEBHOOK DATA RECEIVED!")
    print("=" * 50)
    print(f"Test Person: Test Person")
    print(f"Test Email: [email protected]")
    print(f"Test Phone numbers: +1234567890, +1987654321")
    print("=" * 50)
    
    return jsonify({'status': 'success', 'message': 'Test data processed'})

if __name__ == '__main__':
    print("Starting Apollo webhook server...")
    print("Endpoints available:")
    print("  POST /apollo-webhook - Receives Apollo phone data")
    print("  GET /webhook-health - Health check")
    print("  GET /webhook-data - View all received data")
    print("  POST /test-webhook - Test with mock data")
    print("\nNext steps:")
    print("  1. Run this server")
    print("  2. Start ngrok: ngrok http 5000")
    print("  3. Run test_webhook.py with your ngrok URL")
    print("\nApollo phone data typically arrives 5-30 minutes after request")
    app.run(host='0.0.0.0', port=5000, debug=True)
