# rtcom
# LXMF-CLI - Range Test Client Plugin - WebUI Companion

# Range Test Web Server

Companion web server for `rangetest_client.py` plugin that provides a live navigator view of your range testing sessions.

# rtcom - Range Test Termux Companion App WebUI

Companion web server for LXMF-CLI `rangetest_client.py` plugin that provides a live navigator view of your range testing sessions.

## Features

- 🗺️ **Live GPS tracking** - Shows your current position with a red arrow like a navigator
- 📍 **Real-time updates** - Current position updates every 1 second
- 📊 **Logged points** - Displays all logged range test points with signal quality
- 🎨 **Signal visualization** - Color-coded markers based on RSSI values
- 📱 **Mobile optimized** - Works great on phones and tablets
- 🌐 **LAN accessible** - Access from any device on your network
- 🔺 **Clear position marker** - Red arrow on top of all points, always visible

## Installation

### 1. Install Flask

```bash
# On Termux/Android
pkg install python
pip install flask
```

### 2. Download rtcom.py

```bash
cd ~/lxmf-cli
wget https://your-url/rtcom.py
chmod +x rtcom.py
```

Or copy the `rtcom.py` file to your `lxmf-cli` directory.

## Usage

### Simple Usage (Termux)

From your `lxmf-cli` directory, open a new Termux session and run:

```bash
cd ~/lxmf-cli
python3 rtcom.py
```

Then open your browser to: **http://localhost:8033**

### Run in Background (Termux)

```bash
# Start in background
cd ~/lxmf-cli
nohup python3 rtcom.py > /dev/null 2>&1 &

# Stop
pkill -f rtcom.py
```

## File Structure

rtcom expects this folder structure (created by LXMF-CLI and rangetest plugin):

```
~/lxmf-cli/
├── lxmf-cli                          # Main LXMF-CLI executable
├── rtcom.py                          # This companion app
└── lxmf_client_storage/              # LXMF storage directory
    ├── rangetest.json                # Logged GPS points
    ├── rangetest.html                # Static HTML map
    ├── rangetest.csv                 # CSV export
    ├── rangetest.kml                 # KML export
    └── rangetest.geojson             # GeoJSON export
```

**Important**: The storage path is hardcoded in rtcom.py as:
```python
STORAGE_DIR = '/data/data/com.termux/files/home/lxmf-cli/lxmf_client_storage'
```

If your LXMF-CLI is in a different location, edit this line in rtcom.py.

## Accessing the Web Interface

### Endpoints

- **http://localhost:8033/** - Live navigator with current GPS position (red arrow)
- **http://localhost:8033/map** - Original static HTML map
- **http://localhost:8033/api/current_gps** - Current GPS position (JSON)
- **http://localhost:8033/api/logged_points** - All logged points (JSON)

### From Other Devices (LAN)

The server listens on all interfaces, so you can access it from other devices:

1. Find your device IP: `ip addr show`
2. Access from other device: **http://YOUR_IP:8033/**

Example: If your phone's IP is `192.168.1.100`, access from tablet at `http://192.168.1.100:8033/`

## Configuration

Edit these variables in `rtcom.py`:

```python
PORT = 8033                    # Change port if needed
GPS_UPDATE_INTERVAL = 1        # GPS refresh rate (seconds)
HTML_REFRESH_INTERVAL = 5      # Map refresh rate (seconds)
```

## How It Works

1. **GPS Tracking**: Background thread continuously polls GPS
   - Tries GPS satellite first (2s timeout)
   - Falls back to network location (1s timeout)
   - Updates every 1 second

2. **Map Display**: 
   - Shows current position with **red arrow** (🔺) on top layer
   - Shows logged points from range tests with color-coded signal strength
   - Draws path between logged points
   - Auto-refreshes to show new points
   - **Preserves your zoom level** while keeping map centered on position

3. **No Plugin Editing**: 
   - Works alongside your existing `rangetest_client.py` plugin
   - Reads the same JSON/HTML files from `lxmf_client_storage/`
   - No modifications to plugin code needed

