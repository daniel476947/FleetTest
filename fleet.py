from flask import Flask, request, jsonify, render_template, send_file, redirect
from flask_cors import CORS
from pymongo import MongoClient
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Alignment
from bson.objectid import ObjectId
import os


app = Flask(__name__)
CORS(app)

# MongoDB Atlas connection string
MONGO_URI = os.getenv('MONGO_URI')

# Initialize the client
client = MongoClient(MONGO_URI)

# Specify the database and collection
db = client['Fleettest']
collection = db['Fleet']

@app.route('/')
def index():
    return render_template('form.html')  # Renders the HTML form

@app.route('/upload', methods=['POST'])
def upload():
    try:
        # Retrieve form data as strings
        year_str = request.form.get('Year', '').strip()
        capacity_str = request.form.get('Capacity', '').strip()

        # Try converting year and capacity to integers
        try:
            year_val = int(year_str)
            capacity_val = int(capacity_str)
        except ValueError:
            return jsonify({"success": False, "message": "Year and Capacity must be valid integers."}), 400

        vehicle_data = {
            "Registration No": request.form.get('Registration No', '').strip(),
            "Make": request.form.get('Make', '').strip(),
            "Model": request.form.get('Model', '').strip(),
            "Vehicle Type": request.form.get('Vehicle Type', '').strip(),
            "Year": year_val,                      # store as integer
            "Main Colour": request.form.get('Main Colour', '').strip(),
            "Secondary Colour": request.form.get('Secondary Colour', '').strip(),
            "Fuel": request.form.get('Fuel', '').strip(),
            "Capacity": capacity_val,              # store as integer
            "Chassis No": request.form.get('Chassis No', '').strip(),
            "Model No": request.form.get('Model No', '').strip(),
            "Status": request.form.get('Status', '').strip(),
            "Location": request.form.get('Location', '').strip()
        }

        # Insert data into MongoDB
        result = collection.insert_one(vehicle_data)
        print(f"Data successfully inserted with ID: {result.inserted_id}")
        return jsonify({"success": True, "message": "Data uploaded successfully!"}), 200

    except Exception as e:
        print(f"Error inserting data: {e}")
        return jsonify({"success": False, "message": "Error uploading data."}), 500


@app.route('/view_fleet', methods=['GET', 'POST'])
def view_fleet():
    try:
        query = {}
        if request.method == 'POST':
            # Get the search term from the form
            search_term = request.form.get('search', '').strip()
            
            if search_term:
                # Split the search term into individual words
                search_words = search_term.split()
                
                # Create a list of regex queries for each word
                query["$and"] = []
                for word in search_words:
                    word_query = {
                        "$or": [
                            {"Registration No": {"$regex": word, "$options": "i"}},
                            {"Make": {"$regex": word, "$options": "i"}},
                            {"Model": {"$regex": word, "$options": "i"}},
                            {"Chassis No": {"$regex": word, "$options": "i"}},
                            {"Year": {"$regex": word, "$options": "i"}}
                        ]
                    }
                    query["$and"].append(word_query)
            
            # Apply filters from dropdowns
            vehicle_type = request.form.get('vehicle_type')
            main_colour = request.form.get('main_colour')
            secondary_colour = request.form.get('secondary_colour')
            fuel = request.form.get('fuel')
            status = request.form.get('status')
            location = request.form.get('location')
            registration_status = request.form.get('registration_status')  # Get the new dropdown value

            # Update the query based on selected filters
            if vehicle_type:
                query["Vehicle Type"] = vehicle_type
            if main_colour:
                query["Main Colour"] = main_colour
            if secondary_colour:
                query["Secondary Colour"] = secondary_colour
            if fuel:
                query["Fuel"] = fuel
            if status:
                query["Status"] = status
            if location:
                query["Location"] = location

            # Handle registration status filtering
            if registration_status == 'Registered':
                query["Registration No"] = {"$ne": None, "$ne": ""}  # Ensure that the 'Registration No' field is neither null nor empty
            elif registration_status == 'Unregistered':
                query["Registration No"] = {"$in": [None, ""]}  # Ensure that the 'Registration No' field is null or empty

        # Fetch vehicles from MongoDB based on the query
        vehicles = list(collection.find(query))
        for vehicle in vehicles:
            vehicle['_id'] = str(vehicle['_id'])  # Convert ObjectId to string for rendering
        return render_template('viewfleet.html', vehicles=vehicles)  # Render HTML template
    except Exception as e:
        print(f"Error fetching data: {e}")
        return jsonify({"success": False, "message": "Error fetching data."}), 500
        
