#!/usr/bin/env python3
"""
CircLights - Music Reactive WLED Visualizer
Main application entry point
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

from src.config.manager import ConfigManager
from src.audio.processor import AudioProcessor
from src.led.controller import LEDController
from src.web.server import WebServer
from src.effects.manager import EffectsManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/circLights.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class CircLights:
    def __init__(self):
        self.config_manager = ConfigManager()
        self.audio_processor = None
        self.led_controller = None
        self.effects_manager = None
        self.web_server = None
        self.running = False
        
    async def initialize(self):
        """Initialize all components"""
        try:
            logger.info("Initializing CircLights...")
            
            # Load configuration
            await self.config_manager.load_config()
            
            # Initialize components
            self.audio_processor = AudioProcessor(self.config_manager)
            self.led_controller = LEDController(self.config_manager)
            self.effects_manager = EffectsManager(self.config_manager)
            self.web_server = WebServer(
                self.config_manager,
                self.audio_processor,
                self.led_controller,
                self.effects_manager
            )
            
            # Connect components
            self.audio_processor.set_led_controller(self.led_controller)
            self.audio_processor.set_effects_manager(self.effects_manager)
            
            logger.info("CircLights initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize CircLights: {e}")
            raise
            
    async def start(self):
        """Start the application"""
        try:
            self.running = True
            logger.info("Starting CircLights...")
            
            # Start all components
            tasks = [
                self.audio_processor.start(),
                self.led_controller.start(),
                self.web_server.start()
            ]
            
            await asyncio.gather(*tasks)
            
        except Exception as e:
            logger.error(f"Error starting CircLights: {e}")
            await self.stop()
            
    async def stop(self):
        """Stop the application gracefully"""
        if not self.running:
            return
            
        logger.info("Stopping CircLights...")
        self.running = False
        
        # Stop all components
        if self.audio_processor:
            await self.audio_processor.stop()
        if self.led_controller:
            await self.led_controller.stop()
        if self.web_server:
            await self.web_server.stop()
            
        # Save configuration
        if self.config_manager:
            await self.config_manager.save_config()
            
        logger.info("CircLights stopped")


async def main():
    """Main entry point"""
    # Create logs directory if it doesn't exist
    Path("logs").mkdir(exist_ok=True)
    
    app = CircLights()
    
    # Setup signal handlers for graceful shutdown
    def signal_handler():
        logger.info("Received shutdown signal")
        asyncio.create_task(app.stop())
    
    # Register signal handlers
    for sig in [signal.SIGTERM, signal.SIGINT]:
        signal.signal(sig, lambda s, f: signal_handler())
    
    try:
        await app.initialize()
        await app.start()
        
        # Keep running until stopped
        while app.running:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        await app.stop()


if __name__ == "__main__":
    asyncio.run(main())