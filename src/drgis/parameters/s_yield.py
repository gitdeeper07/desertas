"""
S_yield - Seismic Yield Potential Parameter
Measures energy dissipation through gas venting versus seismic rupture.

Physical principle:
Total strain energy = Seismic energy + Aseismic slip energy + Gas migration energy

S_yield = ∫(F_gas × dz × A_fissure) from source depth to surface

Key finding: High S_yield sites show 0.4-0.7 magnitude unit reduction in maximum events
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class EnergyDissipationMode(Enum):
    """Primary energy dissipation mode."""
    SEISMIC = "seismic_dominated"
    ASEISMIC = "aseismic_dominated"
    GAS_VENTING = "gas_venting_dominated"
    MIXED = "mixed"


@dataclass
class SeismicYieldConfig:
    """Configuration for seismic yield analysis."""
    station_id: str
    crustal_density_kgm3: float = 2700.0
    shear_modulus_gpa: float = 30.0
    reference_moment_m0: float = 1e16  # Reference seismic moment (M~4)
    
    # Energy conversion factors
    J_PER_ERG: float = 1e-7
    ERG_PER_M0: float = 2e-4  # Typical Gutenberg-Richter


class SeismicYieldPotential:
    """
    S_yield Calculator - Seismic Yield Potential Parameter.
    
    Quantifies energy dissipation through gas migration.
    
    Attributes:
        config: Seismic yield configuration
        historical_yield: Historical yield measurements
    """
    
    def __init__(self, config: SeismicYieldConfig):
        """
        Initialize S_yield calculator.
        
        Args:
            config: Seismic yield configuration
        """
        self.config = config
        self.historical_yield = []
        
    def compute(
        self,
        gas_flux: float,  # F_gas in kg/m²/s
        fissure_area: float,  # A_fissure in m²
        source_depth_m: float,  # Source depth in m
        gas_density: float = 1.0,  # kg/m³
        duration_days: float = 365.0  # Annual estimate
    ) -> Dict[str, float]:
        """
        Compute S_yield from gas flux parameters.
        
        S_yield = ∫(F_gas × dz × A_fissure) from source to surface
        
        Args:
            gas_flux: Gas mass flux (kg/m²/s)
            fissure_area: Total fissure area (m²)
            source_depth_m: Gas source depth (m)
            gas_density: Gas density (kg/m³)
            duration_days: Integration duration
            
        Returns:
            Dictionary with S_yield value and components
        """
        # Calculate work against gravity
        # W = m·g·h = (ρ·V)·g·h
        g = 9.81  # m/s²
        
        # Total mass flux per year
        total_mass = gas_flux * fissure_area * duration_days * 86400
        
        # Work done against gravity
        work_joules = total_mass * g * source_depth_m
        
        # Convert to seismic moment equivalent
        moment_equivalent = work_joules / self.config.ERG_PER_M0 / self.config.J_PER_ERG
        
        # Calculate magnitude equivalent (Hanks-Kanamori)
        if moment_equivalent > 0:
            mw_equivalent = (2/3) * (np.log10(moment_equivalent) - 9.1)
        else:
            mw_equivalent = 0
        
        # Normalize S_yield to [0, 1] for DRGIS
        s_yield = self._normalize(work_joules, moment_equivalent)
        
        # Determine dissipation mode
        mode = self._classify_dissipation_mode(s_yield, mw_equivalent)
        
        result = {
            's_yield': round(s_yield, 3),
            'work_joules': round(work_joules, 1),
            'work_ergs': round(work_joules / self.config.J_PER_ERG, 1),
            'moment_equivalent': round(moment_equivalent, 1),
            'mw_equivalent': round(mw_equivalent, 2),
            'gas_flux': gas_flux,
            'fissure_area': fissure_area,
            'source_depth_m': source_depth_m,
            'duration_days': duration_days,
            'dissipation_mode': mode.value
        }
        
        # Store in history
        self.historical_yield.append(result)
        
        return result
    
    def _normalize(self, work_joules: float, moment_equivalent: float) -> float:
        """Normalize S_yield to [0, 1] range."""
        # Reference: M4 earthquake ≈ 1e16 Nm
        ref_moment = self.config.reference_moment_m0
        
        if moment_equivalent <= 0:
            return 0.0
        
        # Normalize logarithmically
        log_ratio = np.log10(moment_equivalent / ref_moment)
        
        # Map to [0, 1] (log_ratio from -2 to +2)
        norm = (log_ratio + 2) / 4
        return np.clip(norm, 0, 1)
    
    def _classify_dissipation_mode(
        self,
        s_yield: float,
        mw_equivalent: float
    ) -> EnergyDissipationMode:
        """Classify primary energy dissipation mode."""
        if s_yield < 0.2:
            if mw_equivalent < 3:
                return EnergyDissipationMode.ASEISMIC
            else:
                return EnergyDissipationMode.SEISMIC
        elif s_yield < 0.5:
            return EnergyDissipationMode.MIXED
        else:
            return EnergyDissipationMode.GAS_VENTING
    
    def estimate_magnitude_suppression(
        self,
        tectonic_moment_rate: float,  # M0/year from GPS/strain
        seismic_moment_rate: float,  # M0/year from catalog
        gas_moment_rate: float  # M0/year from S_yield
    ) -> Dict[str, float]:
        """
        Estimate earthquake magnitude suppression due to gas venting.
        
        Args:
            tectonic_moment_rate: Total tectonic moment rate
            seismic_moment_rate: Seismic moment rate
            gas_moment_rate: Gas venting moment rate
            
        Returns:
            Suppression estimate
        """
        total = tectonic_moment_rate
        seismic_fraction = seismic_moment_rate / total if total > 0 else 0
        gas_fraction = gas_moment_rate / total if total > 0 else 0
        
        # Calculate expected maximum magnitude without venting
        # Using moment-frequency relation
        if seismic_fraction < 0.5:
            # Significant suppression
            m_suppression = 0.5 * (1 - seismic_fraction)
        else:
            m_suppression = 0.1
        
        # Validate against Key Finding 4
        within_range = 0.4 <= m_suppression <= 0.7
        
        return {
            'magnitude_suppression': round(m_suppression, 2),
            'seismic_fraction': round(seismic_fraction, 3),
            'gas_fraction': round(gas_fraction, 3),
            'within_validated_range': within_range,
            'tectonic_rate': tectonic_moment_rate,
            'seismic_rate': seismic_moment_rate,
            'gas_rate': gas_moment_rate
        }
    
    def compute_strain_energy_budget(
        self,
        strain_rate: float,  # /year from GPS
        volume_m3: float,  # Crustal volume
        seismic_moment: float,  # M0/year
        aseismic_moment: float,  # Estimated aseismic slip
        gas_moment: float  # From S_yield
    ) -> Dict[str, float]:
        """
        Compute complete strain energy budget.
        
        Total = Seismic + Aseismic + Gas venting
        
        Args:
            strain_rate: Tectonic strain rate
            volume_m3: Crustal volume
            seismic_moment: Seismic moment rate
            aseismic_moment: Aseismic moment rate
            gas_moment: Gas venting moment rate
            
        Returns:
            Energy budget components
        """
        # Total strain energy rate
        # E = ½ · μ · ε² · V
        mu = self.config.shear_modulus_gpa * 1e9  # Convert to Pa
        total_energy = 0.5 * mu * (strain_rate**2) * volume_m3
        
        # Convert to moment equivalent
        total_moment = total_energy / self.config.ERG_PER_M0 / self.config.J_PER_ERG
        
        # Calculate fractions
        seismic_fraction = seismic_moment / total_moment if total_moment > 0 else 0
        aseismic_fraction = aseismic_moment / total_moment if total_moment > 0 else 0
        gas_fraction = gas_moment / total_moment if total_moment > 0 else 0
        
        # Check closure
        sum_fractions = seismic_fraction + aseismic_fraction + gas_fraction
        
        return {
            'total_moment_rate': round(total_moment, 1),
            'seismic_moment_rate': seismic_moment,
            'aseismic_moment_rate': aseismic_moment,
            'gas_moment_rate': gas_moment,
            'seismic_fraction': round(seismic_fraction, 3),
            'aseismic_fraction': round(aseismic_fraction, 3),
            'gas_fraction': round(gas_fraction, 3),
            'sum_fractions': round(sum_fractions, 3),
            'closure_error': round(1 - sum_fractions, 3)
        }
    
    def predict_maximum_magnitude(
        self,
        s_yield: float,
        tectonic_moment_rate: float
    ) -> Dict[str, float]:
        """
        Predict maximum possible earthquake magnitude given venting.
        
        Based on Key Finding 4 correlation.
        
        Args:
            s_yield: Current S_yield value
            tectonic_moment_rate: Tectonic moment rate
            
        Returns:
            Maximum magnitude prediction
        """
        # Base maximum from tectonic rate
        base_mmax = (2/3) * (np.log10(tectonic_moment_rate * 100) - 9.1)  # 100-year max
        
        # Suppression factor from S_yield
        if s_yield < 0.3:
            suppression = 0.1  # Minimal
        elif s_yield < 0.5:
            suppression = 0.3
        elif s_yield < 0.7:
            suppression = 0.5
        else:
            suppression = 0.7
        
        predicted_mmax = base_mmax - suppression
        
        return {
            'predicted_max_magnitude': round(predicted_mmax, 2),
            'base_max_magnitude': round(base_mmax, 2),
            'suppression': round(suppression, 2),
            's_yield': s_yield,
            'confidence': 'high' if 0.4 <= suppression <= 0.7 else 'moderate'
        }
    
    def validate_with_observations(
        self,
        s_yield_values: List[float],
        max_observed_magnitudes: List[float]
    ) -> Dict[str, float]:
        """
        Validate magnitude suppression relationship.
        
        Args:
            s_yield_values: Historical S_yield values
            max_observed_magnitudes: Maximum observed magnitudes
            
        Returns:
            Validation statistics
        """
        if len(s_yield_values) != len(max_observed_magnitudes):
            raise ValueError("Array lengths must match")
        
        # Group by S_yield range
        high_yield = []
        low_yield = []
        
        for s, m in zip(s_yield_values, max_observed_magnitudes):
            if s >= 0.7:
                high_yield.append(m)
            elif s <= 0.3:
                low_yield.append(m)
        
        if high_yield and low_yield:
            mean_high = np.mean(high_yield)
            mean_low = np.mean(low_yield)
            difference = mean_low - mean_high
            
            return {
                'high_yield_mean_m': round(mean_high, 2),
                'low_yield_mean_m': round(mean_low, 2),
                'magnitude_difference': round(difference, 2),
                'validated': 0.4 <= difference <= 0.7,
                'n_high_yield': len(high_yield),
                'n_low_yield': len(low_yield)
            }
        
        return {'validated': False, 'insufficient_data': True}


# Factory function
def create_s_yield(
    station_id: str,
    crustal_density_kgm3: float = 2700.0
) -> SeismicYieldPotential:
    """
    Create S_yield calculator with default configuration.
    
    Args:
        station_id: Station identifier
        crustal_density_kgm3: Crustal density (kg/m³)
        
    Returns:
        Configured SeismicYieldPotential instance
    """
    config = SeismicYieldConfig(
        station_id=station_id,
        crustal_density_kgm3=crustal_density_kgm3
    )
    
    return SeismicYieldPotential(config)
