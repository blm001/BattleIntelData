# Intelligence Data

This folder contains intelligence reports and target information.

## Files

### reports.json
Contains intelligence reports from various sources in JSON format.
- **Structure**: Array of report objects
- **Fields**: report_id, timestamp, classification, source, subject, priority, location, summary, details, recommendations
- **Update Frequency**: Real-time
- **Classification**: Varies (Confidential to Secret)

### targets.csv
Contains target identification and tracking data in CSV format.
- **Structure**: CSV with headers
- **Fields**: target_id, name, type, priority, last_updated, coordinates, threat_level, status
- **Update Frequency**: Real-time  
- **Classification**: Secret

## Usage
Applications can use this data to:
- Display current intelligence reports
- Track high-value targets
- Generate threat assessments
- Plan tactical operations
- Maintain situational awareness