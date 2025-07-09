#!/usr/bin/env python3

import subprocess
import time
import signal
import sys
import logging
import os
from datetime import datetime
from pathlib import Path

class FanController:
    def __init__(self):
        # Configuration
        self.INTERVAL = 5  # Check every 5 seconds
        
        # GPU temperature thresholds in celsius
        self.GPU_TEMP_LOW = 50
        self.GPU_TEMP_MEDIUM = 60
        self.GPU_TEMP_HIGH = 70
        self.GPU_TEMP_CRITICAL = 80
        
        # CPU temperature thresholds in celsius
        self.CPU_TEMP_LOW = 35
        self.CPU_TEMP_MEDIUM = 45
        self.CPU_TEMP_HIGH = 60
        self.CPU_TEMP_CRITICAL = 75
        
        # Utilization thresholds in percent
        self.UTIL_LOW = 30
        self.UTIL_HIGH = 70
        
        # Fan speeds in hex
        self.FAN_DEFAULT = 0x20    # 50%
        self.FAN_MEDIUM = 0x32     # 78%
        self.FAN_HIGH = 0x48       # 113%
        self.FAN_MAX = 0x64        # 156%
        
        # Setup logging
        self.setup_logging()
        
        # Current fan speed tracking
        self.current_speed = self.FAN_DEFAULT
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.cleanup)
        signal.signal(signal.SIGTERM, self.cleanup)
    
    def setup_logging(self):
        """Setup logging configuration"""
        log_file = "/var/log/gpu-cpu-fan-control.log"
        
        # Create log directory if it doesn't exist
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def check_commands(self):
        """Ensure required commands are available"""
        required_commands = ['ipmitool', 'nvidia-smi']
        
        for cmd in required_commands:
            try:
                subprocess.run(['which', cmd], check=True, capture_output=True)
            except subprocess.CalledProcessError:
                self.logger.error(f"Error: {cmd} is required but not installed.")
                if cmd == 'ipmitool':
                    self.logger.error("Install with: sudo apt-get install ipmitool")
                elif cmd == 'nvidia-smi':
                    self.logger.error("Install NVIDIA drivers")
                sys.exit(1)
    
    def run_command(self, command, capture_output=True):
        """Run a shell command and return the result"""
        try:
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=capture_output, 
                text=True, 
                check=True
            )
            return result.stdout.strip() if capture_output else None
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Command failed: {command}")
            self.logger.error(f"Error: {e}")
            return None
    
    def set_fan_speed(self, speed_hex, reason):
        """Set fan speed using IPMI commands"""
        try:
            # Enable manual fan control
            self.run_command("ipmitool raw 0x30 0x30 0x01 0x00", capture_output=False)
            
            # Set fan speed
            self.run_command(f"ipmitool raw 0x30 0x30 0x02 0xff {speed_hex:#04x}", capture_output=False)
            
            percentage = (speed_hex / 0x64) * 100
            self.logger.info(f"Fan speed set to {percentage:.0f}% ({reason})")
            self.current_speed = speed_hex
            
        except Exception as e:
            self.logger.error(f"Failed to set fan speed: {e}")
    
    def restore_auto_fan(self):
        """Return to automatic fan control"""
        try:
            self.run_command("ipmitool raw 0x30 0x30 0x01 0x01", capture_output=False)
            self.logger.info("Restored automatic fan control")
        except Exception as e:
            self.logger.error(f"Failed to restore automatic fan control: {e}")
    
    def cleanup(self, signum=None, frame=None):
        """Graceful shutdown handler"""
        self.logger.info("Caught signal, restoring automatic fan control...")
        self.restore_auto_fan()
        sys.exit(0)
    
    def get_cpu_temp(self):
        """Get maximum CPU temperature"""
        max_temp = 0
        
        # Method 1: Read from thermal zones (most reliable)
        thermal_zones = Path("/sys/class/thermal").glob("thermal_zone*/temp")
        
        for zone in thermal_zones:
            try:
                with open(zone, 'r') as f:
                    temp_millidegrees = int(f.read().strip())
                    temp_celsius = temp_millidegrees // 1000
                    if temp_celsius > max_temp:
                        max_temp = temp_celsius
            except (FileNotFoundError, ValueError, PermissionError):
                continue
        
        # Method 2: Fallback to sensors command if thermal zones failed
        if max_temp == 0:
            try:
                sensors_output = self.run_command("sensors")
                if sensors_output:
                    # Look for Package temperatures
                    lines = sensors_output.split('\n')
                    for line in lines:
                        if "Package id" in line and "°C" in line:
                            # Extract temperature value
                            temp_str = line.split('+')[1].split('°C')[0]
                            temp = int(float(temp_str))
                            if temp > max_temp:
                                max_temp = temp
            except Exception as e:
                self.logger.warning(f"Failed to get CPU temperature from sensors: {e}")
        
        return max_temp
    
    def get_gpu_data(self):
        """Get GPU temperature and utilization data"""
        try:
            output = self.run_command(
                "nvidia-smi --query-gpu=temperature.gpu,utilization.gpu --format=csv,noheader,nounits"
            )
            
            if not output:
                return 0, 0
            
            max_temp = 0
            max_util = 0
            
            for line in output.split('\n'):
                if line.strip():
                    parts = line.split(',')
                    if len(parts) >= 2:
                        temp = int(parts[0].strip())
                        util = int(parts[1].strip())
                        
                        if temp > max_temp:
                            max_temp = temp
                        if util > max_util:
                            max_util = util
            
            return max_temp, max_util
            
        except Exception as e:
            self.logger.error(f"Failed to get GPU data: {e}")
            return 0, 0
    
    def determine_fan_speed(self, gpu_temp, cpu_temp, gpu_util):
        """Determine appropriate fan speed based on temperatures and utilization"""
        
        # Critical temperature check
        if gpu_temp >= self.GPU_TEMP_CRITICAL or cpu_temp >= self.CPU_TEMP_CRITICAL:
            return self.FAN_MAX, f"CRITICAL temperature (GPU: {gpu_temp}°C, CPU: {cpu_temp}°C)"
        
        # High temperature check
        elif gpu_temp >= self.GPU_TEMP_HIGH or cpu_temp >= self.CPU_TEMP_HIGH:
            return self.FAN_HIGH, f"HIGH temperature (GPU: {gpu_temp}°C, CPU: {cpu_temp}°C)"
        
        # Medium temperature or high utilization check
        elif (gpu_temp >= self.GPU_TEMP_MEDIUM or 
              cpu_temp >= self.CPU_TEMP_MEDIUM or 
              gpu_util >= self.UTIL_HIGH):
            return self.FAN_MEDIUM, "MEDIUM temperature or HIGH utilization"
        
        # Low temperature and utilization
        elif (gpu_temp < self.GPU_TEMP_LOW and 
              cpu_temp < self.CPU_TEMP_LOW and 
              gpu_util < self.UTIL_LOW):
            return self.FAN_DEFAULT, "LOW temperatures and utilization"
        
        # Maintain current level if in middle ranges
        else:
            return self.current_speed, "maintaining current level"
    
    def run(self):
        """Main control loop"""
        self.check_commands()
        
        self.logger.info("Starting GPU/CPU fan control script")
        
        # Set initial fan speed
        self.set_fan_speed(self.current_speed, "initial setting")
        
        try:
            while True:
                # Get current system temperatures and GPU utilization
                gpu_temp, gpu_util = self.get_gpu_data()
                cpu_temp = self.get_cpu_temp()
                
                self.logger.info(
                    f"System temperatures: GPU={gpu_temp}°C, CPU={cpu_temp}°C, GPU util={gpu_util}%"
                )
                
                # Determine new fan speed
                new_speed, reason = self.determine_fan_speed(gpu_temp, cpu_temp, gpu_util)
                
                # Update fan speed if needed
                if new_speed != self.current_speed:
                    self.set_fan_speed(new_speed, reason)
                
                # Wait for next check
                time.sleep(self.INTERVAL)
                
        except KeyboardInterrupt:
            self.cleanup()
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            self.cleanup()

def main():
    """Entry point"""
    # Check if running as root
    if os.geteuid() != 0:
        print("This script must be run as root for IPMI access.")
        sys.exit(1)
    
    # Create and run the fan controller
    controller = FanController()
    controller.run()

if __name__ == "__main__":
    main()