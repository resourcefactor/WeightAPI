# Weight API - Quick Start Guide

## Error: ModuleNotFoundError: No module named 'flask_socketio'

If you see this error, it means the required dependencies are not installed. Follow the steps below:

---

## Installation Steps

### Option 1: Using the Installation Script (Recommended)

#### For Windows:
```bash
install_dependencies.bat
```

#### For Linux/Mac:
```bash
chmod +x install_dependencies.sh
./install_dependencies.sh
```

---

### Option 2: Using pip install (Manual)

#### Install all dependencies at once:
```bash
pip install -r requirements.txt
```

#### Or install individually:
```bash
pip install pyserial==3.5
pip install Flask==2.3.3
pip install Flask-CORS==4.0.0
pip install flask-socketio==5.3.4
pip install python-socketio==5.9.0
pip install eventlet==0.33.3
pip install waitress==2.1.2
```

---

### Option 3: Using Virtual Environment (Best Practice)

#### Windows:
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

#### Linux/Mac:
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## Verify Installation

After installation, verify all packages are installed:

```bash
python -c "import flask_socketio; print('OK')"
```

If you see "OK", the installation was successful.

---

## Running the Application

### 1. Make sure your weight scale is connected to the correct COM port

### 2. Update the COM port in weightapi.py if needed:
```python
serial_config = {
    'port_name': 'COM1',  # Change this to your actual COM port
    'baud_rate': 9600
}
```

### 3. Run the application:
```bash
python weightapi.py
```

### 4. You should see:
```
A9 Weight Indicator - Real-time Monitoring with WebSocket Support
======================================================================
Available serial ports:
  - COM1: USB Serial Port
Serial port COM1 is ready
======================================================================
API Server running on:
  - REST API: http://localhost:5000/api/weight/latest
  - WebSocket: ws://localhost:5000/socket.io/
======================================================================
WebSocket Events:
  - Emit: 'weight_update' (real-time weight data)
  - Listen: 'request_weight' (request current weight)
======================================================================
```

---

## Testing

### Test the WebSocket Connection:

1. Open `websocket_client_sample.html` in your web browser
2. Click "Connect to WebSocket"
3. You should see real-time weight data streaming

### Test the REST API:

```bash
curl http://localhost:5000/api/weight/latest
```

---

## Common Issues

### Issue 1: pip is not recognized
**Solution:** Make sure Python is in your PATH, or use:
```bash
python -m pip install -r requirements.txt
```

### Issue 2: Permission denied (Linux/Mac)
**Solution:** Use pip with --user flag:
```bash
pip install --user -r requirements.txt
```

### Issue 3: Serial port not found
**Solution:**
1. Check which COM port your device is using in Device Manager (Windows)
2. Update the port name in weightapi.py
3. Make sure the USB cable is properly connected

### Issue 4: Port already in use
**Solution:**
1. Close any other applications using the serial port
2. Close any other instances of weightapi.py
3. Restart your computer if needed

---

## Integration with Your Web Application

### Add Socket.IO library to your HTML:
```html
<script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
```

### Connect and receive data:
```javascript
const socket = io('http://localhost:5000');

socket.on('connect', () => {
    console.log('Connected!');
});

socket.on('weight_update', (data) => {
    if (data.success) {
        console.log('Weight:', data.data.weightValue, 'kg');
        console.log('Stable:', data.data.isStable);
        // Update your UI here
    }
});
```

---

## Need More Help?

- Check `WEBSOCKET_GUIDE.md` for detailed WebSocket documentation
- Check `requirements.txt` to see all required packages
- Make sure Python 3.7+ is installed

---

## Quick Command Reference

| Command | Description |
|---------|-------------|
| `pip install -r requirements.txt` | Install all dependencies |
| `python weightapi.py` | Run the server |
| `pip list` | Show installed packages |
| `python --version` | Check Python version |

---

## Success Checklist

- [ ] Python 3.7+ installed
- [ ] All dependencies installed (run verification)
- [ ] COM port configured correctly
- [ ] Weight scale connected
- [ ] Server running without errors
- [ ] WebSocket client can connect
- [ ] Real-time data streaming works

---

**Ready to go!** 🚀
