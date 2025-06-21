#!/usr/bin/env python3
"""
Home LLM Dashboard - Main Application
A lightweight web application for monitoring distributed AI infrastructure
and controlling llama-server instances across multiple machines.
"""

import sqlite3
import json
import subprocess
import threading
import time
import hashlib
import shutil
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO, emit
import logging
import os
from typing import Dict, List, Optional
import asyncio
import configparser
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DashboardConfig:
    """Centralized configuration management for the dashboard."""
    
    def __init__(self, config_file: str = 'dashboard_config.ini'):
        self.config_file = config_file
        self.load_config()
    
    def load_config(self):
        """Load configuration from file and environment variables."""
        # Default configuration
        self.defaults = {
            'SECRET_KEY': 'change-this-secret-key-in-production',
            'ADMIN_PASSWORD': 'admin123',
            'DATABASE_PATH': 'dashboard.db',
            'DATA_RETENTION_DAYS': 7,
            'CLEANUP_INTERVAL_SECONDS': 3600,
            'HOST': '0.0.0.0',
            'PORT': 3030,
            'DEVICE_OFFLINE_THRESHOLD': 60,  # seconds
            'DEBUG': False
        }
        
        # Load from config file if it exists
        if os.path.exists(self.config_file):
            try:
                parser = configparser.ConfigParser()
                parser.read(self.config_file)
                
                if 'dashboard' in parser:
                    for key in self.defaults:
                        if key in parser['dashboard']:
                            value = parser['dashboard'][key]
                            # Convert to appropriate type
                            if key in ['DATA_RETENTION_DAYS', 'CLEANUP_INTERVAL_SECONDS', 'PORT', 'DEVICE_OFFLINE_THRESHOLD']:
                                self.defaults[key] = int(value)
                            elif key in ['DEBUG']:
                                self.defaults[key] = value.lower() in ('true', '1', 'yes')
                            else:
                                self.defaults[key] = value
                
                logger.info(f"Loaded configuration from {self.config_file}")
            except Exception as e:
                logger.warning(f"Failed to load config file: {e}, using defaults")
        
        # Override with environment variables
        env_mappings = {
            'DASHBOARD_SECRET_KEY': 'SECRET_KEY',
            'DASHBOARD_ADMIN_PASSWORD': 'ADMIN_PASSWORD',
            'DASHBOARD_DATABASE_PATH': 'DATABASE_PATH',
            'DASHBOARD_DATA_RETENTION_DAYS': 'DATA_RETENTION_DAYS',
            'DASHBOARD_CLEANUP_INTERVAL': 'CLEANUP_INTERVAL_SECONDS',
            'DASHBOARD_HOST': 'HOST',
            'DASHBOARD_PORT': 'PORT',
            'DASHBOARD_DEVICE_OFFLINE_THRESHOLD': 'DEVICE_OFFLINE_THRESHOLD',
            'DASHBOARD_DEBUG': 'DEBUG'
        }
        
        for env_var, config_key in env_mappings.items():
            env_value = os.getenv(env_var)
            if env_value is not None:
                # Convert to appropriate type
                if config_key in ['DATA_RETENTION_DAYS', 'CLEANUP_INTERVAL_SECONDS', 'PORT', 'DEVICE_OFFLINE_THRESHOLD']:
                    self.defaults[config_key] = int(env_value)
                elif config_key in ['DEBUG']:
                    self.defaults[config_key] = env_value.lower() in ('true', '1', 'yes')
                else:
                    self.defaults[config_key] = env_value
    
    def get(self, key: str):
        """Get configuration value."""
        return self.defaults.get(key)
    
    def create_sample_config(self):
        """Create a sample configuration file."""
        config_content = """[dashboard]
# Dashboard Server Configuration

# Security settings (CHANGE THESE IN PRODUCTION!)
SECRET_KEY = change-this-secret-key-in-production
ADMIN_PASSWORD = admin123

# Database settings
DATABASE_PATH = dashboard.db
DATA_RETENTION_DAYS = 7
CLEANUP_INTERVAL_SECONDS = 3600

# Server settings
HOST = 0.0.0.0
PORT = 3000

# Device monitoring settings
DEVICE_OFFLINE_THRESHOLD = 60

# Debug mode
DEBUG = false

# Note: You can also set these via environment variables:
# export DASHBOARD_SECRET_KEY="your-secret-key"
# export DASHBOARD_ADMIN_PASSWORD="your-password"
# export DASHBOARD_PORT=3000
# etc.
"""
        
        with open(self.config_file, 'w') as f:
            f.write(config_content)
        
        logger.info(f"Sample configuration file created: {self.config_file}")
        logger.warning("Please edit the configuration file with your settings!")

