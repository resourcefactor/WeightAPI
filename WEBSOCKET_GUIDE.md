# Weight API WebSocket Implementation Guide

## Overview

This Weight API now supports **WebSocket connections** in addition to the REST API endpoints. WebSocket support was added to resolve CORS policy errors when accessing the local API from remote HTTPS origins.

## Why WebSocket?

The previous REST API was experiencing CORS errors when accessed from `https://ampi.erprf.com`:

```
Access to fetch at 'http://localhost:5000/api/weight/latest' from origin 'https://ampi.erprf.com'
has been blocked by CORS policy: Permission was denied for this request to access the unknown address space.
```

This error occurs due to browser security restrictions (Private Network Access) that block HTTPS sites from accessing local HTTP services. WebSocket connections bypass many of these restrictions and provide:

- ✅ Real-time data streaming
- ✅ Lower latency than polling
- ✅ Better CORS handling
- ✅ Bidirectional communication

## Server Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the Server

```bash
python weightapi.py
```

The server will start on `http://localhost:5000` with both REST and WebSocket support.

## WebSocket Connection

### Server URL

```
ws://localhost:5000/socket.io/
```

### WebSocket Events

#### Client → Server (Emit)

| Event | Description | Parameters |
|-------|-------------|------------|
| `connect` | Establish connection | None |
| `request_weight` | Request current weight | None |
| `disconnect` | Close connection | None |

#### Server → Client (Listen)

| Event | Description | Data Format |
|-------|-------------|-------------|
| `connection_response` | Connection confirmation | `{status, message, timestamp}` |
| `weight_update` | Real-time weight data | `{success, data: {data, timestamp, weightValue, isStable}}` |
| `weight_data` | Response to manual request | `{success, data: {data, timestamp, weightValue, isStable}}` |

## Client Implementation Examples

### JavaScript (Browser)

```javascript
// Include Socket.IO client library
<script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>

// Connect to WebSocket
const socket = io('http://localhost:5000', {
    transports: ['websocket', 'polling'],
    reconnection: true
});

// Connection established
socket.on('connect', () => {
    console.log('Connected to Weight API');
});

// Receive real-time weight updates
socket.on('weight_update', (data) => {
    if (data.success) {
        console.log('Weight:', data.data.weightValue, 'kg');
        console.log('Stable:', data.data.isStable);
        console.log('Timestamp:', data.data.timestamp);
    }
});

// Request weight manually
function getWeight() {
    socket.emit('request_weight');
}

// Listen for manual request response
socket.on('weight_data', (data) => {
    if (data.success) {
        console.log('Requested weight:', data.data.weightValue, 'kg');
    } else {
        console.error('Error:', data.error);
    }
});

// Handle disconnection
socket.on('disconnect', () => {
    console.log('Disconnected from Weight API');
});
```

### JavaScript (Node.js)

```javascript
const io = require('socket.io-client');

const socket = io('http://localhost:5000', {
    transports: ['websocket'],
    reconnection: true
});

socket.on('connect', () => {
    console.log('Connected to Weight API');
});

socket.on('weight_update', (data) => {
    if (data.success) {
        console.log(`Weight: ${data.data.weightValue} kg`);
        console.log(`Stable: ${data.data.isStable}`);
    }
});

// Request weight
socket.emit('request_weight');

socket.on('weight_data', (data) => {
    if (data.success) {
        console.log('Weight:', data.data);
    }
});
```

### Python Client

```python
import socketio

# Create SocketIO client
sio = socketio.Client()

@sio.event
def connect():
    print('Connected to Weight API')

@sio.on('weight_update')
def on_weight_update(data):
    if data['success']:
        weight_data = data['data']
        print(f"Weight: {weight_data['weightValue']} kg")
        print(f"Stable: {weight_data['isStable']}")

@sio.on('weight_data')
def on_weight_data(data):
    if data['success']:
        print('Requested weight:', data['data'])
    else:
        print('Error:', data['error'])

@sio.event
def disconnect():
    print('Disconnected from Weight API')

# Connect to server
sio.connect('http://localhost:5000')

# Request weight manually
sio.emit('request_weight')

# Keep connection alive
sio.wait()
```

## Integration with Your Application

### For https://ampi.erprf.com

1. **Include Socket.IO library** in your HTML:
   ```html
   <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
   ```

2. **Connect to your local Weight API**:
   ```javascript
   const socket = io('http://localhost:5000');
   ```

3. **Listen for weight updates**:
   ```javascript
   socket.on('weight_update', (data) => {
       // Update your UI with weight data
       updateWeightDisplay(data.data.weightValue);
   });
   ```

4. **Request weight on demand**:
   ```javascript
   socket.emit('request_weight');
   ```

## Testing

### Quick Test with Sample Client

1. Start the Weight API server:
   ```bash
   python weightapi.py
   ```

2. Open `websocket_client_sample.html` in your browser

3. Click "Connect to WebSocket"

4. Watch real-time weight updates stream automatically

5. Click "Request Weight" to get weight on demand

### Test with curl (REST API still works)

```bash
# Get latest weight via REST API
curl http://localhost:5000/api/weight/latest

# Health check
curl http://localhost:5000/api/weight/health
```

## Data Format

### Weight Update Event Data

```json
{
    "success": true,
    "data": {
        "data": "+003290013",
        "timestamp": "2025-11-05T10:30:45.123456",
        "weightValue": 3290.0,
        "isStable": true
    }
}
```

### Error Response

```json
{
    "success": false,
    "error": "Error message here"
}
```

## Configuration

### Server Port

Change the port in `weightapi.py`:
```python
socketio.run(app, host='0.0.0.0', port=5000)
```

### CORS Settings

CORS is configured to allow all origins:
```python
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*")
```

For production, restrict to specific origins:
```python
CORS(app, resources={r"/*": {"origins": "https://ampi.erprf.com"}})
socketio = SocketIO(app, cors_allowed_origins="https://ampi.erprf.com")
```

## Troubleshooting

### Connection Issues

1. **Ensure server is running**:
   ```bash
   python weightapi.py
   ```

2. **Check firewall settings**: Allow port 5000

3. **Verify WebSocket support**: Modern browsers support WebSocket by default

4. **Check browser console**: Look for connection errors

### CORS Still Blocked?

If CORS errors persist:

1. Ensure you're using the WebSocket connection (not fetch/XHR)
2. Check that Socket.IO library is loaded
3. Verify server CORS settings

## REST API (Still Available)

The REST API endpoints remain available for backward compatibility:

- `GET /api/weight/latest` - Get latest weight reading
- `GET /api/weight/health` - Health check
- `GET /api/weight/ports` - List serial ports

## Performance

- **Real-time streaming**: Weight data is pushed automatically as it's read from the scale
- **Efficient**: Only sends data when connected clients exist
- **Reliable**: Auto-reconnection on network interruptions

## Security Notes

⚠️ **Important**: This implementation allows all origins (`cors_allowed_origins="*"`). For production:

1. Restrict CORS to specific domains
2. Add authentication/authorization
3. Use SSL/TLS (wss:// instead of ws://)
4. Implement rate limiting

## Support

For issues or questions:
- Check server logs for errors
- Review the sample client HTML for implementation examples
- Ensure serial port is properly configured

## Version

- Weight API Version: 2.0.0
- WebSocket Support: Added 2025-11-05
