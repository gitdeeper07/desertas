"""
Station-specific background normalization for DRGIS parameters.
Implements 5-stage background modeling pipeline:

1. Harmonic regression for annual and diurnal cycles
2. Barometric pressure regression
3. Dust AOD correction (β_dust effect)
4. Groundwater table correction
5. Empirical mode decomposition (EMD)
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from scipy import signal, stats
from scipy.optimize import curve_fit
import json
import yaml
from pathlib import Path
from enum import Enum


class CorrectionStage(Enum):
    """Background modeling pipeline stages."""
    HARMONIC = "harmonic_regression"
    BAROMETRIC = "barometric_correction"
    DUST = "dust_correction"
    GROUNDWATER = "groundwater_correction"
    EMD = "empirical_mode_decomposition"


@dataclass
class NormalizationConfig:
    """Configuration for background normalization."""
    station_id: str
    craton: str
    
    # Harmonic regression parameters
    annual_period_days: float = 365.25
    diurnal_period_hours: float = 24.0
    
    # Barometric correction
    baro_coefficient: float = -2.8  # Bq·m⁻³/hPa for radon
    
    # Dust correction
    dust_coefficient: float = 0.12  # Adsorption coefficient
    
    # EMD parameters
    emd_max_modes: int = 8
    emd_threshold_ratio: float = 0.1
    
    # Calibration dates
    calibration_start: str = "2004-01-01"
    last_calibration: str = "2026-01-01"


class BackgroundNormalizer:
    """
    Station-specific background normalization for DRGIS.
    
    Implements full 5-stage pipeline for removing environmental
    influences from geogenic gas signals.
    """
    
    def __init__(self, config: NormalizationConfig):
        """
        Initialize background normalizer.
        
        Args:
            config: Normalization configuration
        """
        self.config = config
        self.harmonic_coeffs = {}
        self.baro_coeffs = {}
        self.emd_modes = []
        self.correction_history = []
        
    def harmonic_regression(
        self,
        time_series: np.ndarray,
        timestamps: np.ndarray,
        parameter: str
    ) -> Dict[str, float]:
        """
        Stage 1: Remove annual and diurnal cycles using harmonic regression.
        
        Model: y = a0 + a1·cos(2πt/T_annual) + b1·sin(2πt/T_annual) +
                     a2·cos(2πt/T_diurnal) + b2·sin(2πt/T_diurnal)
        
        Args:
            time_series: Input time series
            timestamps: Timestamps in seconds
            parameter: Parameter name
            
        Returns:
            Dictionary with regression results
        """
        # Convert timestamps to days
        t_days = (timestamps - timestamps[0]) / (24 * 3600)
        
        # Design matrix
        X = np.ones((len(t_days), 5))
        X[:, 1] = np.cos(2 * np.pi * t_days / self.config.annual_period_days)
        X[:, 2] = np.sin(2 * np.pi * t_days / self.config.annual_period_days)
        X[:, 3] = np.cos(2 * np.pi * t_days / (self.config.diurnal_period_hours / 24))
        X[:, 4] = np.sin(2 * np.pi * t_days / (self.config.diurnal_period_hours / 24))
        
        # Solve least squares
        coeffs, residuals, rank, s = np.linalg.lstsq(X, time_series, rcond=None)
        
        # Calculate fitted values
        fitted = X @ coeffs
        
        # Calculate residuals (signal - cycles)
        residuals = time_series - fitted
        
        # Store coefficients
        self.harmonic_coeffs[parameter] = {
            'intercept': coeffs[0],
            'annual_cos': coeffs[1],
            'annual_sin': coeffs[2],
            'diurnal_cos': coeffs[3],
            'diurnal_sin': coeffs[4]
        }
        
        # Calculate variance explained
        total_var = np.var(time_series)
        residual_var = np.var(residuals)
        var_explained = 1 - residual_var / total_var if total_var > 0 else 0
        
        return {
            'stage': CorrectionStage.HARMONIC.value,
            'parameter': parameter,
            'coefficients': self.harmonic_coeffs[parameter],
            'residuals_mean': float(np.mean(residuals)),
            'residuals_std': float(np.std(residuals)),
            'variance_explained': float(var_explained),
            'fitted': fitted.tolist() if len(fitted) < 1000 else None
        }
    
    def barometric_correction(
        self,
        rn_series: np.ndarray,
        pressure: np.ndarray,
        parameter: str = 'rn_pulse'
    ) -> Dict[str, float]:
        """
        Stage 2: Barometric pressure regression.
        
        Rn_corrected = Rn_raw + k·(P - P_mean)
        where k is calibrated per station.
        
        Args:
            rn_series: Radon time series
            pressure: Barometric pressure (hPa)
            parameter: Parameter name
            
        Returns:
            Dictionary with correction results
        """
        if len(rn_series) != len(pressure):
            raise ValueError("Series lengths must match")
        
        # Calculate mean pressure
        p_mean = np.mean(pressure)
        
        # Apply correction
        correction = self.config.baro_coefficient * (pressure - p_mean)
        rn_corrected = rn_series + correction
        
        # Calculate correction statistics
        correction_magnitude = np.mean(np.abs(correction))
        max_correction = np.max(np.abs(correction))
        
        # Store coefficients
        self.baro_coeffs[parameter] = {
            'coefficient': self.config.baro_coefficient,
            'p_mean': float(p_mean)
        }
        
        return {
            'stage': CorrectionStage.BAROMETRIC.value,
            'parameter': parameter,
            'correction_applied': True,
            'coefficient': self.config.baro_coefficient,
            'mean_correction': float(correction_magnitude),
            'max_correction': float(max_correction),
            'p_mean': float(p_mean),
            'corrected_series': rn_corrected.tolist() if len(rn_corrected) < 1000 else None
        }
    
    def dust_correction(
        self,
        signal_series: np.ndarray,
        aod_series: np.ndarray,  # Aerosol Optical Depth
        parameter: str
    ) -> Dict[str, float]:
        """
        Stage 3: Dust AOD correction for β_dust effect.
        
        signal_corrected = signal_raw / (1 - k_dust·AOD)
        
        Args:
            signal_series: Input signal series
            aod_series: Aerosol Optical Depth at 550 nm
            parameter: Parameter name
            
        Returns:
            Dictionary with correction results
        """
        if len(signal_series) != len(aod_series):
            raise ValueError("Series lengths must match")
        
        # Calculate correction factor
        dust_factor = 1 - self.config.dust_coefficient * aod_series
        dust_factor = np.clip(dust_factor, 0.1, 1.0)  # Prevent division by zero
        
        # Apply correction
        signal_corrected = signal_series / dust_factor
        
        # Calculate statistics
        mean_factor = np.mean(dust_factor)
        mean_correction = np.mean(np.abs(signal_corrected - signal_series))
        
        return {
            'stage': CorrectionStage.DUST.value,
            'parameter': parameter,
            'correction_applied': True,
            'dust_coefficient': self.config.dust_coefficient,
            'mean_dust_factor': float(mean_factor),
            'mean_correction': float(mean_correction),
            'max_correction': float(np.max(np.abs(signal_corrected - signal_series))),
            'corrected_series': signal_corrected.tolist() if len(signal_corrected) < 1000 else None
        }
    
    def groundwater_correction(
        self,
        signal_series: np.ndarray,
        water_level: np.ndarray,
        parameter: str
    ) -> Dict[str, float]:
        """
        Stage 4: Groundwater table correction.
        
        For stations with piezometric data.
        
        Args:
            signal_series: Input signal series
            water_level: Groundwater level (m below surface)
            parameter: Parameter name
            
        Returns:
            Dictionary with correction results
        """
        if len(signal_series) != len(water_level):
            raise ValueError("Series lengths must match")
        
        # Normalize water level
        wl_norm = (water_level - np.mean(water_level)) / np.std(water_level)
        
        # Fit linear relationship
        coeffs = np.polyfit(wl_norm, signal_series, 1)
        
        # Calculate correction
        predicted_effect = coeffs[0] * wl_norm + coeffs[1]
        signal_corrected = signal_series - predicted_effect
        
        # Calculate statistics
        variance_explained = 1 - np.var(signal_corrected) / np.var(signal_series)
        
        return {
            'stage': CorrectionStage.GROUNDWATER.value,
            'parameter': parameter,
            'correction_applied': True,
            'coefficient': float(coeffs[0]),
            'intercept': float(coeffs[1]),
            'variance_explained': float(variance_explained),
            'mean_water_level': float(np.mean(water_level)),
            'corrected_series': signal_corrected.tolist() if len(signal_corrected) < 1000 else None
        }
    
    def empirical_mode_decomposition(
        self,
        signal_series: np.ndarray,
        parameter: str,
        max_modes: Optional[int] = None
    ) -> Dict[str, float]:
        """
        Stage 5: Empirical Mode Decomposition (EMD).
        
        Decompose signal into intrinsic mode functions (IMFs)
        and separate signal from noise.
        
        Args:
            signal_series: Input signal (residual after previous stages)
            parameter: Parameter name
            max_modes: Maximum number of IMFs to extract
            
        Returns:
            Dictionary with decomposition results
        """
        if max_modes is None:
            max_modes = self.config.emd_max_modes
        
        # Simplified EMD implementation
        # In production, use proper EMD library (e.g., PyEMD)
        
        # Detrend
        detrended = signal.detrend(signal_series)
        
        # Simple bandpass filtering as proxy for IMFs
        # This is a simplification - real EMD is more sophisticated
        fs = 1.0  # Assuming 1 sample per day
        nyquist = fs / 2
        
        imfs = []
        residual = detrended.copy()
        
        for i in range(min(max_modes, 5)):  # Limit to 5 modes
            # Approximate IMF through bandpass filtering
            if i == 0:
                # Highest frequency
                b, a = signal.butter(4, 0.1, btype='high', fs=fs)
            elif i == max_modes - 1:
                # Lowest frequency (trend)
                b, a = signal.butter(4, 0.01, btype='low', fs=fs)
            else:
                # Mid frequencies
                low = 0.01 * (i + 1)
                high = 0.1 * (i + 1)
                b, a = signal.butter(4, [low, high], btype='band', fs=fs)
            
            imf = signal.filtfilt(b, a, residual)
            imfs.append(imf)
            residual = residual - imf
        
        # Identify signal vs noise components
        # Noise typically in high-frequency IMFs
        noise_threshold = self.config.emd_threshold_ratio * np.std(detrended)
        signal_component = np.zeros_like(detrended)
        
        for i, imf in enumerate(imfs):
            if np.std(imf) > noise_threshold:
                signal_component += imf
        
        self.emd_modes = imfs
        
        return {
            'stage': CorrectionStage.EMD.value,
            'parameter': parameter,
            'n_modes': len(imfs),
            'signal_std': float(np.std(signal_component)),
            'noise_std': float(np.std(residual)),
            'snr': float(np.std(signal_component) / (np.std(residual) + 1e-10)),
            'signal_component': signal_component.tolist() if len(signal_component) < 1000 else None
        }
    
    def full_pipeline(
        self,
        data: Dict[str, np.ndarray],
        timestamps: np.ndarray,
        pressure: Optional[np.ndarray] = None,
        aod: Optional[np.ndarray] = None,
        water_level: Optional[np.ndarray] = None
    ) -> Dict[str, Dict[str, float]]:
        """
        Run full 5-stage normalization pipeline.
        
        Args:
            data: Dictionary of parameter time series
            timestamps: Timestamps array
            pressure: Optional pressure data
            aod: Optional AOD data
            water_level: Optional groundwater data
            
        Returns:
            Dictionary with results for each parameter
        """
        results = {}
        corrected_data = {}
        
        for param_name, series in data.items():
            param_results = []
            current_series = series.copy()
            
            # Stage 1: Harmonic regression
            harmonic_result = self.harmonic_regression(current_series, timestamps, param_name)
            param_results.append(harmonic_result)
            current_series = harmonic_result.get('residuals', current_series)
            
            # Stage 2: Barometric correction (for radon only)
            if param_name == 'rn_pulse' and pressure is not None:
                baro_result = self.barometric_correction(current_series, pressure, param_name)
                param_results.append(baro_result)
                current_series = baro_result.get('corrected_series', current_series)
            
            # Stage 3: Dust correction
            if aod is not None:
                dust_result = self.dust_correction(current_series, aod, param_name)
                param_results.append(dust_result)
                current_series = dust_result.get('corrected_series', current_series)
            
            # Stage 4: Groundwater correction
            if water_level is not None:
                gw_result = self.groundwater_correction(current_series, water_level, param_name)
                param_results.append(gw_result)
                current_series = gw_result.get('corrected_series', current_series)
            
            # Stage 5: EMD
            emd_result = self.empirical_mode_decomposition(current_series, param_name)
            param_results.append(emd_result)
            
            results[param_name] = {
                'stages': param_results,
                'final_signal': emd_result.get('signal_component', current_series),
                'background': float(np.mean(emd_result.get('signal_component', current_series))),
                'sigma': float(np.std(emd_result.get('signal_component', current_series)))
            }
            
            corrected_data[param_name] = results[param_name]['final_signal']
        
        # Store correction history
        self.correction_history.append({
            'timestamp': np.datetime64('now').astype(str),
            'results': results
        })
        
        return results
    
    def calculate_background_statistics(
        self,
        corrected_data: Dict[str, np.ndarray],
        window_days: int = 30
    ) -> Dict[str, Dict[str, float]]:
        """
        Calculate background statistics from corrected data.
        
        Args:
            corrected_data: Corrected parameter time series
            window_days: Rolling window in days
            
        Returns:
            Background statistics for each parameter
        """
        window_samples = window_days * 24  # Assuming hourly data
        
        stats = {}
        for param_name, series in corrected_data.items():
            if len(series) < window_samples:
                # Use all available data
                bg = float(np.median(series))
                sigma = float(np.std(series))
            else:
                # Use rolling window
                recent = series[-window_samples:]
                bg = float(np.median(recent))
                sigma = float(np.std(recent))
            
            # Calculate anomaly threshold (95th percentile)
            threshold = bg + 2 * sigma
            
            stats[param_name] = {
                'background': bg,
                'sigma': sigma,
                'threshold': threshold,
                'min': float(np.min(series)),
                'max': float(np.max(series)),
                'n_samples': len(series)
            }
        
        return stats


# Factory function
def create_normalizer(
    station_id: str,
    craton: str,
    config_file: Optional[Union[str, Path]] = None
) -> BackgroundNormalizer:
    """
    Create background normalizer with configuration.
    
    Args:
        station_id: Station identifier
        craton: Craton name
        config_file: Optional configuration file
        
    Returns:
        Configured BackgroundNormalizer instance
    """
    config = NormalizationConfig(
        station_id=station_id,
        craton=craton
    )
    
    if config_file:
        path = Path(config_file)
        with open(path, 'r') as f:
            if path.suffix in ['.yaml', '.yml']:
                data = yaml.safe_load(f)
            else:
                data = json.load(f)
        
        # Override config from file
        for key, value in data.items():
            if hasattr(config, key):
                setattr(config, key, value)
    
    return BackgroundNormalizer(config)
