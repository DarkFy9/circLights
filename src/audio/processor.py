"""
Audio processing and analysis module
Handles real-time audio input, FFT analysis, and feature extraction
"""

import asyncio
import logging
import numpy as np
import threading
import time
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass

try:
    import sounddevice as sd
except ImportError:
    try:
        import pyaudio
        sd = None
    except ImportError:
        raise ImportError("Neither sounddevice nor pyaudio available")

import librosa
from scipy import signal
import queue
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class AudioFeatures:
    """Container for extracted audio features"""
    spectrum: np.ndarray  # FFT spectrum
    frequencies: np.ndarray  # Frequency bins
    rms: float  # Root mean square (volume)
    peak: float  # Peak amplitude
    centroid: float  # Spectral centroid
    rolloff: float  # Spectral rolloff
    zero_crossings: int  # Zero crossing rate
    mfcc: np.ndarray  # Mel-frequency cepstral coefficients
    
    # Frequency bands
    bass: float  # 20-250 Hz
    mids: float  # 250-4000 Hz  
    highs: float  # 4000-20000 Hz
    
    # Beat/rhythm
    tempo_confidence: float  # Beat tracking confidence
    onset_strength: float  # Onset detection strength


class AudioProcessor:
    """Real-time audio processor with advanced analysis"""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.led_controller = None
        self.effects_manager = None
        
        # Audio settings
        self.sample_rate = 44100
        self.buffer_size = 2048
        self.hop_length = 512
        self.n_fft = 2048
        
        # Audio input
        self.audio_stream = None
        self.input_device = None
        self.use_system_audio = True  # vs microphone
        
        # MP3 file input
        self.mp3_mode = False
        self.mp3_file_path = None
        self.mp3_data = None
        self.mp3_sample_rate = None
        self.mp3_position = 0
        self.mp3_paused = False
        self.mp3_loop = True
        
        # Processing
        self.running = False
        self.audio_thread = None
        self.audio_buffer = np.zeros(self.buffer_size)
        self.spectrum_buffer = []
        self.feature_history = []
        
        # Frequency band definitions (Hz)
        self.freq_bands = {
            'bass': (20, 250),
            'mids': (250, 4000), 
            'highs': (4000, 20000)
        }
        
        # Beat tracking
        self.tempo_tracker = None
        self.onset_detector = None
        self.beat_times = []
        
        # Callbacks
        self.feature_callbacks = []
        
        logger.info("AudioProcessor initialized")
        
    def set_led_controller(self, led_controller):
        """Set LED controller reference"""
        self.led_controller = led_controller
        
    def set_effects_manager(self, effects_manager):
        """Set effects manager reference"""
        self.effects_manager = effects_manager
        
    def add_feature_callback(self, callback: Callable[[AudioFeatures], None]):
        """Add callback for processed audio features"""
        self.feature_callbacks.append(callback)
        
    def get_audio_devices(self) -> Dict[int, Dict[str, Any]]:
        """Get available audio input devices"""
        devices = {}
        
        if sd:
            device_list = sd.query_devices()
            for i, device in enumerate(device_list):
                if device['max_input_channels'] > 0:
                    devices[i] = {
                        'name': device['name'],
                        'channels': device['max_input_channels'],
                        'sample_rate': device['default_samplerate']
                    }
        else:
            # PyAudio fallback
            p = pyaudio.PyAudio()
            for i in range(p.get_device_count()):
                info = p.get_device_info_by_index(i)
                if info['maxInputChannels'] > 0:
                    devices[i] = {
                        'name': info['name'],
                        'channels': info['maxInputChannels'],
                        'sample_rate': info['defaultSampleRate']
                    }
            p.terminate()
            
        return devices
        
    def set_input_device(self, device_id: Optional[int] = None, use_system_audio: bool = True):
        """Set audio input device"""
        self.input_device = device_id
        self.use_system_audio = use_system_audio
        self.mp3_mode = False
        logger.info(f"Audio input set to device {device_id}, system audio: {use_system_audio}")
        
    def set_mp3_input(self, file_path: str, loop: bool = True):
        """Set MP3 file as audio input"""
        try:
            if not Path(file_path).exists():
                logger.error(f"MP3 file not found: {file_path}")
                return False
                
            # Load MP3 file
            audio_data, sample_rate = librosa.load(file_path, sr=self.sample_rate, mono=True)
            
            self.mp3_file_path = file_path
            self.mp3_data = audio_data
            self.mp3_sample_rate = sample_rate
            self.mp3_position = 0
            self.mp3_loop = loop
            self.mp3_mode = True
            self.mp3_paused = False
            
            logger.info(f"MP3 input set: {file_path} ({len(audio_data)/sample_rate:.1f}s)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load MP3 file {file_path}: {e}")
            return False
            
    def mp3_play(self):
        """Resume MP3 playback"""
        if self.mp3_mode:
            self.mp3_paused = False
            logger.info("MP3 playback resumed")
            
    def mp3_pause(self):
        """Pause MP3 playback"""
        if self.mp3_mode:
            self.mp3_paused = True
            logger.info("MP3 playback paused")
            
    def mp3_stop(self):
        """Stop MP3 playback and reset position"""
        if self.mp3_mode:
            self.mp3_position = 0
            self.mp3_paused = False
            logger.info("MP3 playback stopped")
            
    def mp3_seek(self, position: float):
        """Seek to position in MP3 (0.0-1.0)"""
        if self.mp3_mode and self.mp3_data is not None:
            position = max(0.0, min(1.0, position))
            self.mp3_position = int(position * len(self.mp3_data))
            logger.info(f"MP3 seek to {position:.1%}")
            
    def get_mp3_status(self) -> Dict[str, Any]:
        """Get MP3 playback status"""
        if not self.mp3_mode or self.mp3_data is None:
            return {"enabled": False}
            
        total_duration = len(self.mp3_data) / self.mp3_sample_rate
        current_time = self.mp3_position / self.mp3_sample_rate
        
        return {
            "enabled": True,
            "file_path": self.mp3_file_path,
            "paused": self.mp3_paused,
            "loop": self.mp3_loop,
            "duration": total_duration,
            "current_time": current_time,
            "position": self.mp3_position / len(self.mp3_data) if len(self.mp3_data) > 0 else 0.0
        }
        
    def _audio_callback(self, indata, frames, time, status):
        """Audio stream callback for live input"""
        if status:
            logger.warning(f"Audio callback status: {status}")
            
        # Convert to mono if stereo
        if indata.ndim > 1:
            audio_data = np.mean(indata, axis=1)
        else:
            audio_data = indata.flatten()
            
        # Update buffer
        self.audio_buffer = audio_data.copy()
        
    def _get_mp3_audio_chunk(self) -> np.ndarray:
        """Get next audio chunk from MP3 data"""
        if not self.mp3_mode or self.mp3_data is None or self.mp3_paused:
            return np.zeros(self.buffer_size)
            
        # Get chunk from current position
        start_pos = self.mp3_position
        end_pos = start_pos + self.buffer_size
        
        if end_pos > len(self.mp3_data):
            if self.mp3_loop:
                # Loop back to beginning
                chunk = np.concatenate([
                    self.mp3_data[start_pos:],
                    self.mp3_data[:end_pos - len(self.mp3_data)]
                ])
                self.mp3_position = end_pos - len(self.mp3_data)
            else:
                # End of file, pad with zeros
                chunk = np.concatenate([
                    self.mp3_data[start_pos:],
                    np.zeros(end_pos - len(self.mp3_data))
                ])
                self.mp3_position = len(self.mp3_data)
        else:
            chunk = self.mp3_data[start_pos:end_pos]
            self.mp3_position = end_pos
            
        # Ensure correct length
        if len(chunk) < self.buffer_size:
            chunk = np.pad(chunk, (0, self.buffer_size - len(chunk)))
        elif len(chunk) > self.buffer_size:
            chunk = chunk[:self.buffer_size]
            
        return chunk
        
    def _process_audio_loop(self):
        """Main audio processing loop"""
        logger.info("Audio processing loop started")
        
        while self.running:
            try:
                # Get audio data based on input mode
                if self.mp3_mode:
                    audio_data = self._get_mp3_audio_chunk()
                else:
                    audio_data = self.audio_buffer.copy() if len(self.audio_buffer) > 0 else np.zeros(self.buffer_size)
                
                if len(audio_data) > 0:
                    features = self._extract_features(audio_data)
                    
                    # Store in history
                    self.feature_history.append(features)
                    if len(self.feature_history) > 100:  # Keep last 100 frames
                        self.feature_history.pop(0)
                    
                    # Call feature callbacks
                    for callback in self.feature_callbacks:
                        try:
                            callback(features)
                        except Exception as e:
                            logger.error(f"Feature callback error: {e}")
                            
                # Target 60 FPS processing
                time.sleep(1.0 / 60.0)
                
            except Exception as e:
                logger.error(f"Audio processing error: {e}")
                time.sleep(0.1)
                
        logger.info("Audio processing loop stopped")
        
    def _extract_features(self, audio_data: np.ndarray) -> AudioFeatures:
        """Extract audio features from buffer"""
        # Ensure minimum length
        if len(audio_data) < self.n_fft:
            audio_data = np.pad(audio_data, (0, self.n_fft - len(audio_data)))
            
        # Basic amplitude features
        rms = np.sqrt(np.mean(audio_data**2))
        peak = np.max(np.abs(audio_data))
        
        # FFT analysis
        fft = np.fft.rfft(audio_data, n=self.n_fft)
        spectrum = np.abs(fft)
        frequencies = np.fft.rfftfreq(self.n_fft, 1/self.sample_rate)
        
        # Spectral features
        centroid = np.sum(frequencies * spectrum) / np.sum(spectrum) if np.sum(spectrum) > 0 else 0
        rolloff = self._spectral_rolloff(spectrum, frequencies, 0.85)
        zero_crossings = librosa.zero_crossings(audio_data).sum()
        
        # MFCC features
        try:
            mfcc = librosa.feature.mfcc(y=audio_data.astype(np.float32), 
                                      sr=self.sample_rate, 
                                      n_mfcc=13)
            mfcc = np.mean(mfcc, axis=1)
        except:
            mfcc = np.zeros(13)
            
        # Frequency bands
        bass = self._get_band_energy(spectrum, frequencies, *self.freq_bands['bass'])
        mids = self._get_band_energy(spectrum, frequencies, *self.freq_bands['mids'])
        highs = self._get_band_energy(spectrum, frequencies, *self.freq_bands['highs'])
        
        # Onset detection
        onset_strength = self._detect_onset_strength(spectrum)
        
        return AudioFeatures(
            spectrum=spectrum,
            frequencies=frequencies,
            rms=rms,
            peak=peak,
            centroid=centroid,
            rolloff=rolloff,
            zero_crossings=zero_crossings,
            mfcc=mfcc,
            bass=bass,
            mids=mids,
            highs=highs,
            tempo_confidence=0.0,  # Will be implemented with beat tracking
            onset_strength=onset_strength
        )
        
    def _spectral_rolloff(self, spectrum: np.ndarray, frequencies: np.ndarray, rolloff_percent: float) -> float:
        """Calculate spectral rolloff frequency"""
        total_energy = np.sum(spectrum)
        if total_energy == 0:
            return 0
            
        cumulative_energy = np.cumsum(spectrum)
        rolloff_threshold = rolloff_percent * total_energy
        
        rolloff_idx = np.where(cumulative_energy >= rolloff_threshold)[0]
        if len(rolloff_idx) > 0:
            return frequencies[rolloff_idx[0]]
        return frequencies[-1]
        
    def _get_band_energy(self, spectrum: np.ndarray, frequencies: np.ndarray, 
                        low_freq: float, high_freq: float) -> float:
        """Get energy in frequency band"""
        band_mask = (frequencies >= low_freq) & (frequencies <= high_freq)
        return np.sum(spectrum[band_mask])
        
    def _detect_onset_strength(self, spectrum: np.ndarray) -> float:
        """Simple onset strength detection"""
        if len(self.spectrum_buffer) < 2:
            self.spectrum_buffer.append(spectrum)
            return 0.0
            
        # Keep last few spectra
        self.spectrum_buffer.append(spectrum)
        if len(self.spectrum_buffer) > 10:
            self.spectrum_buffer.pop(0)
            
        # Calculate spectral flux (change between frames)
        prev_spectrum = self.spectrum_buffer[-2]
        diff = spectrum - prev_spectrum
        onset_strength = np.sum(np.maximum(0, diff))  # Only positive changes
        
        return onset_strength
        
    async def start(self):
        """Start audio processing"""
        if self.running:
            logger.warning("AudioProcessor already running")
            return
            
        self.running = True
        logger.info("Starting AudioProcessor...")
        
        try:
            # Start audio stream (only if not in MP3 mode)
            if not self.mp3_mode:
                if sd:
                    self.audio_stream = sd.InputStream(
                        device=self.input_device,
                        channels=1,
                        samplerate=self.sample_rate,
                        blocksize=self.buffer_size,
                        callback=self._audio_callback
                    )
                    self.audio_stream.start()
                else:
                    # PyAudio fallback implementation would go here
                    logger.error("PyAudio implementation not complete")
                    return
            else:
                logger.info("Starting in MP3 file mode")
                
            # Start processing thread
            self.audio_thread = threading.Thread(target=self._process_audio_loop)
            self.audio_thread.daemon = True
            self.audio_thread.start()
            
            logger.info("AudioProcessor started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start AudioProcessor: {e}")
            self.running = False
            raise
            
    async def stop(self):
        """Stop audio processing"""
        if not self.running:
            return
            
        logger.info("Stopping AudioProcessor...")
        self.running = False
        
        # Stop audio stream
        if self.audio_stream:
            self.audio_stream.stop()
            self.audio_stream.close()
            self.audio_stream = None
            
        # Wait for processing thread
        if self.audio_thread and self.audio_thread.is_alive():
            self.audio_thread.join(timeout=2.0)
            
        logger.info("AudioProcessor stopped")
        
    def get_current_features(self) -> Optional[AudioFeatures]:
        """Get most recent audio features"""
        return self.feature_history[-1] if self.feature_history else None
        
    def get_feature_history(self, count: int = 10) -> list:
        """Get recent feature history"""
        return self.feature_history[-count:] if self.feature_history else []