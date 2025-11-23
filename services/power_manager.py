import time
from fabric.core.service import Service, Signal
from gi.repository import GLib
from loguru import logger

from modules.upower.upower import UPowerManager
from services.brightness import Brightness
from utils.functions import send_notification
from config.data import load_config


class PowerManagerService(Service):
    """Service for power management including low battery notifications and power controls."""
    
    instance = None
    
    @staticmethod
    def get_initial():
        """Singleton to get PowerManagerService instance."""
        if PowerManagerService.instance is None:
            PowerManagerService.instance = PowerManagerService()
        return PowerManagerService.instance

    @Signal
    def battery_level_changed(self, level: int, is_charging: bool) -> None:
        """Signal emitted when battery level changes."""
        pass

    @Signal
    def low_battery_warning(self, level: int) -> None:
        """Signal emitted when low battery warning is triggered."""
        pass

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.upower = UPowerManager()
        self.brightness_service = None
        self.last_battery_level = -1
        self.last_charging_state = None
        self.notified_levels = set()  # Track which levels we've already notified about
        self.battery_timer = None
        self.brightness_dimmed = False
        self.original_brightness = None
        self.suspend_warning_sent = False
        self.suspend_timer = None
        self.performance_mode_set = False
        
        # Initialize brightness service
        try:
            self.brightness_service = Brightness.get_initial()
        except Exception as e:
            logger.warning(f"Could not initialize brightness service: {e}")
        
        # Start monitoring battery
        self._start_battery_monitoring()

    def _start_battery_monitoring(self):
        """Start periodic battery monitoring."""
        self.battery_timer = GLib.timeout_add(5000, self._check_battery_status)  # Check every 5 seconds

    def _check_battery_status(self):
        """Check current battery status and handle notifications/power controls."""
        try:
            # Get battery devices
            devices = self.upower.detect_devices()
            battery_device = None
            
            # Find the first battery device
            for device in devices:
                device_info = self.upower.get_full_device_information(device)
                if device_info.get('Type') == 2:  # Battery type
                    battery_device = device
                    break
            
            if not battery_device:
                return True  # Continue monitoring
            
            # Get battery information
            battery_info = self.upower.get_full_device_information(battery_device)
            battery_level = int(battery_info.get('Percentage', 0))
            is_charging = battery_info.get('State') == 1  # Charging state
            is_on_battery = self.upower.on_battery()
            
            # Check if battery level or charging state changed
            if battery_level != self.last_battery_level or is_charging != self.last_charging_state:
                self.emit("battery_level_changed", battery_level, is_charging)
                
                # Handle charging state change - reset notifications when plugged in
                if is_charging and not self.last_charging_state:
                    self.notified_levels.clear()
                    self._restore_brightness()
                
                self.last_battery_level = battery_level
                self.last_charging_state = is_charging
            
            # Only process low battery warnings when on battery power
            if is_on_battery and not is_charging:
                self._handle_low_battery_notifications(battery_level)
                self._handle_power_controls(battery_level)
                self._handle_auto_suspend(battery_level)
            else:
                # Cancel suspend timer if charging
                if self.suspend_timer:
                    GLib.source_remove(self.suspend_timer)
                    self.suspend_timer = None
                    self.suspend_warning_sent = False
            
            # Handle performance mode regardless of power source
            self._handle_performance_mode(battery_level, is_on_battery)
            
            return True  # Continue monitoring
            
        except Exception as e:
            logger.error(f"Error checking battery status: {e}")
            return True  # Continue monitoring despite errors

    def _handle_low_battery_notifications(self, battery_level):
        """Handle low battery notifications based on config."""
        config = load_config()
        power_config = config.get("power_controls", {})
        
        # Default notification levels
        notification_levels = power_config.get("notification_levels", [20, 10, 5])
        enable_notifications = power_config.get("enable_low_battery_notifications", True)
        
        if not enable_notifications:
            return
        
        # Check each notification level
        for level in notification_levels:
            if battery_level <= level and level not in self.notified_levels:
                self._send_low_battery_notification(battery_level)
                self.notified_levels.add(level)
                self.emit("low_battery_warning", battery_level)
                break  # Only notify for the highest level reached

    def _send_low_battery_notification(self, battery_level):
        """Send low battery notification."""
        config = load_config()
        power_config = config.get("power_controls", {})
        
        # Determine urgency and message based on level
        if battery_level <= 5:
            urgency = "critical"
            title = "Critical Battery Level!"
            body = f"Battery is at {battery_level}%. Please plug in your charger immediately."
            icon = "battery-caution"
        elif battery_level <= 10:
            urgency = "critical" 
            title = "Very Low Battery"
            body = f"Battery is at {battery_level}%. Consider plugging in your charger."
            icon = "battery-low"
        else:
            urgency = "normal"
            title = "Low Battery"
            body = f"Battery is at {battery_level}%. You may want to plug in your charger."
            icon = "battery-low"
        
        # Send notification
        try:
            timeout = power_config.get("notification_timeout", 8000)  # 8 seconds default
            send_notification(
                title=title,
                body=body,
                urgency=urgency,
                icon=icon,
                app_name="Rz-Shell Power Manager",
                timeout=timeout
            )
        except Exception as e:
            logger.error(f"Failed to send low battery notification: {e}")

    def _handle_power_controls(self, battery_level):
        """Handle automatic power controls based on battery level."""
        config = load_config()
        power_config = config.get("power_controls", {})
        
        enable_auto_dim = power_config.get("enable_auto_dim", True)
        dim_trigger_level = power_config.get("dim_trigger_level", 20)
        dim_brightness_level = power_config.get("dim_brightness_level", 30)
        
        if not enable_auto_dim or not self.brightness_service:
            return
        
        # Trigger dimming when battery hits the configured level
        if battery_level <= dim_trigger_level and not self.brightness_dimmed:
            self._dim_brightness(dim_brightness_level)
        elif battery_level > dim_trigger_level and self.brightness_dimmed:
            self._restore_brightness()

    def _dim_brightness(self, target_level):
        """Dim the screen brightness to the specified level."""
        try:
            if not self.brightness_service:
                return
            
            # Store original brightness
            current_brightness = self.brightness_service.screen_brightness
            if current_brightness > target_level:
                self.original_brightness = current_brightness
                self.brightness_service.screen_brightness = target_level
                self.brightness_dimmed = True
                logger.info(f"Dimmed brightness from {current_brightness}% to {target_level}% due to low battery")
        except Exception as e:
            logger.error(f"Failed to dim brightness: {e}")

    def _restore_brightness(self):
        """Restore original brightness level."""
        try:
            if not self.brightness_service or not self.brightness_dimmed:
                return
            
            if self.original_brightness is not None:
                self.brightness_service.screen_brightness = self.original_brightness
                logger.info(f"Restored brightness to {self.original_brightness}%")
            
            self.brightness_dimmed = False
            self.original_brightness = None
        except Exception as e:
            logger.error(f"Failed to restore brightness: {e}")

    def get_battery_info(self):
        """Get current battery information."""
        try:
            devices = self.upower.detect_devices()
            for device in devices:
                device_info = self.upower.get_full_device_information(device)
                if device_info.get('Type') == 2:  # Battery type
                    return {
                        'percentage': int(device_info.get('Percentage', 0)),
                        'is_charging': device_info.get('State') == 1,
                        'is_on_battery': self.upower.on_battery(),
                        'time_to_empty': device_info.get('TimeToEmpty', 0),
                        'time_to_full': device_info.get('TimeToFull', 0)
                    }
        except Exception as e:
            logger.error(f"Failed to get battery info: {e}")
        return None

    def _handle_auto_suspend(self, battery_level):
        """Handle automatic system suspend on critical battery."""
        config = load_config()
        power_config = config.get("power_controls", {})
        
        enable_auto_suspend = power_config.get("enable_auto_suspend", False)
        suspend_trigger_level = power_config.get("suspend_trigger_level", 5)
        suspend_delay_minutes = power_config.get("suspend_delay_minutes", 5)
        
        if not enable_auto_suspend:
            return
        
        # Trigger suspend warning and timer
        if battery_level <= suspend_trigger_level and not self.suspend_warning_sent:
            self._send_suspend_warning(battery_level, suspend_delay_minutes)
            self.suspend_warning_sent = True
            
            # Set timer for actual suspend
            delay_ms = suspend_delay_minutes * 60 * 1000  # Convert to milliseconds
            self.suspend_timer = GLib.timeout_add(delay_ms, self._execute_suspend)
        
        # Cancel suspend if battery level goes above trigger
        elif battery_level > suspend_trigger_level and self.suspend_timer:
            GLib.source_remove(self.suspend_timer)
            self.suspend_timer = None
            self.suspend_warning_sent = False

    def _send_suspend_warning(self, battery_level, delay_minutes):
        """Send warning notification before auto-suspend."""
        try:
            send_notification(
                title="Critical Battery - Auto Suspend",
                body=f"Battery at {battery_level}%! System will suspend in {delay_minutes} minutes to prevent data loss. Plug in charger to cancel.",
                urgency="critical",
                icon="battery-caution",
                app_name="Rz-Shell Power Manager",
                timeout=10000  # 10 seconds
            )
        except Exception as e:
            logger.error(f"Failed to send suspend warning: {e}")

    def _execute_suspend(self):
        """Execute system suspend."""
        try:
            logger.info("Executing auto-suspend due to critical battery level")
            from fabric.utils.helpers import exec_shell_command_async
            exec_shell_command_async("systemctl suspend")
        except Exception as e:
            logger.error(f"Failed to execute suspend: {e}")
        return False  # Don't repeat timer

    def _handle_performance_mode(self, battery_level, is_on_battery):
        """Handle automatic performance mode switching."""
        config = load_config()
        power_config = config.get("power_controls", {})
        
        enable_performance_mode = power_config.get("enable_performance_mode", True)
        performance_battery_level = power_config.get("performance_mode_battery_level", 50)
        
        if not enable_performance_mode:
            return
        
        # Switch to power-save mode when battery is low and on battery
        should_use_powersave = is_on_battery and battery_level <= performance_battery_level
        
        if should_use_powersave and not self.performance_mode_set:
            self._set_performance_mode("powersave")
            self.performance_mode_set = True
        elif not should_use_powersave and self.performance_mode_set:
            self._set_performance_mode("performance")
            self.performance_mode_set = False

    def _set_performance_mode(self, mode):
        """Set CPU performance mode."""
        try:
            from fabric.utils.helpers import exec_shell_command_async
            
            # Try different governors based on availability
            governors = {
                "powersave": ["powersave", "conservative"],
                "performance": ["performance", "ondemand", "schedutil"]
            }
            
            target_governors = governors.get(mode, ["ondemand"])
            
            # Try to set governor for all CPUs
            for governor in target_governors:
                command = f"echo {governor} | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor"
                exec_shell_command_async(
                    command,
                    lambda exit_code, stdout, stderr: 
                        logger.info(f"Set CPU governor to {governor}") if exit_code == 0 
                        else logger.debug(f"Failed to set governor {governor}: {stderr}")
                )
                break  # Use first available governor
            
        except Exception as e:
            logger.error(f"Failed to set performance mode: {e}")

    def cleanup(self):
        """Clean up resources when service is stopped."""
        if self.battery_timer:
            GLib.source_remove(self.battery_timer)
            self.battery_timer = None
        
        if self.suspend_timer:
            GLib.source_remove(self.suspend_timer)
            self.suspend_timer = None
        
        # Restore brightness if dimmed
        self._restore_brightness()
        
        # Restore performance mode if changed
        if self.performance_mode_set:
            self._set_performance_mode("performance")