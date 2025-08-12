from flask import Flask, request, jsonify
import json
import datetime
import os
import time

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
        
        # Save to timestamped logs file
        timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        unix_timestamp = int(time.time())
        log_filename = f'apollo_num_response.{timestamp_str}_{unix_timestamp}.json'
        
        with open(log_filename, 'w', encoding='utf-8') as f:
            json.dump(webhook_entry, f, indent=2)
        
        # Save to data file (overwrite mode for orchestrator)
        with open('webhook_data.json', 'w', encoding='utf-8') as f:
            json.dump(webhook_data, f, indent=2, ensure_ascii=False)
        
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



if __name__ == '__main__':
    print("Starting Apollo webhook server...")
    print("Endpoints available:")
    print("  POST /apollo-webhook - Receives Apollo phone data")
    print("  GET /webhook-health - Health check")
    print("  GET /webhook-data - View all received data")
    print("\nNext steps:")
    print("  1. Run this server")
    print("  2. Start ngrok: ngrok http 5000")
    print("  3. Run get_apollo_nums.py with your ngrok URL")
    print("\nApollo phone data typically arrives 5-30 minutes after request")
    app.run(host='0.0.0.0', port=5000, debug=True)
