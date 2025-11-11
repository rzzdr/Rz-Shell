"""
Enhanced Mixer module with three subtabs inspired by pavucontrol:
- Playback: Shows active applications playing audio with volume/mute controls
- Output Devices: Lists output devices with volume/mute controls and device selection
- Input Devices: Lists input devices with gain/mute controls and device selection

Maintains full design consistency with existing UI components and follows the same
patterns used in the dashboard and other modules.
"""

import math

import gi
from fabric.audio.service import Audio
from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.label import Label
from fabric.widgets.scale import Scale
from fabric.widgets.scrolledwindow import ScrolledWindow
from fabric.widgets.stack import Stack
from gi.repository import GLib

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

import config.data as data
import modules.icons as icons

vertical_mode = (
    True
    if data.PANEL_THEME == "Panel"
    and (
        data.BAR_POSITION in ["Left", "Right"]
        or data.PANEL_POSITION in ["Start", "End"]
    )
    else False
)


class MuteToggleButton(Button):
    """A mute/unmute toggle button that follows existing button styling patterns."""
    
    def __init__(self, stream, **kwargs):
        self.stream = stream
        self._updating_from_stream = False
        
        # Create the button with initial mute state
        self.icon_label = Label(
            name="mute-toggle-icon",
            markup=self._get_mute_icon(),
        )
        
        super().__init__(
            name="mute-toggle-button",
            child=self.icon_label,
            on_clicked=self._on_clicked,
            tooltip_text=self._get_tooltip_text(),
            **kwargs
        )
        
        # Connect to stream changes
        stream.connect("changed", self._on_stream_changed)
        self._update_appearance()
    
    def _get_mute_icon(self):
        """Get the appropriate mute icon based on stream type and state."""
        if hasattr(self.stream, "type") and ("microphone" in self.stream.type.lower() or "input" in self.stream.type.lower()):
            return icons.mic_mute if self.stream.muted else icons.mic
        else:
            return icons.vol_mute if self.stream.muted else icons.vol_medium
    
    def _get_tooltip_text(self):
        """Get tooltip text based on current mute state."""
        return "Unmute" if self.stream.muted else "Mute"
    
    def _on_clicked(self, *args):
        """Toggle mute state when clicked."""
        if self._updating_from_stream:
            return
        if self.stream:
            self.stream.muted = not self.stream.muted
    
    def _on_stream_changed(self, stream):
        """Update button when stream changes."""
        self._updating_from_stream = True
        self._update_appearance()
        self._updating_from_stream = False
    
    def _update_appearance(self):
        """Update button appearance based on mute state."""
        self.icon_label.set_markup(self._get_mute_icon())
        self.set_tooltip_text(self._get_tooltip_text())
        
        # Update style classes
        if self.stream.muted:
            self.add_style_class("muted")
        else:
            self.remove_style_class("muted")


class DeviceSelector(Button):
    """A radio button-style device selector for marking active devices."""
    
    def __init__(self, device, is_active=False, on_select=None, **kwargs):
        self.device = device
        self.is_active = is_active
        self.on_select_callback = on_select
        
        # Create the selection indicator
        self.selection_icon = Label(
            name="device-selector-icon",
            markup=icons.circle if is_active else icons.circle,
        )
        
        super().__init__(
            name="device-selector-button",
            child=self.selection_icon,
            on_clicked=self._on_clicked,
            tooltip_text="Set as active device",
            **kwargs
        )
        
        self._update_appearance()
    
    def set_active(self, active):
        """Set the active state of this selector."""
        self.is_active = active
        self._update_appearance()
    
    def _on_clicked(self, *args):
        """Handle click to select this device."""
        if self.on_select_callback and not self.is_active:
            self.on_select_callback(self.device)
    
    def _update_appearance(self):
        """Update appearance based on active state."""
        if self.is_active:
            self.add_style_class("active")
            self.selection_icon.set_markup("●")  # Filled circle
        else:
            self.remove_style_class("active")
            self.selection_icon.set_markup("○")  # Empty circle


