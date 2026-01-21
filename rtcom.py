#!/usr/bin/env python3
"""
rtcom.py - Range Test Termux Companion App WebUI for LXMF-CLI rangetest plugin
Exposes the range test HTML map via Flask on localhost:8033
Features:
- Live HTML map with auto-refresh
- Current GPS position tracking (red arrow like a navigator)
- Real-time point updates
- Mobile-optimized interface

Usage:
    python3 rtcom.py
    
Then open: http://localhost:8033 on a phone web browser
"""

import os
import sys
import json
import time
import subprocess
from datetime import datetime
from flask import Flask, render_template_string, jsonify, send_file
from threading import Thread, Lock

app = Flask(__name__)

# Configuration
PORT = 8033
HOST = '0.0.0.0'  # Listen on all interfaces for LAN access
GPS_UPDATE_INTERVAL = 1  # seconds between GPS updates
HTML_REFRESH_INTERVAL = 5  # seconds between HTML file checks

# Global state
current_gps = {
    'latitude': None,
    'longitude': None,
    'accuracy': None,
    'speed': None,
    'altitude': None,
    'provider': None,
    'timestamp': None,
    'available': False
}
gps_lock = Lock()

# File paths (matching rangetest_client.py)
STORAGE_DIR = os.path.expanduser('/data/data/com.termux/files/home/lxmf-cli/lxmf_client_storage')
HTML_FILE = os.path.join(STORAGE_DIR, 'rangetest.html')
JSON_FILE = os.path.join(STORAGE_DIR, 'rangetest.json')

def is_termux():
    """Check if running on Termux"""
    return os.path.exists('/data/data/com.termux')

def get_current_gps():
    """Get current GPS position (non-blocking)"""
    if not is_termux():
        return None
    
    try:
        # Try GPS first (quick 2s timeout)
        result = subprocess.run(
            ['termux-location', '-p', 'gps', '-r', 'once'],
            capture_output=True,
            text=True,
            timeout=2,
            env=os.environ.copy()
        )
        
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout.strip())
            if 'latitude' in data and 'longitude' in data:
                lat = data.get('latitude')
                lon = data.get('longitude')
                if lat and lon and (abs(lat) > 0.001 or abs(lon) > 0.001):
                    return data
        
        # Fallback to network (1s timeout)
        result = subprocess.run(
            ['termux-location', '-p', 'network', '-r', 'once'],
            capture_output=True,
            text=True,
            timeout=1,
            env=os.environ.copy()
        )
        
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout.strip())
            if 'latitude' in data and 'longitude' in data:
                lat = data.get('latitude')
                lon = data.get('longitude')
                if lat and lon and (abs(lat) > 0.001 or abs(lon) > 0.001):
                    return data
    
    except Exception as e:
        print(f"[GPS] Error: {e}")
    
    return None

def gps_updater():
    """Background thread to continuously update GPS position"""
    global current_gps
    
    print(f"[GPS Updater] Started (interval: {GPS_UPDATE_INTERVAL}s)")
    
    while True:
        try:
            gps_data = get_current_gps()
            
            with gps_lock:
                if gps_data:
                    current_gps = {
                        'latitude': gps_data.get('latitude'),
                        'longitude': gps_data.get('longitude'),
                        'accuracy': gps_data.get('accuracy', 0),
                        'speed': gps_data.get('speed', 0),
                        'altitude': gps_data.get('altitude', 0),
                        'provider': gps_data.get('provider', 'unknown'),
                        'timestamp': datetime.now().isoformat(),
                        'available': True
                    }
                else:
                    current_gps['available'] = False
        
        except Exception as e:
            print(f"[GPS Updater] Error: {e}")
        
        time.sleep(GPS_UPDATE_INTERVAL)

def get_logged_points():
    """Get logged points from JSON file"""
    try:
        if os.path.exists(JSON_FILE):
            with open(JSON_FILE, 'r') as f:
                data = json.load(f)
                return data.get('points', [])
    except Exception as e:
        print(f"[Points] Error reading JSON: {e}")
    
    return []

