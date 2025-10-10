# WeightAPI
this Program runs on a local machin and publish it's captured Serial data realtime to API's

Install dependencies:

bash
pip install -r requirements.txt
Update the COM port in the serial_config section (line near the bottom) to match your weight scale.

Run the application:

bash
python weightapi.py

# Test the API
curl http://localhost:5000/api/weight/latest
curl http://localhost:5000/api/weight/health
curl http://localhost:5000/api/weight/ports

Efficient Data Handling
Real time Serial Port Data display at the terminal.
Realtime data fetch for each API Call
