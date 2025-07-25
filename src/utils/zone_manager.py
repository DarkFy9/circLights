"""
Zone management system for LED strip control
Handles zone creation, management, and audio mapping
"""

import logging
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from src.config.manager import ZoneConfig
from src.audio.processor import AudioFeatures

logger = logging.getLogger(__name__)


class FrequencyRange(Enum):
    """Frequency range options for zones"""
    ALL = "all"
    BASS = "bass"
    MIDS = "mids"  
    HIGHS = "highs"
    CUSTOM = "custom"


class EffectType(Enum):
    """Effect type options for zones"""
    SPECTRUM = "spectrum"
    FLASH = "flash"
    COLOR_CHANGE = "color_change"
    MOVING = "moving"
    SOLID = "solid"
    GRADIENT = "gradient"


@dataclass
class ZoneState:
    """Current state of a zone"""
    name: str
    colors: np.ndarray  # RGB values for each LED in zone
    brightness: float = 1.0
    last_update: float = 0.0
    effect_state: Dict[str, Any] = field(default_factory=dict)


class Zone:
    """Represents a controllable zone on the LED strip"""
    
    def __init__(self, config: ZoneConfig, led_count: int):
        self.config = config
        self.led_count = led_count
        
        # Calculate LED indices
        self.start_led = int(config.start_percent * led_count)
        self.end_led = int(config.end_percent * led_count)
        self.zone_size = self.end_led - self.start_led
        
        # Zone state
        self.state = ZoneState(
            name=config.name,
            colors=np.zeros((self.zone_size, 3), dtype=np.uint8)
        )
        
        # Audio processing
        self.frequency_range = FrequencyRange(config.frequency_range)
        self.effect_type = EffectType(config.effect_type)
        self.sensitivity = config.sensitivity
        
        # Effect-specific state
        self.flash_decay = 0.0
        self.color_change_target = [255, 255, 255]
        self.moving_position = 0.0
        self.moving_speed = 1.0
        self.gradient_colors = [[255, 0, 0], [0, 255, 0], [0, 0, 255]]
        
        logger.info(f"Zone '{config.name}' created: LEDs {self.start_led}-{self.end_led}")
        
    def update_led_count(self, led_count: int):
        """Update zone when total LED count changes"""
        self.led_count = led_count
        self.start_led = int(self.config.start_percent * led_count)
        self.end_led = int(self.config.end_percent * led_count)
        old_size = self.zone_size
        self.zone_size = self.end_led - self.start_led
        
        # Resize colors array if needed
        if self.zone_size != old_size:
            self.state.colors = np.resize(self.state.colors, (self.zone_size, 3))
            
    def get_frequency_value(self, features: AudioFeatures) -> float:
        """Extract frequency value based on zone's frequency range"""
        if self.frequency_range == FrequencyRange.BASS:
            return features.bass
        elif self.frequency_range == FrequencyRange.MIDS:
            return features.mids
        elif self.frequency_range == FrequencyRange.HIGHS:
            return features.highs
        elif self.frequency_range == FrequencyRange.ALL:
            return features.rms
        else:  # CUSTOM
            # Use custom frequency range from config
            custom_range = self.config.custom_params.get('frequency_range', [20, 20000])
            # Would need spectrum analysis for custom ranges
            return features.rms
            
    def update(self, features: AudioFeatures, dt: float):
        """Update zone based on audio features"""
        if not self.config.enabled:
            return
            
        # Get audio value for this zone's frequency range
        audio_value = self.get_frequency_value(features) * self.sensitivity
        
        # Apply effect based on type
        if self.effect_type == EffectType.SPECTRUM:
            self._update_spectrum_effect(features, audio_value)
        elif self.effect_type == EffectType.FLASH:
            self._update_flash_effect(features, audio_value, dt)
        elif self.effect_type == EffectType.COLOR_CHANGE:
            self._update_color_change_effect(features, audio_value)
        elif self.effect_type == EffectType.MOVING:
            self._update_moving_effect(features, audio_value, dt)
        elif self.effect_type == EffectType.SOLID:
            self._update_solid_effect(audio_value)
        elif self.effect_type == EffectType.GRADIENT:
            self._update_gradient_effect(audio_value)
            
    def _update_spectrum_effect(self, features: AudioFeatures, audio_value: float):
        """Update spectrum visualizer effect"""
        # Simple spectrum: map audio value to brightness across zone
        max_brightness = min(255, int(audio_value * 255))
        
        # Create rainbow colors across zone
        colors = []
        for i in range(self.zone_size):
            hue = (i / max(1, self.zone_size - 1)) * 360  # Spread across hue spectrum
            brightness = max_brightness * (0.3 + 0.7 * (i / max(1, self.zone_size - 1)))
            
            # Convert HSV to RGB
            rgb = self._hsv_to_rgb(hue, 1.0, brightness / 255.0)
            colors.append(rgb)
            
        self.state.colors = np.array(colors, dtype=np.uint8)
        
    def _update_flash_effect(self, features: AudioFeatures, audio_value: float, dt: float):
        """Update flash effect"""
        flash_threshold = self.config.custom_params.get('threshold', 0.7)
        flash_color = self.config.custom_params.get('color', [255, 255, 255])
        decay_time = self.config.custom_params.get('decay_time', 0.5)
        
        # Trigger flash on audio spike
        if audio_value > flash_threshold:
            self.flash_decay = 1.0
            
        # Apply flash with decay
        if self.flash_decay > 0:
            brightness = self.flash_decay
            color = [int(c * brightness) for c in flash_color]
            self.state.colors.fill(0)
            self.state.colors[:] = color
            
            # Decay over time
            self.flash_decay -= dt / decay_time
            self.flash_decay = max(0, self.flash_decay)
        else:
            self.state.colors.fill(0)
            
    def _update_color_change_effect(self, features: AudioFeatures, audio_value: float):
        """Update color change effect"""
        threshold = self.config.custom_params.get('threshold', 0.5)
        
        if audio_value > threshold:
            # Change to random color
            self.color_change_target = [
                np.random.randint(0, 256),
                np.random.randint(0, 256), 
                np.random.randint(0, 256)
            ]
            
        # Set zone to target color with audio-controlled brightness
        brightness = min(1.0, audio_value)
        color = [int(c * brightness) for c in self.color_change_target]
        self.state.colors[:] = color
        
    def _update_moving_effect(self, features: AudioFeatures, audio_value: float, dt: float):
        """Update moving pattern effect"""
        base_speed = self.config.custom_params.get('base_speed', 1.0)
        pattern_width = self.config.custom_params.get('pattern_width', 3)
        
        # Speed increases with audio
        self.moving_speed = base_speed * (1 + audio_value * 2)
        
        # Update position
        self.moving_position += self.moving_speed * dt
        if self.moving_position >= self.zone_size:
            self.moving_position -= self.zone_size
            
        # Create moving pattern
        self.state.colors.fill(0)
        center = int(self.moving_position)
        
        for i in range(max(0, center - pattern_width), 
                      min(self.zone_size, center + pattern_width + 1)):
            distance = abs(i - center)
            brightness = max(0, 1.0 - distance / pattern_width) * audio_value * 255
            
            # Rainbow color based on position
            hue = (i / max(1, self.zone_size - 1)) * 360
            rgb = self._hsv_to_rgb(hue, 1.0, brightness / 255.0)
            self.state.colors[i] = rgb
            
    def _update_solid_effect(self, audio_value: float):
        """Update solid color effect"""
        color = self.config.custom_params.get('color', [255, 255, 255])
        brightness = min(1.0, audio_value)
        
        final_color = [int(c * brightness) for c in color]
        self.state.colors[:] = final_color
        
    def _update_gradient_effect(self, audio_value: float):
        """Update gradient effect"""
        colors = self.config.custom_params.get('colors', self.gradient_colors)
        
        if len(colors) < 2:
            colors = [[255, 0, 0], [0, 0, 255]]  # Default red to blue
            
        # Create gradient across zone
        for i in range(self.zone_size):
            position = i / max(1, self.zone_size - 1)
            
            # Find which two colors to interpolate between
            segment = position * (len(colors) - 1)
            idx1 = int(segment)
            idx2 = min(idx1 + 1, len(colors) - 1)
            blend = segment - idx1
            
            # Interpolate colors
            color1 = colors[idx1]
            color2 = colors[idx2]
            
            r = int(color1[0] * (1 - blend) + color2[0] * blend)
            g = int(color1[1] * (1 - blend) + color2[1] * blend)
            b = int(color1[2] * (1 - blend) + color2[2] * blend)
            
            # Apply audio-controlled brightness
            brightness = min(1.0, audio_value)
            self.state.colors[i] = [int(r * brightness), int(g * brightness), int(b * brightness)]
            
    def _hsv_to_rgb(self, h: float, s: float, v: float) -> Tuple[int, int, int]:
        """Convert HSV to RGB"""
        h = h % 360
        c = v * s
        x = c * (1 - abs((h / 60) % 2 - 1))
        m = v - c
        
        if 0 <= h < 60:
            r, g, b = c, x, 0
        elif 60 <= h < 120:
            r, g, b = x, c, 0
        elif 120 <= h < 180:
            r, g, b = 0, c, x
        elif 180 <= h < 240:
            r, g, b = 0, x, c
        elif 240 <= h < 300:
            r, g, b = x, 0, c
        else:
            r, g, b = c, 0, x
            
        return int((r + m) * 255), int((g + m) * 255), int((b + m) * 255)
        
    def set_custom_colors(self, colors: np.ndarray):
        """Set custom colors for the zone"""
        if len(colors) == self.zone_size:
            self.state.colors = colors.astype(np.uint8)
        else:
            # Resize colors to fit zone
            self.state.colors = np.resize(colors, (self.zone_size, 3)).astype(np.uint8)
            
    def get_colors(self) -> np.ndarray:
        """Get current zone colors"""
        return self.state.colors.copy()
        
    def get_led_range(self) -> Tuple[int, int]:
        """Get LED range for this zone"""
        return self.start_led, self.end_led