@app.route('/export_fleet', methods=['GET'])
def export_fleet():
    try:
        # Get filter parameters from the query string
        search_term = request.args.get('search', '').strip()
        vehicle_type = request.args.get('vehicle_type', '')
        main_colour = request.args.get('main_colour', '')
        secondary_colour = request.args.get('secondary_colour', '')
        fuel = request.args.get('fuel', '')
        status = request.args.get('status', '')
        location = request.args.get('location', '')
        registration_status = request.args.get('registration_status', '')

        # Build the query based on filters
        query = {}
        if search_term:
            query = {"$or": [
                {"Registration No": {"$regex": search_term, "$options": "i"}},
                {"Make": {"$regex": search_term, "$options": "i"}},
                {"Model": {"$regex": search_term, "$options": "i"}},
                {"Chassis No": {"$regex": search_term, "$options": "i"}},
                {"Year": {"$regex": search_term, "$options": "i"}}
            ]}
        
        if vehicle_type:
            query["Vehicle Type"] = vehicle_type
        if main_colour:
            query["Main Colour"] = main_colour
        if secondary_colour:
            query["Secondary Colour"] = secondary_colour
        if fuel:
            query["Fuel"] = fuel
        if status:
            query["Status"] = status
        if location:
            query["Location"] = location

        if registration_status == 'Registered':
            query["Registration No"] = {"$ne": None, "$ne": ""}
        elif registration_status == 'Unregistered':
            query["Registration No"] = {"$in": [None, ""]}
        
        # Fetch filtered vehicles from MongoDB
        vehicles = list(collection.find(query))
        for vehicle in vehicles:
            vehicle.pop('_id')  # Remove _id field from data

        # Convert the filtered data to a pandas DataFrame
        df = pd.DataFrame(vehicles)

        # Save the DataFrame to an Excel file
        excel_file = '/tmp/fleet_data_filtered.xlsx'  # Path to save the file temporarily
        df.to_excel(excel_file, index=False)

        # Load the workbook and sheet to apply formatting
        wb = load_workbook(excel_file)
        ws = wb.active

        # Apply right alignment to all cells
        for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=ws.max_column):
            for cell in row:
                cell.alignment = Alignment(horizontal='right')

        # Save the modified Excel file
        wb.save(excel_file)

        # Send the Excel file as a download to the client
        return send_file(excel_file, as_attachment=True, download_name='fleet_data.xlsx')
    except Exception as e:
        print(f"Error exporting data: {e}")
        return jsonify({"success": False, "message": "Error exporting data."}), 500
        
@app.route('/edit/<id>', methods=['GET', 'POST'])
def edit_vehicle(id):
    try:
        vehicle = collection.find_one({"_id": ObjectId(id)})
        if not vehicle:
            return jsonify({"success": False, "message": "Vehicle not found."}), 404

        if request.method == 'POST':
            # Parse as integers
            year_str = request.form.get('Year', '').strip()
            capacity_str = request.form.get('Capacity', '').strip()

            try:
                year_val = int(year_str)
                capacity_val = int(capacity_str)
            except ValueError:
                return jsonify({"success": False, "message": "Year and Capacity must be valid integers."}), 400

            updated_data = {
                "Registration No": request.form.get('Registration No', '').strip(),
                "Make": request.form.get('Make', '').strip(),
                "Model": request.form.get('Model', '').strip(),
                "Vehicle Type": request.form.get('Vehicle Type', '').strip(),
                "Year": year_val,
                "Main Colour": request.form.get('Main Colour', '').strip(),
                "Secondary Colour": request.form.get('Secondary Colour', '').strip(),
                "Fuel": request.form.get('Fuel', '').strip(),
                "Capacity": capacity_val,
                "Chassis No": request.form.get('Chassis No', '').strip(),
                "Model No": request.form.get('Model No', '').strip(),
                "Status": request.form.get('Status', '').strip(),
                "Location": request.form.get('Location', '').strip()
            }
            collection.update_one({"_id": ObjectId(id)}, {"$set": updated_data})
            return redirect('/view_fleet')

        return render_template('editvehicle.html', vehicle=vehicle)
    except Exception as e:
        print(f"Error editing vehicle: {e}")
        return jsonify({"success": False, "message": "Error editing vehicle."}), 500


@app.route('/delete/<id>', methods=['POST'])
def delete_vehicle(id):
    try:
        result = collection.delete_one({"_id": ObjectId(id)})
        if result.deleted_count == 1:
            print(f"Vehicle with ID {id} deleted successfully.")
            return redirect('/view_fleet')
        else:
            return jsonify({"success": False, "message": "Vehicle not found."}), 404
    except Exception as e:
        print(f"Error deleting vehicle: {e}")
        return jsonify({"success": False, "message": "Error deleting vehicle."}), 500    
        

if __name__ == '__main__':
    app.run()