## Workflow

### Typical Range Test Session

1. **Terminal 1**: Run LXMF-CLI with range test plugin
   ```bash
   cd ~/lxmf-cli
   ./lxmf-cli
   ```

2. **Terminal 2**: Start rtcom web server
   ```bash
   cd ~/lxmf-cli
   python3 rtcom.py
   ```

3. **Browser**: Open http://localhost:8033

4. **Start Testing**: 
   - Server sends range test pings
   - Client receives pings and logs GPS positions to `lxmf_client_storage/`
   - Web map updates automatically showing both:
     - Your current GPS position (red arrow 🔺, always on top)
     - All logged test points (colored by signal strength)

5. **Navigate**: The map follows your position like a car GPS navigator
   - Zoom in/out as needed - your zoom level is preserved
   - Map stays centered on your red arrow position

## Visual Guide

### Map Markers

- 🔺 **Red Arrow** - Your current position (always on top, updates every 1s)
- 🟢 **Green Circle** - Start point (first logged test)
- 🔴 **Red Circle** - End point (last logged test)
- 🟡/🟠 **Colored Circles** - Test points colored by RSSI signal strength
- ━━ **Red Line** - Path traveled during testing

### Signal Colors (RSSI)

- 🟢 Green: Excellent (≥-60 dBm)
- 🟡 Yellow: Good (-70 to -80 dBm)
- 🟠 Orange: Fair (-80 to -90 dBm)
- 🔴 Red: Poor (≤-90 dBm)
- 🔵 Blue: No signal data

## Troubleshooting

### "GPS Unavailable"

Make sure:
- You're on Termux/Android
- GPS Locker or similar app is running
- Location permissions granted to Termux
- termux-api is installed: `pkg install termux-api`

### "Range test map not found"

- Make sure you've logged at least one point with rangetest_client.py
- Check that `~/lxmf-cli/lxmf_client_storage/rangetest.json` exists
- Run `rangelogs` in LXMF-CLI to verify file locations

### "Storage directory not found"

- Make sure you're running from `~/lxmf-cli/` directory
- Verify LXMF-CLI has created `lxmf_client_storage/` directory
- Check the STORAGE_DIR path in rtcom.py matches your setup

### Port Already in Use

```bash
# Find what's using port 8033
lsof -i :8033

# Or change PORT in rtcom.py
```

### Can't Access from Other Devices

- Check firewall rules
- Make sure devices are on same network
- Use correct IP address (not localhost)

## Requirements

- Python 3.6+
- Flask (`pip install flask`)
- Termux (for GPS tracking)
- termux-api package (for GPS: `pkg install termux-api`)
- LXMF-CLI with rangetest_client.py plugin

## Performance

- Lightweight: ~10-20MB RAM
- Battery efficient GPS polling (1s interval)
- Non-blocking GPS updates
- Suitable for long-duration testing

## Tips

- Keep screen on during testing for consistent GPS
- Use GPS Locker app for better GPS performance
- Access from tablet/laptop for larger map view
- Zoom in/out freely - your zoom level is remembered
- Export points periodically with `rangeexport` command in LXMF-CLI

## Integration with LXMF-CLI

rtcom is designed to work seamlessly with your existing setup:

```
LXMF-CLI (Terminal 1)
  └─> rangetest_client.py plugin
       └─> Logs points to lxmf_client_storage/rangetest.json

rtcom (Terminal 2)
  ├─> Reads lxmf_client_storage/rangetest.json
  ├─> Gets live GPS position
  └─> Serves live web map with red arrow tracker
```

No configuration or code changes needed!

## Project Info

- **Name**: rtcom (Range Test Termux Companion App WebUI)
- **For**: LXMF-CLI rangetest plugin
- **Platform**: Termux/Android
- **License**: Free to use

## Support

For issues or questions, refer to:
- Reticulum community
- LXMF-CLI documentation
- GitHub issues (if available)
