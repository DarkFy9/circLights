"""
Effects manager for advanced visualization effects
Provides higher-level effects that can span multiple zones and integrate beat detection
"""

import logging
import numpy as np
import time
import math
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

from src.audio.processor import AudioFeatures
from src.audio.beat_detector import BeatInfo
from src.config.manager import EffectConfig

logger = logging.getLogger(__name__)


class EffectCategory(Enum):
    """Effect categories"""
    REACTIVE = "reactive"  # Audio-reactive effects
    AMBIENT = "ambient"   # Non-reactive ambient effects
    BEAT = "beat"        # Beat-synchronized effects
    TRANSITION = "transition"  # Transition effects between states


@dataclass
class EffectState:
    """State container for effects"""
    name: str
    active: bool = True
    parameters: Dict[str, Any] = field(default_factory=dict)
    last_update: float = 0.0
    
    # Internal state
    phase: float = 0.0
    intensity: float = 0.0
    color_index: float = 0.0
    beat_sync: bool = False


class BaseEffect:
    """Base class for all effects"""
    
    def __init__(self, name: str, config: EffectConfig):
        self.name = name
        self.config = config
        self.category = EffectCategory.REACTIVE
        self.state = EffectState(name)
        
        # Default parameters
        self.default_params = {
            'intensity': 1.0,
            'speed': 1.0,
            'color_scheme': 'rainbow',
            'smoothing': 0.3
        }
        
        # Merge config parameters
        self.parameters = {**self.default_params, **config.parameters}
        self.state.parameters = self.parameters
        
    def update(self, features: AudioFeatures, beat_info: Optional[BeatInfo], 
               dt: float, led_count: int) -> np.ndarray:
        """Update effect and return LED colors"""
        self.state.last_update = time.time()
        return self._generate_colors(features, beat_info, dt, led_count)
        
    def _generate_colors(self, features: AudioFeatures, beat_info: Optional[BeatInfo], 
                        dt: float, led_count: int) -> np.ndarray:
        """Override this method in subclasses"""
        return np.zeros((led_count, 3), dtype=np.uint8)
        
    def set_parameter(self, key: str, value: Any):
        """Set effect parameter"""
        self.parameters[key] = value
        self.state.parameters[key] = value
        
    def get_parameter(self, key: str, default: Any = None) -> Any:
        """Get effect parameter"""
        return self.parameters.get(key, default)