class ZoneManager:
    """Manages all zones and their interactions"""
    
    def __init__(self, led_count: int = 30):
        self.led_count = led_count
        self.zones: List[Zone] = []
        self.zone_configs: List[ZoneConfig] = []
        
        # Combined output
        self.combined_colors = np.zeros((led_count, 3), dtype=np.uint8)
        
        logger.info(f"ZoneManager initialized with {led_count} LEDs")
        
    def add_zone(self, config: ZoneConfig) -> Zone:
        """Add a new zone"""
        zone = Zone(config, self.led_count)
        self.zones.append(zone)
        self.zone_configs.append(config)
        
        logger.info(f"Added zone '{config.name}'")
        return zone
        
    def remove_zone(self, name: str) -> bool:
        """Remove a zone by name"""
        for i, zone in enumerate(self.zones):
            if zone.config.name == name:
                del self.zones[i]
                del self.zone_configs[i]
                logger.info(f"Removed zone '{name}'")
                return True
        return False
        
    def get_zone(self, name: str) -> Optional[Zone]:
        """Get zone by name"""
        for zone in self.zones:
            if zone.config.name == name:
                return zone
        return None
        
    def update_led_count(self, led_count: int):
        """Update LED count for all zones"""
        self.led_count = led_count
        self.combined_colors = np.zeros((led_count, 3), dtype=np.uint8)
        
        for zone in self.zones:
            zone.update_led_count(led_count)
            
    def update_all_zones(self, features: AudioFeatures, dt: float):
        """Update all zones based on audio features"""
        # Clear combined output
        self.combined_colors.fill(0)
        
        # Update each zone
        for zone in self.zones:
            zone.update(features, dt)
            
            # Add zone colors to combined output
            start_led, end_led = zone.get_led_range()
            if start_led < len(self.combined_colors) and end_led <= len(self.combined_colors):
                # Use additive blending for overlapping zones
                zone_colors = zone.get_colors()
                self.combined_colors[start_led:end_led] = np.maximum(
                    self.combined_colors[start_led:end_led],
                    zone_colors
                )
                
    def get_combined_colors(self) -> np.ndarray:
        """Get combined colors from all zones"""
        return self.combined_colors.copy()
        
    def get_zone_list(self) -> List[Dict[str, Any]]:
        """Get list of all zones with their info"""
        zone_list = []
        for zone in self.zones:
            zone_list.append({
                'name': zone.config.name,
                'start_percent': zone.config.start_percent,
                'end_percent': zone.config.end_percent,
                'start_led': zone.start_led,
                'end_led': zone.end_led,
                'size': zone.zone_size,
                'enabled': zone.config.enabled,
                'frequency_range': zone.config.frequency_range,
                'effect_type': zone.config.effect_type,
                'sensitivity': zone.sensitivity
            })
        return zone_list
        
    def enable_zone(self, name: str, enabled: bool = True):
        """Enable/disable a zone"""
        zone = self.get_zone(name)
        if zone:
            zone.config.enabled = enabled
            logger.info(f"Zone '{name}' {'enabled' if enabled else 'disabled'}")
            
    def set_zone_sensitivity(self, name: str, sensitivity: float):
        """Set zone sensitivity"""
        zone = self.get_zone(name)
        if zone:
            zone.sensitivity = max(0.1, min(10.0, sensitivity))
            zone.config.sensitivity = zone.sensitivity
            logger.info(f"Zone '{name}' sensitivity set to {zone.sensitivity}")
            
    def set_zone_effect(self, name: str, effect_type: str, parameters: Dict[str, Any] = None):
        """Set zone effect type and parameters"""
        zone = self.get_zone(name)
        if zone:
            try:
                zone.effect_type = EffectType(effect_type)
                zone.config.effect_type = effect_type
                
                if parameters:
                    zone.config.custom_params.update(parameters)
                    
                logger.info(f"Zone '{name}' effect set to {effect_type}")
                return True
            except ValueError:
                logger.error(f"Invalid effect type: {effect_type}")
                
        return False
        
    def clear_all_zones(self):
        """Clear all zones"""
        self.zones.clear()
        self.zone_configs.clear()
        self.combined_colors.fill(0)
        logger.info("All zones cleared")
        
    def load_zones_from_config(self, zone_configs: List[ZoneConfig]):
        """Load zones from configuration"""
        self.clear_all_zones()
        
        for config in zone_configs:
            self.add_zone(config)
            
        logger.info(f"Loaded {len(zone_configs)} zones from configuration")