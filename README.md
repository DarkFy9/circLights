# CircLights - Music Reactive LED Visualizer

A comprehensive music-reactive LED visualizer that controls WLED strips over WiFi with advanced audio analysis, beat detection, and real-time web interface.

## Features

### 🎵 Audio Processing
- **Multiple Input Sources**: System audio, microphone, or MP3 files
- **Advanced Analysis**: Real-time FFT, frequency separation (bass/mids/highs)
- **Beat Detection**: Multi-method beat detection with tempo tracking
- **Cross-Platform**: Windows and Linux support

### 💡 LED Control
- **WLED Integration**: Full WLED API support with auto-discovery
- **High Performance**: 60 FPS updates with UDP communication
- **Flexible Configuration**: User-configurable LED count and brightness
- **Zone Support**: Define zones by percentage with independent effects

### 🎨 Visualization Effects
- **Spectrum Analyzer**: Classic rainbow spectrum with multiple color modes
- **Beat Flash**: Synchronized flashes on beat detection
- **Wave Patterns**: Moving waves with audio modulation
- **Fire Effect**: Realistic fire simulation with heat diffusion
- **Rainbow**: Smooth rainbow animations
- **Strobe**: Beat-synchronized strobing

### 🎯 Zone Management
- **Percentage-Based**: Define zones by start/end percentage (e.g., 25%-75%)
- **Independent Control**: Each zone can react to different frequencies
- **Effect Types**: Spectrum, flash, color change, moving patterns, gradients
- **Sensitivity Control**: Per-zone audio sensitivity adjustment

### 🌐 Web Interface
- **Real-Time Control**: Live audio visualization and LED preview
- **Modern UI**: Dark theme with glassmorphism effects
- **Complete Management**: Audio, LED, zone, and preset configuration
- **Performance Monitoring**: Live FPS, audio levels, and system stats

### 🎛️ Preset System
- **Built-in Presets**: Professional presets for different music styles
- **Custom Presets**: Save and load your own configurations
- **Categorization**: Organize presets by music type (ambient, party, etc.)
- **Import/Export**: Share presets between installations

## Quick Start

### Prerequisites
- Python 3.8+
- WLED device on the same network
- Audio input (system audio, microphone, or MP3 files)

### Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd circLights
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run CircLights:**
   ```bash
   python start.py
   ```

4. **Open the web interface:**
   - Navigate to `http://localhost:8080`
   - Configure your WLED device IP
   - Set up audio input
   - Create zones and enjoy!

### Configuration

#### WLED Setup
1. Flash your ESP32 with WLED firmware
2. Connect to your WiFi network
3. Note the device's IP address
4. Enter the IP in the CircLights web interface

#### Audio Setup
- **System Audio**: Captures audio output from your computer
- **Microphone**: Uses microphone input for live music
- **MP3 Files**: Load MP3/WAV files for testing (see MP3 Setup below)

#### MP3 Testing Setup
```bash
python start.py --setup-mp3
```
This creates a `music/` directory. Place your MP3 files there and select them in the web interface.

## Usage

### Basic Usage
1. Start CircLights: `python start.py`
2. Open web interface: `http://localhost:8080`
3. Configure WLED IP address
4. Select audio input source
5. Create zones or load presets
6. Enjoy your music visualization!

### Advanced Usage

#### Creating Zones
1. Click "Add Zone" in the web interface
2. Set start/end percentages (e.g., 0%-50% for first half)
3. Choose frequency range (bass, mids, highs, or all)
4. Select effect type and adjust sensitivity
5. Zone colors update in real-time on LED strip

#### Using Presets
- **Built-in Presets**: Load professional presets for different styles
- **Save Current**: Save your current configuration as a custom preset
- **Categories**: Browse presets by type (music, ambient, party)