class MixerSlider(Scale):
    def __init__(self, stream, **kwargs):
        super().__init__(
            name="control-slider",
            orientation="h",
            h_expand=True,
            h_align="fill",
            has_origin=True,
            increments=(0.01, 0.1),
            style_classes=["no-icon"],
            **kwargs,
        )

        self.stream = stream
        self._updating_from_stream = False
        self.set_value(stream.volume / 100)
        self.set_size_request(-1, 30)  # Fixed height for sliders

        self.connect("value-changed", self.on_value_changed)
        stream.connect("changed", self.on_stream_changed)

        # Apply appropriate style class based on stream type
        if hasattr(stream, "type"):
            if "microphone" in stream.type.lower() or "input" in stream.type.lower():
                self.add_style_class("mic")
            else:
                self.add_style_class("vol")
        else:
            # Default to volume style
            self.add_style_class("vol")

        # Set initial tooltip and muted state
        self.set_tooltip_text(f"{stream.volume:.0f}%")
        self.update_muted_state()

    def on_value_changed(self, _):
        if self._updating_from_stream:
            return
        if self.stream:
            self.stream.volume = self.value * 100
            self.set_tooltip_text(f"{self.value * 100:.0f}%")

    def on_stream_changed(self, stream):
        self._updating_from_stream = True
        self.value = stream.volume / 100
        self.set_tooltip_text(f"{stream.volume:.0f}%")
        self.update_muted_state()
        self._updating_from_stream = False

    def update_muted_state(self):
        if self.stream.muted:
            self.add_style_class("muted")
        else:
            self.remove_style_class("muted")


class StreamControl(Box):
    """A complete stream control with label, slider, and mute button."""
    
    def __init__(self, stream, show_device_selector=False, on_device_select=None, **kwargs):
        super().__init__(
            name="stream-control",
            orientation="v",
            spacing=4,
            h_expand=True,
            v_expand=False,
            **kwargs
        )
        
        self.stream = stream
        
        # Create top row with label and controls
        self.top_row = Box(
            orientation="h",
            spacing=8,
            h_expand=True,
            v_expand=False,
        )
        
        # Stream name and volume info
        label_text = stream.description
        if hasattr(stream, "type") and "application" in stream.type.lower():
            label_text = getattr(stream, "name", stream.description)
        
        self.stream_label = Label(
            name="mixer-stream-label",
            label=f"[{math.ceil(stream.volume)}%] {label_text}",
            h_expand=True,
            h_align="start",
            v_align="center",
            ellipsization="end",
            max_chars_width=35,
            height_request=20,
        )
        
        # Control buttons container
        self.controls_box = Box(
            orientation="h",
            spacing=4,
            h_expand=False,
            v_expand=False,
        )
        
        # Device selector (for output/input devices)
        if show_device_selector:
            self.device_selector = DeviceSelector(
                device=stream,
                is_active=False,  # Will be set by parent
                on_select=on_device_select,
            )
            self.controls_box.add(self.device_selector)
        else:
            self.device_selector = None
        
        # Mute toggle button
        self.mute_button = MuteToggleButton(stream)
        self.controls_box.add(self.mute_button)
        
        # Add to top row
        self.top_row.add(self.stream_label)
        self.top_row.add(self.controls_box)
        
        # Volume slider
        self.slider = MixerSlider(stream)
        
        # Connect to stream changes to update label
        stream.connect("changed", self._on_stream_changed)
        
        # Add components
        self.add(self.top_row)
        self.add(self.slider)
    
    def _on_stream_changed(self, stream):
        """Update label when stream changes."""
        label_text = stream.description
        if hasattr(stream, "type") and "application" in stream.type.lower():
            label_text = getattr(stream, "name", stream.description)
        
        self.stream_label.set_label(f"[{math.ceil(stream.volume)}%] {label_text}")
    
    def set_device_active(self, active):
        """Set the device selector active state."""
        if self.device_selector:
            self.device_selector.set_active(active)


