"""
Dust AOD Correction for β_dust Effect
Corrects for dust adsorption of radon progeny

Corrected = Raw / (1 - k_dust·AOD)
where k_dust is calibrated per station mineralogy

Includes:
- AOD data ingestion from MODIS
- Mineralogy-specific coefficients
- Dust event detection
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from scipy import stats, signal
from datetime import datetime, timedelta
import json
import yaml
from pathlib import Path
from enum import Enum


class DustMineralogy(Enum):
    """Dust mineralogy types."""
    SILICATE = "silicate"
    CARBONATE = "carbonate"
    MIXED = "mixed"
    QUARTZ = "quartz"
    FELDSPAR = "feldspar"
    CLAY = "clay"
    GYPSUM = "gypsum"
    HALITE = "halite"


@dataclass
class DustConfig:
    """Configuration for dust correction."""
    station_id: str
    mineralogy: DustMineralogy = DustMineralogy.MIXED
    
    # Adsorption coefficients by mineralogy
    ADSORPTION_COEFF = {
        DustMineralogy.SILICATE: 0.85,
        DustMineralogy.CARBONATE: 0.75,
        DustMineralogy.MIXED: 0.80,
        DustMineralogy.QUARTZ: 0.82,
        DustMineralogy.FELDSPAR: 0.88,
        DustMineralogy.CLAY: 0.92,
        DustMineralogy.GYPSUM: 0.70,
        DustMineralogy.HALITE: 0.65
    }
    
    # AOD thresholds
    low_dust_threshold: float = 0.1
    moderate_dust_threshold: float = 0.3
    high_dust_threshold: float = 0.5
    extreme_dust_threshold: float = 1.0
    
    # Quality control
    max_aod: float = 5.0
    min_aod: float = 0.0
    
    # Correction limits
    min_correction_factor: float = 0.3
    max_correction_factor: float = 1.0


class DustCorrection:
    """
    Dust AOD correction for radon measurements.
    
    Corrects for adsorption of radon progeny onto dust particles,
    which reduces measured activity.
    """
    
    def __init__(self, config: DustConfig):
        """
        Initialize dust correction.
        
        Args:
            config: Dust correction configuration
        """
        self.config = config
        self.k_dust = self.config.ADSORPTION_COEFF[config.mineralogy]
        self.dust_events = []
        
    def correct(
        self,
        signal_series: np.ndarray,
        aod: np.ndarray,
        timestamps: Optional[np.ndarray] = None
    ) -> Dict[str, Union[np.ndarray, Dict]]:
        """
        Apply dust correction to signal.
        
        Args:
            signal_series: Input signal (radon, etc.)
            aod: Aerosol Optical Depth at 550 nm
            timestamps: Optional timestamps for event detection
            
        Returns:
            Corrected signal and metadata
        """
        if len(signal_series) != len(aod):
            raise ValueError("Signal and AOD lengths must match")
        
        # Quality control
        valid_mask = self._quality_control(aod)
        
        # Calculate correction factor
        dust_factor = 1 - self.k_dust * aod
        dust_factor = np.clip(
            dust_factor,
            self.config.min_correction_factor,
            self.config.max_correction_factor
        )
        
        # Apply correction
        corrected = signal_series.copy()
        corrected[valid_mask] = signal_series[valid_mask] / dust_factor[valid_mask]
        
        # Detect dust events
        dust_levels = self._classify_dust_levels(aod)
        
        # Calculate statistics
        stats = self._calculate_statistics(
            signal_series, corrected, aod, dust_factor, valid_mask
        )
        
        # Record dust events if timestamps provided
        if timestamps is not None:
            self._record_dust_events(timestamps, aod, dust_levels)
        
        result = {
            'corrected': corrected,
            'dust_factor': dust_factor,
            'k_dust': self.k_dust,
            'valid_mask': valid_mask,
            'dust_levels': dust_levels,
            'valid_fraction': float(np.mean(valid_mask)),
            **stats
        }
        
        return result
    
    def _quality_control(self, aod: np.ndarray) -> np.ndarray:
        """Apply quality control to AOD data."""
        mask = np.ones(len(aod), dtype=bool)
        mask &= (aod >= self.config.min_aod) & (aod <= self.config.max_aod)
        mask &= ~np.isnan(aod)
        mask &= ~np.isinf(aod)
        return mask
    
    def _classify_dust_levels(self, aod: np.ndarray) -> List[str]:
        """Classify dust levels based on AOD."""
        levels = []
        for a in aod:
            if a >= self.config.extreme_dust_threshold:
                levels.append('EXTREME')
            elif a >= self.config.high_dust_threshold:
                levels.append('HIGH')
            elif a >= self.config.moderate_dust_threshold:
                levels.append('MODERATE')
            elif a >= self.config.low_dust_threshold:
                levels.append('LOW')
            else:
                levels.append('BACKGROUND')
        return levels
    
    def _calculate_statistics(
        self,
        original: np.ndarray,
        corrected: np.ndarray,
        aod: np.ndarray,
        dust_factor: np.ndarray,
        valid_mask: np.ndarray
    ) -> Dict[str, float]:
        """Calculate correction statistics."""
        # Use only valid data
        orig_valid = original[valid_mask]
        corr_valid = corrected[valid_mask]
        aod_valid = aod[valid_mask]
        factor_valid = dust_factor[valid_mask]
        
        if len(orig_valid) == 0:
            return {
                'mean_correction': 0,
                'max_correction': 0,
                'mean_dust_factor': 1.0,
                'corr_orig_aod': 0,
                'corr_corr_aod': 0
            }
        
        # Correction magnitude
        correction = corr_valid - orig_valid
        mean_correction = np.mean(np.abs(correction))
        max_correction = np.max(np.abs(correction))
        
        # Correlation with AOD
        corr_orig = np.corrcoef(orig_valid, aod_valid)[0, 1]
        corr_corr = np.corrcoef(corr_valid, aod_valid)[0, 1]
        
        # Dust factor statistics
        mean_factor = np.mean(factor_valid)
        min_factor = np.min(factor_valid)
        
        return {
            'mean_correction': float(mean_correction),
            'max_correction': float(max_correction),
            'mean_dust_factor': float(mean_factor),
            'min_dust_factor': float(min_factor),
            'corr_orig_aod': float(corr_orig) if not np.isnan(corr_orig) else 0,
            'corr_corr_aod': float(corr_corr) if not np.isnan(corr_corr) else 0,
            'correction_improvement': float(abs(corr_orig) - abs(corr_corr)) if not np.isnan(corr_orig) and not np.isnan(corr_corr) else 0
        }
    
    def _record_dust_events(
        self,
        timestamps: np.ndarray,
        aod: np.ndarray,
        dust_levels: List[str]
    ):
        """Record significant dust events for tracking."""
        # Find continuous periods of high dust
        high_dust = np.array([l in ['HIGH', 'EXTREME'] for l in dust_levels])
        
        # Find start and end of events
        diff = np.diff(np.concatenate(([0], high_dust.astype(int), [0])))
        starts = np.where(diff == 1)[0]
        ends = np.where(diff == -1)[0]
        
        for start, end in zip(starts, ends):
            if end - start >= 6:  # At least 6 hours
                event = {
                    'start_time': float(timestamps[start]),
                    'end_time': float(timestamps[end-1]),
                    'duration_hours': end - start,
                    'max_aod': float(np.max(aod[start:end])),
                    'mean_aod': float(np.mean(aod[start:end])),
                    'peak_level': dust_levels[start + np.argmax(aod[start:end])]
                }
                self.dust_events.append(event)
    
    def get_dust_statistics(self) -> Dict[str, float]:
        """Get statistics about dust events."""
        if not self.dust_events:
            return {
                'n_events': 0,
                'total_dust_hours': 0,
                'mean_duration': 0,
                'max_duration': 0
            }
        
        durations = [e['duration_hours'] for e in self.dust_events]
        
        return {
            'n_events': len(self.dust_events),
            'total_dust_hours': sum(durations),
            'mean_duration': float(np.mean(durations)),
            'max_duration': float(np.max(durations)),
            'max_aod_recorded': float(max(e['max_aod'] for e in self.dust_events))
        }
    
    def calibrate_coefficient(
        self,
        signal_series: np.ndarray,
        aod: np.ndarray,
        reference_periods: Optional[List[Tuple[int, int]]] = None
    ) -> Dict[str, float]:
        """
        Calibrate dust adsorption coefficient.
        
        Uses periods of known low dust as reference.
        
        Args:
            signal_series: Signal time series
            aod: AOD time series
            reference_periods: Optional list of (start, end) indices for reference
            
        Returns:
            Calibrated coefficient
        """
        if reference_periods is None:
            # Use periods with lowest AOD as reference
            low_aod_indices = np.where(aod < self.config.low_dust_threshold)[0]
            if len(low_aod_indices) < 100:
                return {'coefficient': self.k_dust, 'confidence': 'low'}
            
            # Use these as reference
            ref_signal = signal_series[low_aod_indices]
            ref_mean = np.mean(ref_signal)
            
            # Estimate correction needed for high AOD
            high_aod_indices = np.where(aod > self.config.moderate_dust_threshold)[0]
            if len(high_aod_indices) == 0:
                return {'coefficient': self.k_dust, 'confidence': 'low'}
            
            high_signal = signal_series[high_aod_indices]
            high_aod = aod[high_aod_indices]
            
            # Solve for k: high_signal * (1 - k*high_aod) = ref_mean
            # => k = (1 - ref_mean/high_signal) / high_aod
            ratios = 1 - ref_mean / high_signal
            k_estimates = ratios / high_aod
            
            # Filter plausible values
            k_estimates = k_estimates[
                (k_estimates > 0) & (k_estimates < 1.0)
            ]
            
            if len(k_estimates) > 0:
                k_new = float(np.median(k_estimates))
                confidence = 'high' if len(k_estimates) > 100 else 'moderate'
            else:
                k_new = self.k_dust
                confidence = 'low'
        
        else:
            # Use provided reference periods
            ref_values = []
            high_values = []
            high_aods = []
            
            for start, end in reference_periods:
                if end - start < 24:
                    continue
                
                period_signal = signal_series[start:end]
                period_aod = aod[start:end]
                
                if np.mean(period_aod) < self.config.low_dust_threshold:
                    ref_values.extend(period_signal)
                elif np.mean(period_aod) > self.config.moderate_dust_threshold:
                    high_values.extend(period_signal)
                    high_aods.extend(period_aod)
            
            if len(ref_values) > 0 and len(high_values) > 0:
                ref_mean = np.mean(ref_values)
                high_array = np.array(high_values)
                aod_array = np.array(high_aods)
                
                ratios = 1 - ref_mean / high_array
                k_estimates = ratios / aod_array
                k_estimates = k_estimates[(k_estimates > 0) & (k_estimates < 1.0)]
                
                if len(k_estimates) > 0:
                    k_new = float(np.median(k_estimates))
                    confidence = 'high' if len(k_estimates) > 100 else 'moderate'
                else:
                    k_new = self.k_dust
                    confidence = 'low'
            else:
                k_new = self.k_dust
                confidence = 'low'
        
        # Update coefficient
        self.k_dust = k_new
        
        return {
            'coefficient': k_new,
            'confidence': confidence,
            'n_estimates': len(k_estimates) if 'k_estimates' in locals() else 0
        }
    
    def estimate_transport_range(
        self,
        aod: float,
        wind_speed: float = 5.0  # m/s
    ) -> float:
        """
        Estimate downwind transport range based on dust loading.
        
        Args:
            aod: Aerosol Optical Depth
            wind_speed: Wind speed in m/s
            
        Returns:
            Estimated transport range in km
        """
        # Base range from validation (340 km max)
        base_range = 340 * (aod / self.config.high_dust_threshold)
        
        # Adjust for wind speed
        daily_transport = wind_speed * 86.4  # km/day
        
        # Max 3 days transport
        range_km = min(base_range, daily_transport * 3)
        
        return float(range_km)
    
    def get_mineralogy_info(self) -> Dict[str, Union[str, float]]:
        """Get information about current mineralogy."""
        return {
            'mineralogy': self.config.mineralogy.value,
            'adsorption_coefficient': self.k_dust,
            'description': f"{self.config.mineralogy.value} dust with k={self.k_dust:.2f}"
        }


# Factory function
def create_dust_correction(
    station_id: str,
    mineralogy: Union[str, DustMineralogy] = DustMineralogy.MIXED,
    config_file: Optional[Union[str, Path]] = None
) -> DustCorrection:
    """
    Create dust correction instance.
    
    Args:
        station_id: Station identifier
        mineralogy: Dust mineralogy type
        config_file: Optional configuration file
        
    Returns:
        Configured DustCorrection instance
    """
    if isinstance(mineralogy, str):
        mineralogy = DustMineralogy(mineralogy)
    
    config = DustConfig(
        station_id=station_id,
        mineralogy=mineralogy
    )
    
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
    
    return DustCorrection(config)
