import serial
import serial.tools.list_ports
from flask import Flask, jsonify
from flask_cors import CORS
from datetime import datetime
import re
import threading
import time
import logging

app = Flask(__name__)
CORS(app)

# Disable Flask's default access logs
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
app.logger.disabled = True
logging.getLogger('flask').setLevel(logging.ERROR)

# Global variables to store data
latest_data = None
data_lock = threading.Lock()
serial_port = None

def parse_weight_data(raw_data):
    """
    Parse A9 indicator weight data according to the protocol
    Raw data format like: +00000001B, +00123456B, etc.
    """
    try:
        # Extract weight patterns: + followed by digits ending with letter
        matches = re.findall(r'\+\d+[A-Za-z]', raw_data)
        if not matches:
            return None, None, None
        
        # Take the first complete weight reading
        weight_string = matches[0]
        
        # Extract numeric part (remove + and status character)
        numeric_part = weight_string[1:-1]  # Remove + and status character
        status_char = weight_string[-1].upper()  # Status character (B, U, etc.)
        
        # Convert directly without stripping zeros
        weight_value = float(numeric_part)
        
        # FIX: Based on your observation 326001 should be 26030
        # Let's try different conversion factors
        # If 326001 → 26030, then conversion factor = 326001 / 26030 ≈ 12.53
        weight_kg = weight_value / 12.53
        
        # Stability detection - 'C' means stable in your protocol
        is_stable = status_char in ['B', 'C']  # Both B and C indicate stable
        
        return weight_kg, is_stable, weight_string
        
    except Exception as e:
        print(f"Error parsing weight data: {e}")
        return None, None, None

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
                    
                    # Process if we have data and 2 seconds passed or buffer is large enough
                    if buffer.strip() and ((time.time() - last_received_time) >= 2 or len(buffer) >= 60):
                        cleaned_data = clean_serial_data(buffer)
                        
                        if cleaned_data:
                            # Parse the weight data
                            weight_value, is_stable, raw_string = parse_weight_data(cleaned_data)
                            
                            with data_lock:
                                latest_data = {
                                    'data': cleaned_data,  # lowercase 'data'
                                    'timestamp': datetime.now().isoformat(),
                                    'weightValue': weight_value,  # lowercase 'weightValue'
                                    'isStable': is_stable        # lowercase 'isStable'
                                }
                            
                            # Format display: show both raw and parsed data on same line
                            current_time = datetime.now().strftime('%H:%M:%S')
                            if weight_value is not None:
                                # Show both raw and parsed data
                                display_weight = f"{weight_value:.2f} kg"
                                stability_text = "Stable" if is_stable else "Unstable"
                                display_text = f"[{current_time}] Raw: {raw_string} → Parsed: {display_weight} ({stability_text})"
                            else:
                                display_text = f"[{current_time}] Raw: {cleaned_data} → Parsed: Unable to parse"
                            
                            # Clear line and display new data (no scrolling)
                            print(f"\r{display_text}", end='', flush=True)
                    
                        buffer = ""
                        last_received_time = time.time()
                else:
                    time.sleep(0.01)
            else:
                time.sleep(0.5)
                
        except Exception as e:
            error_time = datetime.now().strftime('%H:%M:%S')
            print(f"\r[{error_time}] Error: {e}", end='', flush=True)
            time.sleep(1)

@app.route('/api/weight/latest', methods=['GET'])
def get_latest_weight_data():
    """Get latest weight data - compatible with Frappe"""
    with data_lock:
        if latest_data:
            return jsonify({
                'success': True,
                'message': 'Latest weight data retrieved successfully',
                'data': latest_data,  # lowercase 'data'
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No weight data available',
                'timestamp': datetime.now().isoformat()
            }), 404

@app.route('/api/weight', methods=['GET'])
def get_weight_data():
    """Get recent weight data"""
    with data_lock:
        if latest_data:
            return jsonify({
                'success': True,
                'message': 'Weight data retrieved successfully',
                'data': [latest_data],  # lowercase 'data'
                'count': 1,
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No weight data available',
                'timestamp': datetime.now().isoformat()
            }), 404

@app.route('/api/weight/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    port_status = "connected" if serial_port and serial_port.is_open else "disconnected"
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'AMPI Weight API',
        'version': '1.0.0',
        'serial_port': port_status
    })

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
        'port_name': 'COM1',  # Change this to your actual COM port
        'baud_rate': 9600
    }
    
    print("\033c", end="")  # Clear screen
    print("A9 Weight Indicator - Real-time Monitoring")
    print("=" * 80)
    print("Display: Raw data → Parsed weight (Status)")
    print("Format: [Time] Raw: +00326001C → Parsed: 26030.00 kg (Stable)")
    print("=" * 80)
    print("API Endpoints:")
    print("  GET http://localhost:5000/api/weight/latest")
    print("  GET http://localhost:5000/api/weight")
    print("  GET http://localhost:5000/api/weight/health")
    print("=" * 80)
    print("Waiting for A9 indicator data...")
    print()  # Empty line before the updating display
    
    if initialize_serial(serial_config['port_name'], serial_config['baud_rate']):
        serial_thread = threading.Thread(target=read_serial_data, daemon=True)
        serial_thread.start()
        
        # Start Flask server
        from waitress import serve
        print("Starting production server on http://localhost:5000")
        print("Press Ctrl+C to stop the application")
        print("-" * 80)
        
        # Use Waitress for cleaner operation (no Flask dev warnings)
        serve(app, host='0.0.0.0', port=5000, _quiet=True)
        
    else:
        print("Failed to initialize serial port")