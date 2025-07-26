#!/usr/bin/env python3
"""
Simple test web server to verify basic functionality
"""

from flask import Flask
import socket

app = Flask(__name__)

@app.route('/')
def hello():
    return """
    <html>
    <head><title>Test Server</title></head>
    <body>
        <h1>Test Web Server Working!</h1>
        <p>If you can see this, the basic web server setup is working.</p>
        <p>Port 8080 is accessible and Flask is functioning correctly.</p>
    </body>
    </html>
    """

@app.route('/test')
def test():
    return {'status': 'ok', 'message': 'Test endpoint working'}

if __name__ == '__main__':
    host = '127.0.0.1'
    port = 8080
    
    # Test if port is available
    try:
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.bind((host, port))
        test_socket.close()
        print(f"Port {port} is available")
    except OSError as e:
        print(f"Cannot bind to port {port}: {e}")
        exit(1)
    
    print(f"Starting test server on http://{host}:{port}")
    print("Try accessing http://localhost:8080 in your browser")
    
    try:
        app.run(host=host, port=port, debug=False)
    except Exception as e:
        print(f"Failed to start server: {e}")