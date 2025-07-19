from flask import Flask, jsonify, request
import gspread
import json
from google.oauth2.service_account import Credentials
from flask_cors import CORS
import googlemaps
from dotenv import load_dotenv
import os
import base64
from google.cloud import firestore

load_dotenv()

app = Flask(__name__)
CORS(
    app, 
    resources={r"/api/*": {"origins": r"https://mcc-carpools.vercel.app"}}, 
    methods=["GET", "POST", "OPTIONS"], 
    allow_headers=["Content-Type", "Authorization"]
)

# Initialize Google credentials
credentials_base64 = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_BASE64")
service_account_info = json.loads(base64.b64decode(credentials_base64).decode("utf-8"))
creds = Credentials.from_service_account_info(service_account_info)

# Initialize Google Maps Client
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

# Initialize Firebase
firebase_base64 = os.getenv("FIREBASE_ADMIN_CREDS_BASE64")
firebase_info = json.loads(base64.b64decode(firebase_base64).decode("utf-8"))
project_id = firebase_info.get("project_id")
firebase_creds = Credentials.from_service_account_info(firebase_info)
firestore_client = firestore.Client(project_id, credentials=firebase_creds)


class DriverModel:
    @staticmethod
    def get_all():
        """Fetch all drivers from Firestore"""
        drivers_ref = firestore_client.collection("drivers")
        docs = drivers_ref.stream()
        return [{**doc.to_dict(), "id": doc.id} for doc in docs]

    @staticmethod
    def get_by_id(driver_id):
        """Fetch a single driver by ID"""
        doc_ref = firestore_client.collection("drivers").document(driver_id)
        doc = doc_ref.get()
        if doc.exists:
            return {**doc.to_dict(), "id": doc.id}
        return None

    @staticmethod
    def create(data):
        """Create a new driver"""
        doc_ref = firestore_client.collection("drivers").document()
        doc_ref.set(data)
        return doc_ref.id

    @staticmethod
    def update(driver_id, data):
        """Update an existing driver"""
        doc_ref = firestore_client.collection("drivers").document(driver_id)
        doc_ref.update(data)

    @staticmethod
    def delete(driver_id):
        """Delete a driver"""
        firestore_client.collection("drivers").document(driver_id).delete()


class RiderModel:
    @staticmethod
    def get_all():
        """Fetch all riders from Firestore"""
        riders_ref = firestore_client.collection("riders")
        docs = riders_ref.stream()
        return [{**doc.to_dict(), "id": doc.id} for doc in docs]

    @staticmethod
    def get_by_id(rider_id):
        """Fetch a single rider by ID"""
        doc_ref = firestore_client.collection("riders").document(rider_id)
        doc = doc_ref.get()
        if doc.exists:
            return {**doc.to_dict(), "id": doc.id}
        return None

    @staticmethod
    def create(data):
        """Create a new rider"""
        doc_ref = firestore_client.collection("riders").document()
        doc_ref.set(data)
        return doc_ref.id

    @staticmethod
    def update(rider_id, data):
        """Update an existing rider"""
        doc_ref = firestore_client.collection("riders").document(rider_id)
        doc_ref.update(data)

    @staticmethod
    def delete(rider_id):
        """Delete a rider"""
        firestore_client.collection("riders").document(rider_id).delete()

    @staticmethod
    def find_by_name(name):
        """Find a rider by name"""
        riders_ref = firestore_client.collection("riders")
        query = riders_ref.where("name", "==", name).stream()
        
        for doc in query:
            return doc
        return None


def validate_address(address):
    """Validate and geocode an address"""
    try:
        geocode_result = gmaps.geocode(address)
        if geocode_result and len(geocode_result) > 0:
            location = geocode_result[0]['geometry']['location']
            return True, location['lat'], location['lng']
        else:
            return False, None, None
    except Exception as e:
        print(f"Geocoding error: {e}")
        return False, None, None


def get_region(address, lat, lng):
    """Determine the region based on coordinates and address"""
    regions = []

    # Kerrytown
    if 42.279277 <= lat <= 42.286811 and -83.747954 <= lng <= -83.733047:
        regions.append('kerrytown')

    # Central
    if 42.271742 <= lat <= 42.279677 and -83.747954 <= lng <= -83.733047:
        regions.append('central')

    # The Hill
    if 42.274770 <= lat <= 42.286811 and -83.733447 <= lng <= -83.722809:
        regions.append('hill')

    # Lower Burns Park
    if 42.264330 <= lat <= 42.272142 and -83.747954 <= lng <= -83.733047:
        regions.append('lower_bp')

    # Upper Burns Park
    if 42.264330 <= lat <= 42.275170 and -83.733447 <= lng <= -83.722809:
        regions.append('upper_bp')

    # Check for Pierpont in address
    if 'pierpont' in str(address).lower():
        regions.append('pierpont')

    return regions if regions else ['Unknown']


def get_google_sheets_data():
    """Fetch data from Google Sheets"""
    scope = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    client = gspread.authorize(creds.with_scopes(scope))
    sheet = client.open_by_key(os.getenv("SPREADSHEET_ID")).sheet1
    return sheet.get_all_records()


# API Routes
@app.route('/api/sheets', methods=['GET'])
def fetch_sheets_data():
    """Fetch data from Google Sheets"""
    try:
        data = get_google_sheets_data()
        return jsonify({'data': data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/drivers', methods=['GET'])
def get_drivers():
    """Get all drivers"""
    try:
        drivers = DriverModel.get_all()
        return jsonify(drivers)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/drivers', methods=['POST'])
def add_driver():
    """Add a new driver"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['name', 'email', 'address', 'drives']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400

        name = data['name']
        email = data['email']
        address = data['address']
        drives = data['drives']

        # Validate address
        is_valid, lat, lng = validate_address(address)
        if not is_valid:
            return jsonify({'error': 'Invalid address!'}), 400
        
        # Get region
        regions = get_region(address, lat, lng)
        if 'Unknown' in regions:
            return jsonify({'error': 'Address not in supported region!'}), 400

        # Create driver data
        driver_data = {
            "name": name,
            "email": email,
            "address": address,
            "region": regions,
            "drives": drives,
            "lat": lat,
            "lng": lng
        }

        # Store in Firestore
        driver_id = DriverModel.create(driver_data)
        
        return jsonify({
            'message': 'Driver added successfully!',
            'driver_id': driver_id
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/riders', methods=['GET'])
def get_riders():
    """Get all riders"""
    try:
        riders = RiderModel.get_all()
        return jsonify(riders)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/riders', methods=['POST'])
def add_rider():
    """Add or update a rider"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['name', 'email', 'availability', 'divisions']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400

        name = data['name']
        email = data['email']
        availability = data['availability']
        divisions = data['divisions']

        # Check if rider already exists
        existing_rider = RiderModel.find_by_name(name)

        if existing_rider:
            # Update existing rider
            RiderModel.update(existing_rider.id, {
                "email": email,
                "availability": availability,
                "divisions": divisions
            })
            message = 'Rider updated successfully!'
            rider_id = existing_rider.id
        else:
            # Add new rider
            rider_data = {
                "name": name,
                "email": email,
                "availability": availability,
                "divisions": divisions
            }
            rider_id = RiderModel.create(rider_data)
            message = 'Rider added successfully!'

        return jsonify({
            'message': message,
            'rider_id': rider_id
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/')
def home():
    """Home endpoint"""
    return "Hello, Vercel!"


if __name__ == '__main__':
    app.run()

