#!/bin/bash

# Configuration
INTERVAL=5          # Check every 5 seconds

# GPU temperature thresholds in celsius
GPU_TEMP_LOW=50
GPU_TEMP_MEDIUM=60
GPU_TEMP_HIGH=70
GPU_TEMP_CRITICAL=80

# CPU temperature thresholds in celsius (lower since your CPUs run cooler)
CPU_TEMP_LOW=35
CPU_TEMP_MEDIUM=45
CPU_TEMP_HIGH=60
CPU_TEMP_CRITICAL=75

UTIL_LOW=30         # Utilization thresholds in percent
UTIL_HIGH=70

FAN_DEFAULT=0x20    # Fan speeds in hex (32% - minimum recommended)
FAN_MEDIUM=0x32     # 50%
FAN_HIGH=0x48       # 72% 
FAN_MAX=0x64        # 100%

LOG_FILE="/var/log/gpu-cpu-fan-control.log"

# Ensure we have required commands
check_commands() {
    for cmd in ipmitool nvidia-smi; do
        if ! command -v $cmd &> /dev/null; then
            echo "Error: $cmd is required but not installed. Exiting."
            exit 1
        fi
    done
}

# Log with timestamp
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a $LOG_FILE
}

# Set fan speed
set_fan_speed() {
    local speed=$1
    local reason=$2
    
    # Enable manual fan control
    ipmitool raw 0x30 0x30 0x01 0x00 &> /dev/null
    
    # Set fan speed
    ipmitool raw 0x30 0x30 0x02 0xff $speed &> /dev/null
    
    log "Fan speed set to $(printf "%.0f" $((0x$speed * 100 / 0x64)))% ($reason)"
}

# Return to automatic fan control
restore_auto_fan() {
    ipmitool raw 0x30 0x30 0x01 0x01 &> /dev/null
    log "Restored automatic fan control"
}

# Graceful shutdown for script termination
cleanup() {
    log "Caught signal, restoring automatic fan control..."
    restore_auto_fan
    exit 0
}

# Get CPU temperature using thermal_zone method (most reliable)
get_cpu_temp() {
    # Read from thermal zones and convert from millidegrees to degrees
    local max_temp=0
    for zone in /sys/class/thermal/thermal_zone*/temp; do
        if [ -f "$zone" ]; then
            local temp=$(($(cat $zone) / 1000))
            if [ "$temp" -gt "$max_temp" ]; then
                max_temp=$temp
            fi
        fi
    done
    
    # If thermal zones didn't work, try coretemp as fallback
    if [ "$max_temp" -eq 0 ]; then
        # Parse coretemp Package values (most reliable indicator for overall CPU temp)
        local package_temps=$(sensors | grep -E "Package id [0-9]+:" | grep -o "+[0-9]\+\.[0-9]\+" | grep -o "[0-9]\+")
        for temp in $package_temps; do
            if [ "$temp" -gt "$max_temp" ]; then
                max_temp=$temp
            fi
        done
    fi
    
    echo $max_temp
}

# Main function
main() {
    local current_speed=$FAN_DEFAULT
    
    # Trap signals to ensure we restore auto fan control on exit
    trap cleanup SIGINT SIGTERM
    
    log "Starting GPU/CPU fan control script"
    
    # Enable manual fan control initially
    set_fan_speed $current_speed "initial setting"
    
    while true; do
        # === GPU TEMPERATURE MONITORING ===
        # Get GPU temperature and utilization for all GPUs
        mapfile -t gpu_data < <(nvidia-smi --query-gpu=temperature.gpu,utilization.gpu --format=csv,noheader,nounits)
        
        # Initialize variables to track highest values
        max_gpu_temp=0
        max_gpu_util=0
        
        # Process each GPU's data
        for gpu_line in "${gpu_data[@]}"; do
            # Extract temperature and utilization values
            gpu_temp=$(echo "$gpu_line" | cut -d',' -f1 | tr -d ' ')
            gpu_util=$(echo "$gpu_line" | cut -d',' -f2 | tr -d ' ')
            
            # Update maximums if current GPU has higher values
            if [ "$gpu_temp" -gt "$max_gpu_temp" ]; then
                max_gpu_temp=$gpu_temp
            fi
            
            if [ "$gpu_util" -gt "$max_gpu_util" ]; then
                max_gpu_util=$gpu_util
            fi
        done
        
        # === CPU TEMPERATURE MONITORING ===
        cpu_temp=$(get_cpu_temp)
        
        log "System temperatures: GPU=${max_gpu_temp}°C, CPU=${cpu_temp}°C, GPU util=${max_gpu_util}%"
        
        # Determine new fan speed based on GPU and CPU temperatures
        if [ $max_gpu_temp -ge $GPU_TEMP_CRITICAL ] || [ $cpu_temp -ge $CPU_TEMP_CRITICAL ]; then
            new_speed=$FAN_MAX
            reason="CRITICAL temperature (GPU: ${max_gpu_temp}°C, CPU: ${cpu_temp}°C)"
        elif [ $max_gpu_temp -ge $GPU_TEMP_HIGH ] || [ $cpu_temp -ge $CPU_TEMP_HIGH ]; then
            new_speed=$FAN_HIGH
            reason="HIGH temperature (GPU: ${max_gpu_temp}°C, CPU: ${cpu_temp}°C)"
        elif [ $max_gpu_temp -ge $GPU_TEMP_MEDIUM ] || [ $cpu_temp -ge $CPU_TEMP_MEDIUM ] || [ $max_gpu_util -ge $UTIL_HIGH ]; then
            new_speed=$FAN_MEDIUM
            reason="MEDIUM temperature or HIGH utilization"
        elif [ $max_gpu_temp -lt $GPU_TEMP_LOW ] && [ $cpu_temp -lt $CPU_TEMP_LOW ] && [ $max_gpu_util -lt $UTIL_LOW ]; then
            new_speed=$FAN_DEFAULT
            reason="LOW temperatures and utilization"
        else
            # Keep current speed if in the middle ranges
            new_speed=$current_speed
            reason="maintaining current level"
        fi
        
        # Only change speed if different from current
        if [ "$new_speed" != "$current_speed" ]; then
            set_fan_speed $new_speed "$reason"
            current_speed=$new_speed
        fi
        
        sleep $INTERVAL
    done
}

# Entry point
check_commands
main