# Initialize configuration
config = DashboardConfig()

app = Flask(__name__)
app.config['SECRET_KEY'] = config.get('SECRET_KEY')
socketio = SocketIO(app, cors_allowed_origins="*")

# Configuration values
DATABASE_PATH = config.get('DATABASE_PATH')
ADMIN_PASSWORD = config.get('ADMIN_PASSWORD')
DATA_RETENTION_DAYS = config.get('DATA_RETENTION_DAYS')
CLEANUP_INTERVAL_SECONDS = config.get('CLEANUP_INTERVAL_SECONDS')
DEVICE_OFFLINE_THRESHOLD = config.get('DEVICE_OFFLINE_THRESHOLD')  # 60 seconds

# Global variables for script execution status
script_status = {
    'running': False,
    'current_script': None,
    'logs': []
}

class DatabaseManager:
    """Handles all database operations for the dashboard."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the database with required tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create metrics table with TTL support
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS device_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_name TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                cpu_usage REAL,
                ram_usage REAL,
                ram_total REAL,
                gpu_usage REAL,
                vram_usage REAL,
                vram_total REAL,
                network_tx REAL,
                network_rx REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create index for faster queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_device_timestamp 
            ON device_metrics(device_name, timestamp)
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")
    
    def insert_metrics(self, device_name: str, metrics: Dict):
        """Insert device metrics into the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO device_metrics 
            (device_name, timestamp, cpu_usage, ram_usage, ram_total, 
             gpu_usage, vram_usage, vram_total, network_tx, network_rx)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            device_name,
            datetime.now(timezone.utc),
            metrics.get('cpu_usage'),
            metrics.get('ram_usage'),
            metrics.get('ram_total'),
            metrics.get('gpu_usage'),
            metrics.get('vram_usage'),
            metrics.get('vram_total'),
            metrics.get('network_tx'),
            metrics.get('network_rx')
        ))
        
        conn.commit()
        conn.close()
    
    def get_metrics(self, device_name: str = None, hours: int = 24) -> List[Dict]:
        """Retrieve metrics from the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        since_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        if device_name:
            cursor.execute('''
                SELECT * FROM device_metrics 
                WHERE device_name = ? AND timestamp >= ?
                ORDER BY timestamp DESC
            ''', (device_name, since_time))
        else:
            cursor.execute('''
                SELECT * FROM device_metrics 
                WHERE timestamp >= ?
                ORDER BY device_name, timestamp DESC
            ''', (since_time,))
        
        columns = [description[0] for description in cursor.description]
        results = []
        
        for row in cursor.fetchall():
            row_dict = dict(zip(columns, row))
            # Convert timestamp to ISO format for JavaScript compatibility
            try:
                if isinstance(row_dict['timestamp'], str):
                    # Handle different timestamp formats
                    if 'T' in row_dict['timestamp']:
                        # ISO format
                        timestamp_obj = datetime.fromisoformat(row_dict['timestamp'].replace('Z', '+00:00'))
                    else:
                        # SQLite datetime format - handle timezone info
                        if '+' in row_dict['timestamp'] or 'Z' in row_dict['timestamp']:
                            # Handle timezone-aware timestamps
                            timestamp_obj = datetime.fromisoformat(row_dict['timestamp'].replace('Z', '+00:00'))
                        else:
                            # Handle naive timestamps
                            timestamp_obj = datetime.strptime(row_dict['timestamp'], '%Y-%m-%d %H:%M:%S.%f')
                else:
                    timestamp_obj = row_dict['timestamp']
                row_dict['timestamp'] = timestamp_obj.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
            except (ValueError, AttributeError) as e:
                logger.warning(f"Invalid timestamp in metrics: {row_dict['timestamp']}, error: {e}")
                row_dict['timestamp'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
            
            results.append(row_dict)
        
        conn.close()
        return results
    
    def get_latest_metrics(self) -> Dict[str, Dict]:
        """Get the latest metrics for each device."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get the latest record for each device using a subquery approach
        cursor.execute('''
            SELECT dm1.device_name, 
                   dm1.timestamp,
                   dm1.cpu_usage, dm1.ram_usage, dm1.ram_total,
                   dm1.gpu_usage, dm1.vram_usage, dm1.vram_total,
                   dm1.network_tx, dm1.network_rx
            FROM device_metrics dm1
            INNER JOIN (
                SELECT device_name, MAX(timestamp) as max_timestamp
                FROM device_metrics 
                GROUP BY device_name
            ) dm2 ON dm1.device_name = dm2.device_name 
                 AND dm1.timestamp = dm2.max_timestamp
            ORDER BY dm1.timestamp DESC
        ''')
        
        results = {}
        for row in cursor.fetchall():
            device_name = row[0]
            # Convert timestamp to ISO format for JavaScript compatibility
            timestamp_str = row[1]
            try:
                # Parse the timestamp and convert to ISO format
                if isinstance(timestamp_str, str):
                    # Handle different timestamp formats
                    if 'T' in timestamp_str:
                        # ISO format
                        timestamp_obj = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    else:
                        # SQLite datetime format - handle timezone info
                        if '+' in timestamp_str or 'Z' in timestamp_str:
                            # Handle timezone-aware timestamps
                            timestamp_obj = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        else:
                            # Handle naive timestamps
                            timestamp_obj = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S.%f')
                else:
                    # Assume it's already a datetime object
                    timestamp_obj = timestamp_str
                
                iso_timestamp = timestamp_obj.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
            except (ValueError, AttributeError, TypeError) as e:
                logger.warning(f"Invalid timestamp for device {device_name}: {timestamp_str}, error: {e}")
                iso_timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
            
            results[device_name] = {
                'timestamp': iso_timestamp,
                'cpu_usage': row[2],
                'ram_usage': row[3],
                'ram_total': row[4],
                'gpu_usage': row[5],
                'vram_usage': row[6],
                'vram_total': row[7],
                'network_tx': row[8],
                'network_rx': row[9]
            }
        
        conn.close()
        return results
    
    def cleanup_old_data(self):
        """Remove data older than the retention period."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=DATA_RETENTION_DAYS)
        cursor.execute('''
            DELETE FROM device_metrics WHERE timestamp < ?
        ''', (cutoff_time,))
        
        deleted_rows = cursor.rowcount
        conn.commit()
        conn.close()
        
        if deleted_rows > 0:
            logger.info(f"Cleaned up {deleted_rows} old metric records")

# Initialize database manager
db_manager = DatabaseManager(DATABASE_PATH)

class ScriptManager:
    """Handles execution of predefined scripts via SSH."""
    
    def __init__(self, scripts_config_file: str = 'scripts_config.json'):
        # SSH password configuration - set via environment variable for security
        self.ssh_password = os.getenv('SSH_PASSWORD', '')
        self.scripts_config_file = scripts_config_file
        
        # Check if sshpass is available
        self.has_sshpass = shutil.which('sshpass') is not None
        if not self.has_sshpass and self.ssh_password:
            logger.warning("sshpass not found but SSH password is set. Install sshpass: apt-get install sshpass")
        elif not self.has_sshpass and not self.ssh_password:
            logger.info("SSH password authentication: Set SSH_PASSWORD environment variable and install sshpass for password-based SSH")
        elif self.has_sshpass and self.ssh_password:
            logger.info("SSH password authentication enabled")
        
        # Load scripts from external JSON file
        self.scripts = self.load_scripts_config()
    
    def load_scripts_config(self) -> Dict:
        """Load scripts configuration from JSON file."""
        try:
            if os.path.exists(self.scripts_config_file):
                with open(self.scripts_config_file, 'r') as f:
                    scripts = json.load(f)
                logger.info(f"Loaded {len(scripts)} scripts from {self.scripts_config_file}")
                return scripts
            else:
                logger.warning(f"Scripts config file {self.scripts_config_file} not found, using empty scripts")
                return {}
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {self.scripts_config_file}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Error loading scripts config: {e}")
            return {}
    
    def reload_scripts_config(self) -> bool:
        """Reload scripts configuration from file."""
        try:
            new_scripts = self.load_scripts_config()
            self.scripts = new_scripts
            logger.info("Scripts configuration reloaded successfully")
            return True
        except Exception as e:
            logger.error(f"Error reloading scripts config: {e}")
            return False
    
    def wrap_ssh_command(self, command: str) -> str:
        """Wrap SSH commands with sshpass if password is available."""
        if not command.strip().startswith('ssh '):
            return command
        
        # Parse the SSH command to insert options correctly
        parts = command.split(' ', 2)  # ['ssh', 'user@host', '"command"']
        if len(parts) < 3:
            return command
        
        ssh_cmd = parts[0]  # 'ssh'
        user_host = parts[1]  # 'user@host'
        remote_cmd = parts[2]  # '"command"'
        
        if self.has_sshpass and self.ssh_password:
            # Add sshpass with password and SSH options
            return f'sshpass -p "{self.ssh_password}" {ssh_cmd} -o StrictHostKeyChecking=no {user_host} {remote_cmd}'
        else:
            # Just add SSH options for passwordless SSH
            return f'{ssh_cmd} -o StrictHostKeyChecking=no {user_host} {remote_cmd}'
    
    def execute_script(self, script_id: str) -> bool:
        """Execute a predefined script."""
        global script_status
        
        if script_id not in self.scripts:
            logger.error(f"Script {script_id} not found")
            return False
        
        if script_status['running']:
            logger.warning("Another script is already running")
            return False
        
        script = self.scripts[script_id]
        script_status['running'] = True
        script_status['current_script'] = script['name']
        script_status['logs'] = []
        
        def run_script():
            try:
                for command in script['commands']:
                    # Wrap SSH commands with password support
                    wrapped_command = self.wrap_ssh_command(command)
                    
                    logger.info(f"Executing: {command}")
                    script_status['logs'].append(f"Executing: {command}")
                    socketio.emit('script_log', {'message': f"Executing: {command}"})
                    
                    # Execute the wrapped command
                    result = subprocess.run(
                        wrapped_command, 
                        shell=True, 
                        capture_output=True, 
                        text=True,
                        timeout=60  # 60 second timeout
                    )
                    
                    if result.returncode == 0:
                        log_msg = f"✓ Command completed successfully"
                        if result.stdout:
                            log_msg += f"\nOutput: {result.stdout.strip()}"
                    else:
                        log_msg = f"✗ Command failed (exit code: {result.returncode})"
                        if result.stderr:
                            log_msg += f"\nError: {result.stderr.strip()}"
                    
                    logger.info(log_msg)
                    script_status['logs'].append(log_msg)
                    socketio.emit('script_log', {'message': log_msg})
                
                script_status['logs'].append("Script execution completed")
                socketio.emit('script_log', {'message': "Script execution completed"})
                socketio.emit('script_finished', {'success': True})
                
            except subprocess.TimeoutExpired:
                error_msg = "Script execution timed out"
                logger.error(error_msg)
                script_status['logs'].append(error_msg)
                socketio.emit('script_log', {'message': error_msg})
                socketio.emit('script_finished', {'success': False})
                
            except Exception as e:
                error_msg = f"Script execution failed: {str(e)}"
                logger.error(error_msg)
                script_status['logs'].append(error_msg)
                socketio.emit('script_log', {'message': error_msg})
                socketio.emit('script_finished', {'success': False})
                
            finally:
                script_status['running'] = False
                script_status['current_script'] = None
        
        # Run script in background thread
        thread = threading.Thread(target=run_script)
        thread.daemon = True
        thread.start()
        
        return True
    
    def get_scripts(self) -> Dict:
        """Get list of available scripts."""
        return {
            script_id: {
                'name': script['name'],
                'description': script['description']
            }
            for script_id, script in self.scripts.items()
        }

script_manager = ScriptManager()

def cleanup_old_data_periodic():
    """Periodic cleanup task for old data."""
    while True:
        try:
            db_manager.cleanup_old_data()
            time.sleep(CLEANUP_INTERVAL_SECONDS)
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            time.sleep(CLEANUP_INTERVAL_SECONDS)

# Start cleanup thread
cleanup_thread = threading.Thread(target=cleanup_old_data_periodic)
cleanup_thread.daemon = True
cleanup_thread.start()

# Authentication helper
def check_auth():
    """Check if user is authenticated."""
    return session.get('authenticated', False)

# Routes
@app.route('/')
def index():
    """Main dashboard page."""
    if not check_auth():
        return redirect(url_for('login'))
    return render_template('dashboard.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page."""
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['authenticated'] = True
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Invalid password')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout endpoint."""
    session.pop('authenticated', None)
    return redirect(url_for('login'))

