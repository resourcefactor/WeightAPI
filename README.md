# WeightAPI
this Program runs on a local machin and publish it's captured Serial data realtime to API's

Install dependencies:

bash
pip install -r requirements.txt
Update the COM port in the serial_config section (line near the bottom) to match your weight scale.

Run the application:

bash
python serial_api.py

/api/current - Latest received data

/api/last_changed - Data from last actual value change

Single-line console updates - Uses \r carriage return to overwrite previous line

Efficient Data Handling
Buffer management - Accumulates data until 60+ characters or 2-second timeout

Thread-safe operations - Uses locks for shared data access

Change detection - Only updates last_changed_data when values actually change

Robust Serial Communication
Automatic port detection - Lists available ports on startup 

Error handling - Continues running even if serial communication fails

Proper cleanup - Uses daemon thread for automatic cleanup


API Usage Examples:

Get current data (always shows latest):
curl http://localhost:5000/api/current

curl http://localhost:5000/api/last_changed

curl http://localhost:5000/api/health