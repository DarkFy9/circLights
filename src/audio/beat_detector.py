"""
Advanced beat detection and tempo analysis
"""

import numpy as np
import logging
from typing import List, Tuple, Optional
from dataclasses import dataclass
from collections import deque

logger = logging.getLogger(__name__)


@dataclass 
class BeatInfo:
    """Beat detection result"""
    is_beat: bool
    confidence: float
    tempo: float
    beat_phase: float  # 0.0-1.0, position within beat cycle
    time_since_last_beat: float


class BeatDetector:
    """Real-time beat detection using multiple methods"""
    
    def __init__(self, sample_rate: int = 44100, hop_length: int = 512):
        self.sample_rate = sample_rate
        self.hop_length = hop_length
        
        # Onset detection
        self.onset_history = deque(maxlen=100)
        self.onset_threshold = 0.1
        self.adaptive_threshold = 0.1
        
        # Tempo tracking
        self.tempo_history = deque(maxlen=50)
        self.current_tempo = 120.0
        self.tempo_confidence = 0.0
        
        # Beat tracking
        self.beat_times = deque(maxlen=50)
        self.last_beat_time = 0.0
        self.beat_phase = 0.0
        
        # Energy-based detection
        self.energy_history = deque(maxlen=20)
        self.energy_threshold = 0.1
        
        # Frequency band analysis for beat detection
        self.bass_history = deque(maxlen=20)
        self.kick_detector_enabled = True
        
    def detect_beat(self, features, current_time: float) -> BeatInfo:
        """
        Detect beats using multiple methods and return combined result
        """
        # Update histories
        self.onset_history.append(features.onset_strength)
        self.energy_history.append(features.rms)
        self.bass_history.append(features.bass)
        
        # Method 1: Onset-based detection
        onset_beat = self._onset_beat_detection(features.onset_strength)
        
        # Method 2: Energy-based detection  
        energy_beat = self._energy_beat_detection(features.rms)
        
        # Method 3: Bass/kick detection
        bass_beat = self._bass_beat_detection(features.bass)
        
        # Method 4: Spectral flux detection
        spectral_beat = self._spectral_flux_detection(features.spectrum)
        
        # Combine methods
        beat_votes = [onset_beat, energy_beat, bass_beat, spectral_beat]
        beat_confidence = sum(beat_votes) / len(beat_votes)
        is_beat = beat_confidence > 0.5
        
        # Update tempo estimation
        if is_beat:
            self._update_tempo(current_time)
            
        # Update beat phase
        self._update_beat_phase(current_time)
        
        return BeatInfo(
            is_beat=is_beat,
            confidence=beat_confidence,
            tempo=self.current_tempo,
            beat_phase=self.beat_phase,
            time_since_last_beat=current_time - self.last_beat_time
        )
        
    def _onset_beat_detection(self, onset_strength: float) -> float:
        """Onset-based beat detection"""
        if len(self.onset_history) < 5:
            return 0.0
            
        # Adaptive threshold
        recent_onsets = list(self.onset_history)[-10:]
        mean_onset = np.mean(recent_onsets)
        std_onset = np.std(recent_onsets)
        
        self.adaptive_threshold = mean_onset + 1.5 * std_onset
        
        # Check if current onset exceeds threshold
        if onset_strength > self.adaptive_threshold and onset_strength > self.onset_threshold:
            # Check if enough time has passed since last beat (avoid double triggers)
            if len(self.beat_times) == 0 or (time.time() - self.beat_times[-1]) > 0.2:
                return 1.0
                
        return 0.0
        
    def _energy_beat_detection(self, rms: float) -> float:
        """Energy-based beat detection"""
        if len(self.energy_history) < 5:
            return 0.0
            
        # Look for energy spikes
        recent_energy = list(self.energy_history)
        if len(recent_energy) < 3:
            return 0.0
            
        current = recent_energy[-1]
        previous = recent_energy[-2]
        avg_recent = np.mean(recent_energy[-10:])
        
        # Detect significant energy increase
        energy_ratio = current / (avg_recent + 1e-10)
        energy_diff = current - previous
        
        if energy_ratio > 1.3 and energy_diff > 0.02:
            return min(energy_ratio - 1.0, 1.0)
            
        return 0.0
        
    def _bass_beat_detection(self, bass_energy: float) -> float:
        """Bass/kick drum detection"""
        if not self.kick_detector_enabled or len(self.bass_history) < 5:
            return 0.0
            
        # Bass energy spike detection
        recent_bass = list(self.bass_history)
        if len(recent_bass) < 3:
            return 0.0
            
        current = recent_bass[-1]
        avg_recent = np.mean(recent_bass[-10:])
        
        # Strong bass indicates kick drum
        bass_ratio = current / (avg_recent + 1e-10)
        
        if bass_ratio > 1.5 and current > 100:  # Threshold for bass energy
            return min((bass_ratio - 1.0) / 2.0, 1.0)
            
        return 0.0
        
    def _spectral_flux_detection(self, spectrum: np.ndarray) -> float:
        """Spectral flux-based beat detection"""
        if not hasattr(self, 'prev_spectrum'):
            self.prev_spectrum = spectrum
            return 0.0
            
        # Calculate spectral flux (sum of positive spectral differences)
        flux = np.sum(np.maximum(0, spectrum - self.prev_spectrum))
        self.prev_spectrum = spectrum
        
        if not hasattr(self, 'flux_history'):
            self.flux_history = deque(maxlen=20)
            
        self.flux_history.append(flux)
        
        if len(self.flux_history) < 5:
            return 0.0
            
        # Adaptive threshold for flux
        recent_flux = list(self.flux_history)
        mean_flux = np.mean(recent_flux)
        std_flux = np.std(recent_flux)
        
        threshold = mean_flux + 1.2 * std_flux
        
        if flux > threshold and flux > mean_flux * 1.3:
            return min((flux - threshold) / threshold, 1.0)
            
        return 0.0
        
    def _update_tempo(self, current_time: float):
        """Update tempo estimation from beat times"""
        self.beat_times.append(current_time) 
        self.last_beat_time = current_time
        
        if len(self.beat_times) < 3:
            return
            
        # Calculate intervals between recent beats
        beat_list = list(self.beat_times)
        intervals = []
        
        for i in range(1, min(len(beat_list), 10)):
            interval = beat_list[-i] - beat_list[-i-1]
            if 0.3 < interval < 2.0:  # Reasonable beat intervals (30-200 BPM)
                intervals.append(interval)
                
        if intervals:
            # Estimate tempo from intervals
            avg_interval = np.median(intervals)  # Use median for robustness
            estimated_tempo = 60.0 / avg_interval
            
            # Update tempo with smoothing
            alpha = 0.1  # Smoothing factor
            self.current_tempo = alpha * estimated_tempo + (1 - alpha) * self.current_tempo
            
            # Update confidence based on interval consistency
            interval_std = np.std(intervals)
            self.tempo_confidence = max(0, 1.0 - interval_std / avg_interval)
            
    def _update_beat_phase(self, current_time: float):
        """Update beat phase (position within beat cycle)"""
        if self.current_tempo <= 0:
            self.beat_phase = 0.0
            return
            
        beat_period = 60.0 / self.current_tempo
        time_since_beat = current_time - self.last_beat_time
        
        self.beat_phase = (time_since_beat % beat_period) / beat_period
        
    def get_tempo_confidence(self) -> float:
        """Get current tempo detection confidence"""
        return self.tempo_confidence
        
    def set_onset_threshold(self, threshold: float):
        """Set onset detection threshold"""
        self.onset_threshold = max(0.01, min(1.0, threshold))
        
    def enable_kick_detection(self, enabled: bool):
        """Enable/disable kick drum detection"""
        self.kick_detector_enabled = enabled
        
    def reset(self):
        """Reset all detection state"""
        self.onset_history.clear()
        self.energy_history.clear() 
        self.bass_history.clear()
        self.beat_times.clear()
        self.tempo_history.clear()
        
        self.last_beat_time = 0.0
        self.beat_phase = 0.0
        self.current_tempo = 120.0
        self.tempo_confidence = 0.0