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
import os
import traceback
from contextlib import contextmanager

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
last_error = None
serial_thread = None
should_stop_serial_thread = False

# Error logging setup
ERROR_LOG_FILE = "error.txt"

def log_error(error_msg, exception=None):
    """Log errors to file with timestamp"""
    global last_error
    try:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(ERROR_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"\n[{timestamp}] {error_msg}\n")
            if exception:
                f.write(f"Exception: {str(exception)}\n")
                f.write(f"Traceback: {traceback.format_exc()}\n")
        last_error = error_msg
        print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ERROR: {error_msg}", end='', flush=True)
    except Exception as e:
        print(f"\r[{datetime.now().strftime('%H:%M:%S')}] Failed to write error log: {e}", end='', flush=True)

@contextmanager
def serial_operation(operation_name):
    """Context manager for serial operations with error handling"""
    try:
        yield
    except SerialException as e:
        error_msg = f"Serial operation '{operation_name}' failed: {str(e)}"
        log_error(error_msg, e)
        raise
    except Exception as e:
        error_msg = f"Unexpected error in '{operation_name}': {str(e)}"
        log_error(error_msg, e)
        raise

def parse_weight_data(raw_data):
    """
    Parse A9 indicator weight data according to the protocol
    Format: +00326001C
    - First char: + or - sign
    - Last char: Status (B, C = stable)
    - 2nd last char: Number of decimals
    - Middle: Weight value
    """
    try:
        # Extract weight patterns: + or - followed by digits ending with letter
        matches = re.findall(r'[+-]\d+[A-Za-z]', raw_data)
        if not matches:
            return None, None, None
        
        # Take the first complete weight reading
        weight_string = matches[0]
        
        # Extract components
        sign_char = weight_string[0]  # + or -
        status_char = weight_string[-1].upper()  # Status character (B, C, etc.)
        decimal_digits = int(weight_string[-2])  # Number of decimal places
        numeric_part = weight_string[1:-2]  # The actual number part
        
        # Remove leading zeros from numeric part
        clean_numeric = numeric_part.lstrip('0') or '0'
        
        # Convert to float and apply sign
        weight_value = float(clean_numeric)
        if sign_char == '-':
            weight_value = -weight_value
        
        # Apply decimal places
        weight_kg = weight_value / (10 ** decimal_digits)
        
        # Stability detection - 'B' and 'C' mean stable
        is_stable = status_char in ['B', 'C']
        
        return weight_kg, is_stable, weight_string
        
    except Exception as e:
        log_error(f"Error parsing weight data: {raw_data}", e)
        return None, None, None

def has_complete_reading(buffer):
    """Check if buffer contains a complete weight reading"""
    return re.search(r'[+-]\d+[A-Za-z]', buffer) is not None

def extract_weight_reading(buffer):
    """Extract the first complete weight reading from buffer"""
    matches = re.findall(r'[+-]\d+[A-Za-z]', buffer)
    return matches[0] if matches else None

def clean_serial_buffer():
    """Clear any pending data in the serial buffer"""
    global serial_port
    if serial_port and serial_port.is_open:
        try:
            with serial_operation("clear_buffer"):
                while serial_port.in_waiting > 0:
                    serial_port.read(serial_port.in_waiting)
                time.sleep(0.1)  # Small delay after clearing
        except Exception as e:
            log_error("Failed to clear serial buffer", e)

def update_terminal_display(weight_value, is_stable, raw_string):
    """Update the terminal display on the same line"""
    try:
        current_time = datetime.now().strftime('%H:%M:%S')
        if weight_value is not None:
            stability_text = "Stable" if is_stable else "Unstable"
            display_text = f"[{current_time}] Raw: {raw_string} → Parsed: {weight_value:.2f} kg ({stability_text})"
        else:
            display_text = f"[{current_time}] Raw: {raw_string} → Parsed: Unable to parse"
        
        # Clear line and display new data (no scrolling)
        print(f"\r{display_text}", end='', flush=True)
    except Exception as e:
        log_error("Failed to update terminal display", e)

