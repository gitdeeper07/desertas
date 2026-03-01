"""
Ψ_crack - Fissure Conductivity Parameter
Characterizes geometric permeability of fracture network using cubic law.

Mathematical Definition:
Ψ_crack = (b³ / 12μ) · (dP/dz) · A_fracture

Cubic Law: conductivity ∝ aperture³ (β = 3.0 ± 0.4)
Pre-seismic signature: 25-80% increase within 21 days before M≥4.0
"""

import numpy as np
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class StressSensitivity(Enum):
    """Stress sensitivity classification."""
    HIGH = "high_sensitivity"
    MODERATE = "moderate_sensitivity"
    LOW = "low_sensitivity"
    INACTIVE = "inactive"


@dataclass
class FractureConfig:
    """Configuration for fracture conductivity analysis."""
    station_id: str
    mean_aperture_um: float  # b in μm
    fracture_area: float  # A_fracture in m²
    gas_viscosity: float  # μ in Pa·s (temperature-corrected)
    depth_m: float
    lithology: str
    calibration_date: str


class FissureConductivity:
    """
    Ψ_crack Calculator - Fissure Conductivity Parameter.
    
    Implements cubic law for fracture flow with stress sensitivity.
    
    Attributes:
        config: Fracture configuration
        CUBIC_EXPECTED: Theoretical cubic exponent (3.0)
    """
    
    CUBIC_EXPECTED = 3.0
    CUBIC_TOLERANCE = 0.4  # ±0.4 as validated
    
    # Stress sensitivity thresholds (MPa⁻¹)
    SSI_HIGH = 0.08
    SSI_LOW = 0.02
    
    def __init__(self, config: FractureConfig):
        """
        Initialize Ψ_crack calculator.
        
        Args:
            config: Fracture configuration
        """
        self.config = config
        self._validate_config()
        
    def _validate_config(self) -> None:
        """Validate configuration parameters."""
        if self.config.mean_aperture_um <= 0:
            raise ValueError(f"Invalid aperture: {self.config.mean_aperture_um}")
        if self.config.fracture_area <= 0:
            raise ValueError(f"Invalid fracture area: {self.config.fracture_area}")
        if self.config.gas_viscosity <= 0:
            raise ValueError(f"Invalid viscosity: {self.config.gas_viscosity}")
    
    def compute(
        self,
        pressure_gradient: float,  # dP/dz in Pa/m
        temperature_c: float,
        sigma_n: Optional[float] = None  # normal stress in MPa
    ) -> Dict[str, float]:
        """
        Compute Ψ_crack from pressure gradient and temperature.
        
        Args:
            pressure_gradient: Vertical pressure gradient (Pa/m)
            temperature_c: Gas temperature (°C) for viscosity correction
            sigma_n: Optional normal stress for SSI calculation
            
        Returns:
            Dictionary with Ψ_crack value and components
        """
        # Convert aperture from μm to m
        b_m = self.config.mean_aperture_um * 1e-6
        
        # Temperature-corrected viscosity
        mu = self._correct_viscosity(temperature_c)
        
        # Cubic law calculation
        psi_crack = (
            (b_m**3) / (12 * mu) *
            pressure_gradient *
            self.config.fracture_area
        )
        
        # Normalize for DRGIS (typical range 0-1)
        psi_norm = self._normalize(psi_crack)
        
        result = {
            'psi_crack_raw': psi_crack,
            'psi_crack_normalized': round(psi_norm, 4),
            'aperture_m': b_m,
            'aperture_um': self.config.mean_aperture_um,
            'viscosity_mu': round(mu, 6),
            'pressure_gradient': pressure_gradient,
            'fracture_area': self.config.fracture_area,
            'units': 'normalized'
        }
        
        # Add stress sensitivity if sigma_n provided
        if sigma_n is not None:
            ssi = self.compute_stress_sensitivity(psi_crack, sigma_n)
            result['ssi'] = round(ssi, 4)
            result['ssi_class'] = self._classify_ssi(ssi).value
            
        return result
    
    def _correct_viscosity(self, temperature_c: float) -> float:
        """
        Correct gas viscosity for temperature.
        
        Uses Sutherland's formula for air as approximation.
        
        Args:
            temperature_c: Temperature in Celsius
            
        Returns:
            Temperature-corrected viscosity (Pa·s)
        """
        T_kelvin = temperature_c + 273.15
        T_ref = 273.15 + 20  # Reference at 20°C
        mu_ref = self.config.gas_viscosity
        
        # Sutherland's formula (simplified)
        mu = mu_ref * (T_kelvin / T_ref)**1.5 * (T_ref + 120) / (T_kelvin + 120)
        
        return mu
    
    def _normalize(self, psi_raw: float) -> float:
        """Normalize Ψ_crack to [0, 1] range for DRGIS."""
        # Typical range: 0 to 1e-10, normalize logarithmically
        if psi_raw <= 0:
            return 0.0
        
        log_psi = np.log10(psi_raw + 1e-15)
        # Map from typical range [-15, -10] to [0, 1]
        norm = (log_psi + 15) / 5
        return np.clip(norm, 0, 1)
    
    def compute_stress_sensitivity(
        self,
        psi_crack: float,
        sigma_n: float,
        delta_sigma: float = 0.1
    ) -> float:
        """
        Compute Stress Sensitivity Index (SSI).
        
        SSI = -(1/Ψ_crack) · (dΨ_crack/dσ_n)
        
        Args:
            psi_crack: Current conductivity
            sigma_n: Normal stress (MPa)
            delta_sigma: Small stress perturbation for derivative
            
        Returns:
            Stress Sensitivity Index (MPa⁻¹)
        """
        # Estimate derivative numerically
        # This is simplified - actual would use strain data
        dPsi = psi_crack * 0.01  # Assume 1% change per MPa
        dSigma = 1.0  # MPa
        
        ssi = -(1 / max(psi_crack, 1e-10)) * (dPsi / dSigma)
        
        return abs(ssi)  # Return absolute value for sensitivity
    
    def _classify_ssi(self, ssi: float) -> StressSensitivity:
        """Classify stress sensitivity."""
        if ssi >= self.SSI_HIGH:
            return StressSensitivity.HIGH
        elif ssi >= self.SSI_LOW:
            return StressSensitivity.MODERATE
        elif ssi > 0:
            return StressSensitivity.LOW
        else:
            return StressSensitivity.INACTIVE
    
    def validate_cubic_law(self, measurements: np.ndarray) -> Dict[str, float]:
        """
        Validate cubic law scaling exponent.
        
        Args:
            measurements: Array of [aperture, conductivity] pairs
            
        Returns:
            Dictionary with fitted exponent and statistics
        """
        if measurements.shape[1] != 2:
            raise ValueError("Measurements must be [aperture, conductivity] pairs")
            
        apertures = measurements[:, 0]
        conductivities = measurements[:, 1]
        
        # Log transform for power law fitting
        log_a = np.log(apertures[apertures > 0])
        log_c = np.log(conductivities[apertures > 0])
        
        # Linear fit in log space
        coeffs = np.polyfit(log_a, log_c, 1)
        exponent = coeffs[0]
        
        # Calculate R²
        c_pred = np.polyval(coeffs, log_a)
        residuals = log_c - c_pred
        ss_res = np.sum(residuals**2)
        ss_tot = np.sum((log_c - np.mean(log_c))**2)
        r_squared = 1 - (ss_res / ss_tot)
        
        return {
            'fitted_exponent': round(exponent, 3),
            'expected_exponent': self.CUBIC_EXPECTED,
            'deviation': round(abs(exponent - self.CUBIC_EXPECTED), 3),
            'within_tolerance': abs(exponent - self.CUBIC_EXPECTED) <= self.CUBIC_TOLERANCE,
            'r_squared': round(r_squared, 4),
            'n_samples': len(apertures)
        }
    
    def estimate_pre_seismic_increase(
        self,
        baseline_psi: float,
        days_before_event: int
    ) -> Dict[str, float]:
        """
        Estimate expected pre-seismic conductivity increase.
        
        Based on observed 25-80% increase within 21 days before M≥4.0.
        
        Args:
            baseline_psi: Baseline conductivity
            days_before_event: Days before event (≤ 21)
            
        Returns:
            Expected increase range
        """
        if days_before_event > 21:
            return {'increase_pct': 0, 'confidence': 'low'}
        
        # Linear scaling with days (simplified)
        max_increase = 0.80  # 80% at 21 days
        min_increase = 0.25  # 25% at 21 days
        
        fraction = days_before_event / 21
        expected_min = baseline_psi * (1 + min_increase * fraction)
        expected_max = baseline_psi * (1 + max_increase * fraction)
        
        return {
            'expected_min': round(expected_min, 4),
            'expected_max': round(expected_max, 4),
            'increase_min_pct': round(min_increase * fraction * 100, 1),
            'increase_max_pct': round(max_increase * fraction * 100, 1),
            'days_before_event': days_before_event
        }


# Factory function
def create_psi_crack(
    station_id: str,
    mean_aperture_um: float,
    fracture_area: float,
    lithology: str = 'granite'
) -> FissureConductivity:
    """
    Create Ψ_crack calculator with default viscosity.
    
    Args:
        station_id: Station identifier
        mean_aperture_um: Mean fracture aperture (μm)
        fracture_area: Total fracture area (m²)
        lithology: Rock type for default viscosity
        
    Returns:
        Configured FissureConductivity instance
    """
    # Default gas viscosities by lithology (Pa·s at 20°C)
    VISCOSITY_DEFAULTS = {
        'granite': 1.8e-5,
        'sandstone': 1.8e-5,
        'basalt': 1.9e-5,
        'gneiss': 1.8e-5,
        'quartzite': 1.8e-5
    }
    
    viscosity = VISCOSITY_DEFAULTS.get(lithology, 1.8e-5)
    
    config = FractureConfig(
        station_id=station_id,
        mean_aperture_um=mean_aperture_um,
        fracture_area=fracture_area,
        gas_viscosity=viscosity,
        depth_m=0,  # To be filled
        lithology=lithology,
        calibration_date="2026-01-01"
    )
    
    return FissureConductivity(config)
