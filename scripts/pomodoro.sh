#!/bin/bash

# Default settings (will be overridden by config if available)
WORK_MINUTES=25
BREAK_MINUTES=5
LONG_BREAK_MINUTES=15
POMODOROS_PER_LONG_BREAK=4
AUTO_START_BREAKS=true
AUTO_START_POMODOROS=true
TICKING_SOUND=false

# Path to Rz-Shell config
CONFIG_DIR="$HOME/.config/Rz-Shell"
CONFIG_FILE="$CONFIG_DIR/config/config.json"
ASSETS_DIR="$CONFIG_DIR/assets"
ALARM_SOUND="$ASSETS_DIR/alarm-kitchen.mp3"
TICKING_SOUND_FILE="$ASSETS_DIR/ticking-slow.mp3"

# Background job PIDs for audio
TICKING_PID=""

# Function to load settings from config.json
load_config() {
    if [[ -f "$CONFIG_FILE" ]]; then
        # Extract pomodoro settings using jq if available, fallback to grep/sed
        if command -v jq >/dev/null 2>&1; then
            local config_data=$(jq -r '.pomodoro_settings // empty' "$CONFIG_FILE" 2>/dev/null)
            if [[ "$config_data" != "null" && -n "$config_data" ]]; then
                WORK_MINUTES=$(echo "$config_data" | jq -r '.work_minutes // 25')
                BREAK_MINUTES=$(echo "$config_data" | jq -r '.break_minutes // 5')
                LONG_BREAK_MINUTES=$(echo "$config_data" | jq -r '.long_break_minutes // 15')
                POMODOROS_PER_LONG_BREAK=$(echo "$config_data" | jq -r '.pomodoros_per_long_break // 4')
                AUTO_START_BREAKS=$(echo "$config_data" | jq -r '.auto_start_breaks // true')
                AUTO_START_POMODOROS=$(echo "$config_data" | jq -r '.auto_start_pomodoros // true')
                TICKING_SOUND=$(echo "$config_data" | jq -r '.ticking_sound // false')
            fi
        fi
    fi
}

# Function to play alarm sound
play_alarm() {
    if [[ -f "$ALARM_SOUND" ]]; then
        # Try different audio players
        if command -v paplay >/dev/null 2>&1; then
            paplay "$ALARM_SOUND" >/dev/null 2>&1 &
        elif command -v aplay >/dev/null 2>&1; then
            aplay "$ALARM_SOUND" >/dev/null 2>&1 &
        elif command -v ffplay >/dev/null 2>&1; then
            ffplay -nodisp -autoexit "$ALARM_SOUND" >/dev/null 2>&1 &
        elif command -v mpg123 >/dev/null 2>&1; then
            mpg123 -q "$ALARM_SOUND" >/dev/null 2>&1 &
        fi
    fi
}

# Function to start ticking sound
start_ticking() {
    if [[ "$TICKING_SOUND" == "true" && -f "$TICKING_SOUND_FILE" ]]; then
        stop_ticking  # Stop any existing ticking first
        if command -v paplay >/dev/null 2>&1; then
            # Use paplay in loop mode
            while true; do paplay "$TICKING_SOUND_FILE" 2>/dev/null || break; done &
            TICKING_PID=$!
        elif command -v aplay >/dev/null 2>&1; then
            while true; do aplay "$TICKING_SOUND_FILE" 2>/dev/null || break; done &
            TICKING_PID=$!
        elif command -v ffplay >/dev/null 2>&1; then
            ffplay -nodisp -loop -1 "$TICKING_SOUND_FILE" >/dev/null 2>&1 &
            TICKING_PID=$!
        elif command -v mpg123 >/dev/null 2>&1; then
            mpg123 -q --loop -1 "$TICKING_SOUND_FILE" >/dev/null 2>&1 &
            TICKING_PID=$!
        fi
    fi
}

# Function to stop ticking sound
stop_ticking() {
    if [[ -n "$TICKING_PID" ]]; then
        kill "$TICKING_PID" 2>/dev/null
        TICKING_PID=""
    fi
    # Also kill any orphaned audio processes for ticking
    pkill -f "$(basename "$TICKING_SOUND_FILE")" 2>/dev/null
}

# Function to wait for user input if auto-start is disabled
wait_for_start() {
    local message="$1"
    local auto_start="$2"
    
    if [[ "$auto_start" != "true" ]]; then
        notify-send "Pomodoro Timer" "$message (Click this notification to start)" -a "Pomodoro" -t 0
        read -p "Press Enter to start..."
    fi
}

# Cleanup function
cleanup() {
    stop_ticking
    exit 0
}

# Set up signal handlers
trap cleanup EXIT INT TERM

# Get the PID of this script (excluding the grep process itself)
MYPID=$$
if pgrep -f "pomodoro.sh" | grep -qv "$MYPID"; then
  # Another instance is running - kill it
  stop_ticking
  notify-send "Pomodoro Timer" "Timer stopped" -a "Pomodoro"
  pkill -KILL -f "pomodoro.sh"
  exit
fi

# Load configuration
load_config

# Initialize counters
pomodoro_count=0

# Main loop
while true; do
  # Work period
  play_alarm
  notify-send "Pomodoro Timer" "Work time! ($WORK_MINUTES minutes)" -a "Pomodoro"
  wait_for_start "Ready to start work session?" "$AUTO_START_POMODOROS"
  
  start_ticking
  sleep ${WORK_MINUTES}m
  stop_ticking

  ((pomodoro_count++))

  # Break period
  play_alarm
  if ((pomodoro_count % POMODOROS_PER_LONG_BREAK == 0)); then
    notify-send "Pomodoro Timer" "Great job! Take a long break ($LONG_BREAK_MINUTES minutes)" -a "Pomodoro"
    wait_for_start "Ready to start long break?" "$AUTO_START_BREAKS"
    sleep ${LONG_BREAK_MINUTES}m
  else
    notify-send "Pomodoro Timer" "Good work! Take a short break ($BREAK_MINUTES minutes)" -a "Pomodoro"
    wait_for_start "Ready to start short break?" "$AUTO_START_BREAKS"
    sleep ${BREAK_MINUTES}m
  fi

done