def read_serial_data_continuous():
    """Continuously read and display data from serial port in real-time"""
    global should_stop_serial_thread
    
    if not serial_port or not serial_port.is_open:
        log_error("Serial port not available for continuous reading")
        return
    
    buffer = ""
    consecutive_errors = 0
    max_consecutive_errors = 5
    
    print(f"\r[{datetime.now().strftime('%H:%M:%S')}] Starting continuous serial reading...", end='', flush=True)
    
    while not should_stop_serial_thread:
        try:
            with serial_operation("continuous_read"):
                if serial_port.in_waiting > 0:
                    raw_data = serial_port.read(serial_port.in_waiting).decode('utf-8', errors='ignore')
                    buffer += raw_data
                    
                    # Process if we have complete data
                    if has_complete_reading(buffer):
                        cleaned_data = extract_weight_reading(buffer)
                        
                        if cleaned_data:
                            # Parse the weight data
                            weight_value, is_stable, raw_string = parse_weight_data(cleaned_data)
                            
                            # Update the terminal display
                            update_terminal_display(weight_value, is_stable, raw_string)
                            
                            # Reset buffer after processing complete reading
                            buffer = ""
                            consecutive_errors = 0  # Reset error counter on success
            
            time.sleep(0.05)  # Reduced delay for better responsiveness
                
        except SerialException as e:
            consecutive_errors += 1
            if consecutive_errors >= max_consecutive_errors:
                log_error(f"Too many consecutive serial errors ({consecutive_errors}), stopping thread", e)
                break
            time.sleep(0.5)  # Longer delay on error
            
        except Exception as e:
            consecutive_errors += 1
            log_error(f"Unexpected error in continuous reading", e)
            if consecutive_errors >= max_consecutive_errors:
                log_error(f"Too many consecutive errors ({consecutive_errors}), stopping thread", e)
                break
            time.sleep(0.5)
    
    print(f"\r[{datetime.now().strftime('%H:%M:%S')}] Serial reading thread stopped", end='', flush=True)

def read_from_serial_with_timeout(timeout=2.0):
    """
    Read from serial port with configurable timeout for API calls
    Returns: raw data string or None if timeout
    """
    global serial_port
    
    if not serial_port or not serial_port.is_open:
        raise SerialException("Serial port not available or not open")
    
    with serial_operation("timeout_read"):
        # Set a shorter read timeout for individual read operations
        original_timeout = serial_port.timeout
        serial_port.timeout = 0.1  # Short timeout for each read operation
        
        try:
            buffer = ""
            start_time = time.time()
            
            while (time.time() - start_time) < timeout:
                try:
                    # Read available data
                    if serial_port.in_waiting > 0:
                        chunk = serial_port.read(serial_port.in_waiting).decode('utf-8', errors='ignore')
                        buffer += chunk
                        
                        # Check if we have a complete reading
                        if has_complete_reading(buffer):
                            cleaned_data = extract_weight_reading(buffer)
                            if cleaned_data:
                                return cleaned_data
                    
                    # Small delay to prevent CPU spinning
                    time.sleep(0.01)
                        
                except Exception as e:
                    continue
            
            # Timeout reached
            return None
            
        finally:
            # Restore original timeout
            serial_port.timeout = original_timeout

def restart_serial_connection():
    """Restart serial connection in case of failure"""
    global serial_port, serial_thread, should_stop_serial_thread
    
    print(f"\r[{datetime.now().strftime('%H:%M:%S')}] Attempting to restart serial connection...", end='', flush=True)
    
    # Stop the current serial thread
    should_stop_serial_thread = True
    if serial_thread and serial_thread.is_alive():
        serial_thread.join(timeout=2.0)
    
    # Close current serial port
    close_serial()
    
    # Reinitialize
    time.sleep(1)
    if initialize_serial('COM4', 9600):
        should_stop_serial_thread = False
        serial_thread = threading.Thread(target=read_serial_data_continuous, daemon=True)
        serial_thread.start()
        print(f"\r[{datetime.now().strftime('%H:%M:%S')}] Serial connection restarted successfully", end='', flush=True)
        return True
    else:
        print(f"\r[{datetime.now().strftime('%H:%M:%S')}] Failed to restart serial connection", end='', flush=True)
        return False

@app.route('/api/weight/latest', methods=['GET'])
def get_latest_weight_data():
    """Get latest weight data - read fresh from scale on each request"""
    try:
        # Clear any old data from buffer first
        clean_serial_buffer()
        
        # Attempt to read fresh data from serial port (not from memory)
        raw_data = read_from_serial_with_timeout(timeout=2.0)
        
        if raw_data:
            # Parse the fresh data
            weight_value, is_stable, raw_string = parse_weight_data(raw_data)
            
            if weight_value is not None:
                response_data = {
                    'data': raw_string,
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
                return jsonify({
                    'success': False,
                    'error': 'Failed to parse weight data',
                    'rawData': raw_data,
                    'timestamp': datetime.now().isoformat()
                }), 422  # Unprocessable Entity
        else:
            # Try to restart connection if no data received
            restart_serial_connection()
            return jsonify({
                'success': False,
                'error': 'No data received from scale within timeout period',
                'timestamp': datetime.now().isoformat()
            }), 503  # Service Unavailable
            
    except SerialException as e:
        error_msg = f"Serial port error: {str(e)}"
        restart_serial_connection()
        return jsonify({
            'success': False,
            'error': error_msg,
            'timestamp': datetime.now().isoformat()
        }), 503  # Service Unavailable
        
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        log_error("Error in /api/weight/latest", e)
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
        'version': '2.1.0',
        'serial_port_connected': False,
        'scale_responding': False,
        'serial_thread_alive': False,
        'last_error': last_error,
        'last_health_check': datetime.now().isoformat()
    }
    
    try:
        # Check serial port connection
        if serial_port and serial_port.is_open:
            health_status['serial_port_connected'] = True
            
            # Check if serial thread is alive
            if serial_thread and serial_thread.is_alive():
                health_status['serial_thread_alive'] = True
            
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
        log_error("Health check failed", e)
    
    # Determine overall status
    if (health_status['serial_port_connected'] and 
        health_status['scale_responding'] and 
        health_status['serial_thread_alive']):
        health_status['status'] = 'healthy'
        status_code = 200
    elif health_status['serial_port_connected']:
        health_status['status'] = 'degraded'
        health_status['message'] = 'Serial port connected but scale not responding or thread dead'
        status_code = 503
    else:
        health_status['status'] = 'unhealthy'
        health_status['message'] = 'Serial port not connected'
        status_code = 503
    
    return jsonify(health_status), status_code

