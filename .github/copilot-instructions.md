# Rz-Shell AI Coding Agent Instructions

## Overview
Rz-Shell is a hackable Wayland shell for Hyprland built with Python and Fabric (GTK layer-shell). It provides a modular desktop environment with multi-monitor support, featuring bars, docks, notifications, launchers, and widgets.

## Architecture & Key Concepts

### Entry Point & Application Structure
- **`main.py`**: Single entry point that creates multi-monitor UI components
- **Fabric Application**: Uses `fabric.Application` to manage multiple GTK layer-shell windows
- **Multi-monitor Architecture**: Components are instantiated per-monitor with centralized management via `MonitorManager`
- **Component Types**: `Bar`, `Notch` (dashboard), `Dock`, `Corners`, `NotificationPopup`

### Core Module Pattern
All UI modules inherit from `WaylandWindow` (custom `widgets/wayland.py`):
```python
from widgets.wayland import WaylandWindow as Window

class MyModule(Window):
    def __init__(self, monitor_id=None):
        super().__init__(
            layer=Layer.TOP,
            exclusivity=WaylandWindowExclusivity.AUTO,
            monitor=monitor_id
        )
```

### Configuration System
- **Main Config**: `config/config.json` with defaults in `config/settings_constants.py`
- **Loading Pattern**: Use `config.data.load_config()` for runtime config access
- **Theme Integration**: Matugen integration for dynamic theming from wallpapers
- **Config Updates**: Live updates via settings GUI (`config/settings_gui.py`)

### Multi-Monitor Management
- **MonitorManager** (`utils/monitor_manager.py`): Singleton managing monitor detection and component instances
- **MonitorFocusService** (`services/monitor_focus.py`): Tracks focused monitor via Hyprland events
- **Global Keybinds** (`utils/global_keybinds.py`): Routes commands to focused monitor
- **Instance Registration**: Each monitor registers its component instances with MonitorManager

### Services Architecture
Services extend `fabric.core.service.Service` for reactive patterns:
- **Network**: `services/network.py` (Wifi, Ethernet, NetworkClient)
- **MPRIS**: `services/mpris.py` (Media player control)
- **Brightness**: `services/brightness.py` (Monitor brightness)
- **Monitor Focus**: `services/monitor_focus.py` (Hyprland integration)

## Development Patterns

### Widget Creation
Use Fabric widgets with consistent styling:
```python
from fabric.widgets.button import Button
from fabric.widgets.box import Box

button = Button(
    child=Label("Text"),
    name="my-button",  # CSS class
    tooltip_markup="<b>Tooltip</b>"
)
```

### CSS Styling
- **Main stylesheet**: `main.css` imports all styles from `styles/`
- **Naming convention**: Use hyphenated names matching widget `name` property
- **Dynamic colors**: Use CSS variables populated by Matugen
- **Responsive design**: Handle both horizontal and vertical bar orientations

### Hyprland Integration
Use Fabric's Hyprland widgets and services:
```python
from fabric.hyprland.widgets import HyprlandWorkspaces, WorkspaceButton
from fabric.hyprland.service import HyprlandEvent
```

### Async Operations
Use Fabric's async helpers for shell commands:
```python
from fabric.utils.helpers import exec_shell_command_async
exec_shell_command_async("command")
```

## Testing & Development

### Launch Commands
- **Production**: `uwsm -- app /usr/bin/python3.13 ~/.config/Rz-Shell/main.py > /dev/null 2>&1 & disown`
- **Testing/Debugging (with logs)**: `uwsm -- app /usr/bin/python3.13 ~/.config/Rz-Shell/main.py`
- **Config GUI**: `/usr/bin/python3.13 /home/rzzdr/.config/Rz-Shell/config/config.py`
- **Simple dev mode**: `python main.py` (from project directory)

### Key Files for Extension
- **New modules**: Add to `modules/` following existing patterns
- **New services**: Add to `services/` extending `Service`
- **Styling**: Add CSS to `styles/` and import in `main.css`
- **Icons**: Use `modules/icons.py` constants
- **Scripts**: Shell utilities go in `scripts/`

### Configuration Extension
1. Add defaults to `config/settings_constants.py`
2. Add GUI controls to `config/settings_gui.py`
3. Use `config.data.load_config()` to access values

### Multi-Monitor Considerations
- Always check if `monitor_id` parameter is needed
- Register new components with MonitorManager if monitor-specific
- Test with both single and multi-monitor setups
- Use `GlobalKeybindHandler` for cross-monitor actions

## Dependencies & External Integration
- **Fabric Framework**: Core UI toolkit and Wayland integration
- **Matugen**: Dynamic theme generation from wallpapers
- **Hyprland**: Window manager integration via IPC
- **System Tools**: NetworkManager, UPower, MPRIS, etc.
- **Scripts**: Shell utilities for screenshots, OCR, color picking

## Common Pitfalls
- Don't forget `monitor_id` parameter for new UI components
- Always use `WaylandWindow` instead of `fabric.widgets.window.Window`
- CSS names must match widget `name` properties exactly
- Multi-monitor components need MonitorManager registration
- Use `exec_shell_command_async` for non-blocking shell commands