class PlaybackTab(Box):
    """Tab for active applications playing audio (like pavucontrol's Playback tab)."""
    
    def __init__(self, audio_service, **kwargs):
        super().__init__(
            name="playback-tab",
            orientation="v",
            spacing=8,
            h_expand=True,
            v_expand=True,
            **kwargs
        )
        
        self.audio = audio_service
        
        # Header
        self.header = Label(
            name="mixer-section-title",
            label="Active Applications",
            h_expand=True,
            h_align="start",
        )
        
        # Scrolled window for applications
        self.scrolled = ScrolledWindow(
            name="playback-scrolled",
            h_expand=True,
            v_expand=True,
            h_align="fill",
            v_align="fill",
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            propagate_width=False,
            propagate_height=False,
        )
        
        # Set height constraints to prevent overflow
        self.scrolled.set_size_request(-1, 200)
        self.scrolled.set_max_content_height(200)
        
        # Content container
        self.content_box = Box(
            name="playback-content",
            orientation="v",
            spacing=8,
            h_expand=True,
            v_expand=False,
        )
        
        self.scrolled.add_with_viewport(self.content_box)
        
        # No applications message
        self.no_apps_label = Label(
            name="no-apps-label",
            label="No applications are currently playing audio",
            h_align="center",
            v_align="center",
            h_expand=True,
            v_expand=True,
        )
        
        self.add(self.header)
        self.add(self.scrolled)
        
        # Initialize content
        self.update_applications()
    
    def update_applications(self):
        """Update the list of active applications."""
        # Clear existing content
        for child in self.content_box.get_children():
            self.content_box.remove(child)
        
        # Get active applications
        applications = self.audio.applications if self.audio else []
        
        if not applications:
            # Show no applications message
            self.content_box.add(self.no_apps_label)
        else:
            # Add application controls
            for app in applications:
                app_control = StreamControl(app)
                self.content_box.add(app_control)
        
        self.content_box.show_all()


class OutputDevicesTab(Box):
    """Tab for output devices (like pavucontrol's Output Devices tab)."""
    
    def __init__(self, audio_service, **kwargs):
        super().__init__(
            name="output-devices-tab",
            orientation="v",
            spacing=8,
            h_expand=True,
            v_expand=True,
            **kwargs
        )
        
        self.audio = audio_service
        self.device_selectors = []
        
        # Header
        self.header = Label(
            name="mixer-section-title",
            label="Output Devices",
            h_expand=True,
            h_align="start",
        )
        
        # Scrolled window for devices
        self.scrolled = ScrolledWindow(
            name="output-devices-scrolled",
            h_expand=True,
            v_expand=True,
            h_align="fill",
            v_align="fill",
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            propagate_width=False,
            propagate_height=False,
        )
        
        # Set height constraints to prevent overflow
        self.scrolled.set_size_request(-1, 200)
        self.scrolled.set_max_content_height(200)
        
        # Content container
        self.content_box = Box(
            name="output-devices-content",
            orientation="v",
            spacing=8,
            h_expand=True,
            v_expand=False,
        )
        
        self.scrolled.add_with_viewport(self.content_box)
        
        # No devices message
        self.no_devices_label = Label(
            name="no-devices-label",
            label="No output devices available",
            h_align="center",
            v_align="center",
            h_expand=True,
            v_expand=True,
        )
        
        self.add(self.header)
        self.add(self.scrolled)
        
        # Initialize content
        self.update_devices()
    
    def update_devices(self):
        """Update the list of output devices."""
        # Clear existing content
        for child in self.content_box.get_children():
            self.content_box.remove(child)
        
        self.device_selectors.clear()
        
        # Get all available output devices (speakers)
        devices = []
        if self.audio:
            # Use all speakers, not just the active one
            devices.extend(self.audio.speakers)
            
            # If no speakers found but there's an active speaker, include it
            if not devices and self.audio.speaker:
                devices.append(self.audio.speaker)
        
        if not devices:
            # Show no devices message
            self.content_box.add(self.no_devices_label)
        else:
            # Add device controls
            current_speaker = self.audio.speaker if self.audio else None
            for i, device in enumerate(devices):
                device_control = StreamControl(
                    device,
                    show_device_selector=True,
                    on_device_select=self._on_device_select
                )
                
                # Set the current active speaker as active
                is_active = (current_speaker and device == current_speaker)
                device_control.set_device_active(is_active)
                self.device_selectors.append(device_control)
                
                self.content_box.add(device_control)
        
        self.content_box.show_all()
    
    def _refresh_output_devices(self):
        """Refresh output devices after a short delay."""
        self.update_devices()
        return GLib.SOURCE_REMOVE
    
    def _on_device_select(self, device):
        """Handle device selection."""
        # Update device selector states
        for selector in self.device_selectors:
            selector.set_device_active(selector.stream == device)
        
        # Actually switch the output device
        try:
            if self.audio:
                print(f"Attempting to switch to output device: {device.description}")
                # Use the underlying control to set the default sink
                if hasattr(self.audio, '_control') and hasattr(device, 'stream'):
                    # For Cvc.MixerSink, we need to set it as the default sink
                    success = self.audio._control.set_default_sink(device.stream)
                    if success:
                        print(f"Successfully switched to output device: {device.description}")
                    else:
                        print(f"Failed to switch to output device: {device.description} (set_default_sink returned False)")
                        # Revert the UI state if switching failed
                        current_speaker = self.audio.speaker if self.audio else None
                        for selector in self.device_selectors:
                            selector.set_device_active(selector.stream == current_speaker)
                        return
                else:
                    print("Control or stream not available for device switching")
                    # Revert the UI state if switching failed
                    current_speaker = self.audio.speaker if self.audio else None
                    for selector in self.device_selectors:
                        selector.set_device_active(selector.stream == current_speaker)
                    return
                
                # Give the audio service a moment to process the change
                GLib.timeout_add(100, self._refresh_output_devices)
        except Exception as e:
            print(f"Failed to switch output device: {e}")
            # Revert the UI state if switching failed
            current_speaker = self.audio.speaker if self.audio else None
            for selector in self.device_selectors:
                selector.set_device_active(selector.stream == current_speaker)


