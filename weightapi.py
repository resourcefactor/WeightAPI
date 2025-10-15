import serial
import serial.tools.list_ports
from serial import SerialException
from flask import Flask, jsonify
from flask_cors import CORS
from datetime import datetime
import re
import time
import logging
import threading

app = Flask(__name__)
CORS(app)

# Disable Flask's default access logs
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
app.logger.disabled = True
logging.getLogger('flask').setLevel(logging.ERROR)

# Global variables
serial_port = None
data_lock = threading.Lock()

def parse_weight_data(raw_data):
    """
    Parse A9 indicator weight data according to the actual protocol from debug log
    Format from debug: +003290013 (9 characters between STX and ETX)
    - First char: + or - sign
    - Next 7 chars: Weight value (0032900)
    - 2nd last char: Number of decimal places (1 in the example)
    - Last char: Status/Unit (3 in the example)
    """
    try:
        # Clean the input - remove any non-printable characters including STX (\x02) and ETX (\x03)
        # Only keep +, -, and digits
        clean_data = ''.join(char for char in raw_data if char in '+-0123456789')
        
        if not clean_data or len(clean_data) < 9:
            return None, None, None
        
        # Extract components based on the actual format from debug log
        sign_char = clean_data[0]  # + or -
        numeric_part = clean_data[1:8]  # The actual number part (0032900) - 7 digits
        decimal_places = int(clean_data[8])  # Number of decimal places (1 in +003290013)
        status_char = clean_data[9] if len(clean_data) > 9 else '0'  # Status character (3 in the example)
        
        # Remove leading zeros from numeric part, but keep at least one zero
        if numeric_part and all(c == '0' for c in numeric_part):
            clean_numeric = '0'
        else:
            clean_numeric = numeric_part.lstrip('0') or '0'
        
        # Convert to float and apply sign
        weight_value = float(clean_numeric)
        if sign_char == '-':
            weight_value = -weight_value
        
        # Apply decimal places scaling
        weight_kg = weight_value / (10 ** decimal_places)
        
        # Stability detection - adjust based on your device's status codes
        is_stable = status_char in ['B', 'C', '3']  # Adjust based on your device manual
        
        return weight_kg, is_stable, raw_data
        
    except Exception as e:
        # Don't print error here to avoid terminal scrolling - just return None
        return None, None, None

def has_complete_reading(buffer):
    """Check if buffer contains a complete weight reading using message framing"""
    # Look for STX (\x02) and ETX (\x03) markers with data in between
    return b'\x02' in buffer and b'\x03' in buffer

def extract_weight_reading(buffer):
    """Extract the first complete weight reading from buffer using STX/ETX framing"""
    try:
        if b'\x02' in buffer and b'\x03' in buffer:
            stx_pos = buffer.find(b'\x02')
            etx_pos = buffer.find(b'\x03', stx_pos)
            
            if etx_pos > stx_pos:
                # Extract message between STX and ETX
                message_bytes = buffer[stx_pos+1:etx_pos]
                message = message_bytes.decode('ascii', errors='ignore')
                return message
    except Exception as e:
        print(f"Error extracting reading: {e}")
    
    return None

def clean_serial_buffer(buffer):
    """Clean the buffer - return empty as we use message framing"""
    return ""

def update_terminal_display(weight_value, is_stable, raw_string):
    """Update the terminal display on the same line"""
    current_time = datetime.now().strftime('%H:%M:%S')
    if weight_value is not None:
        stability_text = "Stable" if is_stable else "Unstable"
        display_text = f"[{current_time}] Raw: {raw_string} � Parsed: {weight_value:.3f} kg ({stability_text})"
    else:
        display_text = f"[{current_time}] Raw: {raw_string} � Parsed: Unable to parse"
    
    # Clear line and display new data (no scrolling)
    print(f"\r{display_text}", end='', flush=True)

