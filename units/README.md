# Units Data

This folder contains data about military units, personnel, and equipment.

## Files

### personnel.json
Contains information about military squads and personnel units in JSON format.
- **Structure**: Array of unit objects
- **Fields**: id, name, type, strength, status, location, equipment, readiness
- **Update Frequency**: Real-time
- **Classification**: Confidential

### vehicles.csv  
Contains information about military vehicles and equipment in CSV format.
- **Structure**: CSV with headers
- **Fields**: id, type, model, status, fuel_level, crew_size, armament, location coordinates
- **Update Frequency**: Real-time
- **Classification**: Confidential

## Usage
Applications can read this data to:
- Track unit locations and status
- Monitor equipment readiness
- Plan resource allocation
- Generate unit status reports