import numpy as np
from typing import List, Optional

class AudioVisualizer:
    """Visualizes audio levels for both input and output streams"""
    def __init__(self, width: int = 40):
        self.width = width
        self.input_level = 0.0
        self.output_level = 0.0
        self.history: List[float] = []
        self.max_history = 100
        
    def update_input_level(self, audio_data: bytes) -> None:
        """Update input audio level from raw PCM16 data"""
        # Convert bytes to numpy array of 16-bit integers
        samples = np.frombuffer(audio_data, dtype=np.int16)
        # Calculate RMS value and normalize
        rms = np.sqrt(np.mean(samples.astype(np.float32)**2))
        self.input_level = min(1.0, rms / 32768.0)  # Normalize to 0-1
        self.history.append(self.input_level)
        if len(self.history) > self.max_history:
            self.history.pop(0)

    def update_output_level(self, audio_data: bytes) -> None:
        """Update output audio level from raw PCM16 data"""
        samples = np.frombuffer(audio_data, dtype=np.int16)
        rms = np.sqrt(np.mean(samples.astype(np.float32)**2))
        self.output_level = min(1.0, rms / 32768.0)

    def get_visualization(self) -> str:
        """Returns a string visualization of current audio levels"""
        in_bars = int(self.input_level * self.width)
        out_bars = int(self.output_level * self.width)
        
        in_viz = f"In  [{('|' * in_bars).ljust(self.width)}] {self.input_level:.2f}"
        out_viz = f"Out [{('|' * out_bars).ljust(self.width)}] {self.output_level:.2f}"
        
        return f"\r{in_viz}\n{out_viz}"

    def get_dynamic_duck_ratio(self) -> float:
        """Calculate dynamic ducking ratio based on recent audio history"""
        if not self.history:
            return 0.3  # Default ratio
            
        # Use recent history to determine baseline
        recent = self.history[-10:] if len(self.history) >= 10 else self.history
        baseline = np.mean(recent)
        
        # More aggressive ducking for louder input
        if baseline > 0.7:
            return 0.2  # Strong ducking
        elif baseline > 0.4:
            return 0.3  # Medium ducking
        else:
            return 0.4  # Light ducking