class SpectrumEffect(BaseEffect):
    """Classic spectrum analyzer effect"""
    
    def __init__(self, name: str, config: EffectConfig):
        super().__init__(name, config)
        self.category = EffectCategory.REACTIVE
        
        self.default_params.update({
            'height_scale': 2.0,
            'frequency_range': 'all',
            'color_mode': 'rainbow',
            'mirror_mode': False,
            'peak_decay': 0.95
        })
        
        self.parameters = {**self.default_params, **config.parameters}
        self.peak_levels = None
        
    def _generate_colors(self, features: AudioFeatures, beat_info: Optional[BeatInfo], 
                        dt: float, led_count: int) -> np.ndarray:
        
        if self.peak_levels is None:
            self.peak_levels = np.zeros(led_count)
            
        colors = np.zeros((led_count, 3), dtype=np.uint8)
        
        # Get frequency data
        if hasattr(features, 'spectrum') and len(features.spectrum) > 0:
            # Downsample spectrum to LED count
            spectrum_bins = len(features.spectrum) // 2  # Use positive frequencies only
            led_per_bin = max(1, led_count // spectrum_bins)
            
            # Create spectrum levels
            spectrum_levels = []
            for i in range(led_count):
                bin_idx = min(i // led_per_bin, spectrum_bins - 1)
                level = features.spectrum[bin_idx] * self.get_parameter('height_scale', 2.0)
                spectrum_levels.append(level)
                
            spectrum_levels = np.array(spectrum_levels)
        else:
            # Fallback: create fake spectrum from audio features
            spectrum_levels = np.zeros(led_count)
            bass_leds = led_count // 4
            mid_leds = led_count // 2
            
            # Bass section
            spectrum_levels[:bass_leds] = features.bass * 2
            # Mid section  
            spectrum_levels[bass_leds:mid_leds] = features.mids * 1.5
            # High section
            spectrum_levels[mid_leds:] = features.highs * 1.2
            
        # Apply smoothing and peak hold
        peak_decay = self.get_parameter('peak_decay', 0.95)
        smoothing = self.get_parameter('smoothing', 0.3)
        
        # Update peaks with decay
        self.peak_levels = np.maximum(spectrum_levels, self.peak_levels * peak_decay)
        
        # Smooth the levels
        smooth_levels = (smoothing * self.peak_levels + 
                        (1 - smoothing) * spectrum_levels)
        
        # Generate colors
        color_mode = self.get_parameter('color_mode', 'rainbow')
        mirror_mode = self.get_parameter('mirror_mode', False)
        
        for i in range(led_count):
            level = smooth_levels[i]
            
            if color_mode == 'rainbow':
                hue = (i / max(1, led_count - 1)) * 360
                if mirror_mode and i > led_count // 2:
                    hue = ((led_count - i - 1) / max(1, led_count - 1)) * 360
                    
                brightness = min(1.0, level)
                colors[i] = self._hsv_to_rgb(hue, 1.0, brightness)
                
            elif color_mode == 'mono':
                base_color = self.get_parameter('base_color', [255, 100, 0])
                brightness = min(1.0, level)
                colors[i] = [int(c * brightness) for c in base_color]
                
            elif color_mode == 'energy':
                # Color based on energy level
                if level < 0.3:
                    colors[i] = [0, int(255 * level / 0.3), 255]  # Blue to cyan
                elif level < 0.7:
                    colors[i] = [0, 255, int(255 * (0.7 - level) / 0.4)]  # Cyan to green
                else:
                    colors[i] = [int(255 * (level - 0.7) / 0.3), 255, 0]  # Green to yellow
                    
        return colors


class BeatFlashEffect(BaseEffect):
    """Flash effect synchronized to beats"""
    
    def __init__(self, name: str, config: EffectConfig):
        super().__init__(name, config)
        self.category = EffectCategory.BEAT
        
        self.default_params.update({
            'flash_duration': 0.2,
            'flash_color': [255, 255, 255],
            'background_color': [0, 0, 0],
            'min_confidence': 0.5,
            'fade_mode': 'exponential'  # 'linear', 'exponential'
        })
        
        self.parameters = {**self.default_params, **config.parameters}
        self.flash_time = 0.0
        
    def _generate_colors(self, features: AudioFeatures, beat_info: Optional[BeatInfo], 
                        dt: float, led_count: int) -> np.ndarray:
        
        colors = np.zeros((led_count, 3), dtype=np.uint8)
        flash_color = self.get_parameter('flash_color', [255, 255, 255])
        background_color = self.get_parameter('background_color', [0, 0, 0])
        flash_duration = self.get_parameter('flash_duration', 0.2)
        min_confidence = self.get_parameter('min_confidence', 0.5)
        fade_mode = self.get_parameter('fade_mode', 'exponential')
        
        # Check for beat
        if beat_info and beat_info.is_beat and beat_info.confidence >= min_confidence:
            self.flash_time = flash_duration
            
        # Apply flash with fade
        if self.flash_time > 0:
            fade_progress = self.flash_time / flash_duration
            
            if fade_mode == 'exponential':
                brightness = fade_progress ** 0.5  # Exponential fade
            else:
                brightness = fade_progress  # Linear fade
                
            # Interpolate between flash and background color
            for i in range(led_count):
                color = [
                    int(background_color[j] + (flash_color[j] - background_color[j]) * brightness)
                    for j in range(3)
                ]
                colors[i] = color
                
            self.flash_time -= dt
            self.flash_time = max(0, self.flash_time)
        else:
            # Background color
            colors[:] = background_color
            
        return colors


class WaveEffect(BaseEffect):
    """Wave patterns that move across the strip"""
    
    def __init__(self, name: str, config: EffectConfig):
        super().__init__(name, config)
        self.category = EffectCategory.REACTIVE
        
        self.default_params.update({
            'wave_speed': 2.0,
            'wave_width': 5,
            'wave_count': 1,
            'color_cycle_speed': 1.0,
            'audio_modulation': True
        })
        
        self.parameters = {**self.default_params, **config.parameters}
        
    def _generate_colors(self, features: AudioFeatures, beat_info: Optional[BeatInfo], 
                        dt: float, led_count: int) -> np.ndarray:
        
        colors = np.zeros((led_count, 3), dtype=np.uint8)
        
        wave_speed = self.get_parameter('wave_speed', 2.0)
        wave_width = self.get_parameter('wave_width', 5)
        wave_count = self.get_parameter('wave_count', 1)
        color_cycle_speed = self.get_parameter('color_cycle_speed', 1.0)
        audio_modulation = self.get_parameter('audio_modulation', True)
        
        # Update phase
        speed_mod = 1.0
        if audio_modulation:
            speed_mod = 1.0 + features.rms * 2.0
            
        self.state.phase += wave_speed * speed_mod * dt
        self.state.color_index += color_cycle_speed * dt * 60  # Color cycle
        
        # Generate waves
        for wave_idx in range(wave_count):
            wave_offset = (wave_idx / wave_count) * led_count
            
            for i in range(led_count):
                # Calculate wave position
                wave_pos = (self.state.phase + wave_offset) % led_count
                distance = min(abs(i - wave_pos), abs(i - wave_pos + led_count), 
                             abs(i - wave_pos - led_count))
                
                if distance <= wave_width:
                    # Calculate wave intensity
                    intensity = 1.0 - (distance / wave_width)
                    if audio_modulation:
                        intensity *= (0.5 + features.rms * 0.5)
                        
                    # Calculate color
                    hue = (self.state.color_index + wave_idx * 60) % 360
                    color = self._hsv_to_rgb(hue, 1.0, intensity)
                    
                    # Add to existing color (for multiple waves)
                    colors[i] = np.maximum(colors[i], color)
                    
        return colors


class RainbowEffect(BaseEffect):
    """Classic rainbow effect"""
    
    def __init__(self, name: str, config: EffectConfig):
        super().__init__(name, config)
        self.category = EffectCategory.AMBIENT
        
        self.default_params.update({
            'speed': 1.0,
            'density': 1.0,  # How many rainbows fit on strip
            'audio_reactive': False
        })
        
        self.parameters = {**self.default_params, **config.parameters}
        
    def _generate_colors(self, features: AudioFeatures, beat_info: Optional[BeatInfo], 
                        dt: float, led_count: int) -> np.ndarray:
        
        colors = np.zeros((led_count, 3), dtype=np.uint8)
        
        speed = self.get_parameter('speed', 1.0)
        density = self.get_parameter('density', 1.0)
        audio_reactive = self.get_parameter('audio_reactive', False)
        
        # Update phase
        self.state.phase += speed * dt * 360  # Degrees per second
        
        # Brightness modulation
        brightness = 1.0
        if audio_reactive:
            brightness = 0.3 + features.rms * 0.7
            
        for i in range(led_count):
            # Calculate hue with density and phase
            hue = (i / led_count * 360 * density + self.state.phase) % 360
            colors[i] = self._hsv_to_rgb(hue, 1.0, brightness)
            
        return colors


class FireEffect(BaseEffect):
    """Fire/flame effect"""
    
    def __init__(self, name: str, config: EffectConfig):
        super().__init__(name, config)
        self.category = EffectCategory.REACTIVE
        
        self.default_params.update({
            'cooling': 0.55,
            'sparkling': 0.8,
            'audio_intensity': True
        })
        
        self.parameters = {**self.default_params, **config.parameters}
        self.heat = None
        
    def _generate_colors(self, features: AudioFeatures, beat_info: Optional[BeatInfo], 
                        dt: float, led_count: int) -> np.ndarray:
        
        if self.heat is None:
            self.heat = np.zeros(led_count)
            
        colors = np.zeros((led_count, 3), dtype=np.uint8)
        
        cooling = self.get_parameter('cooling', 0.55)
        sparkling = self.get_parameter('sparkling', 0.8)
        audio_intensity = self.get_parameter('audio_intensity', True)
        
        # Cool down every cell a little
        cooldown = np.random.rand(led_count) * cooling * dt * 100
        self.heat = np.maximum(0, self.heat - cooldown)
        
        # Heat from each cell drifts up and diffuses slightly
        for i in range(led_count - 1, 1, -1):
            self.heat[i] = (self.heat[i - 1] + self.heat[i - 2] + self.heat[i - 2]) / 3
            
        # Randomly ignite new sparks of heat near bottom
        spark_probability = sparkling * dt * 10
        if audio_intensity:
            spark_probability *= (1 + features.rms * 2)
            
        if np.random.rand() < spark_probability:
            spark_pos = np.random.randint(0, min(3, led_count))
            self.heat[spark_pos] = np.random.rand() * 0.5 + 0.5
            
        # Convert heat to LED colors
        for i in range(led_count):
            heat_val = min(1.0, self.heat[i])
            
            if heat_val < 0.33:
                # Black to red
                colors[i] = [int(255 * heat_val * 3), 0, 0]
            elif heat_val < 0.66:
                # Red to yellow
                colors[i] = [255, int(255 * (heat_val - 0.33) * 3), 0]
            else:
                # Yellow to white
                white_amount = int(255 * (heat_val - 0.66) * 3)
                colors[i] = [255, 255, white_amount]
                
        return colors


class StrobeEffect(BaseEffect):
    """Strobe effect with beat sync"""
    
    def __init__(self, name: str, config: EffectConfig):
        super().__init__(name, config)
        self.category = EffectCategory.BEAT
        
        self.default_params.update({
            'strobe_rate': 10.0,  # Hz
            'strobe_color': [255, 255, 255],
            'background_color': [0, 0, 0],
            'beat_sync': True,
            'duty_cycle': 0.1  # Fraction of time light is on
        })
        
        self.parameters = {**self.default_params, **config.parameters}
        self.strobe_time = 0.0
        
    def _generate_colors(self, features: AudioFeatures, beat_info: Optional[BeatInfo], 
                        dt: float, led_count: int) -> np.ndarray:
        
        colors = np.zeros((led_count, 3), dtype=np.uint8)
        
        strobe_rate = self.get_parameter('strobe_rate', 10.0)
        strobe_color = self.get_parameter('strobe_color', [255, 255, 255])
        background_color = self.get_parameter('background_color', [0, 0, 0])
        beat_sync = self.get_parameter('beat_sync', True)
        duty_cycle = self.get_parameter('duty_cycle', 0.1)
        
        # Update strobe timing
        if beat_sync and beat_info and beat_info.is_beat:
            self.strobe_time = 0.0  # Reset on beat
        else:
            self.strobe_time += dt
            
        # Calculate strobe period
        period = 1.0 / strobe_rate
        phase = (self.strobe_time % period) / period
        
        # Apply strobe
        if phase < duty_cycle:
            colors[:] = strobe_color
        else:
            colors[:] = background_color
            
        return colors


class EffectsManager:
    """Manages and combines multiple effects"""
    
    def __init__(self):
        self.effects: Dict[str, BaseEffect] = {}
        self.active_effects: List[str] = []
        self.global_brightness = 1.0
        self.blend_mode = 'add'  # 'add', 'multiply', 'overlay'
        
        # Beat detection integration
        self.beat_detector = None
        
        logger.info("EffectsManager initialized")
        
    def register_effect(self, effect: BaseEffect):
        """Register a new effect"""
        self.effects[effect.name] = effect
        logger.info(f"Registered effect: {effect.name}")
        
    def create_default_effects(self):
        """Create default effect set"""
        from src.config.manager import EffectConfig
        
        # Spectrum analyzer
        spectrum_config = EffectConfig(
            name="Spectrum",
            type="spectrum",
            parameters={
                'color_mode': 'rainbow',
                'height_scale': 2.0,
                'smoothing': 0.3
            }
        )
        self.register_effect(SpectrumEffect("Spectrum", spectrum_config))
        
        # Beat flash
        flash_config = EffectConfig(
            name="Beat Flash",
            type="beat_flash",
            parameters={
                'flash_color': [255, 255, 255],
                'flash_duration': 0.15
            }
        )
        self.register_effect(BeatFlashEffect("Beat Flash", flash_config))
        
        # Wave effect
        wave_config = EffectConfig(
            name="Wave",
            type="wave",
            parameters={
                'wave_speed': 3.0,
                'wave_width': 4,
                'audio_modulation': True
            }
        )
        self.register_effect(WaveEffect("Wave", wave_config))
        
        # Rainbow
        rainbow_config = EffectConfig(
            name="Rainbow",
            type="rainbow",
            parameters={
                'speed': 1.0,
                'audio_reactive': False
            }
        )
        self.register_effect(RainbowEffect("Rainbow", rainbow_config))
        
        # Fire
        fire_config = EffectConfig(
            name="Fire",
            type="fire",
            parameters={
                'cooling': 0.6,
                'sparkling': 0.7,
                'audio_intensity': True
            }
        )
        self.register_effect(FireEffect("Fire", fire_config))
        
        # Strobe
        strobe_config = EffectConfig(
            name="Strobe",
            type="strobe",
            parameters={
                'strobe_rate': 8.0,
                'beat_sync': True,
                'duty_cycle': 0.2
            }
        )
        self.register_effect(StrobeEffect("Strobe", strobe_config))
        
        logger.info(f"Created {len(self.effects)} default effects")
        
    def activate_effect(self, name: str):
        """Activate an effect"""
        if name in self.effects and name not in self.active_effects:
            self.active_effects.append(name)
            self.effects[name].state.active = True
            logger.info(f"Activated effect: {name}")
            
    def deactivate_effect(self, name: str):
        """Deactivate an effect"""
        if name in self.active_effects:
            self.active_effects.remove(name)
            self.effects[name].state.active = False
            logger.info(f"Deactivated effect: {name}")
            
    def set_single_effect(self, name: str):
        """Activate single effect, deactivate all others"""
        self.active_effects.clear()
        for effect in self.effects.values():
            effect.state.active = False
            
        if name in self.effects:
            self.activate_effect(name)
            
    def update_effects(self, features: AudioFeatures, beat_info: Optional[BeatInfo], 
                      dt: float, led_count: int) -> np.ndarray:
        """Update all active effects and blend results"""
        
        if not self.active_effects:
            return np.zeros((led_count, 3), dtype=np.uint8)
            
        combined_colors = np.zeros((led_count, 3), dtype=float)
        
        # Update each active effect
        for effect_name in self.active_effects:
            if effect_name not in self.effects:
                continue
                
            effect = self.effects[effect_name]
            effect_colors = effect.update(features, beat_info, dt, led_count)
            
            # Blend effect into combined result
            if self.blend_mode == 'add':
                combined_colors += effect_colors.astype(float)
            elif self.blend_mode == 'multiply':
                combined_colors = combined_colors * (effect_colors.astype(float) / 255.0)
            elif self.blend_mode == 'overlay':
                # Simple overlay blend
                mask = effect_colors.sum(axis=1) > 0
                combined_colors[mask] = effect_colors[mask].astype(float)
                
        # Apply global brightness and clamp
        combined_colors *= self.global_brightness
        combined_colors = np.clip(combined_colors, 0, 255)
        
        return combined_colors.astype(np.uint8)
        
    def set_global_brightness(self, brightness: float):
        """Set global brightness multiplier"""
        self.global_brightness = max(0.0, min(1.0, brightness))
        
    def set_blend_mode(self, mode: str):
        """Set color blending mode"""
        if mode in ['add', 'multiply', 'overlay']:
            self.blend_mode = mode
            logger.info(f"Blend mode set to: {mode}")
            
    def get_effect_list(self) -> List[Dict[str, Any]]:
        """Get list of all effects with their info"""
        effect_list = []
        for name, effect in self.effects.items():
            effect_list.append({
                'name': name,
                'type': effect.__class__.__name__,
                'category': effect.category.value,
                'active': effect.state.active,
                'parameters': effect.parameters
            })
        return effect_list
        
    def get_active_effects(self) -> List[str]:
        """Get list of active effect names"""
        return self.active_effects.copy()
        
    def set_effect_parameter(self, effect_name: str, param_name: str, value: Any):
        """Set parameter for specific effect"""
        if effect_name in self.effects:
            self.effects[effect_name].set_parameter(param_name, value)
            logger.info(f"Set {effect_name}.{param_name} = {value}")
            
    def _hsv_to_rgb(self, h: float, s: float, v: float) -> np.ndarray:
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
            
        return np.array([int((r + m) * 255), int((g + m) * 255), int((b + m) * 255)], dtype=np.uint8)