# Enhanced HTML template with live GPS tracking
NAVIGATOR_TEMPLATE = '''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Range Test Navigator - Live</title>
    <style>
        body { 
            margin: 0; 
            padding: 0; 
            font-family: Arial, sans-serif;
            overflow: hidden;
        }
        #map { 
            position: absolute; 
            top: 0; 
            bottom: 180px; 
            width: 100%; 
        }
        #info {
            position: absolute; 
            bottom: 0; 
            width: 100%; 
            height: 180px;
            background: rgba(255, 255, 255, 0.95); 
            padding: 15px;
            box-sizing: border-box; 
            border-top: 3px solid #0078d4;
            overflow-y: auto;
        }
        .gps-status {
            background: #e8f5e9;
            border-left: 4px solid #4caf50;
            padding: 10px;
            margin-bottom: 10px;
            border-radius: 4px;
        }
        .gps-status.offline {
            background: #ffebee;
            border-left-color: #f44336;
        }
        .current-position {
            font-weight: bold;
            color: #2e7d32;
            font-size: 16px;
            margin-bottom: 5px;
        }
        .stat { 
            display: inline-block; 
            margin-right: 15px; 
            margin-bottom: 5px; 
            font-size: 13px; 
        }
        .stat-label { 
            font-weight: bold; 
            color: #0078d4; 
        }
        .pulse {
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .legend {
            background: white;
            padding: 10px;
            border-radius: 5px;
            box-shadow: 0 1px 5px rgba(0,0,0,0.4);
            font-size: 12px;
        }
        .legend-item {
            margin: 4px 0;
        }
        @media (max-width: 600px) {
            #info { height: 200px; }
            .stat { display: block; margin: 3px 0; }
        }
    </style>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
</head>
<body>
    <div id="map"></div>
    <div id="info">
        <div id="gps-status" class="gps-status">
            <div class="current-position">📍 Current Position: <span id="current-coords">Waiting for GPS...</span></div>
            <div style="font-size: 12px; color: #666;">
                <span id="gps-details"></span>
            </div>
        </div>
        <div class="stat"><span class="stat-label">Logged Points:</span> <span id="points">0</span></div>
        <div class="stat"><span class="stat-label">Distance:</span> <span id="distance">0 km</span></div>
        <div class="stat"><span class="stat-label">Avg RSSI:</span> <span id="avgrssi">N/A</span></div>
        <div class="stat"><span class="stat-label">Avg SNR:</span> <span id="avgsnr">N/A</span></div>
        <div class="stat"><span class="stat-label">Last Update:</span> <span id="lastupdate" class="pulse">Live</span></div>
    </div>

    <script>
        var map = L.map('map').setView([45.0, 7.0], 13);
        
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            attribution: '© OpenStreetMap | Range Test Navigator'
        }).addTo(map);
        
        var loggedMarkers = [];
        var loggedPoints = [];
        var polyline = null;
        var currentMarker = null;
        var currentCircle = null;
        var rssiValues = [];
        var snrValues = [];
        var userSetZoom = false;
        var currentZoom = 16;
        
        // Track user zoom changes
        map.on('zoomend', function() {
            userSetZoom = true;
            currentZoom = map.getZoom();
        });
        
        // Current position marker (red arrow pointing up, on top layer)
        var currentIcon = L.divIcon({
            className: 'current-marker',
            html: '<div style="width: 0; height: 0; border-left: 12px solid transparent; border-right: 12px solid transparent; border-bottom: 24px solid #ff0000; filter: drop-shadow(0 0 8px rgba(255,0,0,0.8)); animation: pulse 2s infinite;"></div>',
            iconSize: [24, 24],
            iconAnchor: [12, 24]
        });
        
        function getSignalColor(rssi) {
            if (rssi === null || rssi === undefined) return '#0078d4';
            if (rssi >= -60) return '#00ff00';
            if (rssi >= -70) return '#7fff00';
            if (rssi >= -80) return '#ffff00';
            if (rssi >= -90) return '#ffa500';
            if (rssi >= -100) return '#ff6600';
            return '#ff0000';
        }
        
        function createLoggedIcon(rssi, isStart, isEnd) {
            if (isStart) {
                return L.divIcon({
                    className: 'logged-marker',
                    html: '<div style="background-color: #00ff00; width: 14px; height: 14px; border-radius: 50%; border: 2px solid white; box-shadow: 0 0 6px rgba(0,0,0,0.6);"></div>',
                    iconSize: [14, 14],
                    iconAnchor: [7, 7]
                });
            }
            if (isEnd) {
                return L.divIcon({
                    className: 'logged-marker',
                    html: '<div style="background-color: #ff0000; width: 14px; height: 14px; border-radius: 50%; border: 2px solid white; box-shadow: 0 0 6px rgba(0,0,0,0.6);"></div>',
                    iconSize: [14, 14],
                    iconAnchor: [7, 7]
                });
            }
            
            var color = getSignalColor(rssi);
            return L.divIcon({
                className: 'logged-marker',
                html: '<div style="background-color: ' + color + '; width: 10px; height: 10px; border-radius: 50%; border: 2px solid white; box-shadow: 0 0 4px rgba(0,0,0,0.5);"></div>',
                iconSize: [10, 10],
                iconAnchor: [5, 5]
            });
        }
        
        var legend = L.control({position: 'topright'});
        legend.onAdd = function(map) {
            var div = L.DomUtil.create('div', 'legend');
            div.innerHTML = '<div style="font-weight: bold; margin-bottom: 5px;">🗺️ Live Navigator</div>' +
                          '<div class="legend-item">🔺 Current Position</div>' +
                          '<div class="legend-item">🟢 Start Point</div>' +
                          '<div class="legend-item">🔴 End Point</div>' +
                          '<div class="legend-item">━━ Path</div>' +
                          '<div style="margin-top: 8px; font-size: 11px; color: #666;">Auto-updates every 1s</div>';
            return div;
        };
        legend.addTo(map);
        
        function updateCurrentPosition(gps) {
            if (!gps.available) {
                document.getElementById('gps-status').className = 'gps-status offline';
                document.getElementById('current-coords').textContent = 'GPS Unavailable';
                document.getElementById('gps-details').textContent = '';
                
                if (currentMarker) {
                    map.removeLayer(currentMarker);
                    currentMarker = null;
                }
                if (currentCircle) {
                    map.removeLayer(currentCircle);
                    currentCircle = null;
                }
                return;
            }
            
            document.getElementById('gps-status').className = 'gps-status';
            document.getElementById('current-coords').textContent = 
                gps.latitude.toFixed(6) + ', ' + gps.longitude.toFixed(6);
            document.getElementById('gps-details').textContent = 
                'Accuracy: ±' + gps.accuracy.toFixed(0) + 'm | ' +
                'Speed: ' + gps.speed.toFixed(1) + ' km/h | ' +
                'Provider: ' + gps.provider;
            
            var latlng = [gps.latitude, gps.longitude];
            
            // Update or create current position marker
            if (currentMarker) {
                currentMarker.setLatLng(latlng);
            } else {
                currentMarker = L.marker(latlng, {
                    icon: currentIcon,
                    zIndexOffset: 1000  // Put on top of all other markers
                }).addTo(map);
                currentMarker.bindPopup('<b>🔺 Current Position</b><br>' +
                    'Live GPS tracking<br>' +
                    'Accuracy: ±' + gps.accuracy.toFixed(0) + 'm');
            }
            
            // Update or create accuracy circle
            if (currentCircle) {
                currentCircle.setLatLng(latlng);
                currentCircle.setRadius(gps.accuracy);
            } else {
                currentCircle = L.circle(latlng, {
                    radius: gps.accuracy,
                    color: '#ff0000',
                    fillColor: '#ff0000',
                    fillOpacity: 0.1,
                    weight: 2
                }).addTo(map);
            }
            
            // Center map on current position, preserving user's zoom level
            if (!userSetZoom) {
                // First time or no user interaction - set appropriate zoom
                currentZoom = gps.accuracy > 100 ? 14 : gps.accuracy > 50 ? 15 : 16;
            }
            
            // Always center on current position, but keep user's zoom
            map.setView(latlng, currentZoom, {animate: true, duration: 0.5});
        }
        
        function updateLoggedPoints(points) {
            // Clear existing logged markers
            loggedMarkers.forEach(m => map.removeLayer(m));
            loggedMarkers = [];
            loggedPoints = [];
            rssiValues = [];
            snrValues = [];
            
            if (polyline) {
                map.removeLayer(polyline);
                polyline = null;
            }
            
            if (points.length === 0) return;
            
            points.forEach((point, idx) => {
                var latlng = [point.latitude, point.longitude];
                loggedPoints.push(latlng);
                
                if (point.rssi !== null) rssiValues.push(point.rssi);
                if (point.snr !== null) snrValues.push(point.snr);
                
                var isStart = (idx === 0);
                var isEnd = (idx === points.length - 1);
                var icon = createLoggedIcon(point.rssi, isStart, isEnd);
                
                var marker = L.marker(latlng, {
                    icon: icon,
                    zIndexOffset: 0  // Logged points stay below current position
                }).addTo(map);
                
                var popup = '<b>Point #' + (idx + 1) + '</b><br>' +
                    'Time: ' + point.time + '<br>' +
                    'Lat: ' + point.latitude.toFixed(6) + '<br>' +
                    'Lon: ' + point.longitude.toFixed(6) + '<br>';
                
                if (point.rssi !== null) {
                    popup += 'RSSI: ' + point.rssi.toFixed(1) + ' dBm<br>';
                }
                if (point.snr !== null) {
                    popup += 'SNR: ' + point.snr.toFixed(1) + ' dB<br>';
                }
                
                marker.bindPopup(popup);
                loggedMarkers.push(marker);
            });
            
            // Draw path (below markers)
            if (loggedPoints.length > 1) {
                polyline = L.polyline(loggedPoints, {
                    color: 'red',
                    weight: 3,
                    opacity: 0.6
                }).addTo(map);
                
                // Bring current marker to front if it exists
                if (currentMarker) {
                    currentMarker.bringToFront();
                }
            }
            
            // Update stats
            document.getElementById('points').textContent = points.length;
            
            var avgRssi = rssiValues.length > 0 ? 
                rssiValues.reduce((a, b) => a + b, 0) / rssiValues.length : null;
            var avgSnr = snrValues.length > 0 ? 
                snrValues.reduce((a, b) => a + b, 0) / snrValues.length : null;
            
            document.getElementById('avgrssi').textContent = 
                avgRssi !== null ? avgRssi.toFixed(1) + ' dBm' : 'N/A';
            document.getElementById('avgsnr').textContent = 
                avgSnr !== null ? avgSnr.toFixed(1) + ' dB' : 'N/A';
            
            if (points.length > 0) {
                document.getElementById('lastupdate').textContent = 
                    points[points.length - 1].time;
            }
        }
        
        // Fetch current GPS position
        function fetchCurrentGPS() {
            fetch('/api/current_gps')
                .then(response => response.json())
                .then(data => updateCurrentPosition(data))
                .catch(err => console.error('GPS fetch error:', err));
        }
        
        // Fetch logged points
        function fetchLoggedPoints() {
            fetch('/api/logged_points')
                .then(response => response.json())
                .then(data => updateLoggedPoints(data.points))
                .catch(err => console.error('Points fetch error:', err));
        }
        
        // Initial load
        fetchCurrentGPS();
        fetchLoggedPoints();
        
        // Auto-refresh
        setInterval(fetchCurrentGPS, {{ gps_interval }} * 1000);
        setInterval(fetchLoggedPoints, {{ html_interval }} * 1000);
    </script>
</body>
</html>'''

