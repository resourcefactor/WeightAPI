@echo off
echo ====================================
echo Weight API - Installing Dependencies
echo ====================================
echo.

echo Installing required Python packages...
echo.

pip install --upgrade pip
pip install pyserial==3.5
pip install Flask==2.3.3
pip install Flask-CORS==4.0.0
pip install flask-socketio==5.3.4
pip install python-socketio==5.9.0
pip install eventlet==0.33.3
pip install waitress==2.1.2

echo.
echo ====================================
echo Installation Complete!
echo ====================================
echo.
echo Verifying installation...
python -c "import flask_socketio; print('✓ flask-socketio installed successfully')"
python -c "import socketio; print('✓ python-socketio installed successfully')"
python -c "import eventlet; print('✓ eventlet installed successfully')"
python -c "import flask; print('✓ Flask installed successfully')"
python -c "import flask_cors; print('✓ Flask-CORS installed successfully')"
python -c "import serial; print('✓ pyserial installed successfully')"
python -c "import waitress; print('✓ waitress installed successfully')"

echo.
echo All dependencies installed successfully!
echo You can now run: python weightapi.py
echo.
pause
