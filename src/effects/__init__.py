"""
Effects module for CircLights
"""

from .manager import (
    EffectsManager, 
    BaseEffect,
    SpectrumEffect,
    BeatFlashEffect, 
    WaveEffect,
    RainbowEffect,
    FireEffect,
    StrobeEffect,
    EffectCategory,
    EffectState
)

__all__ = [
    'EffectsManager',
    'BaseEffect', 
    'SpectrumEffect',
    'BeatFlashEffect',
    'WaveEffect', 
    'RainbowEffect',
    'FireEffect',
    'StrobeEffect',
    'EffectCategory',
    'EffectState'
]