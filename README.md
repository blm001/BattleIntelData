# BattleIntelData
Data used by Battle Intelligence Apps

## Folder Structure

This repository contains organized data folders that Battle Intelligence applications can read from:

### 📁 units/
Contains military unit data, personnel information, and equipment status
- `personnel.json` - Squad and personnel unit data
- `vehicles.csv` - Vehicle and equipment tracking data

### 📁 maps/
Contains geographic and strategic location information
- `strategic_locations.xml` - Military installations and strategic points
- `terrain.csv` - Terrain analysis and environmental data

### 📁 intelligence/
Contains intelligence reports and target tracking data
- `reports.json` - Intelligence reports from various sources
- `targets.csv` - Target identification and status tracking

### 📁 battles/
Contains historical battle data and operational records
- `historical_engagements.yml` - Detailed battle records
- `operations.csv` - Operational summary data

### 📁 config/
Contains system configuration and application settings
- `system_config.json` - Main system configuration
- `app_settings.csv` - Application-specific settings

## Data Formats

The data is provided in multiple common formats:
- **JSON** - For structured, nested data
- **CSV** - For tabular data and easy import
- **XML** - For complex hierarchical data
- **YAML** - For human-readable configuration

## Usage

Applications can read from these folders to:
- Track unit locations and status
- Display strategic information on maps
- Process intelligence reports
- Analyze historical battle data
- Configure system behavior

Each folder contains a README.md with detailed information about the data structure and usage.