@app.route('/api/metrics', methods=['POST'])
def receive_metrics():
    """Receive metrics from agents."""
    try:
        data = request.get_json()
        device_name = data.get('device_name')
        metrics = data.get('metrics', {})
        
        if not device_name:
            return jsonify({'error': 'Device name is required'}), 400
        
        # Store metrics in database
        db_manager.insert_metrics(device_name, metrics)
        
        # Create ISO timestamp for real-time update
        current_time = datetime.now(timezone.utc)
        iso_timestamp = current_time.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        
        # Emit real-time update to connected clients
        socketio.emit('metrics_update', {
            'device_name': device_name,
            'metrics': metrics,
            'timestamp': iso_timestamp
        })
        
        logger.debug(f"Received metrics from {device_name}, timestamp: {iso_timestamp}")
        
        return jsonify({'status': 'success'}), 200
        
    except Exception as e:
        logger.error(f"Error receiving metrics: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/metrics/<device_name>')
def get_device_metrics(device_name):
    """Get metrics for a specific device."""
    if not check_auth():
        return jsonify({'error': 'Authentication required'}), 401
    
    hours = request.args.get('hours', 24, type=int)
    metrics = db_manager.get_metrics(device_name, hours)
    return jsonify(metrics)

@app.route('/api/metrics/latest')
def get_latest_metrics():
    """Get latest metrics for all devices."""
    if not check_auth():
        return jsonify({'error': 'Authentication required'}), 401
    
    metrics = db_manager.get_latest_metrics()
    return jsonify(metrics)

@app.route('/api/scripts')
def get_scripts():
    """Get available scripts."""
    if not check_auth():
        return jsonify({'error': 'Authentication required'}), 401
    
    return jsonify(script_manager.get_scripts())

@app.route('/api/scripts/<script_id>/execute', methods=['POST'])
def execute_script(script_id):
    """Execute a script."""
    if not check_auth():
        return jsonify({'error': 'Authentication required'}), 401
    
    success = script_manager.execute_script(script_id)
    if success:
        return jsonify({'status': 'started'}), 200
    else:
        return jsonify({'error': 'Script execution failed or another script is running'}), 400

@app.route('/api/scripts/status')
def get_script_status():
    """Get current script execution status."""
    if not check_auth():
        return jsonify({'error': 'Authentication required'}), 401
    
    return jsonify(script_status)

@app.route('/api/scripts/reload', methods=['POST'])
def reload_scripts():
    """Reload scripts configuration from file."""
    if not check_auth():
        return jsonify({'error': 'Authentication required'}), 401
    
    success = script_manager.reload_scripts_config()
    if success:
        return jsonify({'status': 'success', 'message': 'Scripts configuration reloaded'}), 200
    else:
        return jsonify({'error': 'Failed to reload scripts configuration'}), 500

# WebSocket events
@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    if check_auth():
        logger.info("Client connected to WebSocket")
        emit('connected', {'status': 'Connected to dashboard'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    logger.info("Client disconnected from WebSocket")

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Home LLM Dashboard Server')
    parser.add_argument('--create-config', action='store_true',
                       help='Create a sample configuration file')
    parser.add_argument('--config', default='dashboard_config.ini',
                       help='Configuration file path')
    
    args = parser.parse_args()
    
    if args.create_config:
        config.create_sample_config()
        print("Sample configuration file created!")
        print("Please edit dashboard_config.ini with your settings before starting the dashboard.")
        exit(0)
    
    # Warn about default credentials
    if config.get('ADMIN_PASSWORD') == 'admin123':
        logger.warning("⚠️  Using default password 'admin123' - CHANGE THIS IN PRODUCTION!")
    if config.get('SECRET_KEY') == 'change-this-secret-key-in-production':
        logger.warning("⚠️  Using default secret key - CHANGE THIS IN PRODUCTION!")
    
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    
    logger.info(f"Starting Home LLM Dashboard on {config.get('HOST')}:{config.get('PORT')}")
    logger.info(f"Device offline threshold: {DEVICE_OFFLINE_THRESHOLD} seconds")
    
    socketio.run(
        app, 
        host=config.get('HOST'), 
        port=config.get('PORT'), 
        debug=config.get('DEBUG')
    )