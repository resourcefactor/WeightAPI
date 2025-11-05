# Python Version Compatibility Guide

## Current Status

The Weight API with WebSocket support has been tested with:
- ✅ Python 3.8
- ✅ Python 3.9
- ✅ Python 3.10
- ✅ Python 3.11
- ✅ Python 3.12
- ⚠️ Python 3.14 (with limitations - see below)

---

## Python 3.14 Compatibility

### Issue
Python 3.14 is very new and the `eventlet` library doesn't fully support it yet, which causes this error:
```
ValueError: Invalid async_mode specified
```

### Current Solution (Automatic Fallback)
The application now **auto-detects** the best available mode:

1. **First tries**: `eventlet` mode (production-ready)
2. **Falls back to**: `threading` mode (Python 3.14 compatible)

When you start the server, you'll see:
```
⚠ Eventlet not available, using threading mode
  Note: For production use, consider Python 3.11 or 3.12 with eventlet
```

### What This Means

#### Threading Mode (Python 3.14):
- ✅ **Works**: WebSocket connections function correctly
- ✅ **Compatible**: No installation errors
- ⚠️ **Warning**: May see occasional error messages in console:
  ```
  AssertionError: write() before start_response
  ```
- ⚠️ **Performance**: Slightly lower performance with many concurrent connections
- ⚠️ **Production**: Not ideal for high-traffic production use

#### Eventlet Mode (Python 3.8-3.12):
- ✅ **Production-ready**: Designed for production workloads
- ✅ **Better performance**: Handles concurrent connections efficiently
- ✅ **No errors**: Clean console output
- ✅ **Stable**: Mature and well-tested

---

## Recommended Solutions

### Option 1: Use Python 3.12 (Recommended for Production)

**Download Python 3.12:**
- Windows: https://www.python.org/downloads/release/python-3120/
- Install alongside Python 3.14 (no need to uninstall 3.14)

**Run with Python 3.12:**
```bash
# Windows
py -3.12 weightapi.py

# Or specify full path
C:\Users\admin\AppData\Local\Programs\Python\Python312\python.exe weightapi.py
```

### Option 2: Use Python 3.11

Python 3.11 is the most stable version for production:
- Download: https://www.python.org/downloads/release/python-3110/
- Excellent eventlet support
- Best overall compatibility

### Option 3: Continue with Python 3.14 (Development Only)

If you're just testing or developing (not production):
- Current setup works fine
- Accept the occasional console warnings
- Performance is adequate for single-user/testing scenarios

---

## Installation for Recommended Setup

### Step 1: Install Python 3.12 or 3.11
Download and install from python.org (can coexist with 3.14)

### Step 2: Create Virtual Environment
```bash
# Navigate to your project folder
cd E:\WeightAPI-main

# Create virtual environment with Python 3.12
py -3.12 -m venv venv

# Or with Python 3.11
py -3.11 -m venv venv

# Activate the virtual environment
venv\Scripts\activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Run the Application
```bash
python weightapi.py
```

You should see:
```
✓ Using eventlet for production WebSocket support
======================================================================
API Server running on:
  - REST API: http://localhost:5000/api/weight/latest
  - WebSocket: ws://localhost:5000/socket.io/
  - Async Mode: eventlet
======================================================================
```

---

## Verification

### Check Your Current Python Version:
```bash
python --version
```

### Check if Eventlet is Working:
```bash
python -c "import eventlet; eventlet.monkey_patch(); print('✓ Eventlet works!')"
```

If you see "✓ Eventlet works!" - you're good to go!

---

## Production Deployment Checklist

For production use, ensure:
- [ ] Using Python 3.11 or 3.12 (not 3.14)
- [ ] Eventlet is installed and working
- [ ] Server starts with "✓ Using eventlet for production WebSocket support"
- [ ] No console errors during operation
- [ ] WebSocket connections are stable under load

---

## FAQ

### Q: Can I use Python 3.14?
**A:** Yes, for development and testing. For production, use Python 3.11 or 3.12.

### Q: Do I need to uninstall Python 3.14?
**A:** No! You can have multiple Python versions installed. Use `py -3.12` to specify which version to use.

### Q: Will this affect my other Python 3.14 projects?
**A:** No, each project can use its own Python version and virtual environment.

### Q: Is threading mode unsafe?
**A:** No, it's functional but not optimal for production with many concurrent WebSocket connections.

### Q: When will Python 3.14 be supported?
**A:** When the eventlet library releases an update with Python 3.14 support (check eventlet GitHub for updates).

---

## Troubleshooting

### Error: "py: command not found" (Windows)
**Solution:** Use the full path to Python:
```bash
C:\Users\admin\AppData\Local\Programs\Python\Python312\python.exe weightapi.py
```

### Error: "No module named 'eventlet'"
**Solution:** Install dependencies:
```bash
pip install -r requirements.txt
```

### Still seeing threading mode with Python 3.12?
**Solution:**
1. Verify eventlet is installed: `pip list | findstr eventlet`
2. Reinstall if needed: `pip install --force-reinstall eventlet`
3. Try importing: `python -c "import eventlet; print('OK')"`

---

## Summary

| Python Version | Status | Eventlet | Production Ready | Recommended |
|---------------|---------|----------|------------------|-------------|
| 3.8-3.10 | ✅ Supported | ✅ Yes | ✅ Yes | ✅ Good |
| 3.11 | ✅ Supported | ✅ Yes | ✅ Yes | ⭐ **Best** |
| 3.12 | ✅ Supported | ✅ Yes | ✅ Yes | ⭐ **Best** |
| 3.14 | ⚠️ Limited | ❌ No | ⚠️ Development Only | 🔄 Testing |

---

**For production deployment, we strongly recommend Python 3.11 or 3.12 with eventlet support.**
