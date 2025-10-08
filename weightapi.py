import serial
import serial.tools.list_ports
from flask import Flask, jsonify
from flask_cors import CORS
from datetime import datetime
import re
import threading
import time

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend access

# Global variable for latest data
latest_data = None
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
        return ''

def read_serial_data():
    """Continuously read and process data from serial port"""
    global latest_data
    
    buffer = ""
    last_received_time = time.time()
    
    while True:
        try:
            if serial_port and serial_port.is_open:
                # Read all available data
                if serial_port.in_waiting > 0:
                    raw_data = serial_port.read(serial_port.in_waiting).decode('utf-8', errors='ignore')
                    buffer += raw_data
                    last_received_time = time.time()
                    
                    # Process whenever we have data
                    if buffer.strip():
                        cleaned_data = clean_serial_data(buffer)
                        
                        if cleaned_data:
                            with data_lock:
                                # Update latest data with current timestamp
                                latest_data = {
                                    'data': cleaned_data,
                                    'timestamp': datetime.now().isoformat()
                                }
                            
                            # Update console display with timestamp (single line)
                            current_time = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                            print(f"\r[{current_time}] {cleaned_data}", end='', flush=True)
                    
                    # Reset buffer after processing
                    buffer = ""
                    last_received_time = time.time()
                else:
                    # Small delay when no data available
                    time.sleep(0.01)
            else:
                time.sleep(0.5)
                
        except Exception as e:
            print(f"\nError reading serial data: {e}")
            time.sleep(1)

def initialize_serial(port_name='COM1', baud_rate=9600):
    """Initialize serial port connection"""
    global serial_port
    
    try:
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
            timeout=0.1
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

# Single API endpoint
@app.route('/api/current', methods=['GET'])
def get_current_data():
    """Get the latest received data"""
    with data_lock:
        if latest_data:
            return jsonify({
                'success': True,
                'data': latest_data,
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'message': 'No data available yet',
                'timestamp': datetime.now().isoformat()
            }), 404

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    port_status = "connected" if serial_port and serial_port.is_open else "disconnected"
    return jsonify({
        'status': 'healthy',
        'service': 'AMPI Weight API',
        'serial_port': port_status,
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    # Initialize serial port - UPDATE THIS TO YOUR COM PORT
    serial_config = {
        'port_name': 'COM1',  # ⚠️ CHANGE THIS TO YOUR ACTUAL COM PORT
        'baud_rate': 9600     # ⚠️ CHANGE BAUD RATE IF NEEDED
    }
    
    # Clear console and set up display
    print("\033c", end="")  # Clear console
    print("AMPI Weight Monitor - Real-time Serial Data + API")
    print("=" * 60)
    print("Terminal: Real-time serial data (updating line)")
    print("API: http://localhost:5000/api/current")
    print("Health: http://localhost:5000/api/health")
    print("=" * 60)
    print("Waiting for serial data...")
    
    if initialize_serial(serial_config['port_name'], serial_config['baud_rate']):
        # Start serial reading in a separate thread
        serial_thread = threading.Thread(target=read_serial_data, daemon=True)
        serial_thread.start()
        
        # Start Flask app in main thread (no console output from API calls)
        print("Starting API server on http://localhost:5000")
        print("API calls will not interrupt terminal display")
        print("-" * 60)
        
        # Run Flask without development messages
        from waitress import serve
        serve(app, host='0.0.0.0', port=5000)
        
    else:
        print("Failed to initialize serial port")