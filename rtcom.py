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
import shutil
import subprocess
from datetime import datetime
from flask import Flask, render_template_string, jsonify, send_file, request
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
    'bearing': None,
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
                        'bearing': gps_data.get('bearing', None),
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
            bottom: 250px; 
            width: 100%; 
        }
        #info {
            position: absolute; 
            bottom: 0; 
            width: 100%; 
            height: 250px;
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
        @keyframes pulse-smooth {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.7; transform: scale(1.1); }
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
            #info { height: 300px; }
            #map { bottom: 300px; }
            .stat { display: block; margin: 3px 0; }
        }
        .orientation-btn {
            position: absolute;
            bottom: 20px;
            left: 20px;
            z-index: 1000;
            width: 50px;
            height: 50px;
            background: #ff9800;
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 24px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.3);
            display: flex;
            align-items: center;
            justify-content: center;
            transition: background 0.3s;
        }
        .orientation-btn:hover {
            background: #f57c00;
        }
        .orientation-btn.active {
            background: #ff5722;
        }
        .modal {
            display: none;
            position: fixed;
            z-index: 2000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.5);
        }
        .modal-content {
            background-color: white;
            margin: 15% auto;
            padding: 20px;
            border-radius: 8px;
            width: 90%;
            max-width: 400px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        .modal-header {
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 15px;
            color: #0078d4;
        }
        .modal-input {
            width: 100%;
            padding: 8px;
            margin: 8px 0;
            border: 1px solid #ddd;
            border-radius: 4px;
            box-sizing: border-box;
            font-size: 14px;
        }
        .modal-label {
            display: block;
            margin-top: 10px;
            font-weight: bold;
            color: #333;
        }
        .modal-buttons {
            margin-top: 20px;
            text-align: right;
        }
        .modal-btn {
            padding: 8px 16px;
            margin-left: 10px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }
        .modal-btn-primary {
            background: #4caf50;
            color: white;
        }
        .modal-btn-cancel {
            background: #ddd;
            color: #333;
        }
        .modal-btn-stop {
            background: #f44336;
            color: white;
        }
    </style>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
</head>
<body>
    <div id="map">
        <!-- Floating Orientation Button -->
        <button id="orientationBtn" class="orientation-btn" onclick="toggleOrientation()" title="Toggle Map Orientation">
            <i class="fas fa-compass"></i>
        </button>
    </div>
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
        <div style="margin-top: 10px; border-top: 1px solid #ddd; padding-top: 10px;">
            <button onclick="toggleFullscreen()" style="padding: 6px 12px; margin-right: 8px; background: #0078d4; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 13px;">
                <i class="fas fa-expand"></i> Fullscreen
            </button>
            <button onclick="exportMap()" style="padding: 6px 12px; margin-right: 8px; background: #4caf50; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 13px;">
                <i class="fas fa-download"></i> Export
            </button>
            <button id="rangeTestBtn" onclick="openRangeTestModal()" style="padding: 6px 12px; background: #9c27b0; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 13px;">
                <i class="fas fa-broadcast-tower"></i> <span id="rangeTestText">Start Test</span>
            </button>
            <span id="export-status" style="margin-left: 10px; font-size: 12px; color: #666;"></span>
        </div>
    </div>

    <!-- Range Test Modal -->
    <div id="rangeTestModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <i class="fas fa-broadcast-tower"></i> Configure Range Test
            </div>
            <label class="modal-label">Contact Index (#):</label>
            <input type="number" id="contactIndex" class="modal-input" placeholder="e.g., 1" min="0" value="0">
            
            <label class="modal-label">Number of Pings (N):</label>
            <input type="number" id="pingCount" class="modal-input" placeholder="e.g., 10" min="1" value="10">
            
            <label class="modal-label">Delay Between Pings (D) seconds:</label>
            <input type="number" id="pingDelay" class="modal-input" placeholder="e.g., 5" min="1" value="5">
            
            <div class="modal-buttons">
                <button class="modal-btn modal-btn-cancel" onclick="closeRangeTestModal()">Cancel</button>
                <button class="modal-btn modal-btn-primary" onclick="startRangeTest()">Start Test</button>
            </div>
        </div>
    </div>

    <!-- Stop Range Test Modal -->
    <div id="stopTestModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <i class="fas fa-stop-circle"></i> Stop Range Test
            </div>
            <p style="margin: 15px 0;">Are you sure you want to stop the range test?</p>
            <div class="modal-buttons">
                <button class="modal-btn modal-btn-cancel" onclick="closeStopTestModal()">Cancel</button>
                <button class="modal-btn modal-btn-stop" onclick="stopRangeTest()">Stop Test</button>
            </div>
        </div>
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
        var orientationEnabled = false;
        var currentHeading = 0;
        var rangeTestActive = false;
        
        // Track user zoom changes
        map.on('zoomend', function() {
            userSetZoom = true;
            currentZoom = map.getZoom();
        });
        
        // Current position marker (white crosshairs with blue outline, on top layer)
        var currentIcon = L.divIcon({
            className: 'current-marker',
            html: '<i class="fa-solid fa-crosshairs" style="font-size: 32px; color: white; text-shadow: 0 0 3px #2196f3, 0 0 6px #2196f3, 0 0 10px #2196f3, 0 0 2px black; animation: pulse-smooth 3s infinite;"></i>',
            iconSize: [32, 32],
            iconAnchor: [16, 16]
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
                          '<div class="legend-item"><i class="fa-solid fa-crosshairs" style="color: #2196f3;"></i> Current Position</div>' +
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
            
            // Update heading if available
            if (gps.bearing !== null && gps.bearing !== undefined) {
                currentHeading = gps.bearing;
            }
            
            // Note: Map rotation requires Leaflet.RotatedMarker plugin or similar
            // For now, orientation just changes the crosshairs icon rotation
            if (orientationEnabled && currentHeading !== null) {
                // Rotate the arrow icon to show direction
                var rotatedIcon = L.divIcon({
                    className: 'current-marker',
                    html: '<i class="fa-solid fa-circle-up" style="font-size: 32px; color: white; text-shadow: 0 0 3px #2196f3, 0 0 6px #2196f3, 0 0 10px #2196f3, 0 0 2px black; animation: pulse-smooth 3s infinite; transform: rotate(' + currentHeading + 'deg); transform-origin: center;"></i>',
                    iconSize: [32, 32],
                    iconAnchor: [16, 16]
                });
                if (currentMarker) {
                    currentMarker.setIcon(rotatedIcon);
                }
            } else if (!orientationEnabled && currentMarker) {
                // Reset to crosshairs when orientation is disabled
                currentMarker.setIcon(currentIcon);
            }
            
            // Update or create current position marker
            if (currentMarker) {
                currentMarker.setLatLng(latlng);
            } else {
                currentMarker = L.marker(latlng, {
                    icon: currentIcon,
                    zIndexOffset: 1000  // Put on top of all other markers
                }).addTo(map);
                currentMarker.bindPopup('<b><i class="fa-solid fa-crosshairs" style="color: #2196f3;"></i> Current Position</b><br>' +
                    'Live GPS tracking<br>' +
                    'Accuracy: ±' + gps.accuracy.toFixed(0) + 'm');
            }
            
            // Update or create accuracy circle (blue with white outline, on top)
            if (currentCircle) {
                currentCircle.setLatLng(latlng);
                currentCircle.setRadius(gps.accuracy);
            } else {
                currentCircle = L.circle(latlng, {
                    radius: gps.accuracy,
                    color: 'white',           // White outline
                    fillColor: '#2196f3',     // Blue fill
                    fillOpacity: 0.15,
                    weight: 3,
                    opacity: 0.8,
                    className: 'accuracy-circle'
                }).addTo(map);
                currentCircle.bringToFront();  // Bring to front layer
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
            }
            
            // Bring current position elements to front
            if (currentCircle) {
                currentCircle.bringToFront();
            }
            if (currentMarker) {
                currentMarker.bringToFront();
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
        
        // Fullscreen toggle
        function toggleFullscreen() {
            if (!document.fullscreenElement) {
                document.documentElement.requestFullscreen().catch(err => {
                    console.error('Fullscreen error:', err);
                });
            } else {
                document.exitFullscreen();
            }
        }
        
        // Orientation toggle
        function toggleOrientation() {
            orientationEnabled = !orientationEnabled;
            const btnElement = document.getElementById('orientationBtn');
            
            if (orientationEnabled) {
                btnElement.classList.add('active');
                // Icon will be updated on next GPS update to show direction
            } else {
                btnElement.classList.remove('active');
                // Reset to crosshairs icon
                if (currentMarker) {
                    currentMarker.setIcon(currentIcon);
                }
            }
        }
        
        // Range Test Modal Functions
        function openRangeTestModal() {
            if (rangeTestActive) {
                // Show stop confirmation
                document.getElementById('stopTestModal').style.display = 'block';
            } else {
                // Show start configuration
                document.getElementById('rangeTestModal').style.display = 'block';
            }
        }
        
        function closeRangeTestModal() {
            document.getElementById('rangeTestModal').style.display = 'none';
        }
        
        function closeStopTestModal() {
            document.getElementById('stopTestModal').style.display = 'none';
        }
        
        function startRangeTest() {
            const contactIndex = document.getElementById('contactIndex').value;
            const pingCount = document.getElementById('pingCount').value;
            const pingDelay = document.getElementById('pingDelay').value;
            
            if (!contactIndex || !pingCount || !pingDelay) {
                alert('Please fill all fields');
                return;
            }
            
            const statusEl = document.getElementById('export-status');
            statusEl.textContent = 'Starting range test...';
            statusEl.style.color = '#9c27b0';
            
            fetch('/api/send_lxmf_command', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    contact_index: contactIndex,
                    command: 'rt',
                    ping_count: pingCount,
                    ping_delay: pingDelay
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    rangeTestActive = true;
                    document.getElementById('rangeTestText').textContent = 'Stop Test';
                    document.getElementById('rangeTestBtn').style.background = '#f44336';
                    statusEl.textContent = '✅ Range test started';
                    statusEl.style.color = '#4caf50';
                    closeRangeTestModal();
                } else {
                    statusEl.textContent = '❌ ' + data.error;
                    statusEl.style.color = '#f44336';
                }
                setTimeout(() => { statusEl.textContent = ''; }, 5000);
            })
            .catch(err => {
                statusEl.textContent = '❌ Command failed';
                statusEl.style.color = '#f44336';
                console.error('Command error:', err);
            });
        }
        
        function stopRangeTest() {
            const contactIndex = document.getElementById('contactIndex').value;
            
            const statusEl = document.getElementById('export-status');
            statusEl.textContent = 'Stopping range test...';
            statusEl.style.color = '#f44336';
            
            fetch('/api/send_lxmf_command', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    contact_index: contactIndex,
                    command: 'rs'
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    rangeTestActive = false;
                    document.getElementById('rangeTestText').textContent = 'Start Test';
                    document.getElementById('rangeTestBtn').style.background = '#9c27b0';
                    statusEl.textContent = '✅ Range test stopped';
                    statusEl.style.color = '#4caf50';
                    closeStopTestModal();
                } else {
                    statusEl.textContent = '❌ ' + data.error;
                    statusEl.style.color = '#f44336';
                }
                setTimeout(() => { statusEl.textContent = ''; }, 5000);
            })
            .catch(err => {
                statusEl.textContent = '❌ Stop command failed';
                statusEl.style.color = '#f44336';
                console.error('Command error:', err);
            });
        }
        
        // Close modals when clicking outside
        window.onclick = function(event) {
            if (event.target.classList.contains('modal')) {
                event.target.style.display = 'none';
            }
        }
        
        // Export map to /sdcard/Download
        function toggleFullscreen() {
            if (!document.fullscreenElement) {
                document.documentElement.requestFullscreen().catch(err => {
                    console.error('Fullscreen error:', err);
                });
            } else {
                document.exitFullscreen();
            }
        }
        
        // Export map to /sdcard/Download
        function exportMap() {
            const statusEl = document.getElementById('export-status');
            statusEl.textContent = 'Exporting...';
            statusEl.style.color = '#0078d4';
            
            fetch('/api/export_map', {
                method: 'POST'
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    statusEl.textContent = '✅ ' + data.filename;
                    statusEl.style.color = '#4caf50';
                    setTimeout(() => {
                        statusEl.textContent = '';
                    }, 5000);
                } else {
                    statusEl.textContent = '❌ ' + data.error;
                    statusEl.style.color = '#f44336';
                }
            })
            .catch(err => {
                statusEl.textContent = '❌ Export failed';
                statusEl.style.color = '#f44336';
                console.error('Export error:', err);
            });
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

@app.route('/api/export_map', methods=['POST'])
def export_map():
    """Export current map HTML to /sdcard/Download with timestamp"""
    try:
        if not is_termux():
            return jsonify({'success': False, 'error': 'Export only works on Termux/Android'})
        
        download_dir = '/sdcard/Download'
        
        if not os.path.exists(download_dir):
            return jsonify({'success': False, 'error': '/sdcard/Download not found'})
        
        # Generate timestamp filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'rangetest_{timestamp}.html'
        dest_path = os.path.join(download_dir, filename)
        
        # Check if source HTML exists
        if not os.path.exists(HTML_FILE):
            return jsonify({'success': False, 'error': 'No range test data to export'})
        
        # Copy HTML file to Download folder
        import shutil
        shutil.copy(HTML_FILE, dest_path)
        
        return jsonify({'success': True, 'filename': filename, 'path': dest_path})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/send_lxmf_command', methods=['POST'])
def send_lxmf_command():
    """Send command to LXMF-CLI via command file"""
    try:
        data = request.get_json()
        contact_index = data.get('contact_index')
        command = data.get('command')
        
        if not contact_index or not command:
            return jsonify({'success': False, 'error': 'Missing required fields'})
        
        # Build message based on command
        if command == 'rt':
            # Start range test: s # rt N D
            ping_count = data.get('ping_count', 10)
            ping_delay = data.get('ping_delay', 5)
            message = f"s {contact_index} rt {ping_count} {ping_delay}"
        elif command == 'rs':
            # Stop range test: s # rs
            message = f"s {contact_index} rs"
        else:
            return jsonify({'success': False, 'error': 'Unknown command'})
        
        # Write command to file as a ONE-TIME TRIGGER
        command_file = os.path.join(STORAGE_DIR, 'rtcom_command.txt')
        
        # Write command
        with open(command_file, 'w') as f:
            f.write(message + '\n')
        
        # Flush to ensure file is written
        import time
        time.sleep(0.1)
        
        # Note: The bridge plugin will clear the file after reading it
        # This ensures the command is only executed once
        
        return jsonify({
            'success': True, 
            'message': message,
            'note': 'Command sent to LXMF-CLI via rtcom_bridge plugin'
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

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
    print(f"   /                   Live navigator with current position")
    print(f"   /map                Original static map")
    print(f"   /api/current_gps    Current GPS JSON")
    print(f"   /api/logged_points  Logged points JSON")
    print(f"   /api/export_map     Export map to /sdcard/Download (POST)")
    
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
