"""
Configuration management system
Handles loading, saving, and managing application settings and presets
"""

import json
import yaml
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class AudioConfig:
    """Audio processing configuration"""
    sample_rate: int = 44100
    buffer_size: int = 2048
    input_device: Optional[int] = None
    use_system_audio: bool = True
    enable_mp3_input: bool = False
    mp3_file_path: str = ""
    target_fps: int = 60
    onset_threshold: float = 0.1
    enable_beat_detection: bool = True


@dataclass
class LEDConfig:
    """LED controller configuration"""
    led_count: int = 30
    brightness: int = 255
    update_rate: int = 60
    wled_ip: str = "192.168.1.100"
    wled_port: int = 80
    auto_discovery: bool = True
    use_udp: bool = True


@dataclass
class ZoneConfig:
    """Zone configuration"""
    name: str
    start_percent: float
    end_percent: float
    enabled: bool = True
    frequency_range: str = "all"  # "bass", "mids", "highs", "all"
    effect_type: str = "spectrum"  # "spectrum", "flash", "color_change", "moving"
    sensitivity: float = 1.0
    custom_params: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.custom_params is None:
            self.custom_params = {}


@dataclass
class EffectConfig:
    """Effect configuration"""
    name: str
    type: str
    enabled: bool = True
    parameters: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}


@dataclass
class WebConfig:
    """Web interface configuration"""
    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = False
    cors_enabled: bool = True
    websocket_enabled: bool = True


@dataclass
class AppConfig:
    """Main application configuration"""
    audio: AudioConfig
    led: LEDConfig
    web: WebConfig
    zones: List[ZoneConfig]
    effects: List[EffectConfig]
    current_preset: str = "default"
    auto_save: bool = True
    log_level: str = "INFO"


