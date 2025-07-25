# CircLights - Music Reactive WLED Visualizer

## Project Overview
Music reactive visualizer controlling WLED strip in loop configuration over WiFi with live web interface.

## Technology Stack
- **Language**: Python
- **Audio Processing**: pyaudio, librosa, numpy
- **Web Interface**: Flask + WebSockets (Socket.IO)
- **WLED Communication**: HTTP requests to WLED JSON API
- **Cross-platform**: Windows/Linux support

## Core Features

### Audio Input
- System audio capture (WASAPI on Windows, ALSA on Linux)
- Microphone input option
- Real-time FFT analysis for frequency separation (lows/mids/highs)
- Configurable audio buffer sizes for latency optimization

### Zone Management
- Define zones by percentage of strip length (e.g., 25%-50%)
- Each zone can have independent:
  - Frequency range (lows/mids/highs/all)
  - Reaction type
  - Custom parameters

### Visualization Effects
1. **Normal Visualizer**: Traditional spectrum visualization
2. **Flash on Spike**: Brightness flash on volume threshold
3. **Color Change on Spike**: Color shift on volume threshold  
4. **Moving Patterns**: Speed varies with volume/beat detection

### Web Interface
- Real-time control and configuration
- Live visualization preview
- Zone management UI
- Effect parameter adjustment

## Hardware Setup
- **Primary**: 1 WLED device (ESP32) - user configurable IP
- **LED Count**: Default 30 LEDs, user configurable
- **Future**: Multiple WLED device support
- **Strip Configuration**: Loop/circular arrangement
- **Network**: Same local network as control device

## Network
- WiFi communication to WLED JSON API
- WebSocket for real-time web interface updates
- HTTP REST API for configuration
- Auto-discovery option for WLED devices

## Performance Requirements
- Target: 60 FPS LED updates
- Fallback: 30 FPS mode for performance issues
- Low latency audio processing (<50ms)
- Responsive web interface

## Advanced Audio Analysis
- **Beat Detection**: Onset detection for rhythm-based effects
- **Musical Analysis**: 
  - Tempo detection
  - Key/pitch analysis
  - Dynamic range analysis
  - Harmonic content analysis
- **Adaptive Algorithms**: Effects that learn and adapt to music style

## Configuration Management
- **Settings Persistence**: JSON config file for user preferences
- **Preset System**: Save/load complete visualization setups
- **Import/Export**: Share presets between installations
- **Live Backup**: Auto-save current settings during use

## Color System
- **Full RGB Flexibility**: 16.7M color support
- **Color Palettes**: Predefined and custom palettes
- **Color Transitions**: Smooth interpolation between colors
- **HSV Support**: For intuitive color manipulation