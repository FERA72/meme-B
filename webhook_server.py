"""
Webhook server for receiving mint events from Helius
Runs a Flask server that listens for webhook POST requests
"""

from flask import Flask, request, jsonify
from threading import Thread
import os
from core.scanner import TokenScanner
from core.data_collector import DataCollector
from core.filters import TokenFilter
from db.database import init_database


# Initialize Flask app
app = Flask(__name__)

# Global scanner instance (initialized in main.py)
scanner: TokenScanner = None


@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint
    Returns 200 OK if server is running
    """
    return jsonify({'status': 'healthy', 'service': 'meme-beta.5'}), 200


@app.route('/webhook/mint', methods=['POST'])
def mint_webhook():
    """
    Main webhook endpoint for receiving mint events from Helius
    
    Helius will POST to this endpoint when a new token is minted
    Configure this URL in your Helius dashboard webhook settings
    
    Example URL: http://your-server-ip:5000/webhook/mint
    Or for ngrok: https://your-id.ngrok.io/webhook/mint
    """
    try:
        # Get JSON payload from Helius
        payload = request.get_json()
        
        if not payload:
            return jsonify({'error': 'No payload received'}), 400
        
        print(f"\n📨 Webhook received at {request.url}")
        
        # Process the mint event
        if scanner:
            result = scanner.process_webhook_payload(payload)
            
            if result:
                return jsonify({
                    'status': 'success',
                    'mint_address': result['mint_address'],
                    'symbol': result['symbol'],
                    'is_safe': result['is_safe']
                }), 200
            else:
                return jsonify({
                    'status': 'processed',
                    'message': 'Event processed but no new mint found'
                }), 200
        else:
            return jsonify({'error': 'Scanner not initialized'}), 500
            
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/webhook/test', methods=['POST'])
def test_webhook():
    """
    Test endpoint - manually submit a mint address to test the system
    
    POST JSON body:
    {
        "mint": "token_mint_address_here"
    }
    """
    try:
        data = request.get_json()
        mint_address = data.get('mint')
        
        if not mint_address:
            return jsonify({'error': 'No mint address provided'}), 400
        
        if scanner:
            result = scanner.process_mint_event(mint_address)
            
            if result:
                return jsonify({
                    'status': 'success',
                    'result': {
                        'mint_address': result['mint_address'],
                        'symbol': result['symbol'],
                        'name': result['name'],
                        'is_safe': result['is_safe'],
                        'filter_results': result['filter_results']
                    }
                }), 200
            else:
                return jsonify({'error': 'Failed to process mint'}), 500
        else:
            return jsonify({'error': 'Scanner not initialized'}), 500
            
    except Exception as e:
        print(f"❌ Test endpoint error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/stats', methods=['GET'])
def get_stats():
    """
    Get scanner statistics
    """
    if scanner:
        stats = scanner.get_stats()
        return jsonify(stats), 200
    else:
        return jsonify({'error': 'Scanner not initialized'}), 500


def init_webhook_server(scanner_instance: TokenScanner):
    """
    Initialize the webhook server with scanner instance
    
    Args:
        scanner_instance: Initialized TokenScanner
    """
    global scanner
    scanner = scanner_instance
    print("✓ Webhook server initialized")


def run_webhook_server(host: str = '0.0.0.0', port: int = 5000):
    """
    Start the Flask webhook server
    
    Args:
        host: Host to bind to (0.0.0.0 = all interfaces)
        port: Port to listen on (default 5000)
    """
    print(f"""
    🚀 Webhook Server Starting
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    Host: {host}
    Port: {port}
    
    Endpoints:
    - Health Check: http://{host}:{port}/health
    - Mint Webhook: http://{host}:{port}/webhook/mint
    - Test Webhook: http://{host}:{port}/webhook/test
    - Statistics:   http://{host}:{port}/stats
    
    Configure your Helius webhook to POST to:
    http://YOUR_SERVER_IP:{port}/webhook/mint
    
    If running locally, use ngrok for public URL:
    ngrok http {port}
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    """)
    
    app.run(host=host, port=port, debug=False, threaded=True)


def run_webhook_server_async(host: str = '0.0.0.0', port: int = 5000):
    """
    Run webhook server in a background thread
    Allows other processes to run simultaneously
    
    Args:
        host: Host to bind to
        port: Port to listen on
    """
    server_thread = Thread(target=run_webhook_server, args=(host, port), daemon=True)
    server_thread.start()
    return server_thread


# Example usage:
# init_webhook_server(scanner)
# run_webhook_server(port=5000)
