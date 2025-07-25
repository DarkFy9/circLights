"""
Web server for CircLights live control interface
Provides real-time control and visualization via web interface
"""

import asyncio
import logging
import json
import time
from typing import Dict, Any, Optional
from pathlib import Path

from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit, disconnect
import eventlet

from src.config.manager import ConfigManager, ZoneConfig, EffectConfig
from src.audio.processor import AudioProcessor
from src.led.controller import LEDController
from src.utils.zone_manager import ZoneManager
from src.effects.manager import EffectsManager

logger = logging.getLogger(__name__)

# Monkey patch for eventlet
eventlet.monkey_patch()


class WebServer:
    """Flask-SocketIO web server for real-time control"""
    
    def __init__(self, config_manager: ConfigManager, audio_processor: AudioProcessor,
                 led_controller: LEDController, effects_manager: Optional['EffectsManager'] = None):
        
        self.config_manager = config_manager
        self.audio_processor = audio_processor
        self.led_controller = led_controller
        self.effects_manager = effects_manager
        
        # Zone manager
        self.zone_manager = ZoneManager(led_count=config_manager.config.led.led_count)
        
        # Flask app
        self.app = Flask(__name__, 
                        static_folder='../../web/static',
                        template_folder='../../web/templates')
        self.app.config['SECRET_KEY'] = 'circLights_secret_key_2024'
        
        # SocketIO
        self.socketio = SocketIO(self.app, cors_allowed_origins="*", async_mode='eventlet')
        
        # Server state
        self.running = False
        self.clients = set()
        self.update_task = None
        
        # Performance tracking
        self.last_update = 0.0
        self.update_rate = 30  # Hz for web updates (lower than LED updates)
        
        self._setup_routes()
        self._setup_socketio_events()
        
        logger.info("WebServer initialized")
        
    def _setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.route('/')
        def index():
            """Main control interface"""
            return render_template('index.html')
            
        @self.app.route('/api/status')
        def get_status():
            """Get system status"""
            config = self.config_manager.get_config()
            
            return jsonify({
                'audio': {
                    'devices': self.audio_processor.get_audio_devices(),
                    'current_device': self.audio_processor.input_device,
                    'system_audio': self.audio_processor.use_system_audio,
                    'mp3_status': self.audio_processor.get_mp3_status()
                },
                'led': {
                    'devices': self.led_controller.get_device_status(),
                    'led_count': self.led_controller.led_count,
                    'brightness': self.led_controller.brightness,
                    'performance': self.led_controller.get_performance_stats()
                },
                'zones': self.zone_manager.get_zone_list(),
                'presets': self.config_manager.get_preset_names(),
                'current_preset': config.current_preset if config else 'default'
            })
            
        @self.app.route('/api/audio/devices')
        def get_audio_devices():
            """Get available audio devices"""
            return jsonify(self.audio_processor.get_audio_devices())
            
        @self.app.route('/api/audio/device', methods=['POST'])
        def set_audio_device():
            """Set audio input device"""
            data = request.get_json()
            device_id = data.get('device_id')
            use_system_audio = data.get('use_system_audio', True)
            
            self.audio_processor.set_input_device(device_id, use_system_audio)
            self.config_manager.update_audio_config(
                input_device=device_id,
                use_system_audio=use_system_audio
            )
            
            return jsonify({'success': True})
            
        @self.app.route('/api/audio/mp3', methods=['POST'])
        def set_mp3_input():
            """Set MP3 file as input"""
            data = request.get_json()
            file_path = data.get('file_path', '')
            loop = data.get('loop', True)
            
            success = self.audio_processor.set_mp3_input(file_path, loop)
            if success:
                self.config_manager.update_audio_config(
                    enable_mp3_input=True,
                    mp3_file_path=file_path
                )
                
            return jsonify({'success': success})
            
        @self.app.route('/api/audio/mp3/control', methods=['POST'])
        def control_mp3():
            """Control MP3 playback"""
            data = request.get_json()
            action = data.get('action', '')
            
            if action == 'play':
                self.audio_processor.mp3_play()
            elif action == 'pause':
                self.audio_processor.mp3_pause()
            elif action == 'stop':
                self.audio_processor.mp3_stop()
            elif action == 'seek':
                position = data.get('position', 0.0)
                self.audio_processor.mp3_seek(position)
                
            return jsonify({'success': True})
            
        @self.app.route('/api/led/config', methods=['POST'])
        def set_led_config():
            """Set LED configuration"""
            data = request.get_json()
            
            if 'led_count' in data:
                self.led_controller.set_led_count(data['led_count'])
                self.zone_manager.update_led_count(data['led_count'])
                self.config_manager.update_led_config(led_count=data['led_count'])
                
            if 'brightness' in data:
                self.led_controller.set_brightness(data['brightness'])
                self.config_manager.update_led_config(brightness=data['brightness'])
                
            if 'wled_ip' in data:
                self.led_controller.set_primary_device(data['wled_ip'])
                self.config_manager.update_led_config(wled_ip=data['wled_ip'])
                
            return jsonify({'success': True})
            
        @self.app.route('/api/zones', methods=['GET'])
        def get_zones():
            """Get all zones"""
            return jsonify(self.zone_manager.get_zone_list())
            
        @self.app.route('/api/zones', methods=['POST'])
        def add_zone():
            """Add a new zone"""
            data = request.get_json()
            
            zone_config = ZoneConfig(
                name=data['name'],
                start_percent=data['start_percent'],
                end_percent=data['end_percent'],
                frequency_range=data.get('frequency_range', 'all'),
                effect_type=data.get('effect_type', 'spectrum'),
                sensitivity=data.get('sensitivity', 1.0),
                custom_params=data.get('custom_params', {})
            )
            
            zone = self.zone_manager.add_zone(zone_config)
            self.config_manager.add_zone(zone_config)
            
            return jsonify({'success': True, 'zone': {
                'name': zone.config.name,
                'start_led': zone.start_led,
                'end_led': zone.end_led
            }})
            
        @self.app.route('/api/zones/<zone_name>', methods=['DELETE'])
        def delete_zone(zone_name):
            """Delete a zone"""
            success = self.zone_manager.remove_zone(zone_name)
            if success:
                self.config_manager.remove_zone(zone_name)
                
            return jsonify({'success': success})
            
        @self.app.route('/api/zones/<zone_name>/effect', methods=['POST'])
        def set_zone_effect(zone_name):
            """Set zone effect"""
            data = request.get_json()
            effect_type = data.get('effect_type', 'spectrum')
            parameters = data.get('parameters', {})
            
            success = self.zone_manager.set_zone_effect(zone_name, effect_type, parameters)
            return jsonify({'success': success})
            
        @self.app.route('/api/zones/<zone_name>/enable', methods=['POST'])
        def enable_zone(zone_name):
            """Enable/disable zone"""
            data = request.get_json()
            enabled = data.get('enabled', True)
            
            self.zone_manager.enable_zone(zone_name, enabled)
            return jsonify({'success': True})
            
        @self.app.route('/api/presets')
        def get_presets():
            """Get available presets"""
            return jsonify(self.config_manager.get_preset_names())
            
        @self.app.route('/api/presets/<preset_name>', methods=['POST'])
        def load_preset(preset_name):
            """Load a preset"""
            success = asyncio.run(self.config_manager.load_preset(preset_name))
            if success:
                # Update zone manager with new configuration
                config = self.config_manager.get_config()
                self.zone_manager.load_zones_from_config(config.zones)
                
            return jsonify({'success': success})
            
        @self.app.route('/api/presets/<preset_name>', methods=['PUT'])
        def save_preset(preset_name):
            """Save current configuration as preset"""
            success = asyncio.run(self.config_manager.save_preset(preset_name))
            return jsonify({'success': success})
            
    def _setup_socketio_events(self):
        """Setup SocketIO event handlers"""
        
        @self.socketio.on('connect')
        def handle_connect():
            """Handle client connection"""
            self.clients.add(request.sid)
            logger.info(f"Client connected: {request.sid}")
            
            # Send initial status
            emit('status_update', self._get_realtime_status())
            
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """Handle client disconnection"""
            self.clients.discard(request.sid)
            logger.info(f"Client disconnected: {request.sid}")
            
        @self.socketio.on('request_status')
        def handle_status_request():
            """Handle status request"""
            emit('status_update', self._get_realtime_status())
            
        @self.socketio.on('zone_update')
        def handle_zone_update(data):
            """Handle zone update from client"""
            zone_name = data.get('name')
            if zone_name:
                zone = self.zone_manager.get_zone(zone_name)
                if zone:
                    if 'enabled' in data:
                        zone.config.enabled = data['enabled']
                    if 'sensitivity' in data:
                        zone.sensitivity = data['sensitivity']
                    if 'effect_type' in data:
                        zone.effect_type = data['effect_type']
                        
        @self.socketio.on('led_test')
        def handle_led_test(data):
            """Handle LED test pattern"""
            pattern = data.get('pattern', 'rainbow')
            
            if pattern == 'rainbow':
                self._test_rainbow_pattern()
            elif pattern == 'white':
                self._test_white_pattern()
            elif pattern == 'off':
                self.led_controller.clear_leds()
                asyncio.run(self.led_controller.update_leds(force=True))
                
    def _get_realtime_status(self) -> Dict[str, Any]:
        """Get real-time status for web interface"""
        features = self.audio_processor.get_current_features()
        
        status = {
            'timestamp': time.time(),
            'audio': {
                'rms': features.rms if features else 0.0,
                'peak': features.peak if features else 0.0,
                'bass': features.bass if features else 0.0,
                'mids': features.mids if features else 0.0,
                'highs': features.highs if features else 0.0,
                'mp3_status': self.audio_processor.get_mp3_status()
            },
            'led': {
                'performance': self.led_controller.get_performance_stats(),
                'device_status': self.led_controller.get_device_status()
            },
            'zones': []
        }
        
        # Add zone colors for visualization
        for zone in self.zone_manager.zones:
            zone_data = {
                'name': zone.config.name,
                'colors': zone.get_colors().tolist(),
                'enabled': zone.config.enabled,
                'start_led': zone.start_led,
                'end_led': zone.end_led
            }
            status['zones'].append(zone_data)
            
        return status
        
    def _test_rainbow_pattern(self):
        """Test with rainbow pattern"""
        import numpy as np
        
        colors = []
        for i in range(self.led_controller.led_count):
            hue = (i / max(1, self.led_controller.led_count - 1)) * 360
            # Simple HSV to RGB conversion
            c = 1.0  # saturation
            x = c * (1 - abs((hue / 60) % 2 - 1))
            
            if 0 <= hue < 60:
                r, g, b = c, x, 0
            elif 60 <= hue < 120:
                r, g, b = x, c, 0
            elif 120 <= hue < 180:
                r, g, b = 0, c, x
            elif 180 <= hue < 240:
                r, g, b = 0, x, c
            elif 240 <= hue < 300:
                r, g, b = x, 0, c
            else:
                r, g, b = c, 0, x
                
            colors.append([int(r * 255), int(g * 255), int(b * 255)])
            
        self.led_controller.set_all_leds(np.array(colors))
        asyncio.run(self.led_controller.update_leds(force=True))
        
    def _test_white_pattern(self):
        """Test with white pattern"""
        import numpy as np
        
        colors = np.full((self.led_controller.led_count, 3), 255, dtype=np.uint8)
        self.led_controller.set_all_leds(colors)
        asyncio.run(self.led_controller.update_leds(force=True))
        
    async def _realtime_update_loop(self):
        """Real-time update loop for web clients"""
        while self.running:
            try:
                current_time = time.time()
                
                # Rate limiting
                if (current_time - self.last_update) >= (1.0 / self.update_rate):
                    if self.clients:
                        status = self._get_realtime_status()
                        self.socketio.emit('realtime_update', status)
                        
                    self.last_update = current_time
                    
                await asyncio.sleep(1.0 / 120.0)  # 120 Hz check rate
                
            except Exception as e:
                logger.error(f"Realtime update error: {e}")
                await asyncio.sleep(1.0)
                
    async def start(self):
        """Start the web server"""
        if self.running:
            logger.warning("WebServer already running")
            return
            
        self.running = True
        config = self.config_manager.get_config()
        
        try:
            # Load zones from configuration
            if config and config.zones:
                self.zone_manager.load_zones_from_config(config.zones)
                
            # Register audio callback for zone updates
            self.audio_processor.add_feature_callback(self._audio_callback)
            
            # Start realtime update task
            self.update_task = asyncio.create_task(self._realtime_update_loop())
            
            # Start Flask-SocketIO server
            host = config.web.host if config else "0.0.0.0"
            port = config.web.port if config else 8080
            
            logger.info(f"Starting web server on http://{host}:{port}")
            
            # Run in separate thread to avoid blocking
            self.socketio.run(self.app, host=host, port=port, debug=False)
            
        except Exception as e:
            logger.error(f"Failed to start WebServer: {e}")
            self.running = False
            raise
            
    async def stop(self):
        """Stop the web server"""
        if not self.running:
            return
            
        logger.info("Stopping WebServer...")
        self.running = False
        
        # Stop update task
        if self.update_task:
            self.update_task.cancel()
            try:
                await self.update_task
            except asyncio.CancelledError:
                pass
                
        # Disconnect all clients
        for client_id in self.clients.copy():
            self.socketio.disconnect(client_id)
            
        self.clients.clear()
        logger.info("WebServer stopped")
        
    def _audio_callback(self, features):
        """Handle audio features for zone updates"""
        try:
            # Update zones with audio features
            dt = 1.0 / 60.0  # Assume 60 FPS
            self.zone_manager.update_all_zones(features, dt)
            
            # Send colors to LED controller
            combined_colors = self.zone_manager.get_combined_colors()
            self.led_controller.set_all_leds(combined_colors)
            
            # Update LEDs (async, will be rate limited)
            asyncio.create_task(self.led_controller.update_leds())
            
        except Exception as e:
            logger.error(f"Audio callback error: {e}")
            
    def get_app(self):
        """Get Flask app for testing"""
        return self.app
        
    def get_socketio(self):
        """Get SocketIO instance for testing"""
        return self.socketio