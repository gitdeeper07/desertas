"""
Harmonic Regression for Seasonal and Diurnal Cycle Removal
Removes periodic components from time series using Fourier analysis

Model: y = a0 + Σ[ai·cos(2πi·t/T) + bi·sin(2πi·t/T)]

Removes:
- Annual cycles (T = 365.25 days)
- Diurnal cycles (T = 24 hours)
- Semi-annual, semi-diurnal, and higher harmonics
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from scipy import signal, stats, fft
from datetime import datetime, timedelta
import json
import yaml
from pathlib import Path


@dataclass
class HarmonicConfig:
    """Configuration for harmonic regression."""
    station_id: str
    
    # Periods in hours
    annual_period_hours: float = 365.25 * 24
    semi_annual_period_hours: float = 182.625 * 24
    diurnal_period_hours: float = 24.0
    semi_diurnal_period_hours: float = 12.0
    
    # Number of harmonics to include
    n_annual_harmonics: int = 3
    n_diurnal_harmonics: int = 3
    
    # Regularization
    lambda_reg: float = 0.1
    
    # Significance testing
    significance_level: float = 0.05
    min_period_hours: float = 2.0
    max_period_hours: float = 365.25 * 24 * 2  # 2 years


class HarmonicRegressor:
    """
    Harmonic regression for removing periodic components.
    
    Fits Fourier series to time series and removes seasonal
    and diurnal cycles to isolate tectonic signal.
    """
    
    def __init__(self, config: HarmonicConfig):
        """
        Initialize harmonic regressor.
        
        Args:
            config: Harmonic regression configuration
        """
        self.config = config
        self.fitted_coefficients = {}
        self.periodic_components = {}
        
    def build_design_matrix(
        self,
        timestamps: np.ndarray,
        periods: List[float],
        n_harmonics: int = 3
    ) -> np.ndarray:
        """
        Build design matrix for harmonic regression.
        
        Args:
            timestamps: Time points in hours
            periods: List of fundamental periods in hours
            n_harmonics: Number of harmonics to include per period
            
        Returns:
            Design matrix X of shape (n_samples, 1 + 2*sum(n_harmonics))
        """
        t_hours = timestamps / 3600  # Convert to hours
        t0 = t_hours[0]
        t_norm = t_hours - t0
        
        n_samples = len(t_norm)
        n_params = 1  # Intercept
        for period in periods:
            n_params += 2 * n_harmonics
        
        X = np.ones((n_samples, n_params))
        col = 1
        
        for period in periods:
            omega = 2 * np.pi / period
            for i in range(1, n_harmonics + 1):
                X[:, col] = np.cos(i * omega * t_norm)
                col += 1
                X[:, col] = np.sin(i * omega * t_norm)
                col += 1
        
        return X
    
    def fit(
        self,
        signal_series: np.ndarray,
        timestamps: np.ndarray,
        periods: Optional[List[float]] = None,
        n_harmonics: Optional[int] = None
    ) -> Dict[str, Union[np.ndarray, Dict]]:
        """
        Fit harmonic model to signal.
        
        Args:
            signal_series: Input time series
            timestamps: Timestamps in seconds
            periods: List of periods to fit (default: annual and diurnal)
            n_harmonics: Number of harmonics per period
            
        Returns:
            Fitted model and residuals
        """
        if periods is None:
            periods = [
                self.config.annual_period_hours,
                self.config.diurnal_period_hours
            ]
        
        if n_harmonics is None:
            n_harmonics = max(
                self.config.n_annual_harmonics,
                self.config.n_diurnal_harmonics
            )
        
        # Build design matrix
        X = self.build_design_matrix(timestamps, periods, n_harmonics)
        
        # Ridge regression for numerical stability
        XtX = X.T @ X
        XtX_reg = XtX + self.config.lambda_reg * np.eye(XtX.shape[0])
        Xty = X.T @ signal_series
        
        try:
            coeffs = np.linalg.solve(XtX_reg, Xty)
        except np.linalg.LinAlgError:
            # Fallback to pseudo-inverse
            coeffs = np.linalg.pinv(X) @ signal_series
        
        # Calculate fitted values
        fitted = X @ coeffs
        
        # Calculate residuals
        residuals = signal_series - fitted
        
        # Calculate statistics
        total_var = np.var(signal_series)
        residual_var = np.var(residuals)
        var_explained = 1 - residual_var / total_var if total_var > 0 else 0
        
        # Extract components
        components = self._extract_components(
            X, coeffs, periods, n_harmonics, timestamps
        )
        
        # Store results
        result = {
            'fitted': fitted,
            'residuals': residuals,
            'coefficients': coeffs.tolist(),
            'variance_explained': float(var_explained),
            'residual_mean': float(np.mean(residuals)),
            'residual_std': float(np.std(residuals)),
            'components': components,
            'periods_used': periods,
            'n_harmonics': n_harmonics
        }
        
        self.fitted_coefficients = {
            'coeffs': coeffs,
            'periods': periods,
            'n_harmonics': n_harmonics
        }
        
        return result
    
    def _extract_components(
        self,
        X: np.ndarray,
        coeffs: np.ndarray,
        periods: List[float],
        n_harmonics: int,
        timestamps: np.ndarray
    ) -> Dict[str, np.ndarray]:
        """Extract individual periodic components."""
        components = {}
        t_hours = timestamps / 3600
        t0 = t_hours[0]
        t_norm = t_hours - t0
        
        col = 1
        for period_idx, period in enumerate(periods):
            omega = 2 * np.pi / period
            period_component = np.zeros(len(t_norm))
            
            for i in range(1, n_harmonics + 1):
                cos_term = coeffs[col] * np.cos(i * omega * t_norm)
                sin_term = coeffs[col + 1] * np.sin(i * omega * t_norm)
                period_component += cos_term + sin_term
                col += 2
            
            period_name = f"period_{period:.1f}h"
            components[period_name] = period_component
        
        # Intercept term
        components['intercept'] = np.ones(len(t_norm)) * coeffs[0]
        
        return components
    
    def detect_significant_periods(
        self,
        signal_series: np.ndarray,
        timestamps: np.ndarray,
        min_period_hours: Optional[float] = None,
        max_period_hours: Optional[float] = None
    ) -> List[Dict[str, float]]:
        """
        Detect statistically significant periods using FFT.
        
        Args:
            signal_series: Input time series
            timestamps: Timestamps in seconds
            min_period_hours: Minimum period to consider
            max_period_hours: Maximum period to consider
            
        Returns:
            List of significant periods with amplitudes
        """
        if min_period_hours is None:
            min_period_hours = self.config.min_period_hours
        if max_period_hours is None:
            max_period_hours = self.config.max_period_hours
        
        # Detrend
        detrended = signal.detrend(signal_series)
        
        # Calculate power spectrum
        n = len(detrended)
        dt = (timestamps[1] - timestamps[0]) / 3600  # hours
        fs = 1 / dt  # Hz
        
        fft_vals = fft.rfft(detrended)
        fft_freqs = fft.rfftfreq(n, d=dt/3600)  # cycles per hour
        power = np.abs(fft_vals)**2 / n
        
        # Convert to periods
        periods = 1 / fft_freqs[fft_freqs > 0]
        power = power[fft_freqs > 0]
        
        # Filter by period range
        valid = (periods >= min_period_hours) & (periods <= max_period_hours)
        periods = periods[valid]
        power = power[valid]
        
        # Find peaks
        peak_indices = signal.find_peaks(power, height=np.mean(power) * 2)[0]
        
        # Calculate significance using Lomb-Scargle
        significant_periods = []
        for idx in peak_indices:
            period = float(periods[idx])
            amplitude = float(np.sqrt(power[idx] * 2))
            
            # Lomb-Scargle p-value approximation
            # Higher power = more significant
            p_value = np.exp(-power[idx] / np.mean(power))
            
            if p_value < self.config.significance_level:
                significant_periods.append({
                    'period_hours': period,
                    'period_days': period / 24,
                    'amplitude': amplitude,
                    'power': float(power[idx]),
                    'p_value': float(p_value),
                    'significant': p_value < self.config.significance_level
                })
        
        # Sort by amplitude
        significant_periods.sort(key=lambda x: x['amplitude'], reverse=True)
        
        return significant_periods
    
    def adapt_fit(
        self,
        signal_series: np.ndarray,
        timestamps: np.ndarray,
        n_segments: int = 4
    ) -> List[Dict]:
        """
        Adapt harmonic fit over time to capture changing patterns.
        
        Splits data into segments and fits separately.
        
        Args:
            signal_series: Input time series
            timestamps: Timestamps in seconds
            n_segments: Number of time segments
            
        Returns:
            List of fit results per segment
        """
        segment_size = len(signal_series) // n_segments
        results = []
        
        for i in range(n_segments):
            start = i * segment_size
            end = start + segment_size if i < n_segments - 1 else len(signal_series)
            
            seg_signal = signal_series[start:end]
            seg_time = timestamps[start:end]
            
            if len(seg_signal) < 100:  # Need enough data
                continue
            
            # Detect significant periods in this segment
            sig_periods = self.detect_significant_periods(seg_signal, seg_time)
            
            # Use top periods for fitting
            if sig_periods:
                periods = [p['period_hours'] for p in sig_periods[:2]]  # Top 2
            else:
                periods = [self.config.diurnal_period_hours]
            
            # Fit
            result = self.fit(seg_signal, seg_time, periods)
            result['segment'] = i
            result['segment_start'] = float(seg_time[0])
            result['segment_end'] = float(seg_time[-1])
            
            results.append(result)
        
        return results
    
    def predict(
        self,
        timestamps: np.ndarray,
        coefficients: Optional[Dict] = None
    ) -> np.ndarray:
        """
        Predict periodic components for new timestamps.
        
        Args:
            timestamps: Timestamps in seconds
            coefficients: Optional coefficients from previous fit
            
        Returns:
            Predicted periodic signal
        """
        if coefficients is None:
            coefficients = self.fitted_coefficients
        
        if not coefficients:
            raise ValueError("No fitted coefficients available")
        
        X = self.build_design_matrix(
            timestamps,
            coefficients['periods'],
            coefficients['n_harmonics']
        )
        
        return X @ coefficients['coeffs']
    
    def remove_periodic(
        self,
        signal_series: np.ndarray,
        timestamps: np.ndarray
    ) -> Dict[str, np.ndarray]:
        """
        Remove all significant periodic components.
        
        Args:
            signal_series: Input time series
            timestamps: Timestamps in seconds
            
        Returns:
            Detrended signal with components
        """
        # Detect significant periods
        sig_periods = self.detect_significant_periods(signal_series, timestamps)
        
        if not sig_periods:
            # No significant periods found
            return {
                'detrended': signal_series,
                'periodic_sum': np.zeros_like(signal_series),
                'periods_removed': []
            }
        
        # Extract periods for fitting
        periods = [p['period_hours'] for p in sig_periods[:3]]  # Top 3
        
        # Fit harmonic model
        result = self.fit(signal_series, timestamps, periods)
        
        return {
            'detrended': result['residuals'],
            'periodic_sum': result['fitted'],
            'periods_removed': periods,
            'variance_explained': result['variance_explained'],
            'components': result['components']
        }
    
    def get_seasonal_strength(self, signal_series: np.ndarray, timestamps: np.ndarray) -> Dict[str, float]:
        """Calculate strength of seasonal components."""
        # Fit full model
        full_result = self.fit(signal_series, timestamps)
        
        # Fit without annual component
        diurnal_only = self.fit(
            signal_series, timestamps,
            periods=[self.config.diurnal_period_hours]
        )
        
        # Fit without diurnal component
        annual_only = self.fit(
            signal_series, timestamps,
            periods=[self.config.annual_period_hours]
        )
        
        return {
            'annual_strength': full_result['variance_explained'] - diurnal_only['variance_explained'],
            'diurnal_strength': full_result['variance_explained'] - annual_only['variance_explained'],
            'total_cyclic': full_result['variance_explained'],
            'residual': 1 - full_result['variance_explained']
        }


# Factory function
def create_harmonic_regressor(
    station_id: str,
    config_file: Optional[Union[str, Path]] = None
) -> HarmonicRegressor:
    """
    Create harmonic regressor with configuration.
    
    Args:
        station_id: Station identifier
        config_file: Optional configuration file
        
    Returns:
        Configured HarmonicRegressor instance
    """
    config = HarmonicConfig(station_id=station_id)
    
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
    
    return HarmonicRegressor(config)
