# Maps and Geographic Data

This folder contains geographic and strategic location data.

## Files

### strategic_locations.xml
Contains detailed information about military installations and strategic points in XML format.
- **Structure**: XML with nested location elements
- **Fields**: coordinates, type, status, capacity, defenses, supplies
- **Update Frequency**: Daily
- **Classification**: Secret

### terrain.csv
Contains terrain analysis data for different regions in CSV format.
- **Structure**: CSV with headers  
- **Fields**: region, terrain_type, elevation, visibility, weather, traversability
- **Update Frequency**: Weekly
- **Classification**: Confidential

## Usage
Applications can use this data to:
- Display strategic locations on maps
- Analyze terrain for mission planning
- Assess defensive capabilities
- Plan movement routes