#### Command Line Options
```bash
python start.py --help                 # Show all options
python start.py --debug               # Enable debug logging
python start.py --list-devices        # List available audio devices
python start.py --setup-mp3           # Create MP3 configuration
python start.py --config custom.yaml  # Use custom configuration
```

## Configuration

### Audio Configuration
```yaml
audio:
  sample_rate: 44100        # Audio sample rate
  buffer_size: 2048         # Buffer size (lower = less latency)
  enable_beat_detection: true
  target_fps: 60           # Processing frame rate
```

### LED Configuration
```yaml
led:
  led_count: 30            # Number of LEDs
  brightness: 255          # Global brightness (0-255)
  wled_ip: "192.168.1.100" # WLED device IP
  update_rate: 60          # LED update rate (FPS)
```

### Zone Configuration
```yaml
zones:
  - name: "Bass Zone"
    start_percent: 0.0     # Start at 0% of strip
    end_percent: 0.33      # End at 33% of strip
    frequency_range: "bass" # React to bass frequencies
    effect_type: "flash"   # Flash effect
    sensitivity: 1.5       # Audio sensitivity multiplier
```

## Project Structure

```
circLights/
├── src/
│   ├── audio/           # Audio processing and beat detection
│   ├── config/          # Configuration and preset management
│   ├── effects/         # Visualization effects
│   ├── led/            # WLED communication
│   ├── utils/          # Zone management utilities
│   └── web/            # Web server and API
├── web/
│   ├── static/         # CSS, JavaScript, assets
│   └── templates/      # HTML templates
├── configs/            # Configuration files
│   ├── presets/       # Preset storage
│   └── backups/       # Configuration backups
├── logs/              # Application logs
└── music/             # MP3 files for testing
```

## API Reference

### REST API Endpoints

#### System Status
- `GET /api/status` - Get complete system status
- `GET /api/audio/devices` - List available audio devices

#### Audio Control
- `POST /api/audio/device` - Set audio input device
- `POST /api/audio/mp3` - Set MP3 file input
- `POST /api/audio/mp3/control` - Control MP3 playback

#### LED Control
- `POST /api/led/config` - Configure LED settings
- `POST /api/zones` - Create new zone
- `DELETE /api/zones/{name}` - Delete zone
- `POST /api/zones/{name}/effect` - Set zone effect

#### Presets
- `GET /api/presets` - List available presets
- `POST /api/presets/{name}` - Load preset
- `PUT /api/presets/{name}` - Save preset

### WebSocket Events
- `realtime_update` - Live audio and LED data
- `status_update` - System status changes
- `zone_update` - Zone configuration changes

## Troubleshooting

### Common Issues

#### No Audio Input
- Check audio device selection in web interface
- Verify system audio is playing
- Try different audio devices with `--list-devices`

#### WLED Not Responding
- Verify WLED device IP address
- Check network connectivity
- Ensure WLED firmware is up to date

#### Poor Performance
- Reduce LED count or update rate
- Lower audio buffer size for better responsiveness
- Enable 30 FPS mode if system struggles with 60 FPS

#### Web Interface Not Loading
- Check if port 8080 is available
- Try different host/port in configuration
- Check firewall settings

### Performance Optimization

#### For Better Responsiveness
- Lower audio buffer size (1024 or 512)
- Reduce LED count
- Use UDP communication for WLED

#### For Smoother Effects
- Higher audio buffer size (4096)
- Enable smoothing in effects
- Use lower update rates (30 FPS)

## Development

### Adding Custom Effects
1. Create new effect class inheriting from `BaseEffect`
2. Implement `_generate_colors()` method
3. Register effect in `EffectsManager`

### Adding API Endpoints
1. Add route handler in `src/web/server.py`
2. Update web interface JavaScript
3. Test with both REST and WebSocket communication

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- WLED project for the excellent LED firmware
- librosa for audio analysis capabilities
- Flask-SocketIO for real-time web communication
- All contributors and users providing feedback

---

🎵 **Enjoy your music visualization with CircLights!** 🎵