@app.route('/')
def index():
    """Serve the live navigator page"""
    return render_template_string(
        NAVIGATOR_TEMPLATE,
        gps_interval=GPS_UPDATE_INTERVAL,
        html_interval=HTML_REFRESH_INTERVAL
    )

@app.route('/api/current_gps')
def api_current_gps():
    """API endpoint for current GPS position"""
    with gps_lock:
        return jsonify(current_gps)

@app.route('/api/logged_points')
def api_logged_points():
    """API endpoint for logged points"""
    points = get_logged_points()
    return jsonify({'points': points})

@app.route('/map')
def static_map():
    """Serve the original static HTML map"""
    if os.path.exists(HTML_FILE):
        return send_file(HTML_FILE)
    else:
        return "Range test map not found. Start logging points first!", 404

def print_banner():
    """Print startup banner"""
    print("\n" + "="*70)
    print("🗺️  rtcom - Range Test Termux Companion App WebUI")
    print("="*70)
    print(f"📡 Listening on: http://{HOST}:{PORT}")
    print(f"🌐 Local access: http://localhost:{PORT}")
    
    # Try to get local IP
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        print(f"📱 LAN access: http://{local_ip}:{PORT}")
    except:
        pass
    
    print(f"\n📂 Data directory: {STORAGE_DIR}")
    print(f"🔄 GPS updates: every {GPS_UPDATE_INTERVAL}s")
    print(f"🔄 Map refresh: every {HTML_REFRESH_INTERVAL}s")
    
    if is_termux():
        print(f"\n✅ Termux detected - GPS tracking enabled")
    else:
        print(f"\n⚠️  Not on Termux - GPS tracking disabled")
    
    print(f"\n📍 Endpoints:")
    print(f"   /              Live navigator with current position")
    print(f"   /map           Original static map")
    print(f"   /api/current_gps    Current GPS JSON")
    print(f"   /api/logged_points  Logged points JSON")
    
    print("\n💡 Press Ctrl+C to stop")
    print("="*70 + "\n")

def main():
    """Main entry point"""
    print_banner()
    
    # Check if storage directory exists
    if not os.path.exists(STORAGE_DIR):
        print(f"⚠️  Warning: Storage directory not found: {STORAGE_DIR}")
        print(f"   Make sure LXMF-CLI is running from the correct directory")
        print(f"   Expected: /data/data/com.termux/files/home/lxmf-cli/")
    
    # Start GPS updater thread (only on Termux)
    if is_termux():
        gps_thread = Thread(target=gps_updater, daemon=True)
        gps_thread.start()
    else:
        print("[Info] GPS tracking disabled (not on Termux)")
    
    # Start Flask server
    try:
        app.run(host=HOST, port=PORT, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\n\n🛑 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Server error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
