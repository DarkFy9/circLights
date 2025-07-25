"""
Advanced preset management with effect and zone integration
"""

import logging
import json
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

from src.config.manager import ConfigManager, ZoneConfig, EffectConfig

logger = logging.getLogger(__name__)


@dataclass
class PresetMetadata:
    """Metadata for presets"""
    name: str
    description: str = ""
    author: str = ""
    version: str = "1.0"
    tags: List[str] = None
    created_at: str = ""
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class PresetManager:
    """Advanced preset management with categorization and metadata"""
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.presets_dir = config_manager.presets_dir
        self.preset_categories = {
            'music': [],
            'ambient': [],
            'party': [],
            'custom': []
        }
        
        # Built-in presets
        self.builtin_presets = {}
        self._create_builtin_presets()
        
        logger.info("PresetManager initialized")
        
    def _create_builtin_presets(self):
        """Create built-in preset configurations"""
        
        # Classic Spectrum Preset
        spectrum_preset = {
            'metadata': PresetMetadata(
                name="Classic Spectrum",
                description="Traditional rainbow spectrum analyzer",
                author="CircLights",
                tags=["music", "spectrum", "rainbow"]
            ),
            'config': {
                'audio': {
                    'sample_rate': 44100,
                    'buffer_size': 2048,
                    'enable_beat_detection': True
                },
                'led': {
                    'led_count': 30,
                    'brightness': 255,
                    'update_rate': 60
                },
                'zones': [
                    {
                        'name': 'Full Strip',
                        'start_percent': 0.0,
                        'end_percent': 1.0,
                        'frequency_range': 'all',
                        'effect_type': 'spectrum',
                        'sensitivity': 1.0,
                        'custom_params': {
                            'color_mode': 'rainbow',
                            'height_scale': 2.0,
                            'smoothing': 0.3
                        }
                    }
                ],
                'effects': [
                    {
                        'name': 'Spectrum',
                        'type': 'spectrum',
                        'enabled': True,
                        'parameters': {
                            'color_mode': 'rainbow',
                            'height_scale': 2.0,
                            'smoothing': 0.3,
                            'mirror_mode': False
                        }
                    }
                ]
            }
        }
        
        # Beat Party Preset
        party_preset = {
            'metadata': PresetMetadata(
                name="Beat Party",
                description="High-energy beat-reactive effects",
                author="CircLights",
                tags=["party", "beats", "flash", "energy"]
            ),
            'config': {
                'audio': {
                    'sample_rate': 44100,
                    'buffer_size': 1024,  # Lower latency for beats
                    'enable_beat_detection': True
                },
                'led': {
                    'led_count': 30,
                    'brightness': 255,
                    'update_rate': 60
                },
                'zones': [
                    {
                        'name': 'Beat Flash',
                        'start_percent': 0.0,
                        'end_percent': 1.0,
                        'frequency_range': 'bass',
                        'effect_type': 'flash',
                        'sensitivity': 1.5,
                        'custom_params': {
                            'threshold': 0.6,
                            'color': [255, 255, 255],
                            'decay_time': 0.2
                        }
                    }
                ],
                'effects': [
                    {
                        'name': 'Beat Flash',
                        'type': 'beat_flash',
                        'enabled': True,
                        'parameters': {
                            'flash_color': [255, 0, 100],
                            'flash_duration': 0.15,
                            'min_confidence': 0.7
                        }
                    },
                    {
                        'name': 'Strobe',
                        'type': 'strobe',
                        'enabled': False,
                        'parameters': {
                            'strobe_rate': 12.0,
                            'beat_sync': True,
                            'duty_cycle': 0.1
                        }
                    }
                ]
            }
        }
        
        # Ambient Rainbow Preset
        ambient_preset = {
            'metadata': PresetMetadata(
                name="Ambient Rainbow",
                description="Smooth rainbow with subtle audio reactivity",
                author="CircLights",
                tags=["ambient", "rainbow", "smooth", "relaxing"]
            ),
            'config': {
                'audio': {
                    'sample_rate': 44100,
                    'buffer_size': 4096,  # Higher latency OK for ambient
                    'enable_beat_detection': False
                },
                'led': {
                    'led_count': 30,
                    'brightness': 180,  # Dimmer for ambient
                    'update_rate': 30   # Lower rate for smooth effect
                },
                'zones': [
                    {
                        'name': 'Rainbow Wave',
                        'start_percent': 0.0,
                        'end_percent': 1.0,
                        'frequency_range': 'all',
                        'effect_type': 'gradient',
                        'sensitivity': 0.3,
                        'custom_params': {
                            'colors': [[255, 0, 0], [255, 127, 0], [255, 255, 0], 
                                     [0, 255, 0], [0, 0, 255], [75, 0, 130], [148, 0, 211]]
                        }
                    }
                ],
                'effects': [
                    {
                        'name': 'Rainbow',
                        'type': 'rainbow',
                        'enabled': True,
                        'parameters': {
                            'speed': 0.5,
                            'density': 1.0,
                            'audio_reactive': True
                        }
                    }
                ]
            }
        }
        
        # Fire Effect Preset
        fire_preset = {
            'metadata': PresetMetadata(
                name="Fire Storm",
                description="Realistic fire effect with audio intensity",
                author="CircLights",
                tags=["fire", "realistic", "warm", "dynamic"]
            ),
            'config': {
                'audio': {
                    'sample_rate': 44100,
                    'buffer_size': 2048,
                    'enable_beat_detection': True
                },
                'led': {
                    'led_count': 30,
                    'brightness': 255,
                    'update_rate': 60
                },
                'zones': [
                    {
                        'name': 'Fire Base',
                        'start_percent': 0.0,
                        'end_percent': 1.0,
                        'frequency_range': 'bass',
                        'effect_type': 'solid',
                        'sensitivity': 2.0,
                        'custom_params': {
                            'color': [255, 50, 0]
                        }
                    }
                ],
                'effects': [
                    {
                        'name': 'Fire',
                        'type': 'fire',
                        'enabled': True,
                        'parameters': {
                            'cooling': 0.55,
                            'sparkling': 0.8,
                            'audio_intensity': True
                        }
                    }
                ]
            }
        }
        
        # Multi-Zone Preset
        multizone_preset = {
            'metadata': PresetMetadata(
                name="Multi-Zone Spectrum",
                description="Different frequency zones with unique effects",
                author="CircLights",
                tags=["multizone", "frequency", "advanced"]
            ),
            'config': {
                'audio': {
                    'sample_rate': 44100,
                    'buffer_size': 2048,
                    'enable_beat_detection': True
                },
                'led': {
                    'led_count': 30,
                    'brightness': 255,
                    'update_rate': 60
                },
                'zones': [
                    {
                        'name': 'Bass Zone',
                        'start_percent': 0.0,
                        'end_percent': 0.33,
                        'frequency_range': 'bass',
                        'effect_type': 'flash',
                        'sensitivity': 2.0,
                        'custom_params': {
                            'threshold': 0.4,
                            'color': [255, 0, 0],
                            'decay_time': 0.3
                        }
                    },
                    {
                        'name': 'Mid Zone', 
                        'start_percent': 0.33,
                        'end_percent': 0.67,
                        'frequency_range': 'mids',
                        'effect_type': 'spectrum',
                        'sensitivity': 1.0,
                        'custom_params': {
                            'color_mode': 'energy'
                        }
                    },
                    {
                        'name': 'High Zone',
                        'start_percent': 0.67,
                        'end_percent': 1.0,
                        'frequency_range': 'highs',
                        'effect_type': 'moving',
                        'sensitivity': 1.5,
                        'custom_params': {
                            'base_speed': 2.0,
                            'pattern_width': 2
                        }
                    }
                ],
                'effects': [
                    {
                        'name': 'Wave',
                        'type': 'wave',
                        'enabled': False,
                        'parameters': {
                            'wave_speed': 3.0,
                            'wave_width': 5,
                            'audio_modulation': True
                        }
                    }
                ]
            }
        }
        
        # Store built-in presets
        self.builtin_presets = {
            'Classic Spectrum': spectrum_preset,
            'Beat Party': party_preset,
            'Ambient Rainbow': ambient_preset,
            'Fire Storm': fire_preset,
            'Multi-Zone Spectrum': multizone_preset
        }
        
        # Categorize presets
        self.preset_categories['music'] = ['Classic Spectrum', 'Beat Party', 'Multi-Zone Spectrum']
        self.preset_categories['ambient'] = ['Ambient Rainbow']
        self.preset_categories['party'] = ['Beat Party', 'Fire Storm']
        
        logger.info(f"Created {len(self.builtin_presets)} built-in presets")
        
    async def install_builtin_presets(self):
        """Install built-in presets to disk"""
        for name, preset_data in self.builtin_presets.items():
            preset_file = self.presets_dir / f"{name.lower().replace(' ', '_')}.json"
            
            if not preset_file.exists():
                try:
                    # Convert to config format
                    config_data = preset_data['config']
                    metadata = asdict(preset_data['metadata'])
                    
                    # Add metadata to config
                    config_data['_metadata'] = metadata
                    
                    with open(preset_file, 'w') as f:
                        json.dump(config_data, f, indent=2)
                        
                    logger.info(f"Installed built-in preset: {name}")
                    
                except Exception as e:
                    logger.error(f"Failed to install preset {name}: {e}")
                    
    def get_preset_metadata(self, preset_name: str) -> Optional[PresetMetadata]:
        """Get metadata for a preset"""
        try:
            preset_file = self.presets_dir / f"{preset_name.lower().replace(' ', '_')}.json"
            if not preset_file.exists():
                return None
                
            with open(preset_file, 'r') as f:
                data = json.load(f)
                
            metadata_dict = data.get('_metadata', {})
            return PresetMetadata(**metadata_dict)
            
        except Exception as e:
            logger.error(f"Failed to load metadata for {preset_name}: {e}")
            return None
            
    def get_presets_by_category(self, category: str) -> List[str]:
        """Get presets in a specific category"""
        if category in self.preset_categories:
            return self.preset_categories[category].copy()
        return []
        
    def get_all_categories(self) -> List[str]:
        """Get all preset categories"""
        return list(self.preset_categories.keys())
        
    def search_presets(self, query: str, tags: List[str] = None) -> List[str]:
        """Search presets by name, description, or tags"""
        results = []
        
        # Get all available presets
        all_presets = self.config_manager.get_preset_names()
        
        for preset_name in all_presets:
            metadata = self.get_preset_metadata(preset_name)
            if not metadata:
                continue
                
            # Check name and description
            if query.lower() in preset_name.lower() or query.lower() in metadata.description.lower():
                results.append(preset_name)
                continue
                
            # Check tags
            if tags:
                if any(tag in metadata.tags for tag in tags):
                    results.append(preset_name)
                    continue
                    
            # Check metadata tags for query
            if any(query.lower() in tag.lower() for tag in metadata.tags):
                results.append(preset_name)
                
        return results
        
    async def create_preset_from_current(self, name: str, description: str = "", 
                                       tags: List[str] = None, author: str = "") -> bool:
        """Create preset from current system state"""
        try:
            # Get current configuration
            current_config = self.config_manager.get_config()
            if not current_config:
                logger.error("No current configuration to save")
                return False
                
            # Create metadata
            metadata = PresetMetadata(
                name=name,
                description=description,
                author=author,
                tags=tags or [],
                created_at=str(int(time.time()))
            )
            
            # Convert config to dict and add metadata
            config_dict = self.config_manager._config_to_dict(current_config)
            config_dict['_metadata'] = asdict(metadata)
            
            # Save preset
            preset_file = self.presets_dir / f"{name.lower().replace(' ', '_')}.json"
            with open(preset_file, 'w') as f:
                json.dump(config_dict, f, indent=2)
                
            logger.info(f"Created preset '{name}' from current state")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create preset from current state: {e}")
            return False
            
    def get_preset_info(self, preset_name: str) -> Optional[Dict[str, Any]]:
        """Get complete preset information including metadata"""
        try:
            preset_file = self.presets_dir / f"{preset_name.lower().replace(' ', '_')}.json"
            if not preset_file.exists():
                return None
                
            with open(preset_file, 'r') as f:
                data = json.load(f)
                
            metadata = data.get('_metadata', {})
            
            return {
                'name': preset_name,
                'metadata': metadata,
                'zones_count': len(data.get('zones', [])),
                'effects_count': len(data.get('effects', [])),
                'led_count': data.get('led', {}).get('led_count', 30),
                'has_beat_detection': data.get('audio', {}).get('enable_beat_detection', False)
            }
            
        except Exception as e:
            logger.error(f"Failed to get preset info for {preset_name}: {e}")
            return None
            
    async def export_presets(self, preset_names: List[str], export_path: str) -> bool:
        """Export selected presets to a file"""
        try:
            export_data = {
                'presets': {},
                'exported_at': str(int(time.time())),
                'version': '1.0'
            }
            
            for preset_name in preset_names:
                preset_file = self.presets_dir / f"{preset_name.lower().replace(' ', '_')}.json"
                if preset_file.exists():
                    with open(preset_file, 'r') as f:
                        preset_data = json.load(f)
                    export_data['presets'][preset_name] = preset_data
                    
            with open(export_path, 'w') as f:
                json.dump(export_data, f, indent=2)
                
            logger.info(f"Exported {len(export_data['presets'])} presets to {export_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export presets: {e}")
            return False
            
    async def import_presets(self, import_path: str) -> int:
        """Import presets from a file"""
        try:
            with open(import_path, 'r') as f:
                import_data = json.load(f)
                
            imported_count = 0
            presets = import_data.get('presets', {})
            
            for preset_name, preset_data in presets.items():
                preset_file = self.presets_dir / f"{preset_name.lower().replace(' ', '_')}.json"
                
                with open(preset_file, 'w') as f:
                    json.dump(preset_data, f, indent=2)
                    
                imported_count += 1
                
            logger.info(f"Imported {imported_count} presets from {import_path}")
            return imported_count
            
        except Exception as e:
            logger.error(f"Failed to import presets: {e}")
            return 0