class ConfigManager:
    """Configuration manager with preset support"""
    
    def __init__(self, config_dir: str = "configs"):
        self.config_dir = Path(config_dir)
        self.presets_dir = self.config_dir / "presets"
        self.config_file = self.config_dir / "config.yaml"
        self.backup_dir = self.config_dir / "backups"
        
        # Ensure directories exist
        self.config_dir.mkdir(exist_ok=True)
        self.presets_dir.mkdir(exist_ok=True)
        self.backup_dir.mkdir(exist_ok=True)
        
        # Current configuration
        self.config: Optional[AppConfig] = None
        self.presets: Dict[str, AppConfig] = {}
        
        logger.info(f"ConfigManager initialized with config dir: {config_dir}")
        
    async def load_config(self, config_file: Optional[str] = None) -> AppConfig:
        """Load configuration from file"""
        config_path = Path(config_file) if config_file else self.config_file
        
        try:
            if config_path.exists():
                with open(config_path, 'r') as f:
                    if config_path.suffix.lower() == '.json':
                        data = json.load(f)
                    else:
                        data = yaml.safe_load(f)
                        
                self.config = self._dict_to_config(data)
                logger.info(f"Configuration loaded from {config_path}")
            else:
                self.config = self._create_default_config()
                await self.save_config()
                logger.info("Created default configuration")
                
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            self.config = self._create_default_config()
            
        # Load all presets
        await self._load_presets()
        
        return self.config
        
    async def save_config(self, config_file: Optional[str] = None):
        """Save current configuration to file"""
        if not self.config:
            logger.warning("No configuration to save")
            return
            
        config_path = Path(config_file) if config_file else self.config_file
        
        try:
            # Create backup
            if config_path.exists():
                backup_name = f"config_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.yaml"
                backup_path = self.backup_dir / backup_name
                config_path.rename(backup_path)
                
                # Keep only last 10 backups
                backups = sorted(self.backup_dir.glob("config_backup_*.yaml"))
                while len(backups) > 10:
                    backups[0].unlink()
                    backups.pop(0)
                    
            # Save configuration
            data = self._config_to_dict(self.config)
            
            with open(config_path, 'w') as f:
                yaml.dump(data, f, default_flow_style=False, indent=2)
                
            logger.info(f"Configuration saved to {config_path}")
            
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            
    def _create_default_config(self) -> AppConfig:
        """Create default configuration"""
        return AppConfig(
            audio=AudioConfig(),
            led=LEDConfig(),
            web=WebConfig(),
            zones=[
                ZoneConfig(
                    name="Full Strip",
                    start_percent=0.0,
                    end_percent=1.0,
                    frequency_range="all",
                    effect_type="spectrum"
                )
            ],
            effects=[
                EffectConfig(
                    name="Spectrum Analyzer",
                    type="spectrum",
                    parameters={
                        "color_mode": "rainbow",
                        "smoothing": 0.3,
                        "gain": 1.0
                    }
                ),
                EffectConfig(
                    name="Beat Flash",
                    type="flash",
                    parameters={
                        "threshold": 0.7,
                        "color": [255, 255, 255],
                        "decay_time": 0.5
                    }
                )
            ]
        )
        
    def _dict_to_config(self, data: Dict[str, Any]) -> AppConfig:
        """Convert dictionary to AppConfig"""
        try:
            audio_data = data.get('audio', {})
            led_data = data.get('led', {})
            web_data = data.get('web', {})
            zones_data = data.get('zones', [])
            effects_data = data.get('effects', [])
            
            return AppConfig(
                audio=AudioConfig(**audio_data),
                led=LEDConfig(**led_data),
                web=WebConfig(**web_data),
                zones=[ZoneConfig(**zone) for zone in zones_data],
                effects=[EffectConfig(**effect) for effect in effects_data],
                current_preset=data.get('current_preset', 'default'),
                auto_save=data.get('auto_save', True),
                log_level=data.get('log_level', 'INFO')
            )
        except Exception as e:
            logger.error(f"Error parsing config: {e}")
            return self._create_default_config()
            
    def _config_to_dict(self, config: AppConfig) -> Dict[str, Any]:
        """Convert AppConfig to dictionary"""
        return {
            'audio': asdict(config.audio),
            'led': asdict(config.led),
            'web': asdict(config.web),
            'zones': [asdict(zone) for zone in config.zones],
            'effects': [asdict(effect) for effect in config.effects],
            'current_preset': config.current_preset,
            'auto_save': config.auto_save,
            'log_level': config.log_level
        }
        
    async def _load_presets(self):
        """Load all presets from presets directory"""
        self.presets.clear()
        
        try:
            for preset_file in self.presets_dir.glob("*.yaml"):
                preset_name = preset_file.stem
                
                with open(preset_file, 'r') as f:
                    data = yaml.safe_load(f)
                    
                preset_config = self._dict_to_config(data)
                self.presets[preset_name] = preset_config
                
            logger.info(f"Loaded {len(self.presets)} presets")
            
        except Exception as e:
            logger.error(f"Error loading presets: {e}")
            
    async def save_preset(self, name: str, config: Optional[AppConfig] = None):
        """Save current configuration as preset"""
        if not config:
            config = self.config
            
        if not config:
            logger.warning("No configuration to save as preset")
            return False
            
        try:
            preset_file = self.presets_dir / f"{name}.yaml"
            data = self._config_to_dict(config)
            
            with open(preset_file, 'w') as f:
                yaml.dump(data, f, default_flow_style=False, indent=2)
                
            self.presets[name] = config
            logger.info(f"Preset '{name}' saved")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save preset '{name}': {e}")
            return False
            
    async def load_preset(self, name: str) -> bool:
        """Load a preset as current configuration"""
        if name not in self.presets:
            # Try to load from file
            preset_file = self.presets_dir / f"{name}.yaml"
            if preset_file.exists():
                try:
                    with open(preset_file, 'r') as f:
                        data = yaml.safe_load(f)
                    self.presets[name] = self._dict_to_config(data)
                except Exception as e:
                    logger.error(f"Failed to load preset file '{name}': {e}")
                    return False
            else:
                logger.warning(f"Preset '{name}' not found")
                return False
                
        self.config = self.presets[name]
        self.config.current_preset = name
        
        if self.config.auto_save:
            await self.save_config()
            
        logger.info(f"Loaded preset '{name}'")
        return True
        
    def get_preset_names(self) -> List[str]:
        """Get list of available preset names"""
        return list(self.presets.keys())
        
    def delete_preset(self, name: str) -> bool:
        """Delete a preset"""
        try:
            preset_file = self.presets_dir / f"{name}.yaml"
            if preset_file.exists():
                preset_file.unlink()
                
            if name in self.presets:
                del self.presets[name]
                
            logger.info(f"Preset '{name}' deleted")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete preset '{name}': {e}")
            return False
            
    def get_config(self) -> Optional[AppConfig]:
        """Get current configuration"""
        return self.config
        
    def update_audio_config(self, **kwargs):
        """Update audio configuration"""
        if self.config:
            for key, value in kwargs.items():
                if hasattr(self.config.audio, key):
                    setattr(self.config.audio, key, value)
                    
    def update_led_config(self, **kwargs):
        """Update LED configuration"""
        if self.config:
            for key, value in kwargs.items():
                if hasattr(self.config.led, key):
                    setattr(self.config.led, key, value)
                    
    def add_zone(self, zone_config: ZoneConfig):
        """Add a zone configuration"""
        if self.config:
            self.config.zones.append(zone_config)
            
    def remove_zone(self, name: str) -> bool:
        """Remove a zone by name"""
        if self.config:
            for i, zone in enumerate(self.config.zones):
                if zone.name == name:
                    del self.config.zones[i]
                    return True
        return False
        
    def get_zone_config(self, name: str) -> Optional[ZoneConfig]:
        """Get zone configuration by name"""
        if self.config:
            for zone in self.config.zones:
                if zone.name == name:
                    return zone
        return None
        
    def add_effect(self, effect_config: EffectConfig):
        """Add an effect configuration"""
        if self.config:
            self.config.effects.append(effect_config)
            
    def get_effect_config(self, name: str) -> Optional[EffectConfig]:
        """Get effect configuration by name"""
        if self.config:
            for effect in self.config.effects:
                if effect.name == name:
                    return effect
        return None
        
    async def export_config(self, file_path: str, include_presets: bool = True):
        """Export configuration to file"""
        try:
            export_data = {
                'config': self._config_to_dict(self.config) if self.config else None,
                'presets': {name: self._config_to_dict(preset) 
                           for name, preset in self.presets.items()} if include_presets else {},
                'exported_at': datetime.now().isoformat(),
                'version': '1.0'
            }
            
            with open(file_path, 'w') as f:
                if file_path.endswith('.json'):
                    json.dump(export_data, f, indent=2)
                else:
                    yaml.dump(export_data, f, default_flow_style=False, indent=2)
                    
            logger.info(f"Configuration exported to {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export config: {e}")
            return False
            
    async def import_config(self, file_path: str, import_presets: bool = True):
        """Import configuration from file"""
        try:
            with open(file_path, 'r') as f:
                if file_path.endswith('.json'):
                    data = json.load(f)
                else:
                    data = yaml.safe_load(f)
                    
            if 'config' in data and data['config']:
                self.config = self._dict_to_config(data['config'])
                
            if import_presets and 'presets' in data:
                for name, preset_data in data['presets'].items():
                    self.presets[name] = self._dict_to_config(preset_data)
                    
            logger.info(f"Configuration imported from {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to import config: {e}")
            return False