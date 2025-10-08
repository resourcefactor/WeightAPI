import serial
import serial.tools.list_ports
from flask import Flask, jsonify
from flask_cors import CORS  # Add this import
from datetime import datetime
import re
import threading
import time
from collections import deque

import os
os.environ['FLASK_ENV'] = 'production'

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Global variables to store data
latest_data = None
last_changed_data = None
data_lock = threading.Lock()
serial_port = None

def clean_serial_data(raw_data):
    """Extract only patterns that start with +, have digits, and end with a letter"""
    try:
        matches = re.findall(r'\+\d+[A-Za-z]', raw_data)
        if matches:
            return ''.join(matches)
        return ''
    except Exception as e:
        print(f"Error cleaning data: {e}")
        return ''

def read_serial_data():
    """Continuously read and process data from serial port"""
    global latest_data, last_changed_data, serial_port
    
    buffer = ""
    last_received_time = time.time()
    
    while True:
        try:
            if serial_port and serial_port.is_open:
                # Read available data
                if serial_port.in_waiting > 0:
                    raw_data = serial_port.read(serial_port.in_waiting).decode('utf-8', errors='ignore')
                    buffer += raw_data
                    last_received_time = time.time()
                    
                    # Process if we have enough data or timeout (2 seconds)
                    if len(buffer) >= 60 or (time.time() - last_received_time) >= 2:
                        if buffer.strip():
                            cleaned_data = clean_serial_data(buffer)
                            
                            if cleaned_data:
                                with data_lock:
                                    # Always update latest data
                                    latest_data = {
                                        'data': cleaned_data,
                                        'timestamp': datetime.now().isoformat()
                                    }
                                    
                                    # Update last_changed only if data actually changed
                                    if not last_changed_data or last_changed_data['data'] != cleaned_data:
                                        last_changed_data = {
                                            'data': cleaned_data,
                                            'timestamp': datetime.now().isoformat()
                                        }
                                
                                # Update console display (overwrite same line)
                                print(f"\r[{datetime.now().strftime('%H:%M:%S')}] Current: {cleaned_data}", end='', flush=True)
                        
                        # Reset buffer
                        buffer = ""
                        last_received_time = time.time()
                else:
                    # Small delay when no data available
                    time.sleep(0.1)
            else:
                time.sleep(1)
                
        except Exception as e:
            print(f"\nError reading serial data: {e}")
            time.sleep(1)

def initialize_serial(port_name='COM3', baud_rate=9600):
    """Initialize serial port connection"""
    global serial_port
    
    try:
        # List available ports
        print("Available serial ports:")
        ports = serial.tools.list_ports.comports()
        for port in ports:
            print(f"  - {port.device}: {port.description}")
        
        print(f"Initializing serial port: {port_name} at {baud_rate} baud")
        
        serial_port = serial.Serial(
            port=port_name,
            baudrate=baud_rate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1
        )
        
        if serial_port.is_open:
            print(f"Serial port {port_name} is ready")
            return True
        else:
            print(f"Failed to open serial port {port_name}")
            return False
            
    except Exception as e:
        print(f"Error initializing serial port: {e}")
        return False

# Flask API Routes
@app.route('/api/current', methods=['GET'])
def get_current_data():
    """Get the latest received data"""
    with data_lock:
        if latest_data:
            return jsonify({
                'success': True,
                'message': 'Current data retrieved successfully',
                'data': latest_data,
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'message': 'No data available',
                'timestamp': datetime.now().isoformat()
            }), 404

@app.route('/api/last_changed', methods=['GET'])
def get_last_changed_data():
    """Get the last changed data (when value actually changed)"""
    with data_lock:
        if last_changed_data:
            return jsonify({
                'success': True,
                'message': 'Last changed data retrieved successfully',
                'data': last_changed_data,
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'message': 'No changed data available',
                'timestamp': datetime.now().isoformat()
            }), 404

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    port_status = "connected" if serial_port and serial_port.is_open else "disconnected"
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'AMPI Weight API - Python',
        'serial_port': port_status
    })

if __name__ == '__main__':
    # Initialize serial port
    serial_config = {
        'port_name': 'COM3',  # Change this to your actual COM port
        'baud_rate': 9600
    }
    
    if initialize_serial(serial_config['port_name'], serial_config['baud_rate']):
        # Start serial reading in a separate thread
        serial_thread = threading.Thread(target=read_serial_data, daemon=True)
        serial_thread.start()
        
        print("Serial reader thread started")
        print("Console display will update on the same line...")
        print("=" * 60)
    else:
        print("Running in API-only mode (no serial data)")
    
    print("API Endpoints:")
    print("  GET http://localhost:5000/api/current")
    print("  GET http://localhost:5000/api/last_changed") 
    print("  GET http://localhost:5000/api/health")
    print("=" * 60)
    
    # Start Flask app
    app.run(host='0.0.0.0', port=5000, debug=False)