@app.route('/api/weight/restart', methods=['POST'])
def restart_serial():
    """Manually restart serial connection"""
    try:
        success = restart_serial_connection()
        return jsonify({
            'success': success,
            'message': 'Serial restart initiated' if success else 'Serial restart failed',
            'timestamp': datetime.now().isoformat()
        }), 200 if success else 500
    except Exception as e:
        log_error("Manual serial restart failed", e)
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

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
        log_error("Failed to list serial ports", e)
        return jsonify({
            'success': False,
            'error': f'Failed to list serial ports: {str(e)}'
        }), 500
    
    return jsonify({
        'success': True,
        'ports': ports,
        'count': len(ports)
    })

def initialize_serial(port_name='COM4', baud_rate=9600):
    """Initialize serial port connection"""
    global serial_port, should_stop_serial_thread
    
    try:
        print(f"\r[{datetime.now().strftime('%H:%M:%S')}] Available serial ports:", end='', flush=True)
        ports = serial.tools.list_ports.comports()
        for port in ports:
            print(f"\r[{datetime.now().strftime('%H:%M:%S')}]   - {port.device}: {port.description}", end='', flush=True)
        
        print(f"\r[{datetime.now().strftime('%H:%M:%S')}] Initializing serial port: {port_name} at {baud_rate} baud", end='', flush=True)
        
        # Close existing connection if any
        if serial_port and serial_port.is_open:
            serial_port.close()
        
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
            print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ✓ Serial port {port_name} is ready", end='', flush=True)
            # Clear any existing data in buffer
            clean_serial_buffer()
            should_stop_serial_thread = False
            return True
        else:
            print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ✗ Failed to open serial port {port_name}", end='', flush=True)
            return False
            
    except Exception as e:
        print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ✗ Error initializing serial port: {e}", end='', flush=True)
        log_error(f"Serial initialization failed for {port_name}", e)
        return False

def close_serial():
    """Close serial port connection"""
    global serial_port, should_stop_serial_thread
    should_stop_serial_thread = True
    
    if serial_port:
        try:
            if serial_port.is_open:
                serial_port.close()
            print(f"\r[{datetime.now().strftime('%H:%M:%S')}] Serial port closed", end='', flush=True)
        except Exception as e:
            log_error("Error closing serial port", e)

def cleanup():
    """Cleanup resources on exit"""
    close_serial()
    print(f"\r[{datetime.now().strftime('%H:%M:%S')}] Application shutdown complete", end='', flush=True)

if __name__ == '__main__':
    # Configuration
    serial_config = {
        'port_name': 'COM4',  # Change this to your actual COM port
        'baud_rate': 9600
    }
    
    # Initialize error log
    try:
        with open(ERROR_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"\n{'='*50}\nApplication started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{'='*50}")
    except Exception as e:
        print(f"Failed to initialize error log: {e}")
    
    print("\033c", end="")  # Clear screen
    print("A9 Weight Indicator - Real-time Monitoring (Improved Stability)")
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
            print(f"\r[{datetime.now().strftime('%H:%M:%S')}] API Server running on http://localhost:5000")
            print(f"\r[{datetime.now().strftime('%H:%M:%S')}] Endpoints: /api/weight/latest, /api/weight/health, /api/weight/restart")
            print(f"\r[{datetime.now().strftime('%H:%M:%S')}] Error log: {ERROR_LOG_FILE}")
            print(f"\r[{datetime.now().strftime('%H:%M:%S')}] Press Ctrl+C to stop\n")
            
            # Use Waitress for production server
            serve(app, host='0.0.0.0', port=5000, _quiet=True)
            
        except KeyboardInterrupt:
            print(f"\r[{datetime.now().strftime('%H:%M:%S')}] Shutting down...", end='', flush=True)
        except Exception as e:
            log_error("Application crash", e)
        finally:
            cleanup()
    else:
        print(f"\r[{datetime.now().strftime('%H:%M:%S')}] Failed to initialize serial port")
        print(f"\r[{datetime.now().strftime('%H:%M:%S')}] You can still use the /api/weight/ports endpoint to see available ports")
        
        # Start server anyway for port listing functionality
        from waitress import serve
        print(f"\r[{datetime.now().strftime('%H:%M:%S')}] Starting server in limited mode (serial port not available)")
        serve(app, host='0.0.0.0', port=5000, _quiet=True)