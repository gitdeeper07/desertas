"""
Ω_arid - Desiccation Index Parameter
Quantifies modulating effect of extreme aridity on geogenic gas transport.

Mathematical Definition:
Ω_arid = D_Rn(RH) / D_Rn(RH_ref) · (1 - f_dust · k_ads)

Operational Ranges:
- OPTIMAL: 0.85-1.00 (max sensitivity)
- GOOD: 0.65-0.85 (standard correction)
- REDUCED: 0.45-0.65 (elevated dust/moisture)
- IMPAIRED: <0.45 (exclude data)

D_Rn = 0.11 · exp(-2.1 · θ_w) cm²/s (empirical relationship)
"""

import numpy as np
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class AridityLevel(Enum):
    """Aridity classification levels."""
    OPTIMAL = "OPTIMAL"
    GOOD = "GOOD"
    REDUCED = "REDUCED"
    IMPAIRED = "IMPAIRED"


@dataclass
class AridityConfig:
    """Configuration for aridity analysis."""
    station_id: str
    soil_type: str  # sand, loam, clay, etc.
    dust_mineralogy: str  # silicate, carbonate, mixed
    calibration_date: str
    rh_ref: float = 15.0  # Reference relative humidity (%)
    
    # Adsorption coefficients by mineralogy (calibrated per station)
    ADSORPTION_COEFF = {
        'silicate': 0.12,
        'carbonate': 0.08,
        'mixed': 0.10,
        'quartz': 0.11,
        'feldspar': 0.13,
        'clay': 0.15
    }
    
    # Soil moisture diffusion parameters
    SOIL_PARAMS = {
        'sand': {'a': 0.11, 'b': 2.1},
        'loamy_sand': {'a': 0.10, 'b': 2.2},
        'sandy_loam': {'a': 0.09, 'b': 2.3},
        'loam': {'a': 0.08, 'b': 2.4},
        'silty_loam': {'a': 0.07, 'b': 2.5},
        'clay': {'a': 0.06, 'b': 2.6}
    }


