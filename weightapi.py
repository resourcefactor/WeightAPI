import serial
import serial.tools.list_ports
from flask import Flask, jsonify, request
from datetime import datetime
import re
import threading
import time

app = Flask(__name__)

# Global variable for latest data
latest_data = None
data_lock = threading.Lock()
serial_port = None

# Manual CORS handling
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# Handle OPTIONS requests for all routes
@app.route('/api/weight', methods=['GET', 'OPTIONS'])
def get_weight_data():
    """Get recent weight data"""
    if request.method == 'OPTIONS':
        return '', 200
        
    with data_lock:
        if latest_data:
            return jsonify({
                'Success': True,
                'Message': 'Weight data retrieved successfully',
                'Data': [latest_data],
                'Count': 1,
                'Timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'Success': False,
                'Error': 'No weight data available',
                'Timestamp': datetime.now().isoformat()
            }), 404

@app.route('/api/weight/latest', methods=['GET', 'OPTIONS'])
def get_latest_weight_data():
    """Get latest weight data"""
    if request.method == 'OPTIONS':
        return '', 200
        
    with data_lock:
        if latest_data:
            return jsonify({
                'Success': True,
                'Message': 'Latest weight data retrieved successfully',
                'Data': latest_data,
                'Timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'Success': False,
                'Error': 'No weight data available',
                'Timestamp': datetime.now().isoformat()
            }), 404

@app.route('/api/weight/health', methods=['GET', 'OPTIONS'])
def health_check():
    """Health check endpoint"""
    if request.method == 'OPTIONS':
        return '', 200
        
    port_status = "connected" if serial_port and serial_port.is_open else "disconnected"
    return jsonify({
        'Status': 'Healthy',
        'Timestamp': datetime.now().isoformat(),
        'Service': 'AMPI Weight API',
        'Version': '1.0.0'
    })

def parse_weight_data(raw_data):
    """
    Parse A9 indicator weight data according to the protocol
    Raw data format like: +00000001B, +00123456B, etc.
    """
    try:
        # Extract weight patterns: + followed by digits ending with letter
        matches = re.findall(r'\+\d+[A-Za-z]', raw_data)
        if not matches:
            return None, None
        
        # Take the first complete weight reading
        weight_string = matches[0]
        
        # Extract numeric part (remove + and status character)
        numeric_part = weight_string[1:-1]  # Remove + and status character
        status_char = weight_string[-1].upper()  # Status character (B, U, etc.)
        
        # Parse weight value (assuming format is always in grams/kilograms)
        # Remove leading zeros and convert to float
        weight_value = float(numeric_part.lstrip('0') or '0')
        
        # Convert to kilograms (assuming the raw data is in grams)
        # A9 indicators often send data in grams, divide by 1000 for KG
        weight_kg = weight_value / 1000.0
        
        # Determine stability based on status character
        # According to A9 protocol, 'B' often means stable, 'U' means unstable
        is_stable = status_char == 'B'  # Adjust based on actual protocol
        
        return weight_kg, is_stable
        
    except Exception as e:
        print(f"Error parsing weight data: {e}")
        return None, None

def clean_serial_data(raw_data):
    """Extract weight patterns from raw serial data"""
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
                if serial_port.in_waiting > 0:
                    raw_data = serial_port.read(serial_port.in_waiting).decode('utf-8', errors='ignore')
                    buffer += raw_data
                    last_received_time = time.time()
                    
                    if buffer.strip():
                        cleaned_data = clean_serial_data(buffer)
                        
                        if cleaned_data:
                            # Parse the weight data
                            weight_value, is_stable = parse_weight_data(cleaned_data)
                            
                            with data_lock:
                                latest_data = {
                                    'Data': cleaned_data,  # Keep raw data
                                    'Timestamp': datetime.now().isoformat(),
                                    'WeightValue': weight_value,  # Parsed weight in KG
                                    'IsStable': is_stable       # Stability status
                                }
                            
                            # Format display: show weight with stability
                            current_time = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                            if weight_value is not None:
                                # Show formatted weight: "1.234 kg (Stable)" or "12.345 kg (Unstable)"
                                display_weight = f"{weight_value:.3f} kg"
                                stability_text = "Stable" if is_stable else "Unstable"
                                display_text = f"{display_weight} ({stability_text})"
                            else:
                                display_text = cleaned_data
                            
                            print(f"\r[{current_time}] {display_text}", end='', flush=True)
                    
                    buffer = ""
                    last_received_time = time.time()
                else:
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

if __name__ == '__main__':
    # Default to COM1 as requested
    serial_config = {
        'port_name': 'COM1',  # Default COM1
        'baud_rate': 9600
    }
    
    print("\033c", end="")
    print("A9 Weight Indicator - Formatted Display")
    print("=" * 50)
    print("Display: Weight in kg with stability status")
    print("API Endpoints:")
    print("  GET http://localhost:5000/api/weight/latest")
    print("  GET http://localhost:5000/api/weight")
    print("  GET http://localhost:5000/api/weight/health")
    print("=" * 50)
    print("Waiting for A9 indicator data...")
    
    if initialize_serial(serial_config['port_name'], serial_config['baud_rate']):
        serial_thread = threading.Thread(target=read_serial_data, daemon=True)
        serial_thread.start()
        
        print("Starting Flask development server on http://localhost:5000")
        print("Press Ctrl+C to stop the application")
        print("-" * 50)
        
        # Use Flask development server
        app.run(host='0.0.0.0', port=5000, debug=False)
        
    else:
        print("Failed to initialize serial port")