def read_serial_data_continuous():
    """Continuously read and display data from serial port in real-time"""
    if not serial_port or not serial_port.is_open:
        return
    
    buffer = b""  # Use bytes buffer for STX/ETX detection
    
    while True:
        try:
            if serial_port.in_waiting > 0:
                raw_data = serial_port.read(serial_port.in_waiting)
                buffer += raw_data
                
                # Process complete messages using STX/ETX framing
                while b'\x02' in buffer and b'\x03' in buffer:
                    stx_pos = buffer.find(b'\x02')
                    etx_pos = buffer.find(b'\x03', stx_pos)
                    
                    if etx_pos > stx_pos:
                        # Extract message between STX and ETX
                        message_bytes = buffer[stx_pos+1:etx_pos]
                        
                        try:
                            message = message_bytes.decode('ascii', errors='ignore')
                            
                            if message and len(message) >= 9:  # Only process valid length messages
                                # Parse the weight data
                                weight_value, is_stable, raw_string = parse_weight_data(message)
                                
                                if weight_value is not None:
                                    # Update the terminal display only if parsing was successful
                                    update_terminal_display(weight_value, is_stable, message)
                                # If parsing failed, don't display anything to avoid scrolling
                        
                        except Exception as e:
                            # Don't print error here to avoid terminal scrolling
                            pass
                        
                        # Remove processed data from buffer (including STX and ETX)
                        buffer = buffer[etx_pos+1:]
                    else:
                        break
            
            time.sleep(0.01)  # Small delay to prevent CPU overload
                
        except Exception as e:
            # Only show serial errors occasionally to avoid scrolling
            error_time = datetime.now().strftime('%H:%M:%S')
            print(f"\r[{error_time}] Serial Error: {e}", end='', flush=True)
            time.sleep(1)
def read_from_serial_with_timeout(timeout=2.0):
    """
    Read from serial port with configurable timeout for API calls
    Returns: raw data string or None if timeout
    """
    global serial_port
    
    if not serial_port or not serial_port.is_open:
        raise SerialException("Serial port not available or not open")
    
    # Set a shorter read timeout for individual read operations
    original_timeout = serial_port.timeout
    serial_port.timeout = 0.1  # Short timeout for each read operation
    
    try:
        buffer = b""
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            try:
                # Read available data
                if serial_port.in_waiting > 0:
                    chunk = serial_port.read(serial_port.in_waiting)
                    buffer += chunk
                    
                    # Process complete messages using STX/ETX framing (SAME AS CONTINUOUS THREAD)
                    while b'\x02' in buffer and b'\x03' in buffer:
                        stx_pos = buffer.find(b'\x02')
                        etx_pos = buffer.find(b'\x03', stx_pos)
                        
                        if etx_pos > stx_pos:
                            # Extract message between STX and ETX
                            message_bytes = buffer[stx_pos+1:etx_pos]
                            message = message_bytes.decode('ascii', errors='ignore')
                            
                            # Only return valid length messages (9 characters)
                            if message and len(message) >= 9:
                                # Remove processed data from buffer
                                buffer = buffer[etx_pos+1:]
                                return message
                            
                            # Remove this message even if invalid and continue
                            buffer = buffer[etx_pos+1:]
                
                # Small delay to prevent CPU spinning
                time.sleep(0.01)
                    
            except Exception as e:
                continue
        
        # Timeout reached
        return None
        
    finally:
        # Restore original timeout
        serial_port.timeout = original_timeout

def clear_serial_buffer():
    """Clear any pending data in the serial buffer more thoroughly"""
    global serial_port
    if serial_port and serial_port.is_open:
        try:
            # Read multiple times to ensure complete clearance
            for _ in range(3):  # Try 3 times
                if serial_port.in_waiting > 0:
                    serial_port.read(serial_port.in_waiting)
                time.sleep(0.01)  # Small delay between reads
        except:
            pass

# [Keep all your API endpoints exactly the same - they're perfect!]
@app.route('/api/weight/latest', methods=['GET'])
def get_latest_weight_data():
    """Get latest weight data - read fresh from scale on each request"""
    try:
        # Clear any old data from buffer first
        clear_serial_buffer()
        
        # Attempt to read fresh data from serial port (not from memory)
        raw_data = read_from_serial_with_timeout(timeout=2.0)
        
        if raw_data:
            # Parse the fresh data
            weight_value, is_stable, raw_string = parse_weight_data(raw_data)
            
            if weight_value is not None:
                response_data = {
                    'data': raw_data,  # Use the original raw_data here
                    'timestamp': datetime.now().isoformat(),
                    'weightValue': weight_value,
                    'isStable': is_stable
                }
                
                return jsonify({
                    'success': True,
                    'message': 'Weight data retrieved successfully',
                    'data': response_data,
                    'timestamp': datetime.now().isoformat()
                })
            else:
                # Failed to parse - include both 'data' and 'rawData' with same value
                return jsonify({
                    'success': False,
                    'error': 'Failed to parse weight data',
                    'data': raw_data,  # Add this line
                    'rawData': raw_data,
                    'timestamp': datetime.now().isoformat()
                }), 422  # Unprocessable Entity
        else:
            return jsonify({
                'success': False,
                'error': 'No data received from scale within timeout period',
                'timestamp': datetime.now().isoformat()
            }), 503  # Service Unavailable
            
    except SerialException as e:
        error_msg = f"Serial port error: {str(e)}"
        return jsonify({
            'success': False,
            'error': error_msg,
            'timestamp': datetime.now().isoformat()
        }), 503  # Service Unavailable
        
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        return jsonify({
            'success': False,
            'error': error_msg,
            'timestamp': datetime.now().isoformat()
        }), 500  # Internal Server Error