class InputDevicesTab(Box):
    """Tab for input devices (like pavucontrol's Input Devices tab)."""
    
    def __init__(self, audio_service, **kwargs):
        super().__init__(
            name="input-devices-tab",
            orientation="v",
            spacing=8,
            h_expand=True,
            v_expand=True,
            **kwargs
        )
        
        self.audio = audio_service
        self.device_selectors = []
        
        # Header
        self.header = Label(
            name="mixer-section-title",
            label="Input Devices",
            h_expand=True,
            h_align="start",
        )
        
        # Scrolled window for devices
        self.scrolled = ScrolledWindow(
            name="input-devices-scrolled",
            h_expand=True,
            v_expand=True,
            h_align="fill",
            v_align="fill",
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            propagate_width=False,
            propagate_height=False,
        )
        
        # Set height constraints to prevent overflow
        self.scrolled.set_size_request(-1, 200)
        self.scrolled.set_max_content_height(200)
        
        # Content container
        self.content_box = Box(
            name="input-devices-content",
            orientation="v",
            spacing=8,
            h_expand=True,
            v_expand=False,
        )
        
        self.scrolled.add_with_viewport(self.content_box)
        
        # No devices message
        self.no_devices_label = Label(
            name="no-devices-label",
            label="No input devices available",
            h_align="center",
            v_align="center",
            h_expand=True,
            v_expand=True,
        )
        
        self.add(self.header)
        self.add(self.scrolled)
        
        # Initialize content
        self.update_devices()
    
    def _is_unwanted_device(self, device):
        """Filter out unwanted input devices like monitors, peak detect, cava, etc."""
        if not hasattr(device, 'description'):
            return False
            
        description = device.description.lower()
        
        # Filter out common unwanted devices
        unwanted_keywords = [
            'monitor',
            'peak detect', 
            'cava',
            '.monitor',
            'echo cancel',
            'rnnoise',
            'webrtc',
            'virtual'
        ]
        
        for keyword in unwanted_keywords:
            if keyword in description:
                return True
                
        # Also filter by type if available
        if hasattr(device, 'type'):
            device_type = device.type.lower()
            if 'monitor' in device_type:
                return True
                
        return False

    def update_devices(self):
        """Update the list of input devices."""
        # Clear existing content
        for child in self.content_box.get_children():
            self.content_box.remove(child)
        
        self.device_selectors.clear()
        
        # Get all available input devices (microphones)
        devices = []
        if self.audio:
            # Use all microphones, not just the active one
            all_mics = self.audio.microphones
            # Filter out unwanted devices
            devices.extend([mic for mic in all_mics if not self._is_unwanted_device(mic)])
            
            # If no microphones found but there's an active microphone, include it if it's not unwanted
            if not devices and self.audio.microphone and not self._is_unwanted_device(self.audio.microphone):
                devices.append(self.audio.microphone)
            
            # Add recording applications as well (but filter them too)
            filtered_recorders = [rec for rec in self.audio.recorders if not self._is_unwanted_device(rec)]
            devices.extend(filtered_recorders)
        
        if not devices:
            # Show no devices message
            self.content_box.add(self.no_devices_label)
        else:
            # Add device controls
            current_microphone = self.audio.microphone if self.audio else None
            for i, device in enumerate(devices):
                # Show device selector for actual microphone devices, not recorder applications
                is_actual_device = hasattr(device, "type") and "microphone" in device.type.lower()
                show_selector = is_actual_device
                
                device_control = StreamControl(
                    device,
                    show_device_selector=show_selector,
                    on_device_select=self._on_device_select
                )
                
                # Set the current active microphone as active
                if show_selector:
                    is_active = (current_microphone and device == current_microphone)
                    device_control.set_device_active(is_active)
                    self.device_selectors.append(device_control)
                
                self.content_box.add(device_control)
        
        self.content_box.show_all()
    
    def _refresh_input_devices(self):
        """Refresh input devices after a short delay."""
        self.update_devices()
        return GLib.SOURCE_REMOVE
    
    def _on_device_select(self, device):
        """Handle device selection."""
        # Update device selector states
        for selector in self.device_selectors:
            selector.set_device_active(selector.stream == device)
        
        # Actually switch the input device
        try:
            if self.audio:
                print(f"Attempting to switch to input device: {device.description}")
                # Use the underlying control to set the default source
                if hasattr(self.audio, '_control') and hasattr(device, 'stream'):
                    # For Cvc.MixerSource, we need to set it as the default source
                    success = self.audio._control.set_default_source(device.stream)
                    if success:
                        print(f"Successfully switched to input device: {device.description}")
                    else:
                        print(f"Failed to switch to input device: {device.description} (set_default_source returned False)")
                        # Revert the UI state if switching failed
                        current_microphone = self.audio.microphone if self.audio else None
                        for selector in self.device_selectors:
                            selector.set_device_active(selector.stream == current_microphone)
                        return
                else:
                    print("Control or stream not available for device switching")
                    # Revert the UI state if switching failed
                    current_microphone = self.audio.microphone if self.audio else None
                    for selector in self.device_selectors:
                        selector.set_device_active(selector.stream == current_microphone)
                    return
                
                # Give the audio service a moment to process the change
                GLib.timeout_add(100, self._refresh_input_devices)
        except Exception as e:
            print(f"Failed to switch input device: {e}")
            # Revert the UI state if switching failed
            current_microphone = self.audio.microphone if self.audio else None
            for selector in self.device_selectors:
                selector.set_device_active(selector.stream == current_microphone)


