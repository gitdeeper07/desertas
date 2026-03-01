"""
Precursor Sequence Tracker
Tracks the multi-stage precursor sequence:

He_ratio onset (deep) → Γ_geo acceleration → Rn_pulse threshold (surface)

Mean sequence timing:
- He_ratio leads by 31 days
- Γ_geo accelerates within 14 days
- Rn_pulse confirms at 58 days mean lead time
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import json
import yaml
from pathlib import Path


class PrecursorStage(Enum):
    """Stages of precursor sequence."""
    NO_ANOMALY = "no_anomaly"
    HE_RATIO_ONSET = "he_ratio_onset"
    GAMMA_GEO_ACCEL = "gamma_geo_acceleration"
    RN_PULSE_THRESHOLD = "rn_pulse_threshold"
    ALL_STAGES = "all_stages"


@dataclass
class PrecursorConfig:
    """Configuration for precursor sequence tracking."""
    station_id: str
    
    # He_ratio thresholds
    he_ratio_background: float = 0.10
    he_ratio_elevated: float = 0.50
    he_ratio_high: float = 2.00
    
    # Γ_geo thresholds
    gamma_geo_acceleration_pct: float = 40.0  # 40% increase
    gamma_geo_window_days: int = 14
    
    # Rn_pulse thresholds
    rn_pulse_watch_sigma: float = 2.0
    rn_pulse_alert_sigma: float = 3.0
    rn_pulse_emergency_sigma: float = 4.0
    
    # Sequence timing
    he_ratio_lead_days: int = 31
    gamma_geo_window_before_rn: int = 14
    max_sequence_duration_days: int = 90
    
    # Confidence thresholds
    confidence_high: float = 0.8
    confidence_moderate: float = 0.6


class PrecursorSequencer:
    """
    Tracks multi-stage precursor sequence.
    
    Monitors He_ratio, Γ_geo, and Rn_pulse to identify
    the full precursor sequence leading to seismic events.
    """
    
    def __init__(self, config: PrecursorConfig):
        """
        Initialize precursor sequencer.
        
        Args:
            config: Precursor configuration
        """
        self.config = config
        self.sequence_history = []
        
    def analyze_he_ratio(
        self,
        he_series: np.ndarray,
        timestamps: np.ndarray
    ) -> Dict[str, Union[float, str, bool]]:
        """
        Analyze He_ratio time series for onset.
        
        Args:
            he_series: He_ratio time series
            timestamps: Timestamps in seconds
            
        Returns:
            He_ratio analysis results
        """
        if len(he_series) < 10:
            return {
                'stage': PrecursorStage.NO_ANOMALY.value,
                'he_ratio_status': 'insufficient_data'
            }
        
        # Calculate background (first half)
        mid = len(he_series) // 2
        background = np.median(he_series[:mid])
        current = he_series[-1]
        
        # Detect onset
        if current > self.config.he_ratio_high:
            status = 'mantle_connected'
            stage = PrecursorStage.HE_RATIO_ONSET
            confidence = 'high'
        elif current > self.config.he_ratio_elevated:
            status = 'deep_crustal'
            stage = PrecursorStage.HE_RATIO_ONSET
            confidence = 'moderate'
        elif current > self.config.he_ratio_background:
            status = 'elevated'
            stage = PrecursorStage.HE_RATIO_ONSET if current > background * 2 else PrecursorStage.NO_ANOMALY
            confidence = 'low' if current > background * 2 else 'none'
        else:
            status = 'background'
            stage = PrecursorStage.NO_ANOMALY
            confidence = 'none'
        
        # Calculate trend
        if len(he_series) > 10:
            recent = he_series[-10:]
            slope = np.polyfit(range(len(recent)), recent, 1)[0]
            trend = 'increasing' if slope > 0.01 else 'decreasing' if slope < -0.01 else 'stable'
        else:
            slope = 0
            trend = 'unknown'
        
        return {
            'stage': stage.value,
            'he_ratio_status': status,
            'current_value': float(current),
            'background': float(background),
            'elevation_ratio': float(current / background) if background > 0 else 0,
            'trend': trend,
            'slope': float(slope),
            'confidence': confidence,
            'timestamp': float(timestamps[-1]) if len(timestamps) > 0 else None
        }
    
    def analyze_gamma_geo(
        self,
        gamma_series: np.ndarray,
        timestamps: np.ndarray
    ) -> Dict[str, Union[float, str, bool]]:
        """
        Analyze Γ_geo time series for acceleration.
        
        Args:
            gamma_series: Γ_geo time series
            timestamps: Timestamps in seconds
            
        Returns:
            Γ_geo analysis results
        """
        if len(gamma_series) < self.config.gamma_geo_window_days:
            return {
                'stage': PrecursorStage.NO_ANOMALY.value,
                'gamma_geo_status': 'insufficient_data'
            }
        
        # Split into baseline and recent
        window_samples = self.config.gamma_geo_window_days * 24  # hours
        if len(gamma_series) > window_samples * 2:
            baseline = gamma_series[:-window_samples]
            recent = gamma_series[-window_samples:]
        else:
            baseline = gamma_series[:len(gamma_series)//2]
            recent = gamma_series[len(gamma_series)//2:]
        
        baseline_mean = np.mean(baseline)
        recent_mean = np.mean(recent)
        
        # Calculate acceleration
        if baseline_mean > 0:
            acceleration_pct = ((recent_mean - baseline_mean) / baseline_mean) * 100
        else:
            acceleration_pct = 0
        
        # Detect acceleration
        if acceleration_pct >= self.config.gamma_geo_acceleration_pct:
            status = 'accelerating'
            stage = PrecursorStage.GAMMA_GEO_ACCEL
            confidence = 'high' if acceleration_pct > 100 else 'moderate'
        elif acceleration_pct > 20:
            status = 'slightly_accelerating'
            stage = PrecursorStage.NO_ANOMALY
            confidence = 'low'
        else:
            status = 'stable'
            stage = PrecursorStage.NO_ANOMALY
            confidence = 'none'
        
        # Calculate trend
        slope = np.polyfit(range(len(recent)), recent, 1)[0]
        
        return {
            'stage': stage.value,
            'gamma_geo_status': status,
            'baseline_mean': float(baseline_mean),
            'recent_mean': float(recent_mean),
            'acceleration_pct': float(acceleration_pct),
            'slope': float(slope),
            'confidence': confidence,
            'timestamp': float(timestamps[-1]) if len(timestamps) > 0 else None
        }
    
    def analyze_rn_pulse(
        self,
        rn_series: np.ndarray,
        timestamps: np.ndarray
    ) -> Dict[str, Union[float, str, bool]]:
        """
        Analyze Rn_pulse time series for threshold crossing.
        
        Args:
            rn_series: Rn_pulse sigma values
            timestamps: Timestamps in seconds
            
        Returns:
            Rn_pulse analysis results
        """
        if len(rn_series) < 10:
            return {
                'stage': PrecursorStage.NO_ANOMALY.value,
                'rn_pulse_status': 'insufficient_data'
            }
        
        current = rn_series[-1]
        
        # Determine level
        if current >= self.config.rn_pulse_emergency_sigma:
            status = 'emergency'
            stage = PrecursorStage.RN_PULSE_THRESHOLD
            confidence = 'high'
        elif current >= self.config.rn_pulse_alert_sigma:
            status = 'alert'
            stage = PrecursorStage.RN_PULSE_THRESHOLD
            confidence = 'high'
        elif current >= self.config.rn_pulse_watch_sigma:
            status = 'watch'
            stage = PrecursorStage.RN_PULSE_THRESHOLD
            confidence = 'moderate'
        else:
            status = 'background'
            stage = PrecursorStage.NO_ANOMALY
            confidence = 'none'
        
        # Calculate trend
        if len(rn_series) > 10:
            recent = rn_series[-10:]
            slope = np.polyfit(range(len(recent)), recent, 1)[0]
            trend = 'increasing' if slope > 0.05 else 'decreasing' if slope < -0.05 else 'stable'
        else:
            slope = 0
            trend = 'unknown'
        
        return {
            'stage': stage.value,
            'rn_pulse_status': status,
            'current_sigma': float(current),
            'trend': trend,
            'slope': float(slope),
            'confidence': confidence,
            'timestamp': float(timestamps[-1]) if len(timestamps) > 0 else None
        }
    
    def track_sequence(
        self,
        he_series: np.ndarray,
        gamma_series: np.ndarray,
        rn_series: np.ndarray,
        timestamps: np.ndarray
    ) -> Dict[str, Union[str, float, Dict]]:
        """
        Track full precursor sequence.
        
        Args:
            he_series: He_ratio time series
            gamma_series: Γ_geo time series
            rn_series: Rn_pulse time series
            timestamps: Timestamps in seconds
            
        Returns:
            Sequence analysis results
        """
        # Analyze each parameter
        he_result = self.analyze_he_ratio(he_series, timestamps)
        gamma_result = self.analyze_gamma_geo(gamma_series, timestamps)
        rn_result = self.analyze_rn_pulse(rn_series, timestamps)
        
        # Determine current stage
        stages = [he_result['stage'], gamma_result['stage'], rn_result['stage']]
        
        if PrecursorStage.RN_PULSE_THRESHOLD.value in stages:
            current_stage = PrecursorStage.RN_PULSE_THRESHOLD
        elif PrecursorStage.GAMMA_GEO_ACCEL.value in stages:
            current_stage = PrecursorStage.GAMMA_GEO_ACCEL
        elif PrecursorStage.HE_RATIO_ONSET.value in stages:
            current_stage = PrecursorStage.HE_RATIO_ONSET
        else:
            current_stage = PrecursorStage.NO_ANOMALY
        
        # Calculate sequence completeness
        stages_present = [s for s in stages if s != PrecursorStage.NO_ANOMALY.value]
        completeness = len(stages_present) / 3
        
        # Estimate lead time based on sequence
        lead_time = self._estimate_lead_time_from_sequence(
            he_result, gamma_result, rn_result
        )
        
        # Calculate confidence
        confidences = []
        if he_result.get('confidence') != 'none':
            confidences.append(self._confidence_to_score(he_result.get('confidence', 'none')))
        if gamma_result.get('confidence') != 'none':
            confidences.append(self._confidence_to_score(gamma_result.get('confidence', 'none')))
        if rn_result.get('confidence') != 'none':
            confidences.append(self._confidence_to_score(rn_result.get('confidence', 'none')))
        
        overall_confidence = np.mean(confidences) if confidences else 0
        
        result = {
            'current_stage': current_stage.value,
            'sequence_completeness': float(completeness),
            'estimated_lead_time_days': float(lead_time),
            'overall_confidence': float(overall_confidence),
            'he_ratio': he_result,
            'gamma_geo': gamma_result,
            'rn_pulse': rn_result,
            'timestamp': float(timestamps[-1]) if len(timestamps) > 0 else None
        }
        
        # Store in history
        self.sequence_history.append(result)
        
        return result
    
    def _confidence_to_score(self, confidence: str) -> float:
        """Convert confidence string to score."""
        mapping = {
            'high': 0.9,
            'moderate': 0.7,
            'low': 0.4,
            'none': 0.0
        }
        return mapping.get(confidence, 0.0)
    
    def _estimate_lead_time_from_sequence(
        self,
        he_result: Dict,
        gamma_result: Dict,
        rn_result: Dict
    ) -> float:
        """Estimate lead time based on sequence stage."""
        # Start with maximum (He_ratio only)
        lead_time = self.config.he_ratio_lead_days
        
        # Adjust based on gamma
        if gamma_result['stage'] == PrecursorStage.GAMMA_GEO_ACCEL.value:
            # Gamma acceleration typically occurs within 14 days before Rn
            lead_time = min(lead_time, 21)
        
        # Adjust based on rn
        if rn_result['stage'] == PrecursorStage.RN_PULSE_THRESHOLD.value:
            rn_status = rn_result.get('rn_pulse_status', '')
            if rn_status == 'emergency':
                lead_time = 7
            elif rn_status == 'alert':
                lead_time = 14
            elif rn_status == 'watch':
                lead_time = 30
        
        return lead_time
    
    def get_sequence_statistics(self) -> Dict[str, float]:
        """Get statistics about tracked sequences."""
        if not self.sequence_history:
            return {}
        
        completed_sequences = [
            s for s in self.sequence_history
            if s['current_stage'] == PrecursorStage.RN_PULSE_THRESHOLD.value
        ]
        
        if completed_sequences:
            mean_lead_time = np.mean([s['estimated_lead_time_days'] for s in completed_sequences])
            mean_confidence = np.mean([s['overall_confidence'] for s in completed_sequences])
        else:
            mean_lead_time = 0
            mean_confidence = 0
        
        return {
            'total_sequences': len(self.sequence_history),
            'completed_sequences': len(completed_sequences),
            'mean_lead_time_days': float(mean_lead_time),
            'mean_confidence': float(mean_confidence),
            'max_lead_time': float(max([s['estimated_lead_time_days'] for s in self.sequence_history])) if self.sequence_history else 0,
            'min_lead_time': float(min([s['estimated_lead_time_days'] for s in self.sequence_history])) if self.sequence_history else 0
        }
    
    def validate_with_events(
        self,
        events: List[Dict[str, float]]
    ) -> Dict[str, float]:
        """
        Validate sequence predictions against known events.
        
        Args:
            events: List of events with times and magnitudes
            
        Returns:
            Validation metrics
        """
        if not self.sequence_history or not events:
            return {}
        
        matches = 0
        lead_time_errors = []
        
        for sequence in self.sequence_history:
            if sequence['current_stage'] != PrecursorStage.RN_PULSE_THRESHOLD.value:
                continue
            
            seq_time = sequence['timestamp']
            predicted_lead = sequence['estimated_lead_time_days']
            
            # Find closest event
            best_match = None 
            min_time_diff = float('inf')
            
            for event in events:
                event_time = event['time']
                time_diff = abs(event_time - seq_time) / (24 * 3600)  # Convert to days
                
                if time_diff < min_time_diff and time_diff < 90:  # Within 90 days
                    min_time_diff = time_diff
                    best_match = event
            
            if best_match is not None:
                matches += 1
                lead_time_error = abs(predicted_lead - min_time_diff)
                lead_time_errors.append(lead_time_error)
        
        total_sequences = len([s for s in self.sequence_history 
                              if s['current_stage'] == PrecursorStage.RN_PULSE_THRESHOLD.value])
        
        if total_sequences == 0:
            return {}
        
        match_rate = matches / total_sequences if total_sequences > 0 else 0
        
        return {
            'match_rate': float(match_rate),
            'matches': matches,
            'total_sequences': total_sequences,
            'mean_lead_time_error': float(np.mean(lead_time_errors)) if lead_time_errors else 0,
            'median_lead_time_error': float(np.median(lead_time_errors)) if lead_time_errors else 0
        }


# Factory function
def create_precursor_sequencer(
    station_id: str,
    config_file: Optional[Union[str, Path]] = None
) -> PrecursorSequencer:
    """
    Create precursor sequencer with configuration.
    
    Args:
        station_id: Station identifier
        config_file: Optional configuration file
        
    Returns:
        Configured PrecursorSequencer instance
    """
    config = PrecursorConfig(station_id=station_id)
    
    if config_file:
        path = Path(config_file)
        with open(path, 'r') as f:
            if path.suffix in ['.yaml', '.yml']:
                data = yaml.safe_load(f)
            else:
                data = json.load(f)
        
        for key, value in data.items():
            if hasattr(config, key):
                setattr(config, key, value)
    
    return PrecursorSequencer(config)