class DesiccationIndex:
    """
    Ω_arid Calculator - Desiccation Index Parameter.
    
    Quantifies and corrects for aridity effects on gas detection.
    
    Attributes:
        config: Aridity configuration
        current_status: Current aridity status
    """
    
    def __init__(self, config: AridityConfig):
        """
        Initialize Ω_arid calculator.
        
        Args:
            config: Aridity configuration
        """
        self.config = config
        self.current_status = {}
        
    def compute(
        self,
        relative_humidity: float,  # RH in %
        soil_moisture: float,  # θ_w volumetric water content (0-1)
        aerosol_optical_depth: float,  # f_dust from MODIS
        temperature: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Compute Ω_arid from environmental parameters.
        
        Args:
            relative_humidity: Relative humidity (%)
            soil_moisture: Volumetric soil water content
            aerosol_optical_depth: AOD at 550 nm
            temperature: Optional air temperature (°C)
            
        Returns:
            Dictionary with Ω_arid value and components
        """
        # Get soil-specific diffusion parameters
        soil_params = self.config.SOIL_PARAMS.get(
            self.config.soil_type,
            {'a': 0.08, 'b': 2.4}  # Default to loam
        )
        
        # Calculate radon diffusion coefficient at current RH
        D_Rn = soil_params['a'] * np.exp(-soil_params['b'] * soil_moisture)
        
        # Calculate reference diffusion at optimal RH (15%)
        # Assume optimal soil moisture for detection (~5%)
        D_Rn_ref = soil_params['a'] * np.exp(-soil_params['b'] * 0.05)
        
        # Get dust adsorption coefficient
        k_ads = self.config.ADSORPTION_COEFF.get(
            self.config.dust_mineralogy,
            0.10  # Default to mixed
        )
        
        # Compute Ω_arid
        omega_arid = (D_Rn / D_Rn_ref) * (1 - aerosol_optical_depth * k_ads)
        
        # Apply temperature correction if provided
        if temperature is not None:
            temp_factor = self._temperature_correction(temperature)
            omega_arid *= temp_factor
        
        # Clip to valid range
        omega_arid = np.clip(omega_arid, 0.1, 1.0)
        
        # Determine operational status
        status = self._classify_status(omega_arid)
        
        # Determine if data should be flagged
        flag_data = omega_arid < 0.45
        
        result = {
            'omega_arid': round(omega_arid, 3),
            'status': status.value,
            'flag_data': flag_data,
            'D_Rn': round(D_Rn, 4),
            'D_Rn_ref': round(D_Rn_ref, 4),
            'diffusion_ratio': round(D_Rn / D_Rn_ref, 3),
            'dust_factor': round(1 - aerosol_optical_depth * k_ads, 3),
            'aerosol_optical_depth': aerosol_optical_depth,
            'k_ads': k_ads,
            'relative_humidity': relative_humidity,
            'soil_moisture': soil_moisture
        }
        
        if temperature is not None:
            result['temperature_c'] = temperature
            result['temp_factor'] = round(temp_factor, 3)
        
        self.current_status = result
        return result
    
    def _temperature_correction(self, temperature: float) -> float:
        """
        Apply temperature correction to diffusion.
        
        Higher temperature increases diffusion.
        """
        # Simple linear correction around 20°C
        temp_factor = 1.0 + 0.01 * (temperature - 20)
        return max(0.8, min(1.2, temp_factor))
    
    def _classify_status(self, omega_arid: float) -> AridityLevel:
        """Classify operational status based on Ω_arid value."""
        if omega_arid >= 0.85:
            return AridityLevel.OPTIMAL
        elif omega_arid >= 0.65:
            return AridityLevel.GOOD
        elif omega_arid >= 0.45:
            return AridityLevel.REDUCED
        else:
            return AridityLevel.IMPAIRED
    
    def correct_radon(self, rn_value: float, omega_arid: float) -> float:
        """
        Apply aridity correction to radon measurement.
        
        Args:
            rn_value: Raw radon measurement (Bq/m³)
            omega_arid: Current Ω_arid value
            
        Returns:
            Aridity-corrected radon value
        """
        if omega_arid <= 0:
            return rn_value
        
        # Correction factor: divide by omega_arid to recover signal
        return rn_value / omega_arid
    
    def estimate_optimal_sampling(self, omega_arid: float) -> Dict[str, float]:
        """
        Estimate optimal sampling frequency based on aridity.
        
        Args:
            omega_arid: Current Ω_arid value
            
        Returns:
            Sampling recommendations
        """
        if omega_arid >= 0.85:
            freq = 1.0  # Normal sampling
            confidence = 'high'
        elif omega_arid >= 0.65:
            freq = 1.2  # 20% increased sampling
            confidence = 'good'
        elif omega_arid >= 0.45:
            freq = 2.0  # Double sampling
            confidence = 'moderate'
        else:
            freq = 0.0  # Exclude data
            confidence = 'low'
        
        return {
            'sampling_multiplier': freq,
            'confidence': confidence,
            'recommendation': 'normal' if freq == 1.0 else 'enhanced' if freq > 1.0 else 'exclude'
        }
    
    def validate_with_measurements(
        self,
        measured_diffusion: np.ndarray,
        predicted_omega: np.ndarray
    ) -> Dict[str, float]:
        """
        Validate Ω_arid model against actual measurements.
        
        Args:
            measured_diffusion: Measured diffusion coefficients
            predicted_omega: Predicted Ω_arid values
            
        Returns:
            Validation statistics
        """
        if len(measured_diffusion) != len(predicted_omega):
            raise ValueError("Array lengths must match")
        
        # Calculate error metrics
        errors = measured_diffusion - predicted_omega
        mae = np.mean(np.abs(errors))
        rmse = np.sqrt(np.mean(errors**2))
        r2 = 1 - np.sum(errors**2) / np.sum((measured_diffusion - np.mean(measured_diffusion))**2)
        
        return {
            'mae': round(mae, 4),
            'rmse': round(rmse, 4),
            'r2': round(r2, 4),
            'n_samples': len(measured_diffusion)
        }


# Factory function
def create_omega_arid(
    station_id: str,
    soil_type: str = 'sand',
    dust_mineralogy: str = 'mixed'
) -> DesiccationIndex:
    """
    Create Ω_arid calculator with default configuration.
    
    Args:
        station_id: Station identifier
        soil_type: Soil type (sand, loam, clay, etc.)
        dust_mineralogy: Dust mineralogy (silicate, carbonate, mixed)
        
    Returns:
        Configured DesiccationIndex instance
    """
    config = AridityConfig(
        station_id=station_id,
        soil_type=soil_type,
        dust_mineralogy=dust_mineralogy,
        calibration_date="2026-01-01"
    )
    
    return DesiccationIndex(config)
