"""
He_ratio - Helium-4 Signature Parameter
Uses helium isotopic composition to discriminate mantle vs crustal sources.

Mathematical Definition:
He_ratio = R/Ra = (³He/⁴He)_sample / (³He/⁴He)_atmosphere

Two-component mixing model:
He_ratio = f_mantle · R_mantle + (1 - f_mantle) · R_crustal

Interpretation:
- R/Ra < 0.10: shallow crustal source (<5 km)
- R/Ra 0.10-0.50: mid-crustal (5-20 km)
- R/Ra 0.50-2.00: deep crust/lower lithosphere (20-50 km)
- R/Ra > 2.00: confirmed mantle connectivity
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum


class SourceType(Enum):
    """Helium source type classification."""
    SHALLOW_CRUSTAL = "shallow_crustal"
    MID_CRUSTAL = "mid_crustal"
    DEEP_CRUSTAL = "deep_crustal"
    LITHOSPHERIC = "lithospheric"
    MANTLE = "mantle"
    MIXED = "mixed"


@dataclass
class HeliumConfig:
    """Configuration for helium isotope analysis."""
    station_id: str
    craton_name: str
    
    # End-member values
    R_mantle: float = 8.0  # MORB-like upper mantle
    R_crustal: float = 0.03  # Mean Precambrian craton
    
    # Depth model parameters
    z_moho_km: float = 35.0  # Moho depth from CRUST1.0
    z_lab_km: float = 150.0  # LAB depth from tomography
    
    # Measurement precision
    precision_ra: float = 0.05  # ±0.05 Ra units
    depth_uncertainty_m: int = 800  # ±800 m


class HeliumRatio:
    """
    He_ratio Calculator - Helium-4 Signature Parameter.
    
    Discriminates mantle vs crustal sources and estimates fissure depth.
    
    Attributes:
        config: Helium analysis configuration
        measurements: Historical measurements
    """
    
    # Atmospheric standard
    RA = 1.384e-6  # (³He/⁴He)_atmosphere
    
    def __init__(self, config: HeliumConfig):
        """
        Initialize He_ratio calculator.
        
        Args:
            config: Helium analysis configuration
        """
        self.config = config
        self.measurements = []
        
    def compute(
        self,
        he3_he4_ratio: float,  # Measured ³He/⁴He ratio
        error: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Compute He_ratio from measured isotopic ratio.
        
        Args:
            he3_he4_ratio: Measured ³He/⁴He ratio
            error: Optional measurement error
            
        Returns:
            Dictionary with He_ratio value and interpretation
        """
        # Calculate R/Ra
        r_ra = he3_he4_ratio / self.RA
        
        # Determine source type
        source_type, mantle_fraction = self._classify_source(r_ra)
        
        # Estimate depth
        depth = self._estimate_depth(r_ra, mantle_fraction)
        
        result = {
            'he_ratio': round(r_ra, 3),
            'raw_ratio': he3_he4_ratio,
            'source_type': source_type.value,
            'mantle_fraction': round(mantle_fraction, 3),
            'crustal_fraction': round(1 - mantle_fraction, 3),
            'depth_km': round(depth, 1),
            'depth_m': int(depth * 1000),
            'depth_uncertainty_m': self.config.depth_uncertainty_m,
            'confidence': self._get_confidence(r_ra, error)
        }
        
        if error is not None:
            result['error'] = error
            result['error_ra'] = error / self.RA
        
        # Store measurement
        self.measurements.append(result)
        
        return result
    
    def _classify_source(self, r_ra: float) -> Tuple[SourceType, float]:
        """
        Classify helium source type and calculate mantle fraction.
        
        Using two-component mixing model:
        f_mantle = (R - R_crustal) / (R_mantle - R_crustal)
        """
        if r_ra <= 0:
            return SourceType.SHALLOW_CRUSTAL, 0.0
        
        # Calculate mantle fraction
        f_mantle = (r_ra - self.config.R_crustal) / (self.config.R_mantle - self.config.R_crustal)
        f_mantle = np.clip(f_mantle, 0, 1)
        
        # Classify based on R/Ra and mantle fraction
        if r_ra < 0.10:
            return SourceType.SHALLOW_CRUSTAL, f_mantle
        elif r_ra < 0.50:
            return SourceType.MID_CRUSTAL, f_mantle
        elif r_ra < 2.00:
            if f_mantle < 0.3:
                return SourceType.DEEP_CRUSTAL, f_mantle
            else:
                return SourceType.LITHOSPHERIC, f_mantle
        elif r_ra < 8.0:
            return SourceType.MANTLE, f_mantle
        else:
            return SourceType.MIXED, f_mantle
    
    def _estimate_depth(self, r_ra: float, mantle_fraction: float) -> float:
        """
        Estimate fissure depth using two-layer model.
        
        z = z_Moho · (1 - f_mantle) + z_LAB · f_mantle
        """
        if mantle_fraction <= 0:
            # Pure crustal - use simplified depth from R/Ra
            if r_ra < 0.10:
                return 2.5  # 2.5 km mean for shallow
            elif r_ra < 0.50:
                return 12.5  # 12.5 km mean for mid-crustal
            else:
                return 35.0  # Near Moho
        
        # Mixing model depth
        depth = (self.config.z_moho_km * (1 - mantle_fraction) + 
                 self.config.z_lab_km * mantle_fraction)
        
        return depth
    
    def _get_confidence(self, r_ra: float, error: Optional[float]) -> str:
        """Get confidence level for measurement."""
        if error is None:
            return 'moderate'
        
        relative_error = error / (r_ra * self.RA)
        
        if relative_error < 0.05:
            return 'high'
        elif relative_error < 0.10:
            return 'moderate'
        else:
            return 'low'
    
    def compute_mantle_flux(
        self,
        total_he_flux: float,  # Total ⁴He flux (atoms/cm²/s)
        r_ra: float
    ) -> Dict[str, float]:
        """
        Compute mantle-derived helium flux.
        
        Args:
            total_he_flux: Total ⁴He flux
            r_ra: Measured R/Ra
            
        Returns:
            Mantle and crustal flux components
        """
        # Calculate mantle fraction
        f_mantle = (r_ra - self.config.R_crustal) / (self.config.R_mantle - self.config.R_crustal)
        f_mantle = np.clip(f_mantle, 0, 1)
        
        mantle_flux = total_he_flux * f_mantle
        crustal_flux = total_he_flux * (1 - f_mantle)
        
        return {
            'total_flux': total_he_flux,
            'mantle_flux': mantle_flux,
            'crustal_flux': crustal_flux,
            'mantle_fraction': f_mantle,
            'units': 'atoms·cm⁻²·s⁻¹'
        }
    
    def detect_deep_connectivity(self, r_ra: float) -> Dict[str, bool]:
        """
        Detect direct lithospheric connectivity.
        
        Args:
            r_ra: Measured R/Ra
            
        Returns:
            Connectivity flags
        """
        return {
            'mantle_connected': r_ra > 2.0,
            'lithospheric_connected': r_ra > 0.5,
            'deep_crustal_connected': r_ra > 0.1,
            'active_conduit': r_ra > 0.5 and r_ra < 8.0
        }
    
    def estimate_magmatic_contribution(
        self,
        r_ra: float,
        co2_flux: Optional[float] = None,
        co2_d13c: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Estimate magmatic contribution in volcanic settings.
        
        Used in Atacama-type environments for volcanic-tectonic discrimination.
        
        Args:
            r_ra: Measured R/Ra
            co2_flux: Optional CO₂ flux
            co2_d13c: Optional δ¹³C value
            
        Returns:
            Magmatic contribution estimate
        """
        # Helium-based magmatic fraction
        f_mantle = (r_ra - self.config.R_crustal) / (self.config.R_mantle - self.config.R_crustal)
        f_mantle = np.clip(f_mantle, 0, 1)
        
        result = {
            'magmatic_fraction_he': round(f_mantle, 3),
            'crustal_fraction_he': round(1 - f_mantle, 3),
            'method': 'helium_only'
        }
        
        # Use CO₂ if available for cross-validation
        if co2_flux is not None and co2_d13c is not None:
            # Simplified CO₂-based estimate
            # Typical mantle δ¹³C ≈ -5‰, crustal ≈ -20‰
            f_mantle_co2 = (co2_d13c + 20) / 15  # -20 to -5 maps to 0-1
            f_mantle_co2 = np.clip(f_mantle_co2, 0, 1)
            
            result['magmatic_fraction_co2'] = round(f_mantle_co2, 3)
            result['method'] = 'combined'
            
            # Weighted average
            f_combined = (f_mantle * 0.7 + f_mantle_co2 * 0.3)
            result['magmatic_fraction_combined'] = round(f_combined, 3)
        
        return result
    
    def time_series_analysis(
        self,
        measurements: List[Dict[str, float]]
    ) -> Dict[str, float]:
        """
        Analyze He_ratio time series for trends.
        
        Args:
            measurements: List of He_ratio measurements with timestamps
            
        Returns:
            Trend analysis results
        """
        if len(measurements) < 2:
            return {'trend_detected': False, 'confidence': 'low'}
        
        # Extract values and times
        times = np.array([m.get('timestamp', i) for i, m in enumerate(measurements)])
        values = np.array([m['he_ratio'] for m in measurements])
        
        # Simple linear trend
        coeffs = np.polyfit(times, values, 1)
        slope = coeffs[0]
        
        # Calculate statistics
        mean_value = np.mean(values)
        std_value = np.std(values)
        
        # Detect significant trend
        trend_detected = abs(slope) > 0.01 * mean_value / (times[-1] - times[0])
        
        return {
            'trend_detected': bool(trend_detected),
            'slope': round(slope, 4),
            'mean_value': round(mean_value, 3),
            'std_value': round(std_value, 3),
            'min_value': round(np.min(values), 3),
            'max_value': round(np.max(values), 3),
            'n_measurements': len(measurements),
            'trend_direction': 'increasing' if slope > 0 else 'decreasing' if slope < 0 else 'stable'
        }
    
    def validate_with_crustal_model(
        self,
        predicted_r_ra: float,
        measured_r_ra: float,
        crustal_age_ma: float
    ) -> Dict[str, float]:
        """
        Validate measurement against crustal production model.
        
        Args:
            predicted_r_ra: Predicted R/Ra from crustal model
            measured_r_ra: Measured R/Ra
            crustal_age_ma: Crustal age in Ma
            
        Returns:
            Validation statistics
        """
        difference = abs(predicted_r_ra - measured_r_ra)
        relative_diff = difference / ((predicted_r_ra + measured_r_ra) / 2) * 100
        
        # Check if within expected range for crustal age
        # Older crust should have lower R/Ra
        expected_max = 0.05 + 0.02 * (4500 / crustal_age_ma)  # Rough approximation
        
        return {
            'agreement': difference <= 0.1,
            'difference': round(difference, 3),
            'relative_diff_pct': round(relative_diff, 1),
            'within_crustal_range': measured_r_ra <= expected_max,
            'expected_max': round(expected_max, 3),
            'crustal_age_ma': crustal_age_ma
        }


# Factory function with craton-specific defaults
def create_he_ratio(
    station_id: str,
    craton_name: str
) -> HeliumRatio:
    """
    Create He_ratio calculator with craton-specific defaults.
    
    Args:
        station_id: Station identifier
        craton_name: Craton name for depth model
        
    Returns:
        Configured HeliumRatio instance
    """
    # Craton-specific Moho depths (from CRUST1.0)
    CRATON_MOHO = {
        'saharan': 38.0,
        'arabian': 42.0,
        'kaapvaal': 40.0,
        'yilgarn': 45.0,
        'atacama': 50.0,
        'tarim': 55.0,
        'scandinavian': 48.0
    }
    
    # Craton-specific crustal end-members
    CRATON_R_CRUSTAL = {
        'saharan': 0.03,
        'arabian': 0.04,
        'kaapvaal': 0.02,
        'yilgarn': 0.02,
        'atacama': 0.05,
        'tarim': 0.03,
        'scandinavian': 0.04
    }
    
    z_moho = CRATON_MOHO.get(craton_name.lower(), 40.0)
    r_crustal = CRATON_R_CRUSTAL.get(craton_name.lower(), 0.03)
    
    config = HeliumConfig(
        station_id=station_id,
        craton_name=craton_name,
        z_moho_km=z_moho,
        R_crustal=r_crustal
    )
    
    return HeliumRatio(config)