@app.route('/api/weight', methods=['GET'])
def get_weight_data():
    """Get weight data (alias for /api/weight/latest)"""
    return get_latest_weight_data()

@app.route('/api/weight/health', methods=['GET'])
def health_check():
    """Comprehensive health check endpoint"""
    health_status = {
        'timestamp': datetime.now().isoformat(),
        'service': 'AMPI Weight API',
        'version': '2.0.0',
        'serial_port_connected': False,
        'scale_responding': False,
        'last_health_check': datetime.now().isoformat()
    }
    
    try:
        # Check serial port connection
        if serial_port and serial_port.is_open:
            health_status['serial_port_connected'] = True
            
            # Test scale communication with shorter timeout
            test_data = read_from_serial_with_timeout(timeout=1.0)
            health_status['scale_responding'] = test_data is not None
            
            if test_data:
                health_status['scale_status'] = 'responsive'
                # Try to parse to check data quality
                weight_value, is_stable, _ = parse_weight_data(test_data)
                health_status['data_quality'] = 'good' if weight_value is not None else 'parse_error'
            else:
                health_status['scale_status'] = 'no_response'
                
        else:
            health_status['scale_status'] = 'port_closed'
            
    except Exception as e:
        health_status['scale_status'] = 'error'
        health_status['error'] = str(e)
    
    # Determine overall status
    if health_status['serial_port_connected'] and health_status['scale_responding']:
        health_status['status'] = 'healthy'
        status_code = 200
    elif health_status['serial_port_connected']:
        health_status['status'] = 'degraded'
        health_status['message'] = 'Serial port connected but scale not responding'
        status_code = 503
    else:
        health_status['status'] = 'unhealthy'
        health_status['message'] = 'Serial port not connected'
        status_code = 503
    
    return jsonify(health_status), status_code

@app.route('/api/weight/ports', methods=['GET'])
def list_serial_ports():
    """List available serial ports"""
    ports = []
    try:
        available_ports = serial.tools.list_ports.comports()
        for port in available_ports:
            ports.append({
                'device': port.device,
                'description': port.description,
                'hwid': port.hwid
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to list serial ports: {str(e)}'
        }), 500
    
    return jsonify({
        'success': True,
        'ports': ports,
        'count': len(ports)
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
            timeout=0.1,  # Short timeout for responsive reading
            write_timeout=1.0,
            exclusive=True  # Prevent other processes from using the port
        )
        
        if serial_port.is_open:
            print(f" Serial port {port_name} is ready")
            # Clear any existing data in buffer
            clear_serial_buffer()
            return True
        else:
            print(f" Failed to open serial port {port_name}")
            return False
            
    except Exception as e:
        print(f" Error initializing serial port: {e}")
        return False

def close_serial():
    """Close serial port connection"""
    global serial_port
    if serial_port and serial_port.is_open:
        try:
            serial_port.close()
            print("Serial port closed")
        except:
            pass

if __name__ == '__main__':
    # Configuration
    serial_config = {
        'port_name': 'COM1',  # Change this to your actual COM port
        'baud_rate': 9600
    }
    
    print("\033c", end="")  # Clear screen
    print("A9 Weight Indicator - Real-time Monitoring")
    print("=" * 60)
    print("Real-time display updating on same line...")
    print("-" * 60)
    
    if initialize_serial(serial_config['port_name'], serial_config['baud_rate']):
        try:
            # Start continuous serial reading thread
            serial_thread = threading.Thread(target=read_serial_data_continuous, daemon=True)
            serial_thread.start()
            
            # Give the serial thread a moment to start
            time.sleep(1)
            
            # Start Flask server
            from waitress import serve
            print("\nAPI Server running on http://localhost:5000/api/weight/latest")
            print("Press Ctrl+C to stop\n")
            
            # Use Waitress for production server
            serve(app, host='0.0.0.0', port=5000, _quiet=True)
            
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            close_serial()
    else:
        print("Failed to initialize serial port")
        print("You can still use the /api/weight/ports endpoint to see available ports")
        
        # Start server anyway for port listing functionality
        from waitress import serve
        print("Starting server in limited mode (serial port not available)")
        serve(app, host='0.0.0.0', port=5000, _quiet=True)