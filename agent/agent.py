#!/usr/bin/env python3
"""
Home LLM Dashboard - Device Agent
Lightweight monitoring agent that runs on each device to collect and send metrics.
"""

import psutil
import requests
import time
import json
import logging
import os
import platform
import socket
import subprocess
import shutil
from typing import Dict, Optional
from datetime import datetime
import configparser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SystemMonitor:
    """Collects system metrics from the device."""
    
    def __init__(self):
        self.system = platform.system()
        self.last_network_stats = None
        self.last_network_time = None
        self.use_macmon = False
        
        # Check if macmon is available on macOS
        if self.system == "Darwin":
            self.use_macmon = shutil.which("macmon") is not None
            if self.use_macmon:
                logger.info("macmon detected, will use for enhanced macOS metrics")
            else:
                logger.info("macmon not found, falling back to psutil (consider installing: brew install macmon)")
        
    def get_cpu_usage(self) -> float:
        """Get CPU usage percentage."""
        return psutil.cpu_percent(interval=1)
    
    def get_memory_info(self) -> Dict[str, float]:
        """Get memory information."""
        memory = psutil.virtual_memory()
        return {
            'ram_usage': memory.used / (1024**3),  # GB
            'ram_total': memory.total / (1024**3)  # GB
        }
    
    def get_gpu_info(self) -> Dict[str, Optional[float]]:
        """Get GPU information if available."""
        gpu_info = {
            'gpu_usage': None,
            'vram_usage': None,
            'vram_total': None
        }
        
        try:
            # Try to get NVIDIA GPU info
            import pynvml
            pynvml.nvmlInit()
            
            # Get first GPU (most common case)
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            
            # Get GPU utilization
            utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
            gpu_info['gpu_usage'] = float(utilization.gpu)
            
            # Get memory info
            memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            gpu_info['vram_usage'] = memory_info.used / (1024**3)  # GB
            gpu_info['vram_total'] = memory_info.total / (1024**3)  # GB
            
        except ImportError:
            # pynvml not installed
            pass
        except Exception as e:
            logger.debug(f"Could not get GPU info: {e}")
        
        # Try alternative methods for other GPUs (AMD, Intel, etc.)
        if gpu_info['gpu_usage'] is None:
            try:
                # This is a placeholder for other GPU monitoring methods
                # You might need platform-specific implementations here
                pass
            except Exception as e:
                logger.debug(f"Alternative GPU monitoring failed: {e}")
        
        return gpu_info
    
    def get_macmon_metrics(self) -> Dict:
        """Get comprehensive metrics using macmon on macOS."""
        try:
            # Run macmon pipe command to get single JSON output
            result = subprocess.run(
                ["macmon", "pipe", "-s", "1"],  # Single sample
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                logger.debug(f"macmon failed with exit code {result.returncode}: {result.stderr}")
                return {}
            
            # Parse JSON output
            macmon_data = json.loads(result.stdout.strip())
            
            # Convert macmon format to our standard format
            metrics = {}
            
            # CPU Usage - macmon provides ecpu_usage and pcpu_usage as [freq, usage]
            cpu_usage = 0
            if 'ecpu_usage' in macmon_data and macmon_data['ecpu_usage']:
                cpu_usage += macmon_data['ecpu_usage'][1] * 100  # Convert to percentage
            if 'pcpu_usage' in macmon_data and macmon_data['pcpu_usage']:
                cpu_usage += macmon_data['pcpu_usage'][1] * 100  # Convert to percentage
            metrics['cpu_usage'] = min(cpu_usage, 100.0)  # Cap at 100%
            
            # Memory info
            if 'memory' in macmon_data:
                memory = macmon_data['memory']
                metrics['ram_usage'] = memory.get('ram_usage', 0) / (1024**3)  # Convert to GB
                metrics['ram_total'] = memory.get('ram_total', 0) / (1024**3)  # Convert to GB
            
            # GPU Usage - macmon provides gpu_usage as [freq, usage]
            if 'gpu_usage' in macmon_data and macmon_data['gpu_usage']:
                metrics['gpu_usage'] = macmon_data['gpu_usage'][1] * 100  # Convert to percentage
            else:
                metrics['gpu_usage'] = None
            
            # VRAM info (macmon doesn't provide detailed VRAM, use psutil fallback)
            metrics['vram_usage'] = None
            metrics['vram_total'] = None
            
            # Network info (use existing psutil method for network)
            network_info = self.get_network_info()
            metrics.update(network_info)
            
            return metrics
            
        except subprocess.TimeoutExpired:
            logger.debug("macmon command timed out")
            return {}
        except json.JSONDecodeError as e:
            logger.debug(f"Failed to parse macmon JSON output: {e}")
            return {}
        except Exception as e:
            logger.debug(f"Error getting macmon metrics: {e}")
            return {}
    
    def get_network_info(self) -> Dict[str, Optional[float]]:
        """Get network traffic information."""
        try:
            current_stats = psutil.net_io_counters()
            current_time = time.time()
            
            network_info = {
                'network_tx': None,
                'network_rx': None
            }
            
            if self.last_network_stats and self.last_network_time:
                time_diff = current_time - self.last_network_time
                
                if time_diff > 0:
                    # Calculate bytes per second, then convert to Mbps
                    tx_diff = current_stats.bytes_sent - self.last_network_stats.bytes_sent
                    rx_diff = current_stats.bytes_recv - self.last_network_stats.bytes_recv
                    
                    network_info['network_tx'] = (tx_diff / time_diff) * 8 / (1024**2)  # Mbps
                    network_info['network_rx'] = (rx_diff / time_diff) * 8 / (1024**2)  # Mbps
            
            # Store current stats for next calculation
            self.last_network_stats = current_stats
            self.last_network_time = current_time
            
            return network_info
            
        except Exception as e:
            logger.debug(f"Could not get network info: {e}")
            return {'network_tx': None, 'network_rx': None}
    
    def collect_all_metrics(self) -> Dict:
        """Collect all available metrics."""
        metrics = {}
        
        # Use macmon on macOS if available, otherwise fall back to individual methods
        if self.use_macmon:
            try:
                macmon_metrics = self.get_macmon_metrics()
                if macmon_metrics:
                    metrics.update(macmon_metrics)
                    logger.debug("Successfully collected metrics using macmon")
                    return metrics
                else:
                    logger.debug("macmon returned empty metrics, falling back to psutil")
            except Exception as e:
                logger.warning(f"macmon failed, falling back to psutil: {e}")
        
        # Fallback to individual metric collection methods
        # CPU usage
        try:
            metrics['cpu_usage'] = self.get_cpu_usage()
        except Exception as e:
            logger.warning(f"Failed to get CPU usage: {e}")
            metrics['cpu_usage'] = None
        
        # Memory info
        try:
            memory_info = self.get_memory_info()
            metrics.update(memory_info)
        except Exception as e:
            logger.warning(f"Failed to get memory info: {e}")
            metrics['ram_usage'] = None
            metrics['ram_total'] = None
        
        # GPU info
        try:
            gpu_info = self.get_gpu_info()
            metrics.update(gpu_info)
        except Exception as e:
            logger.warning(f"Failed to get GPU info: {e}")
            metrics['gpu_usage'] = None
            metrics['vram_usage'] = None
            metrics['vram_total'] = None
        
        # Network info
        try:
            network_info = self.get_network_info()
            metrics.update(network_info)
        except Exception as e:
            logger.warning(f"Failed to get network info: {e}")
            metrics['network_tx'] = None
            metrics['network_rx'] = None
        
        return metrics

class DashboardAgent:
    """Main agent class that coordinates monitoring and communication."""
    
    def __init__(self, config_file: str = 'agent_config.ini'):
        self.config = self.load_config(config_file)
        self.monitor = SystemMonitor()
        self.device_name = self.get_device_name()
        self.session = requests.Session()
        self.session.timeout = 10
        
        # Backoff configuration
        self.consecutive_failures = 0
        self.current_wait_time = self.config['time_period']
        self.original_wait_time = self.config['time_period']
        self.max_wait_time = 1800  # 30 minutes
        self.backoff_threshold = 5  # Start backoff after 5 failures
        self.backoff_multiplier = 2
        
        logger.info(f"Agent initialized for device: {self.device_name}")
        logger.info(f"Dashboard server: {self.config['server_url']}")
        logger.info(f"Update interval: {self.config['time_period']} seconds")
    
    def load_config(self, config_file: str) -> Dict:
        """Load configuration from file or environment variables."""
        config = {
            'server_ip': '192.168.50.210',  # Default to Debian machine
            'server_port': 3030,
            'time_period': 5
        }
        
        # Try to load from config file
        if os.path.exists(config_file):
            try:
                parser = configparser.ConfigParser()
                parser.read(config_file)
                
                if 'agent' in parser:
                    config.update({
                        'server_ip': parser['agent'].get('server_ip', config['server_ip']),
                        'server_port': parser['agent'].getint('server_port', config['server_port']),
                        'time_period': parser['agent'].getint('time_period', config['time_period'])
                    })
                    
                logger.info(f"Loaded configuration from {config_file}")
            except Exception as e:
                logger.warning(f"Failed to load config file: {e}, using defaults")
        
        # Override with environment variables if present
        config['server_ip'] = os.getenv('SERVER_IP_ADDRESS', config['server_ip'])
        config['server_port'] = int(os.getenv('SERVER_PORT', config['server_port']))
        config['time_period'] = int(os.getenv('TIME_PERIOD', config['time_period']))
        
        # Build server URL
        config['server_url'] = f"http://{config['server_ip']}:{config['server_port']}"
        
        return config
    
    def get_device_name(self) -> str:
        """Generate a unique device name."""
        hostname = socket.gethostname()
        system = platform.system()
        
        # Add system type to hostname for clarity
        if system == "Darwin":
            system_name = "macOS"
        elif system == "Windows":
            system_name = "Windows"
        elif system == "Linux":
            system_name = "Linux"
        else:
            system_name = system
        
        return f"{hostname}-{system_name}"
    
    def calculate_backoff_wait_time(self):
        """Calculate wait time based on consecutive failures with exponential backoff."""
        if self.consecutive_failures < self.backoff_threshold:
            return self.original_wait_time
        
        # Calculate exponential backoff starting after threshold
        backoff_exponent = self.consecutive_failures - self.backoff_threshold + 1
        calculated_wait = self.original_wait_time * (self.backoff_multiplier ** backoff_exponent)
        
        # Cap at maximum wait time (30 minutes)
        return min(calculated_wait, self.max_wait_time)
    
    def update_wait_time(self, success: bool):
        """Update wait time based on success or failure."""
        if success:
            # Reset on success
            self.consecutive_failures = 0
            self.current_wait_time = self.original_wait_time
            logger.debug("Connection successful, reset to original wait time")
        else:
            # Increment failures and calculate new wait time
            self.consecutive_failures += 1
            old_wait_time = self.current_wait_time
            self.current_wait_time = self.calculate_backoff_wait_time()
            
            if self.current_wait_time != old_wait_time:
                logger.warning(f"Connection failed {self.consecutive_failures} times, "
                             f"increasing wait time from {old_wait_time}s to {self.current_wait_time}s")
    
    def send_metrics(self, metrics: Dict) -> bool:
        """Send metrics to the dashboard server."""
        try:
            payload = {
                'device_name': self.device_name,
                'metrics': metrics
            }
            
            response = self.session.post(
                f"{self.config['server_url']}/api/metrics",
                json=payload,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                logger.debug("Metrics sent successfully")
                return True
            else:
                logger.warning(f"Failed to send metrics: HTTP {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"Network error sending metrics: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending metrics: {e}")
            return False
    
    def test_connection(self) -> bool:
        """Test connection to the dashboard server."""
        try:
            response = self.session.get(f"{self.config['server_url']}/api/metrics/latest")
            return response.status_code in [200, 401]  # 401 is ok (auth required)
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    def run(self):
        """Main monitoring loop with exponential backoff."""
        logger.info("Starting monitoring loop...")
        
        # Test initial connection (but don't exit if it fails)
        if not self.test_connection():
            logger.warning("Initial connection test failed, will retry with backoff")
            self.update_wait_time(False)
        
        while True:
            try:
                # Collect metrics
                metrics = self.monitor.collect_all_metrics()
                
                # Log current metrics (handle None values)
                def format_metric(value, decimal_places=1):
                    return f"{value:.{decimal_places}f}" if value is not None else "N/A"
                
                logger.info(f"Metrics: CPU={format_metric(metrics.get('cpu_usage'))}% "
                          f"RAM={format_metric(metrics.get('ram_usage'))}GB "
                          f"GPU={format_metric(metrics.get('gpu_usage'))}% "
                          f"Net TX={format_metric(metrics.get('network_tx'))}Mbps")
                
                # Send metrics and update wait time based on success
                success = self.send_metrics(metrics)
                self.update_wait_time(success)
                
                # Log wait time if using backoff
                if self.current_wait_time != self.original_wait_time:
                    logger.info(f"Using backoff wait time: {self.current_wait_time}s "
                              f"(failures: {self.consecutive_failures})")
                
                # Wait for next iteration using current wait time
                time.sleep(self.current_wait_time)
                
            except KeyboardInterrupt:
                logger.info("Agent stopped by user")
                break
            except Exception as e:
                logger.error(f"Unexpected error in main loop: {e}")
                # Treat unexpected errors as connection failures for backoff
                self.update_wait_time(False)
                time.sleep(self.current_wait_time)

def create_sample_config():
    """Create a sample configuration file."""
    config_content = """[agent]
# Dashboard server configuration
server_ip = 192.168.50.210
server_port = 3030

# Update interval in seconds
time_period = 5

# Example usage:
# You can also set these via environment variables:
# export SERVER_IP_ADDRESS=192.168.50.210
# export SERVER_PORT=3030
# export TIME_PERIOD=5
"""
    
    with open('agent_config.ini', 'w') as f:
        f.write(config_content)
    
    print("Sample configuration file 'agent_config.ini' created.")
    print("Please edit it with your dashboard server details.")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Home LLM Dashboard Agent')
    parser.add_argument('--create-config', action='store_true', 
                       help='Create a sample configuration file')
    parser.add_argument('--config', default='agent_config.ini',
                       help='Configuration file path')
    parser.add_argument('--test-connection', action='store_true',
                       help='Test connection to dashboard server')
    
    args = parser.parse_args()
    
    if args.create_config:
        create_sample_config()
    elif args.test_connection:
        agent = DashboardAgent(args.config)
        if agent.test_connection():
            print("✅ Connection to dashboard server successful!")
        else:
            print("❌ Cannot connect to dashboard server.")
    else:
        # Normal operation
        try:
            agent = DashboardAgent(args.config)
            agent.run()
        except KeyboardInterrupt:
            print("\nAgent stopped by user")
        except Exception as e:
            logger.error(f"Agent failed to start: {e}")
            print(f"Error: {e}")