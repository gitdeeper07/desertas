"""
Background Modeling Pipeline for DESERTAS
5-stage background removal pipeline:

1. Harmonic regression for annual and diurnal cycles
2. Barometric pressure regression
3. Dust AOD correction (β_dust effect)
4. Groundwater table correction
5. Empirical mode decomposition (EMD)

Removes environmental confounds to isolate tectonic signal
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from scipy import signal, stats
from scipy.optimize import curve_fit
from datetime import datetime, timedelta
import json
import yaml
from pathlib import Path
from enum import Enum


class CorrectionStage(Enum):
    """Stages of background correction pipeline."""
    HARMONIC = "harmonic_regression"
    BAROMETRIC = "barometric_correction"
    DUST = "dust_correction"
    GROUNDWATER = "groundwater_correction"
    EMD = "empirical_mode_decomposition"


@dataclass
class BackgroundConfig:
    """Configuration for background modeling."""
    station_id: str
    craton: str
    
    # Harmonic regression
    annual_period_days: float = 365.25
    diurnal_period_hours: float = 24.0
    n_harmonics: int = 3
    
    # Barometric correction
    default_baro_coef: float = -2.8  # Bq·m⁻³/hPa for radon
    
    # Dust correction
    default_dust_coef: float = 0.12  # Adsorption coefficient
    
    # EMD parameters
    emd_max_modes: int = 8
    emd_threshold_ratio: float = 0.1
    
    # Rolling window for statistics (days)
    background_window: int = 30
    anomaly_window: int = 7


class BackgroundModeler:
    """
    Background modeling and correction pipeline.
    
    Implements 5-stage correction to isolate tectonic signal
    from environmental influences.
    """
    
    def __init__(self, config: BackgroundConfig):
        """
        Initialize background modeler.
        
        Args:
            config: Background configuration
        """
        self.config = config
        self.correction_history = []
        self.background_stats = {}
        
    def harmonic_regression(
        self,
        signal_series: np.ndarray,
        timestamps: np.ndarray,
        parameter: str = 'rn_pulse'
    ) -> Dict[str, Union[np.ndarray, Dict]]:
        """
        Stage 1: Remove annual and diurnal cycles.
        
        Model: y = a0 + Σ[ai·cos(2πi·t/T) + bi·sin(2πi·t/T)]
        
        Args:
            signal_series: Input time series
            timestamps: Timestamps in seconds
            parameter: Parameter name
            
        Returns:
            Corrected signal and metadata
        """
        # Convert timestamps to days
        t_days = (timestamps - timestamps[0]) / (24 * 3600)
        
        # Build design matrix with harmonics
        n_samples = len(t_days)
        n_params = 1 + 2 * self.config.n_harmonics * 2  # Annual + diurnal
        
        X = np.ones((n_samples, n_params))
        col = 1
        
        # Annual harmonics
        for i in range(1, self.config.n_harmonics + 1):
            X[:, col] = np.cos(2 * np.pi * i * t_days / self.config.annual_period_days)
            col += 1
            X[:, col] = np.sin(2 * np.pi * i * t_days / self.config.annual_period_days)
            col += 1
        
        # Diurnal harmonics
        days_to_hours = 24
        for i in range(1, self.config.n_harmonics + 1):
            X[:, col] = np.cos(2 * np.pi * i * t_days * days_to_hours / self.config.diurnal_period_hours)
            col += 1
            X[:, col] = np.sin(2 * np.pi * i * t_days * days_to_hours / self.config.diurnal_period_hours)
            col += 1
        
        # Solve least squares with regularization
        lambda_reg = 0.1
        XtX = X.T @ X
        XtX_reg = XtX + lambda_reg * np.eye(XtX.shape[0])
        Xty = X.T @ signal_series
        
        try:
            coeffs = np.linalg.solve(XtX_reg, Xty)
        except np.linalg.LinAlgError:
            # Fallback to pseudo-inverse
            coeffs = np.linalg.pinv(X) @ signal_series
        
        # Calculate fitted values
        fitted = X @ coeffs
        
        # Calculate residuals (signal - cycles)
        residuals = signal_series - fitted
        
        # Calculate variance explained
        total_var = np.var(signal_series)
        residual_var = np.var(residuals)
        var_explained = 1 - residual_var / total_var if total_var > 0 else 0
        
        # Detect remaining periodic components
        from scipy import fft
        fft_vals = np.abs(fft.rfft(residuals))
        freqs = fft.rfftfreq(len(residuals), d=(timestamps[1] - timestamps[0]) / (24*3600))
        
        # Find peaks
        peak_indices = signal.find_peaks(fft_vals, height=np.mean(fft_vals) * 2)[0]
        remaining_periods = []
        for idx in peak_indices[:3]:  # Top 3 peaks
            if freqs[idx] > 0:
                remaining_periods.append(1 / freqs[idx])
        
        result = {
            'corrected_signal': residuals,
            'fitted_cycles': fitted,
            'coefficients': coeffs.tolist(),
            'variance_explained': float(var_explained),
            'residual_mean': float(np.mean(residuals)),
            'residual_std': float(np.std(residuals)),
            'remaining_periods': remaining_periods,
            'stage': CorrectionStage.HARMONIC.value
        }
        
        self.correction_history.append(result)
        return result
    
    def barometric_correction(
        self,
        signal_series: np.ndarray,
        pressure: np.ndarray,
        parameter: str = 'rn_pulse',
        fit_coefficient: bool = True
    ) -> Dict[str, Union[np.ndarray, Dict]]:
        """
        Stage 2: Barometric pressure correction.
        
        Corrected = Raw - k·(P - P_mean)
        where k can be fitted or use default.
        
        Args:
            signal_series: Input signal (after harmonic correction)
            pressure: Barometric pressure (hPa)
            parameter: Parameter name
            fit_coefficient: Whether to fit coefficient or use default
            
        Returns:
            Pressure-corrected signal
        """
        if len(signal_series) != len(pressure):
            raise ValueError("Signal and pressure lengths must match")
        
        # Calculate mean pressure
        p_mean = np.mean(pressure)
        p_deviation = pressure - p_mean
        
        if fit_coefficient and len(signal_series) > 100:
            # Fit coefficient using robust regression
            from sklearn.linear_model import HuberRegressor
            model = HuberRegressor()
            model.fit(p_deviation.reshape(-1, 1), signal_series)
            k = model.coef_[0]
        else:
            # Use default coefficient
            k = self.config.default_baro_coef
        
        # Apply correction
        correction = k * p_deviation
        corrected = signal_series - correction
        
        # Calculate effectiveness
        corr_before = np.corrcoef(signal_series, p_deviation)[0, 1] if len(signal_series) > 1 else 0
        corr_after = np.corrcoef(corrected, p_deviation)[0, 1] if len(corrected) > 1 else 0
        
        result = {
            'corrected_signal': corrected,
            'coefficient': float(k),
            'p_mean': float(p_mean),
            'correction_magnitude': float(np.mean(np.abs(correction))),
            'max_correction': float(np.max(np.abs(correction))),
            'correlation_before': float(corr_before),
            'correlation_after': float(corr_after),
            'improvement': float(abs(corr_before) - abs(corr_after)),
            'stage': CorrectionStage.BAROMETRIC.value
        }
        
        self.correction_history.append(result)
        return result
    
    def dust_correction(
        self,
        signal_series: np.ndarray,
        aod: np.ndarray,  # Aerosol Optical Depth
        parameter: str = 'rn_pulse'
    ) -> Dict[str, Union[np.ndarray, Dict]]:
        """
        Stage 3: Dust AOD correction for β_dust effect.
        
        Corrected = Raw / (1 - k_dust·AOD)
        
        Args:
            signal_series: Input signal
            aod: Aerosol Optical Depth at 550 nm
            parameter: Parameter name
            
        Returns:
            Dust-corrected signal
        """
        if len(signal_series) != len(aod):
            raise ValueError("Signal and AOD lengths must match")
        
        # Calculate correction factor
        dust_factor = 1 - self.config.default_dust_coef * aod
        dust_factor = np.clip(dust_factor, 0.3, 1.0)  # Prevent extreme values
        
        # Apply correction
        corrected = signal_series / dust_factor
        
        # Identify periods of high dust
        high_dust = aod > 0.3
        correction_magnitude = np.where(high_dust, corrected - signal_series, 0)
        
        result = {
            'corrected_signal': corrected,
            'dust_factor': dust_factor,
            'dust_coefficient': self.config.default_dust_coef,
            'mean_correction': float(np.mean(np.abs(correction_magnitude))),
            'max_correction': float(np.max(np.abs(correction_magnitude))),
            'high_dust_fraction': float(np.mean(high_dust)),
            'stage': CorrectionStage.DUST.value
        }
        
        self.correction_history.append(result)
        return result
    
    def groundwater_correction(
        self,
        signal_series: np.ndarray,
        water_level: np.ndarray,
        parameter: str = 'rn_pulse'
    ) -> Dict[str, Union[np.ndarray, Dict]]:
        """
        Stage 4: Groundwater table correction.
        
        For stations with available piezometric data.
        
        Args:
            signal_series: Input signal
            water_level: Groundwater level (m below surface)
            parameter: Parameter name
            
        Returns:
            Groundwater-corrected signal
        """
        if len(signal_series) != len(water_level):
            raise ValueError("Signal and water level lengths must match")
        
        # Normalize water level
        wl_mean = np.mean(water_level)
        wl_std = np.std(water_level)
        if wl_std > 0:
            wl_norm = (water_level - wl_mean) / wl_std
        else:
            wl_norm = np.zeros_like(water_level)
        
        # Fit relationship using Theil-Sen robust regression
        from sklearn.linear_model import TheilSenRegressor
        model = TheilSenRegressor()
        model.fit(wl_norm.reshape(-1, 1), signal_series)
        
        # Calculate predicted effect
        predicted_effect = model.predict(wl_norm.reshape(-1, 1))
        
        # Apply correction
        corrected = signal_series - predicted_effect
        
        # Calculate statistics
        variance_before = np.var(signal_series)
        variance_after = np.var(corrected)
        var_reduction = 1 - variance_after / variance_before if variance_before > 0 else 0
        
        result = {
            'corrected_signal': corrected,
            'coefficient': float(model.coef_[0]),
            'intercept': float(model.intercept_),
            'variance_reduction': float(var_reduction),
            'mean_water_level': float(wl_mean),
            'water_level_range': float(np.ptp(water_level)),
            'stage': CorrectionStage.GROUNDWATER.value
        }
        
        self.correction_history.append(result)
        return result
    
    def empirical_mode_decomposition(
        self,
        signal_series: np.ndarray,
        parameter: str = 'rn_pulse',
        max_modes: Optional[int] = None
    ) -> Dict[str, Union[np.ndarray, Dict]]:
        """
        Stage 5: Empirical Mode Decomposition (EMD).
        
        Decompose signal into Intrinsic Mode Functions (IMFs)
        and separate signal from noise.
        
        Args:
            signal_series: Input signal (after previous stages)
            parameter: Parameter name
            max_modes: Maximum number of IMFs
            
        Returns:
            Decomposed signal components
        """
        if max_modes is None:
            max_modes = self.config.emd_max_modes
        
        # Simplified EMD using bandpass filtering
        # In production, use proper EMD library (e.g., PyEMD)
        
        # Detrend
        detrended = signal.detrend(signal_series)
        
        # Sampling frequency (assume 1 sample per hour)
        fs = 1.0 / 3600  # Hz
        
        # Design filter banks for different frequency bands
        imfs = []
        residual = detrended.copy()
        
        # Frequency bands (in Hz)
        freq_bands = [
            (1/24/3600, 1/3600),      # Hours
            (1/7/24/3600, 1/24/3600), # Days
            (1/30/24/3600, 1/7/24/3600), # Weeks
            (1/365/24/3600, 1/30/24/3600), # Months
            (0, 1/365/24/3600)        # Years (trend)
        ]
        
        for i, (low, high) in enumerate(freq_bands[:max_modes]):
            if low == 0:
                # Low-pass filter (trend)
                b, a = signal.butter(4, high, btype='low', fs=fs)
            elif high > fs/2:
                # High-pass filter
                b, a = signal.butter(4, low, btype='high', fs=fs)
            else:
                # Band-pass filter
                b, a = signal.butter(4, [low, high], btype='band', fs=fs)
            
            # Apply filter
            imf = signal.filtfilt(b, a, residual)
            imfs.append(imf)
            residual = residual - imf
        
        # Identify signal vs noise components
        # Noise typically in high-frequency IMFs
        noise_threshold = self.config.emd_threshold_ratio * np.std(detrended)
        
        signal_component = np.zeros_like(detrended)
        noise_component = np.zeros_like(detrended)
        
        for i, imf in enumerate(imfs):
            if np.std(imf) > noise_threshold and i < len(imfs) // 2:
                # Low-frequency IMFs are signal
                signal_component += imf
            else:
                # High-frequency IMFs are noise
                noise_component += imf
        
        result = {
            'corrected_signal': signal_component,
            'noise_component': noise_component,
            'imfs': imfs,
            'n_imfs': len(imfs),
            'signal_std': float(np.std(signal_component)),
            'noise_std': float(np.std(noise_component)),
            'snr': float(np.std(signal_component) / (np.std(noise_component) + 1e-10)),
            'stage': CorrectionStage.EMD.value
        }
        
        self.correction_history.append(result)
        return result
    
    def full_pipeline(
        self,
        data: Dict[str, np.ndarray],
        timestamps: np.ndarray,
        pressure: Optional[np.ndarray] = None,
        aod: Optional[np.ndarray] = None,
        water_level: Optional[np.ndarray] = None
    ) -> Dict[str, Dict]:
        """
        Run full 5-stage correction pipeline.
        
        Args:
            data: Dictionary of parameter time series
            timestamps: Timestamps array
            pressure: Optional pressure data
            aod: Optional AOD data
            water_level: Optional groundwater data
            
        Returns:
            Corrected data for each parameter
        """
        results = {}
        
        for param_name, series in data.items():
            current = series.copy()
            stage_results = []
            
            # Stage 1: Harmonic regression
            harm_result = self.harmonic_regression(current, timestamps, param_name)
            current = harm_result['corrected_signal']
            stage_results.append(harm_result)
            
            # Stage 2: Barometric correction (for radon)
            if param_name == 'rn_pulse' and pressure is not None:
                baro_result = self.barometric_correction(current, pressure, param_name)
                current = baro_result['corrected_signal']
                stage_results.append(baro_result)
            
            # Stage 3: Dust correction
            if aod is not None:
                dust_result = self.dust_correction(current, aod, param_name)
                current = dust_result['corrected_signal']
                stage_results.append(dust_result)
            
            # Stage 4: Groundwater correction
            if water_level is not None:
                gw_result = self.groundwater_correction(current, water_level, param_name)
                current = gw_result['corrected_signal']
                stage_results.append(gw_result)
            
            # Stage 5: EMD
            emd_result = self.empirical_mode_decomposition(current, param_name)
            final_signal = emd_result['corrected_signal']
            stage_results.append(emd_result)
            
            # Calculate final statistics
            results[param_name] = {
                'corrected_signal': final_signal,
                'background': float(np.median(final_signal)),
                'std': float(np.std(final_signal)),
                'stages': stage_results
            }
        
        return results
    
    def calculate_background(
        self,
        corrected_signal: np.ndarray,
        method: str = 'rolling_median'
    ) -> Dict[str, float]:
        """
        Calculate background statistics from corrected signal.
        
        Args:
            corrected_signal: Corrected time series
            method: Background calculation method
            
        Returns:
            Background statistics
        """
        if method == 'rolling_median':
            window = self.config.background_window * 24  # Convert to hours
            if len(corrected_signal) > window:
                background = np.median(corrected_signal[-window:])
                mad = np.median(np.abs(corrected_signal[-window:] - background))
                sigma = mad * 1.4826  # Convert MAD to sigma
            else:
                background = np.median(corrected_signal)
                sigma = np.std(corrected_signal)
        
        elif method == 'harmonic':
            # Use harmonic fit as background
            # Simplified - would need proper implementation
            background = np.mean(corrected_signal)
            sigma = np.std(corrected_signal)
        
        else:
            background = np.mean(corrected_signal)
            sigma = np.std(corrected_signal)
        
        # Calculate anomaly threshold (95th percentile)
        threshold = background + 2 * sigma
        
        return {
            'background': float(background),
            'sigma': float(sigma),
            'threshold': float(threshold),
            'cv': float(sigma / background) if background != 0 else 0,
            'min': float(np.min(corrected_signal)),
            'max': float(np.max(corrected_signal))
        }


# Factory function
def create_background_modeler(
    station_id: str,
    craton: str,
    config_file: Optional[Union[str, Path]] = None
) -> BackgroundModeler:
    """
    Create background modeler with configuration.
    
    Args:
        station_id: Station identifier
        craton: Craton name
        config_file: Optional configuration file
        
    Returns:
        Configured BackgroundModeler instance
    """
    config = BackgroundConfig(
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
        
        for key, value in data.items():
            if hasattr(config, key):
                setattr(config, key, value)
    
    return BackgroundModeler(config)
