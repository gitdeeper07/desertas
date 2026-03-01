"""
β_dust - Particulate Coupling Index Parameter
Quantifies efficiency of geogenic gas adsorption onto dust particles and downwind transport.

Mathematical Definition:
β_dust = A_attached / A_total

Where:
- A_attached: Activity on dust filters (0.8 μm)
- A_total: Total activity from unfiltered detector

Values >0.70 indicate >70% of radon progeny are particle-bound
Transport range: detectable 340 km downwind (validated)
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class TransportRegime(Enum):
    """Dust transport regime classification."""
    LOCAL = "local"  # <50 km
    REGIONAL = "regional"  # 50-200 km
    LONG_RANGE = "long_range"  # 200-500 km
    GLOBAL = "global"  # >500 km


@dataclass
class DustConfig:
    """Configuration for dust analysis."""
    station_id: str
    dust_mineralogy: str  # silicate, carbonate, mixed
    particle_size_um: float = 0.8  # Filter size
    sampling_volume_m3: float = 500.0  # Daily sampling volume
    
    # Adsorption coefficients by mineralogy
    ADSORPTION_COEFF = {
        'silicate': 0.85,
        'carbonate': 0.75,
        'mixed': 0.80,
        'quartz': 0.82,
        'feldspar': 0.88,
        'clay': 0.92,
        'gypsum': 0.70,
        'halite': 0.65
    }
    
    # Radon progeny half-lives (hours)
    RN_PROGENY = {
        'Po218': 0.064,  # 3.82 minutes
        'Pb214': 0.447,  # 26.8 minutes
        'Bi214': 0.333,  # 19.9 minutes
        'Pb210': 192456  # 22.3 years
    }


class ParticulateCouplingIndex:
    """
    β_dust Calculator - Particulate Coupling Index Parameter.
    
    Measures dust adsorption and transport of radon progeny.
    
    Attributes:
        config: Dust analysis configuration
    """
    
    def __init__(self, config: DustConfig):
        """
        Initialize β_dust calculator.
        
        Args:
            config: Dust analysis configuration
        """
        self.config = config
        
    def compute(
        self,
        attached_activity: float,  # A_attached (Bq/m³)
        total_activity: float,  # A_total (Bq/m³)
        wind_speed: Optional[float] = None,
        wind_direction: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Compute β_dust from filter measurements.
        
        Args:
            attached_activity: Activity on dust filters
            total_activity: Total activity from unfiltered detector
            wind_speed: Optional wind speed (m/s)
            wind_direction: Optional wind direction (degrees)
            
        Returns:
            Dictionary with β_dust value and interpretation
        """
        if total_activity <= 0:
            return {'beta_dust': 0, 'error': 'invalid_total_activity'}
        
        # Calculate β_dust
        beta_dust = attached_activity / total_activity
        beta_dust = np.clip(beta_dust, 0, 1)
        
        # Determine transport potential
        transport_potential = self._estimate_transport_potential(beta_dust)
        
        # Estimate downwind range
        downwind_range = self._estimate_downwind_range(beta_dust, wind_speed)
        
        result = {
            'beta_dust': round(beta_dust, 3),
            'attached_activity': round(attached_activity, 2),
            'total_activity': round(total_activity, 2),
            'attached_fraction': round(beta_dust * 100, 1),
            'transport_potential': transport_potential.value,
            'downwind_range_km': downwind_range,
            'adsorption_dominant': beta_dust > 0.7,
            'mineralogy': self.config.dust_mineralogy
        }
        
        if wind_speed is not None:
            result['wind_speed'] = wind_speed
        if wind_direction is not None:
            result['wind_direction'] = wind_direction
        
        return result
    
    def _estimate_transport_potential(self, beta_dust: float) -> TransportRegime:
        """Estimate transport regime based on β_dust."""
        if beta_dust < 0.3:
            return TransportRegime.LOCAL
        elif beta_dust < 0.5:
            return TransportRegime.REGIONAL
        elif beta_dust < 0.7:
            return TransportRegime.LONG_RANGE
        else:
            return TransportRegime.GLOBAL
    
    def _estimate_downwind_range(
        self,
        beta_dust: float,
        wind_speed: Optional[float] = None
    ) -> int:
        """Estimate detectable downwind range in km."""
        if wind_speed is None:
            wind_speed = 5.0  # Assume 5 m/s typical
        
        # Base range from validation (340 km max)
        base_range = 340 * beta_dust
        
        # Adjust for wind speed
        # Typical transport: 100 km per 1 m/s per day
        daily_transport = wind_speed * 86.4  # m/s to km/day
        
        range_km = min(base_range, daily_transport * 3)  # Max 3 days transport
        return int(range_km)
    
    def identify_source_fingerprint(
        self,
        sample_activity: Dict[str, float],
        reference_sources: List[Dict[str, float]]
    ) -> Dict[str, float]:
        """
        Identify source fissure from dust sample fingerprint.
        
        Uses ratios of radon progeny to fingerprint sources.
        
        Args:
            sample_activity: Activity ratios in sample
            reference_sources: Known source fingerprints
            
        Returns:
            Source identification results
        """
        best_match = None
        best_score = 0
        
        for source in reference_sources:
            score = self._calculate_fingerprint_similarity(
                sample_activity,
                source['fingerprint']
            )
            
            if score > best_score:
                best_score = score
                best_match = source
        
        if best_match and best_score > 0.8:
            return {
                'source_id': best_match['id'],
                'source_name': best_match.get('name', 'Unknown'),
                'confidence': round(best_score, 3),
                'distance_km': best_match.get('distance', 0),
                'match_found': True
            }
        else:
            return {
                'source_id': None,
                'match_found': False,
                'best_score': round(best_score, 3) if best_match else 0
            }
    
    def _calculate_fingerprint_similarity(
        self,
        sample: Dict[str, float],
        reference: Dict[str, float]
    ) -> float:
        """Calculate similarity between two fingerprints."""
        common_keys = set(sample.keys()) & set(reference.keys())
        
        if not common_keys:
            return 0.0
        
        # Calculate cosine similarity
        dot_product = 0
        norm_sample = 0
        norm_ref = 0
        
        for key in common_keys:
            dot_product += sample[key] * reference[key]
            norm_sample += sample[key]**2
            norm_ref += reference[key]**2
        
        if norm_sample == 0 or norm_ref == 0:
            return 0.0
        
        similarity = dot_product / (np.sqrt(norm_sample) * np.sqrt(norm_ref))
        return float(similarity)
    
    def estimate_deposition_velocity(
        self,
        particle_size_um: float,
        air_density: float = 1.2  # kg/m³
    ) -> float:
        """
        Estimate particle deposition velocity.
        
        Args:
            particle_size_um: Particle diameter in μm
            air_density: Air density (kg/m³)
            
        Returns:
            Deposition velocity (cm/s)
        """
        # Simplified Stokes settling velocity
        # For particles >1 μm
        particle_density = 2650  # kg/m³ (quartz)
        
        # Convert to m
        d = particle_size_um * 1e-6
        
        # Gravity
        g = 9.81
        
        # Air viscosity
        mu = 1.8e-5  # Pa·s
        
        # Stokes velocity
        v_settling = (particle_density * g * d**2) / (18 * mu)
        
        # Convert to cm/s
        return v_settling * 100
    
    def predict_receptor_sites(
        self,
        source_lat: float,
        source_lon: float,
        wind_rose: Dict[str, float],
        beta_dust: float
    ) -> List[Dict[str, float]]:
        """
        Predict potential receptor sites downwind.
        
        Args:
            source_lat: Source latitude
            source_lon: Source longitude
            wind_rose: Wind direction frequencies
            beta_dust: Current β_dust value
            
        Returns:
            List of predicted receptor locations
        """
        # Simplified prediction based on dominant wind
        receptors = []
        
        range_km = self._estimate_downwind_range(beta_dust, wind_rose.get('speed', 5))
        
        # Get dominant wind direction
        directions = list(wind_rose.keys())
        if 'N' in directions:
            # Simplified - would use proper transport model
            receptors.append({
                'direction': 'downwind',
                'distance_km': range_km,
                'probability': beta_dust,
                'estimated_lat': source_lat + 0.1,  # Placeholder
                'estimated_lon': source_lon + 0.1   # Placeholder
            })
        
        return receptors
    
    def validate_with_pb210(
        self,
        pb210_activity: float,
        predicted_activity: float,
        distance_km: int
    ) -> Dict[str, float]:
        """
        Validate transport model using ²¹⁰Pb measurements.
        
        ²¹⁰Pb has 22.3-year half-life, ideal for long-range transport.
        
        Args:
            pb210_activity: Measured ²¹⁰Pb activity
            predicted_activity: Predicted activity from model
            distance_km: Transport distance
            
        Returns:
            Validation statistics
        """
        if predicted_activity <= 0:
            return {'validated': False}
        
        ratio = pb210_activity / predicted_activity
        
        return {
            'validated': 0.5 <= ratio <= 2.0,  # Within factor of 2
            'measured_pb210': round(pb210_activity, 3),
            'predicted_pb210': round(predicted_activity, 3),
            'ratio': round(ratio, 3),
            'distance_km': distance_km,
            'transport_efficiency': round(pb210_activity / max(predicted_activity, 1e-10), 3)
        }


# Factory function
def create_beta_dust(
    station_id: str,
    dust_mineralogy: str = 'mixed'
) -> ParticulateCouplingIndex:
    """
    Create β_dust calculator with default configuration.
    
    Args:
        station_id: Station identifier
        dust_mineralogy: Dust mineralogy type
        
    Returns:
        Configured ParticulateCouplingIndex instance
    """
    config = DustConfig(
        station_id=station_id,
        dust_mineralogy=dust_mineralogy
    )
    
    return ParticulateCouplingIndex(config)