class MixerSection(Box):
    def __init__(self, title, **kwargs):
        super().__init__(
            name="mixer-section",
            orientation="v",
            spacing=8,
            h_expand=True,
            v_expand=False,  # Prevent vertical stretching
        )

        self.title_label = Label(
            name="mixer-section-title",
            label=title,
            h_expand=True,
            h_align="fill",
        )

        self.content_box = Box(
            name="mixer-content",
            orientation="v",
            spacing=8,
            h_expand=True,
            v_expand=False,  # Prevent vertical stretching
        )

        self.add(self.title_label)
        self.add(self.content_box)

    def update_streams(self, streams):
        for child in self.content_box.get_children():
            self.content_box.remove(child)

        for stream in streams:
            label_text = stream.description
            if hasattr(stream, "type") and "application" in stream.type.lower():
                label_text = getattr(stream, "name", stream.description)

            stream_container = Box(
                orientation="v",
                spacing=4,
                h_expand=True,
                v_expand=False,  # Prevent vertical stretching
            )

            label = Label(
                name="mixer-stream-label",
                label=f"[{math.ceil(stream.volume)}%] {stream.description}",
                h_expand=True,
                h_align="start",
                v_align="center",
                ellipsization="end",
                max_chars_width=45,
                height_request=20,  # Fixed height for labels
            )

            slider = MixerSlider(stream)

            stream_container.add(label)
            stream_container.add(slider)
            self.content_box.add(stream_container)

        self.content_box.show_all()


