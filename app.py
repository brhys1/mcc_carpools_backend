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
from datetime import datetime

load_dotenv()

app = Flask(__name__)
# Get CORS origins from environment variable, with fallback
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "https://mcc-carpools-frontend.vercel.app,http://localhost:3000").split(",")

CORS(
    app, 
    resources={r"/api/*": {"origins": CORS_ORIGINS}}, 
    methods=["GET", "POST", "OPTIONS", "DELETE"], 
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
    
class DriveModel:
    @staticmethod
    def get_all():
        """Fetch all drives from Firestore"""
        drives_ref = firestore_client.collection("drives")
        docs = drives_ref.stream()
        return [{**doc.to_dict(), "id": doc.id} for doc in docs]
    
    @staticmethod
    def get_by_id(drive_id):
        """Fetch a single drive by ID"""
        doc_ref = firestore_client.collection("drives").document(drive_id)
        doc = doc_ref.get()
        if doc.exists:
            return {**doc.to_dict(), "id": doc.id}
        return None
    
    @staticmethod
    def create(data):
        """Create a new drive"""
        doc_ref = firestore_client.collection("drives").document()
        doc_ref.set(data)
        return doc_ref.id
    
    @staticmethod
    def update(drive_id, data):
        """Update an existing drive"""
        doc_ref = firestore_client.collection("drives").document(drive_id)
        doc_ref.update(data)
    
    @staticmethod
    def delete(drive_id):
        """Delete a drive"""
        firestore_client.collection("drives").document(drive_id).delete()
    
    @staticmethod
    def find_by_date_range(start_date, end_date):
        """Find a drive by date range"""
        drives_ref = firestore_client.collection("drives")
        query = drives_ref.where("date", ">=", start_date).where("date", "<=", end_date).stream()
        return [{**doc.to_dict(), "id": doc.id} for doc in query]


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


def pair_riders_with_drive(all_riders, date, start_time, end_time, pickup_address, car_capacity):
    """Pair riders with a specific drive based on availability and location"""
    try:
        print(f"\n=== PAIRING DEBUG ===")
        print(f"Date: {date}")
        print(f"Time: {start_time} - {end_time}")
        print(f"Pickup: {pickup_address}")
        print(f"Capacity: {car_capacity}")
        print(f"Total riders to check: {len(all_riders)}")
        
        # Get driver's region
        is_valid, lat, lng = validate_address(pickup_address)
        if not is_valid:
            print(f"❌ Invalid address: {pickup_address}")
            return []
        
        driver_regions = get_region(pickup_address, lat, lng)
        print(f"✅ Driver regions: {driver_regions}")
        
        # Filter riders who are available for this time slot and in compatible regions
        compatible_riders = []
        
        for rider in all_riders:
            rider_id = rider['id']
            rider_name = rider['name']
            rider_availability = rider.get('availability', {})
            rider_divisions = rider.get('divisions', {})
            
            print(f"\n--- Checking rider: {rider_name} ---")
            
            # Check if rider is available on this date (case-insensitive)
            date_lower = date.lower()
            available_dates = [d.lower() for d in rider_availability.keys()]
            
            if date_lower not in available_dates:
                print(f"❌ No availability for date: {date}")
                print(f"Available dates: {list(rider_availability.keys())}")
                continue
            
            # Get the actual date key (preserve original case)
            actual_date_key = None
            for d in rider_availability.keys():
                if d.lower() == date_lower:
                    actual_date_key = d
                    break
            
            print(f"✅ Has availability for {actual_date_key}")
            
            # Check if rider has time slots that overlap with drive time
            rider_time_slots = rider_availability[actual_date_key]
            has_overlapping_time = False
            
            print(f"Rider time slots: {rider_time_slots}")
            
            for slot in rider_time_slots:
                rider_start = slot.get('start')
                rider_end = slot.get('end')
                
                print(f"Checking slot: {rider_start} - {rider_end}")
                
                # Check if time slots overlap and rider isn't already paired
                if (rider_start and rider_end and 
                    time_overlaps(rider_start, rider_end, start_time, end_time) and
                    not slot.get('driver')):  # Not already paired
                    has_overlapping_time = True
                    print(f"✅ Time overlap found!")
                    break
                else:
                    if not rider_start or not rider_end:
                        print(f"❌ Missing start/end time")
                    elif not time_overlaps(rider_start, rider_end, start_time, end_time):
                        print(f"❌ No time overlap")
                    elif slot.get('driver'):
                        print(f"❌ Already paired with driver: {slot.get('driver')}")
            
            if not has_overlapping_time:
                print(f"❌ No overlapping time slots")
                continue
            
            # Check if rider is in a compatible region
            region_match = False
            print(f"Rider divisions: {rider_divisions}")
            for region in driver_regions:
                if rider_divisions.get(region, False):
                    region_match = True
                    print(f"✅ Region match: {region}")
                    break
            
            if not region_match:
                print(f"❌ No region match. Driver regions: {driver_regions}")
                continue
            
            # Calculate priority score (lower is better)
            priority_score = calculate_priority_score(rider, pickup_address, lat, lng, date)
            
            compatible_riders.append({
                'rider_id': rider_id,
                'rider_name': rider['name'],
                'rider_email': rider['email'],
                'priority_score': priority_score,
                'time_slot_index': next(i for i, slot in enumerate(rider_time_slots) 
                                      if time_overlaps(slot.get('start'), slot.get('end'), start_time, end_time))
            })
            
            print(f"✅ Added to compatible riders with priority: {priority_score}")
        
        print(f"\n=== COMPATIBLE RIDERS ===")
        print(f"Found {len(compatible_riders)} compatible riders")
        for rider in compatible_riders:
            print(f"- {rider['rider_name']}: {rider['priority_score']}")
        
        # Sort by priority score and take up to car_capacity
        compatible_riders.sort(key=lambda x: x['priority_score'])
        selected_riders = compatible_riders[:car_capacity]
        
        print(f"\n=== SELECTED RIDERS ===")
        print(f"Selected {len(selected_riders)} riders")
        for rider in selected_riders:
            print(f"- {rider['rider_name']}")
        
        return [rider['rider_id'] for rider in selected_riders]
        
    except Exception as e:
        print(f"Error in pair_riders_with_drive: {e}")
        import traceback
        traceback.print_exc()
        return []


def time_overlaps(start1, end1, start2, end2):
    """Check if two time ranges overlap"""
    try:
        # Convert time strings to comparable format (assuming HH:MM AM/PM format)
        def time_to_minutes(time_str):
            if not time_str:
                return 0
            # Simple conversion - you might want to use a proper time library
            time_str = time_str.upper()
            
            # Handle 24-hour format with AM/PM (e.g., "19:00 PM")
            if ':' in time_str:
                parts = time_str.split(':')
                hour_str = parts[0]
                minute_part = parts[1]
                
                # Extract minute and AM/PM
                if ' ' in minute_part:
                    minute_str, ampm = minute_part.split()
                else:
                    minute_str = minute_part
                    ampm = ''
                
                hour = int(hour_str)
                minute = int(minute_str)
                
                # If it's already 24-hour format (hour >= 13), don't add 12
                if hour >= 13:
                    return hour * 60 + minute
                
                # Handle AM/PM conversion
                if 'PM' in ampm and hour != 12:
                    hour += 12
                elif 'AM' in ampm and hour == 12:
                    hour = 0
                
                return hour * 60 + minute
            
            return 0
        
        start1_min = time_to_minutes(start1)
        end1_min = time_to_minutes(end1)
        start2_min = time_to_minutes(start2)
        end2_min = time_to_minutes(end2)
        
        result = max(start1_min, start2_min) < min(end1_min, end2_min)
        
        print(f"Time overlap check: {start1}-{end1} vs {start2}-{end2}")
        print(f"  Minutes: {start1_min}-{end1_min} vs {start2_min}-{end2_min}")
        print(f"  Result: {result}")
        
        return result
        
    except Exception as e:
        print(f"Error in time_overlaps: {e}")
        return False


def calculate_priority_score(rider, pickup_address, driver_lat, driver_lng, date):
    """Calculate priority score for rider pairing using priority queue logic"""
    try:
        # Get the week key from the date
        week_key = get_week_key_from_date(date)
        
        # Get rider's pairing history for this week
        rider_id = rider['id']
        pairing_history = get_rider_pairing_history(rider_id, week_key)
        
        # Base priority from random seed
        seed_string = f"{week_key}-{rider['email']}"
        import hashlib
        seed_hash = int(hashlib.md5(seed_string.encode()).hexdigest(), 16)
        
        import random
        random.seed(seed_hash)
        base_priority = random.randint(1, 1000)
        random.seed()  # Reset seed
        
        # Adjust priority based on pairing history
        # Each time a rider is paired, they get a penalty that moves them down the queue
        pairing_penalty = pairing_history * 1000  # Each pairing adds 1000 to priority (lower priority)
        
        final_priority = base_priority + pairing_penalty
        
        print(f"Priority calculation for {rider['email']} on {date}: base={base_priority}, history={pairing_history}, penalty={pairing_penalty}, final={final_priority}")
        
        return final_priority
        
    except Exception as e:
        print(f"Error in calculate_priority_score: {e}")
        return 10000  # Very high score = very low priority


def get_rider_pairing_history(rider_id, week_key):
    """Get how many times a rider has been paired this week"""
    try:
        # Get all drives for this week
        all_drives = DriveModel.get_all()
        pairing_count = 0
        
        print(f"Checking pairing history for rider {rider_id} in week {week_key}")
        
        for drive in all_drives:
            # Check if this drive is from the same week
            drive_date = drive.get('date', '')
            if drive_date:
                try:
                    from datetime import datetime
                    date_parts = drive_date.split(', ')
                    if len(date_parts) >= 2:
                        date_str = date_parts[1]
                        parsed_date = datetime.strptime(date_str, '%m/%d/%y')
                        drive_week_key = f"{parsed_date.year}-{parsed_date.isocalendar()[1]}"
                        
                        # Only count drives from the same week
                        if drive_week_key == week_key:
                            if rider_id in drive.get('paired_riders', []):
                                pairing_count += 1
                                print(f"  Found pairing: {drive_date} -> {drive_week_key} (count: {pairing_count})")
                        else:
                            print(f"  Skipping drive from different week: {drive_date} -> {drive_week_key} (target: {week_key})")
                except Exception as parse_error:
                    print(f"Error parsing drive date {drive_date}: {parse_error}")
                    continue
        
        print(f"Total pairing count for rider {rider_id} in week {week_key}: {pairing_count}")
        return pairing_count
        
    except Exception as e:
        print(f"Error in get_rider_pairing_history: {e}")
        return 0


def update_rider_availability(rider_id, date, start_time, end_time, drive_id):
    """Update rider's availability to mark them as paired and remove all availability for that day (case-insensitive date match)"""
    try:
        rider = RiderModel.get_by_id(rider_id)
        if not rider:
            return False
        
        availability = rider.get('availability', {})
        # Find the actual date key (case-insensitive)
        date_lower = date.lower()
        actual_date_key = None
        for d in availability.keys():
            if d.lower() == date_lower:
                actual_date_key = d
                break
        if not actual_date_key:
            return False
        
        # Mark the slot as paired (for record-keeping, optional)
        for slot in availability[actual_date_key]:
            if (slot.get('start') and slot.get('end') and 
                time_overlaps(slot.get('start'), slot.get('end'), start_time, end_time)):
                slot['driver'] = drive_id
                break

        # Remove all availability for that date
        del availability[actual_date_key]

        # Update the rider document
        RiderModel.update(rider_id, {'availability': availability})
        return True
        
    except Exception as e:
        print(f"Error in update_rider_availability: {e}")
        return False


def get_week_key_from_date(date_string):
    """Extract week key from date string (e.g., 'Monday, 12/16/24' -> '2024-50')"""
    try:
        from datetime import datetime
        
        # Parse the date string (assuming format like "Monday, 12/16/24")
        date_parts = date_string.split(', ')
        if len(date_parts) >= 2:
            date_str = date_parts[1]  # "12/16/24"
            parsed_date = datetime.strptime(date_str, '%m/%d/%y')
            # Get the week number (year + week number)
            week_key = f"{parsed_date.year}-{parsed_date.isocalendar()[1]}"
            return week_key
        else:
            # Fallback: use current week
            return f"{datetime.now().year}-{datetime.now().isocalendar()[1]}"
    except Exception as e:
        print(f"Error extracting week key from date '{date_string}': {e}")
        # Fallback: use current week
        from datetime import datetime
        return f"{datetime.now().year}-{datetime.now().isocalendar()[1]}"


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
        required_fields = ['name', 'email', 'address', 'drives', 'phone']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400

        name = data['name']
        email = data['email']
        address = data['address']
        drives = data['drives']
        phone = data['phone']
        capacity = data.get('capacity', 1)  # Default capacity of 1

        # Validate address
        is_valid, lat, lng = validate_address(address)
        if not is_valid:
            return jsonify({'error': 'Invalid address!'}), 400
        
        # Get region
        regions = get_region(address, lat, lng)
        if 'Unknown' in regions:
            return jsonify({'error': 'Address not in supported region!'}), 400

        # Add drives and pair with riders
        drive_success = add_drive(data)
        if not drive_success:
            return jsonify({'error': 'Failed to process drives and pair riders'}), 500

        # Create driver data
        driver_data = {
            "name": name,
            "email": email,
            "address": address,
            "region": regions,
            "drives": drives,
            "capacity": capacity,
            "lat": lat,
            "lng": lng,
            "phone": phone
        }

        # Store in Firestore
        driver_id = DriverModel.create(driver_data)
        
        return jsonify({
            'message': 'Driver added successfully and paired with available riders!',
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

def add_drive(data):
    """Add drives for a driver and pair with riders"""
    try:
        name = data['name']
        email = data['email']
        address = data['address']
        drives = data['drives']
        phone = data.get('phone', None)
        capacity = data.get('capacity', 1)  # Default capacity of 1

        # Get all available riders
        all_riders = RiderModel.get_all()
        
        for drive_data in drives:
            # Each drive_data is a dictionary with date as key
            for date, time_slots in drive_data.items():
                for time_slot in time_slots:
                    start_time = time_slot.get('start')
                    end_time = time_slot.get('end')
                    car_capacity = int(time_slot.get('capacity', capacity))
                    
                    # Create drive document
                    drive_info = {
                        "driver_name": name,
                        "driver_email": email,
                        "driver_phone": phone,
                        "pickup_address": address,
                        "date": date,
                        "start_time": start_time,
                        "end_time": end_time,
                        "total_capacity": car_capacity,
                        "remaining_capacity": car_capacity,
                        "paired_riders": [],
                        "status": "available",
                        "phone": phone
                    }
                    
                    # Store drive in Firestore
                    drive_id = DriveModel.create(drive_info)
                    
                    # Pair riders based on availability and location
                    paired_riders = pair_riders_with_drive(
                        all_riders, 
                        date, 
                        start_time, 
                        end_time, 
                        address, 
                        car_capacity
                    )
                    
                    # Update drive with paired riders
                    if paired_riders:
                        updated_drive = {
                            "paired_riders": paired_riders,
                            "remaining_capacity": car_capacity - len(paired_riders),
                            "status": "partially_filled" if len(paired_riders) < car_capacity else "filled"
                        }
                        DriveModel.update(drive_id, updated_drive)
                        
                        # Update rider availability to mark them as paired
                        for rider_id in paired_riders:
                            update_rider_availability(rider_id, date, start_time, end_time, drive_id)
        
        return True
        
    except Exception as e:
        print(f"Error in add_drive: {e}")
        return False
    
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


@app.route('/api/drives', methods=['GET'])
def get_drives():
    """Get all drives"""
    try:
        drives = DriveModel.get_all()
        return jsonify(drives)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/rides/<rider_id>', methods=['GET'])
def get_rider_rides(rider_id):
    """Get all rides for a specific rider"""
    try:
        # Get all drives where this rider is paired
        all_drives = DriveModel.get_all()
        rider_rides = []
        
        for drive in all_drives:
            if rider_id in drive.get('paired_riders', []):
                ride_info = {
                    'drive_id': drive['id'],
                    'driver_name': drive['driver_name'],
                    'driver_email': drive['driver_email'],
                    'pickup_address': drive['pickup_address'],
                    'date': drive['date'],
                    'start_time': drive['start_time'],
                    'end_time': drive['end_time'],
                    'status': drive['status']
                }
                rider_rides.append(ride_info)
        
        return jsonify(rider_rides)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/drives/<drive_id>/capacity', methods=['PUT'])
def update_drive_capacity(drive_id):
    """Update remaining capacity of a drive"""
    try:
        data = request.get_json()
        new_capacity = data.get('remaining_capacity')
        
        if new_capacity is None:
            return jsonify({'error': 'Missing remaining_capacity field'}), 400
        
        # Update the drive
        DriveModel.update(drive_id, {'remaining_capacity': new_capacity})
        
        # Update status based on capacity
        drive = DriveModel.get_by_id(drive_id)
        if drive:
            total_capacity = drive.get('total_capacity', 0)
            if new_capacity == 0:
                status = 'filled'
            elif new_capacity < total_capacity:
                status = 'partially_filled'
            else:
                status = 'available'
            
            DriveModel.update(drive_id, {'status': status})
        
        return jsonify({'message': 'Drive capacity updated successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/priority-queue/<date>', methods=['GET'])
def get_priority_queue(date):
    """Get the priority queue for a specific date (for debugging/transparency)"""
    try:
        # Get all riders
        all_riders = RiderModel.get_all()
        
        # Calculate priority scores for each rider
        priority_queue = []
        for rider in all_riders:
            priority_score = calculate_priority_score(
                rider, 
                "dummy_address", 
                0, 
                0, 
                date
            )
            
            # Get pairing history for this week
            week_key = get_week_key_from_date(date)
            
            pairing_history = get_rider_pairing_history(rider['id'], week_key)
            
            priority_queue.append({
                'rider_id': rider['id'],
                'rider_name': rider['name'],
                'rider_email': rider['email'],
                'priority_score': priority_score,
                'pairing_history': pairing_history,
                'base_priority': priority_score - (pairing_history * 1000)
            })
        
        # Sort by priority score (lower is better)
        priority_queue.sort(key=lambda x: x['priority_score'])
        
        return jsonify({
            'date': date,
            'week_key': week_key,
            'priority_queue': priority_queue
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/debug/riders', methods=['GET'])
def debug_riders():
    """Debug endpoint to see all riders and their availability"""
    try:
        all_riders = RiderModel.get_all()
        debug_data = []
        
        for rider in all_riders:
            rider_data = {
                'id': rider['id'],
                'name': rider['name'],
                'email': rider['email'],
                'availability': rider.get('availability', {}),
                'divisions': rider.get('divisions', {})
            }
            debug_data.append(rider_data)
        
        return jsonify({
            'total_riders': len(debug_data),
            'riders': debug_data
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/current-week-drives', methods=['GET'])
def get_current_week_drives():
    """Get all drives for today and the next 7 days"""
    try:
        from datetime import datetime, timedelta
        
        # Get today and next 7 days
        today = datetime.now()
        
        # Generate dates for today and next 7 days
        week_dates = []
        for i in range(7):  # Today + 7 more days = 8 total
            date = today + timedelta(days=i)
            # Format as "Monday, MM/DD/YY"
            day_name = date.strftime('%A')
            date_str = date.strftime('%m/%d/%y')
            week_dates.append(f"{day_name}, {date_str}")
        
        print(f"=== WEEK DRIVES DEBUG ===")
        print(f"Today: {today.strftime('%A, %m/%d/%y')}")
        print(f"Looking for dates: {week_dates}")
        
        # Get all drives
        all_drives = DriveModel.get_all()
        print(f"Total drives in database: {len(all_drives)}")
        
        # Print all drive dates for debugging
        all_drive_dates = []
        for drive in all_drives:
            drive_date = drive.get('date', '')
            if drive_date:
                all_drive_dates.append(drive_date)
        print(f"All drive dates in database: {all_drive_dates}")
        
        current_week_drives = []
        
        for drive in all_drives:
            drive_date = drive.get('date', '')
            print(f"Checking drive date: '{drive_date}'")
            if drive_date in week_dates:
                print(f"✅ Found matching drive for {drive_date}")
                # Get rider details for paired riders
                paired_riders_details = []
                for rider_id in drive.get('paired_riders', []):
                    rider = RiderModel.get_by_id(rider_id)
                    if rider:
                        paired_riders_details.append({
                            'name': rider.get('name', 'Unknown'),
                            'email': rider.get('email', 'Unknown')
                        })
                
                drive_info = {
                    'id': drive['id'],
                    'driver_name': drive.get('driver_name', 'Unknown'),
                    'driver_email': drive.get('driver_email', 'Unknown'),
                    'pickup_address': drive.get('pickup_address', 'Unknown'),
                    'date': drive_date,
                    'start_time': drive.get('start_time', 'Unknown'),
                    'end_time': drive.get('end_time', 'Unknown'),
                    'total_capacity': drive.get('total_capacity', 0),
                    'remaining_capacity': drive.get('remaining_capacity', 0),
                    'status': drive.get('status', 'unknown'),
                    'paired_riders': paired_riders_details,
                }
                current_week_drives.append(drive_info)
            else:
                print(f"❌ Drive date '{drive_date}' not in week_dates")
        
        # Group drives by day
        drives_by_day = {}
        for drive in current_week_drives:
            day = drive['date']
            if day not in drives_by_day:
                drives_by_day[day] = []
            drives_by_day[day].append(drive)
        
        # Sort drives within each day by start time
        for day in drives_by_day:
            drives_by_day[day].sort(key=lambda x: x['start_time'] or '')
        
        return jsonify({
            'period_start': today.strftime('%Y-%m-%d'),
            'period_end': (today + timedelta(days=7)).strftime('%Y-%m-%d'),
            'drives_by_day': drives_by_day,
            'total_drives': len(current_week_drives)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    


@app.route('/api/drives/by-phone', methods=['DELETE'])
def delete_drive_by_phone():
    """Delete a drive if the phone number matches the driver's phone (now stored on the drive)"""
    try:
        print("Deleting drive by phone")
        data = request.get_json()
        phone = data.get('phone')
        drive_id = data.get('drive_id')
        if not phone or not drive_id:
            return jsonify({'error': 'Missing phone or drive_id'}), 400
        
        print(f"Phone: {phone}, Drive ID: {drive_id}")

        drive = DriveModel.get_by_id(drive_id)
        if not drive:
            return jsonify({'error': 'Drive not found'}), 404

        # Check phone number directly on the drive
        if drive.get('driver_phone') != phone:
            return jsonify({'error': 'Phone number does not match'}), 403

        # Delete the drive
        DriveModel.delete(drive_id)
        return jsonify({'message': 'Drive deleted successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/drives/<drive_id>/signup', methods=['POST'])
def signup_for_drive(drive_id):
    """Sign up a user for a specific drive slot"""
    try:
        data = request.get_json()
        name = data.get('name')
        email = data.get('email')
        regions = data.get('regions', {})  # dict of region: bool
        if not name or not email:
            return jsonify({'error': 'Missing name or email'}), 400

        drive = DriveModel.get_by_id(drive_id)
        if not drive:
            return jsonify({'error': 'Drive not found'}), 404

        drive_date = drive['date']
        start_time = drive['start_time']
        end_time = drive['end_time']
        drive_region = drive.get('region') or drive.get('regions') or drive.get('pickup_address')
        # If drive_region is a list, use it; if string, make dict
        if isinstance(drive_region, list):
            drive_regions = {r: True for r in drive_region}
        elif isinstance(drive_region, dict):
            drive_regions = drive_region
        else:
            # fallback: try to get region from address
            is_valid, lat, lng = validate_address(drive.get('pickup_address', ''))
            drive_regions = {r: True for r in get_region(drive.get('pickup_address', ''), lat, lng)}

        # Merge regions from form and drive
        merged_regions = {**drive_regions, **regions}
        for k in drive_regions:
            merged_regions[k] = True

        # Find if rider exists for this week
        all_riders = RiderModel.get_all()
        rider = next((r for r in all_riders if r['email'].lower() == email.lower()), None)
        week_key = get_week_key_from_date(drive_date)
        today_week_key = get_week_key_from_date(datetime.now().strftime('%A, %m/%d/%y'))

        # Build availability for this slot
        slot = {'start': start_time, 'end': end_time, 'driver': drive_id}
        availability = {}
        availability[drive_date] = [slot]

        if rider:
            # Update regions: add drive's region(s)
            updated_regions = dict(rider.get('divisions', {}))
            for k in merged_regions:
                updated_regions[k] = updated_regions.get(k, False) or merged_regions[k]
            # Remove all other availability for this day
            updated_availability = dict(rider.get('availability', {}))
            updated_availability[drive_date] = [slot]
            # Remove all other slots for this date
            for d in list(updated_availability.keys()):
                if d != drive_date and get_week_key_from_date(d) == week_key:
                    del updated_availability[d]
            RiderModel.update(rider['id'], {'divisions': updated_regions, 'availability': updated_availability})
            rider_id = rider['id']
        else:
            # New rider: only this slot, only these regions
            new_rider = {
                'name': name,
                'email': email,
                'availability': availability,
                'divisions': merged_regions
            }
            rider_id = RiderModel.create(new_rider)

        # Add rider to drive if not already present
        paired_riders = list(drive.get('paired_riders', []))
        if rider_id not in paired_riders:
            paired_riders.append(rider_id)
            # Decrement remaining_capacity
            remaining_capacity = drive.get('remaining_capacity', drive.get('total_capacity', 0))
            remaining_capacity = max(0, remaining_capacity - 1)
            # Update status
            total_capacity = drive.get('total_capacity', 0)
            if remaining_capacity == 0:
                status = 'filled'
            elif remaining_capacity < total_capacity:
                status = 'partially_filled'
            else:
                status = 'available'
            DriveModel.update(drive_id, {
                'paired_riders': paired_riders,
                'remaining_capacity': remaining_capacity,
                'status': status
            })

        return jsonify({'message': 'Signed up for drive successfully', 'rider_id': rider_id}), 200
    except Exception as e:
        print(f"Error in signup_for_drive: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/')
def home():
    """Home endpoint"""
    return "MCC Carpools Backend"


if __name__ == '__main__':
    app.run()
