# rtcom
# LXMF-CLI - Range Test Client Plugin - WebUI Companion

# Range Test Web Server

Companion web server for `rangetest_client.py` plugin that provides a live navigator view of your range testing sessions.

## Features

- 🗺️ **Live GPS tracking** - Shows your current position like a navigator
- 📍 **Real-time updates** - Current position updates every 2 seconds
- 📊 **Logged points** - Displays all logged range test points with signal quality
- 🎨 **Signal visualization** - Color-coded markers based on RSSI values
- 📱 **Mobile optimized** - Works great on phones and tablets
- 🌐 **LAN accessible** - Access from any device on your network

## Installation

### 1. Install Flask

```bash
# On Termux/Android
pkg install python
pip install flask

# On regular Linux
pip3 install flask
```

### 2. Download the script

```bash
cd ~/.lxmf/plugins
wget https://your-url/rangetest_webserver.py
chmod +x rangetest_webserver.py
```

Or just copy the `rangetest_webserver.py` file to your preferred location.

## Usage

### Simple Usage (Termux)

Open a new Termux session and run:

```bash
python3 rangetest_webserver.py
```

Then open your browser to: **http://localhost:8033**

### Run in Background (Termux)

```bash
# Start in background
nohup python3 rangetest_webserver.py > /dev/null 2>&1 &

# Stop
pkill -f rangetest_webserver.py
```

### Systemd Service (Linux VPS/Desktop)

Create `/etc/systemd/system/rangetest-web.service`:

```ini
[Unit]
Description=Range Test Web Navigator
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME
ExecStart=/usr/bin/python3 /path/to/rangetest_webserver.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable rangetest-web
sudo systemctl start rangetest-web
sudo systemctl status rangetest-web
```

## Accessing the Web Interface

### Endpoints

- **http://localhost:8033/** - Live navigator with current GPS position
- **http://localhost:8033/map** - Original static HTML map
- **http://localhost:8033/api/current_gps** - Current GPS position (JSON)
- **http://localhost:8033/api/logged_points** - All logged points (JSON)

### From Other Devices (LAN)

The server listens on all interfaces, so you can access it from other devices:

1. Find your device IP: `ip addr show` or `ifconfig`
2. Access from other device: **http://YOUR_IP:8033/**

Example: If your phone's IP is `192.168.1.100`, access from tablet at `http://192.168.1.100:8033/`

## Configuration

Edit these variables in `rangetest_webserver.py`:

```python
PORT = 8033                    # Change port if needed
GPS_UPDATE_INTERVAL = 2        # GPS refresh rate (seconds)
HTML_REFRESH_INTERVAL = 5      # Map refresh rate (seconds)
```

## How It Works

1. **GPS Tracking**: Background thread continuously polls GPS (Termux only)
   - Tries GPS satellite first (10s timeout)
   - Falls back to network location (1s timeout)
   - Updates every 2 seconds

2. **Map Display**: 
   - Shows current position with blue pulsing marker
   - Shows logged points from range tests with color-coded signal strength
   - Draws path between logged points
   - Auto-refreshes to show new points

3. **No Editing Required**: 
   - Works alongside your existing `rangetest_client.py` plugin
   - Reads the same JSON/HTML files
   - No modifications to plugin code needed

## Workflow

### Typical Range Test Session

1. **Terminal 1**: Run LXMF-CLI with range test plugin
   ```bash
   lxmf-cli
   ```

2. **Terminal 2**: Start the web server
   ```bash
   python3 rangetest_webserver.py
   ```

3. **Browser**: Open http://localhost:8033

4. **Start Testing**: 
   - Server sends range test pings
   - Client receives pings and logs GPS positions
   - Web map updates automatically showing both:
     - Your current GPS position (live, blue marker)
     - All logged test points (colored by signal strength)

5. **Navigate**: The map follows your position like a car GPS navigator

## Troubleshooting

### "GPS Unavailable"

Make sure:
- You're on Termux/Android
- GPS Locker or similar app is running
- Location permissions granted to Termux
- termux-api is installed: `pkg install termux-api`

### "Range test map not found"

- Make sure you've logged at least one point with rangetest_client.py
- Check that `~/.lxmf/rangetest.json` exists
- The plugin must receive a range test ping first

### Port Already in Use

```bash
# Find what's using port 8033
lsof -i :8033

# Or change PORT in rangetest_webserver.py
```

### Can't Access from Other Devices

- Check firewall rules
- Make sure devices are on same network
- Use correct IP address (not localhost)

## Requirements

- Python 3.6+
- Flask
- Termux (for GPS tracking)
- termux-api package (for GPS)

## Performance

- Lightweight: ~10-20MB RAM
- Battery efficient GPS polling
- Non-blocking GPS updates
- Suitable for long-duration testing

## Tips

- Keep screen on during testing for consistent GPS
- Use GPS Locker app for better GPS performance
- Access from tablet/laptop for larger map view
- Export points periodically with `rangeexport` command

## Integration with LXMF-CLI

This server is designed to work seamlessly with your existing setup:

```
LXMF-CLI (Terminal 1)
  └─> rangetest_client.py plugin
       └─> Logs points to ~/.lxmf/rangetest.json

Range Test Web Server (Terminal 2)
  ├─> Reads ~/.lxmf/rangetest.json
  ├─> Gets live GPS position
  └─> Serves live web map
```

No configuration or code changes needed!

## License

Same as rangetest_client.py - use freely!

## Support

For issues or questions, refer to the Reticulum community or LXMF-CLI documentation.
