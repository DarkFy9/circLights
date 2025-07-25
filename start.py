#!/usr/bin/env python3
"""
CircLights advanced startup script with initialization and preset installation
"""

import asyncio
import sys
import logging
import argparse
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.config.manager import ConfigManager
from src.config.presets import PresetManager
from src.audio.processor import AudioProcessor
from src.led.controller import LEDController
from src.effects.manager import EffectsManager
from src.web.server import WebServer
from src.utils.zone_manager import ZoneManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/circLights_startup.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


async def initialize_system():
    """Initialize CircLights system with all components"""
    logger.info("🎵 Initializing CircLights System...")
    
    # Create directories
    Path("logs").mkdir(exist_ok=True)
    Path("configs").mkdir(exist_ok=True)
    Path("configs/presets").mkdir(exist_ok=True)
    Path("configs/backups").mkdir(exist_ok=True)
    
    # Initialize configuration manager
    logger.info("📋 Loading configuration...")
    config_manager = ConfigManager()
    config = await config_manager.load_config()
    
    # Initialize preset manager and install built-ins
    logger.info("🎨 Setting up presets...")
    preset_manager = PresetManager(config_manager)
    await preset_manager.install_builtin_presets()
    
    # Initialize audio processor
    logger.info("🎤 Initializing audio system...")
    audio_processor = AudioProcessor(config_manager)
    
    # Get available audio devices
    devices = audio_processor.get_audio_devices()
    logger.info(f"Found {len(devices)} audio devices:")
    for device_id, device in devices.items():
        logger.info(f"  - {device_id}: {device['name']} ({device['channels']} channels)")
    
    # Initialize LED controller
    logger.info("💡 Initializing LED controller...")
    led_controller = LEDController(config_manager)
    
    # Initialize effects manager
    logger.info("✨ Setting up effects...")
    effects_manager = EffectsManager()
    effects_manager.create_default_effects()
    
    # Initialize zone manager
    logger.info("🎯 Setting up zones...")
    zone_manager = ZoneManager(led_count=config.led.led_count)
    if config.zones:
        zone_manager.load_zones_from_config(config.zones)
    else:
        # Create default zone if none exist
        from src.config.manager import ZoneConfig
        default_zone = ZoneConfig(
            name="Full Strip",
            start_percent=0.0,
            end_percent=1.0,
            frequency_range="all",
            effect_type="spectrum"
        )
        zone_manager.add_zone(default_zone)
        config_manager.add_zone(default_zone)
        await config_manager.save_config()
    
    # Initialize web server
    logger.info("🌐 Starting web interface...")
    web_server = WebServer(config_manager, audio_processor, led_controller, effects_manager)
    
    # Connect components
    audio_processor.set_led_controller(led_controller)
    audio_processor.set_effects_manager(effects_manager)
    
    components = {
        'config_manager': config_manager,
        'preset_manager': preset_manager,
        'audio_processor': audio_processor,
        'led_controller': led_controller,
        'effects_manager': effects_manager,
        'zone_manager': zone_manager,
        'web_server': web_server
    }
    
    logger.info("✅ System initialization complete!")
    return components


async def start_system(components):
    """Start all system components"""
    logger.info("🚀 Starting CircLights...")
    
    config = components['config_manager'].get_config()
    
    try:
        # Start components in order
        await components['audio_processor'].start()
        await components['led_controller'].start()
        
        # Set up audio callback for effects
        def audio_callback(features):
            try:
                # Update zones
                dt = 1.0 / 60.0
                components['zone_manager'].update_all_zones(features, None, dt)
                
                # Get combined colors from zones
                zone_colors = components['zone_manager'].get_combined_colors()
                
                # Update effects (if not using zones exclusively)
                # effect_colors = components['effects_manager'].update_effects(features, None, dt, config.led.led_count)
                
                # Send to LED controller (zones take priority)
                components['led_controller'].set_all_leds(zone_colors)
                asyncio.create_task(components['led_controller'].update_leds())
                
            except Exception as e:
                logger.error(f"Audio callback error: {e}")
        
        components['audio_processor'].add_feature_callback(audio_callback)
        
        # Start web server (this will block)
        logger.info(f"🌐 Web interface available at http://{config.web.host}:{config.web.port}")
        logger.info("📱 Open the web interface to control CircLights!")
        logger.info("🎵 System ready - enjoy your music visualization!")
        
        await components['web_server'].start()
        
    except Exception as e:
        logger.error(f"Failed to start system: {e}")
        await stop_system(components)
        raise


async def stop_system(components):
    """Stop all system components gracefully"""
    logger.info("🛑 Stopping CircLights...")
    
    # Stop components in reverse order
    if 'web_server' in components:
        await components['web_server'].stop()
    if 'led_controller' in components:
        await components['led_controller'].stop()
    if 'audio_processor' in components:
        await components['audio_processor'].stop()
        
    # Save configuration
    if 'config_manager' in components:
        await components['config_manager'].save_config()
        
    logger.info("✅ CircLights stopped gracefully")


def create_sample_mp3_config():
    """Create a sample MP3 configuration for testing"""
    sample_config = """
# Sample MP3 configuration for testing
# Place your MP3 files in a 'music' directory and update paths below

MP3_TEST_FILES = [
    "music/test_song.mp3",
    "music/electronic_track.mp3", 
    "music/rock_song.mp3"
]

# To use MP3 input:
# 1. Place MP3 files in the music directory
# 2. Start CircLights  
# 3. In the web interface, select "MP3 File" as input source
# 4. Choose your file and click play
    """
    
    music_dir = Path("music")
    music_dir.mkdir(exist_ok=True)
    
    with open("music/README.txt", "w") as f:
        f.write(sample_config)


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="CircLights - Music Reactive LED Visualizer")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--setup-mp3", action="store_true", help="Create sample MP3 configuration")
    parser.add_argument("--list-devices", action="store_true", help="List audio devices and exit")
    parser.add_argument("--config", type=str, help="Custom configuration file path")
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        
    if args.setup_mp3:
        create_sample_mp3_config()
        logger.info("📁 Created sample MP3 configuration in music/ directory")
        return
        
    # Initialize system
    components = await initialize_system()
    
    if args.list_devices:
        logger.info("Available audio devices:")
        devices = components['audio_processor'].get_audio_devices()
        for device_id, device in devices.items():
            print(f"  {device_id}: {device['name']} ({device['channels']} channels, {device['sample_rate']} Hz)")
        return
    
    # Load custom config if specified
    if args.config:
        config_path = Path(args.config)
        if config_path.exists():
            logger.info(f"Loading custom configuration: {config_path}")
            await components['config_manager'].load_config(str(config_path))
        else:
            logger.error(f"Configuration file not found: {config_path}")
            return
    
    # Setup signal handlers for graceful shutdown
    import signal
    
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}")
        asyncio.create_task(stop_system(components))
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await start_system(components)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"System error: {e}")
    finally:
        await stop_system(components)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 CircLights stopped by user")
    except Exception as e:
        print(f"❌ Failed to start CircLights: {e}")
        sys.exit(1)