class Mixer(Box):
    """Main Mixer component with three subtabs: Playback, Output Devices, and Input Devices."""
    
    def __init__(self, **kwargs):
        super().__init__(
            name="mixer",
            orientation="v",
            spacing=8,
            h_expand=True,
            v_expand=True,
            **kwargs
        )

        try:
            self.audio = Audio()
            
            # Check if audio service is connecting - give it some time to initialize
            if hasattr(self.audio, 'state') and self.audio.state == "connecting":
                # Schedule an update after a short delay to allow audio service to connect
                GLib.timeout_add(1000, self._delayed_update)
                
        except Exception as e:
            error_label = Label(
                label=f"Audio service unavailable: {str(e)}",
                h_align="center",
                v_align="center",
                h_expand=True,
                v_expand=True,
            )
            self.add(error_label)
            self.show_all()
            return

        # Create the stack for subtabs
        self.stack = Stack(
            name="mixer-stack",
            transition_type="slide-left-right",
            transition_duration=500,
            v_expand=True,
            v_align="fill",
            h_expand=True,
            h_align="fill",
        )
        
        self.stack.set_homogeneous(False)
        # Set height constraint to prevent overflow
        self.stack.set_size_request(-1, 250)

        # Create the switcher for subtabs
        self.switcher = Gtk.StackSwitcher(
            name="mixer-switcher",
            spacing=8,
        )

        # Create the three tabs
        self.playback_tab = PlaybackTab(self.audio)
        self.output_devices_tab = OutputDevicesTab(self.audio)
        self.input_devices_tab = InputDevicesTab(self.audio)

        # Add tabs to stack
        self.stack.add_titled(self.playback_tab, "playback", "Playback")
        self.stack.add_titled(self.output_devices_tab, "output-devices", "Output Devices")
        self.stack.add_titled(self.input_devices_tab, "input-devices", "Input Devices")

        # Configure switcher
        self.switcher.set_stack(self.stack)
        self.switcher.set_hexpand(True)
        self.switcher.set_homogeneous(True)
        self.switcher.set_can_focus(True)

        # Add components to main container
        self.add(self.switcher)
        self.add(self.stack)

        # Setup switcher icons for vertical mode
        if vertical_mode:
            GLib.idle_add(self._setup_switcher_icons)

        # Connect to audio service changes
        self.audio.connect("changed", self.on_audio_changed)
        self.audio.connect("stream-added", self.on_audio_changed)
        self.audio.connect("stream-removed", self.on_audio_changed)
        self.audio.connect("speaker-changed", self.on_speaker_changed)
        self.audio.connect("microphone-changed", self.on_microphone_changed)

        # Initial update
        self.update_all_tabs()
        self.show_all()
    
    def _setup_switcher_icons(self):
        """Setup icons for switcher buttons in vertical mode."""
        icon_details_map = {
            "Playback": {"icon": icons.speaker, "name": "playback"},
            "Output Devices": {"icon": icons.headphones, "name": "output-devices"},
            "Input Devices": {"icon": icons.mic, "name": "input-devices"},
        }

        buttons = self.switcher.get_children()
        for btn in buttons:
            if isinstance(btn, Gtk.ToggleButton):
                original_gtk_label = None
                for child_widget in btn.get_children():
                    if isinstance(child_widget, Gtk.Label):
                        original_gtk_label = child_widget
                        break

                if original_gtk_label:
                    label_text = original_gtk_label.get_text()
                    if label_text in icon_details_map:
                        details = icon_details_map[label_text]
                        icon_markup = details["icon"]
                        css_name_suffix = details["name"]

                        btn.remove(original_gtk_label)

                        new_icon_label = Label(
                            name=f"mixer-switcher-icon-{css_name_suffix}", 
                            markup=icon_markup
                        )
                        btn.add(new_icon_label)
                        new_icon_label.show_all()
        
        return GLib.SOURCE_REMOVE
    
    def _delayed_update(self):
        """Delayed update for when audio service is connecting."""
        self.update_all_tabs()
        return GLib.SOURCE_REMOVE
    
    def on_audio_changed(self, *args):
        """Handle audio service changes and update all tabs."""
        self.update_all_tabs()
    
    def on_speaker_changed(self, *args):
        """Handle speaker device changes."""
        # Only update output devices tab for better performance
        self.output_devices_tab.update_devices()
    
    def on_microphone_changed(self, *args):
        """Handle microphone device changes."""
        # Only update input devices tab for better performance
        self.input_devices_tab.update_devices()
    
    def update_all_tabs(self):
        """Update content in all tabs."""
        self.playback_tab.update_applications()
        self.output_devices_tab.update_devices()
        self.input_devices_tab.update_devices()
    
    def go_to_tab(self, tab_name):
        """Navigate to a specific tab."""
        if tab_name == "playback":
            self.stack.set_visible_child(self.playback_tab)
        elif tab_name == "output-devices":
            self.stack.set_visible_child(self.output_devices_tab)
        elif tab_name == "input-devices":
            self.stack.set_visible_child(self.input_devices_tab)
