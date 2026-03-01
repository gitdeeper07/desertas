"""
DRGIS Composite Score Calculator
Desert Rock-Gas Intelligence Score - Core calculation engine

DRGIS = 0.18·ΔΦ_th* + 0.16·Ψ_crack* + 0.18·Rn_pulse* + 0.12·Ω_arid*
      + 0.14·Γ_geo* + 0.10·He_ratio* + 0.07·β_dust* + 0.05·S_yield*

where Pi* = (Pi_obs - Pi_background) / (Pi_anomaly_threshold - Pi_background)

AI-adjusted: DRGIS_adj = sigmoid(DRGIS_raw + β_craton + β_season + β_depth)
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import json
import yaml
from pathlib import Path


class AlertLevel(Enum):
    """DRGIS alert levels with operational thresholds."""
    BACKGROUND = "BACKGROUND"  # < 0.30
    WATCH = "WATCH"           # 0.30 - 0.48
    ALERT = "ALERT"           # 0.48 - 0.65
    EMERGENCY = "EMERGENCY"    # 0.65 - 0.80
    CRITICAL = "CRITICAL"     # > 0.80


@dataclass
class ParameterWeights:
    """DRGIS parameter weights (from Bayesian analysis)."""
    delta_phi_th: float = 0.18  # Diurnal Thermal Flux
    psi_crack: float = 0.16     # Fissure Conductivity
    rn_pulse: float = 0.18      # Radon Spiking Index
    omega_arid: float = 0.12    # Desiccation Index
    gamma_geo: float = 0.14     # Geogenic Migration Velocity
    he_ratio: float = 0.10      # Helium-4 Signature
    beta_dust: float = 0.07     # Particulate Coupling Index
    s_yield: float = 0.05       # Seismic Yield Potential
    
    def validate(self) -> bool:
        """Validate weights sum to 1.0."""
        total = (self.delta_phi_th + self.psi_crack + self.rn_pulse +
                self.omega_arid + self.gamma_geo + self.he_ratio +
                self.beta_dust + self.s_yield)
        return abs(total - 1.0) < 1e-6
    
    def to_dict(self) -> Dict[str, float]:
        """Convert weights to dictionary."""
        return {
            'ΔΦ_th': self.delta_phi_th,
            'Ψ_crack': self.psi_crack,
            'Rn_pulse': self.rn_pulse,
            'Ω_arid': self.omega_arid,
            'Γ_geo': self.gamma_geo,
            'He_ratio': self.he_ratio,
            'β_dust': self.beta_dust,
            'S_yield': self.s_yield
        }


@dataclass
class AlertThresholds:
    """Operational alert thresholds."""
    background_max: float = 0.30
    watch_max: float = 0.48
    alert_max: float = 0.65
    emergency_max: float = 0.80
    
    def get_level(self, drgis: float) -> AlertLevel:
        """Determine alert level from DRGIS value."""
        if drgis < self.background_max:
            return AlertLevel.BACKGROUND
        elif drgis < self.watch_max:
            return AlertLevel.WATCH
        elif drgis < self.alert_max:
            return AlertLevel.ALERT
        elif drgis < self.emergency_max:
            return AlertLevel.EMERGENCY
        else:
            return AlertLevel.CRITICAL


@dataclass
class StationBackground:
    """Station-specific background statistics."""
    station_id: str
    craton: str
    delta_phi_th: Dict[str, float] = field(default_factory=dict)
    psi_crack: Dict[str, float] = field(default_factory=dict)
    rn_pulse: Dict[str, float] = field(default_factory=dict)
    omega_arid: Dict[str, float] = field(default_factory=dict)
    gamma_geo: Dict[str, float] = field(default_factory=dict)
    he_ratio: Dict[str, float] = field(default_factory=dict)
    beta_dust: Dict[str, float] = field(default_factory=dict)
    s_yield: Dict[str, float] = field(default_factory=dict)
    
    def get_background(self, param: str) -> float:
        """Get background value for parameter."""
        return getattr(self, param, {}).get('background', 0.0)
    
    def get_threshold(self, param: str) -> float:
        """Get anomaly threshold for parameter."""
        return getattr(self, param, {}).get('threshold', 1.0)


class DRGISCalculator:
    """
    DRGIS Composite Score Calculator.
    
    Computes Desert Rock-Gas Intelligence Score from eight parameters
    with station-specific normalization and AI adjustment.
    
    Attributes:
        weights: Parameter weights
        thresholds: Alert thresholds
        backgrounds: Station-specific backgrounds
    """
    
    def __init__(
        self,
        weights: Optional[ParameterWeights] = None,
        thresholds: Optional[AlertThresholds] = None
    ):
        """
        Initialize DRGIS calculator.
        
        Args:
            weights: Optional custom parameter weights
            thresholds: Optional custom alert thresholds
        """
        self.weights = weights or ParameterWeights()
        self.thresholds = thresholds or AlertThresholds()
        self.backgrounds: Dict[str, StationBackground] = {}
        
        if not self.weights.validate():
            raise ValueError("Parameter weights must sum to 1.0")
    
    def load_backgrounds(self, background_file: Union[str, Path]) -> None:
        """
        Load station-specific backgrounds from file.
        
        Args:
            background_file: Path to YAML/JSON file with backgrounds
        """
        path = Path(background_file)
        
        if path.suffix in ['.yaml', '.yml']:
            with open(path, 'r') as f:
                data = yaml.safe_load(f)
        elif path.suffix == '.json':
            with open(path, 'r') as f:
                data = json.load(f)
        else:
            raise ValueError(f"Unsupported file format: {path.suffix}")
        
        for station_data in data.get('stations', []):
            station_id = station_data['station_id']
            bg = StationBackground(
                station_id=station_id,
                craton=station_data.get('craton', 'unknown')
            )
            
            # Load backgrounds for each parameter
            for param in ['delta_phi_th', 'psi_crack', 'rn_pulse', 'omega_arid',
                         'gamma_geo', 'he_ratio', 'beta_dust', 's_yield']:
                if param in station_data:
                    setattr(bg, param, station_data[param])
            
            self.backgrounds[station_id] = bg
    
    def normalize_parameter(
        self,
        value: float,
        station_id: str,
        param_name: str
    ) -> float:
        """
        Normalize parameter using station-specific backgrounds.
        
        Pi* = (Pi_obs - Pi_background) / (Pi_threshold - Pi_background)
        """
        if station_id not in self.backgrounds:
            # Return raw value if no background
            return value
        
        bg = self.backgrounds[station_id]
        background = bg.get_background(param_name)
        threshold = bg.get_threshold(param_name)
        
        if threshold <= background:
            return 0.0
        
        # Normalize and clip to [0, 1]
        normalized = (value - background) / (threshold - background)
        return float(np.clip(normalized, 0, 1))
    
    def compute_raw(
        self,
        params: Dict[str, float],
        station_id: Optional[str] = None
    ) -> float:
        """
        Compute raw (unadjusted) DRGIS score.
        
        Args:
            params: Dictionary of parameter values
            station_id: Optional station ID for normalization
            
        Returns:
            Raw DRGIS score (0-1)
        """
        # Normalize parameters if station ID provided
        if station_id and station_id in self.backgrounds:
            norm_params = {}
            for p_name, p_value in params.items():
                norm_name = self._map_param_name(p_name)
                norm_params[p_name] = self.normalize_parameter(
                    p_value, station_id, norm_name
                )
        else:
            norm_params = params
        
        # Apply weights
        drgis = (
            self.weights.delta_phi_th * norm_params.get('delta_phi_th', 0) +
            self.weights.psi_crack * norm_params.get('psi_crack', 0) +
            self.weights.rn_pulse * norm_params.get('rn_pulse', 0) +
            self.weights.omega_arid * norm_params.get('omega_arid', 0) +
            self.weights.gamma_geo * norm_params.get('gamma_geo', 0) +
            self.weights.he_ratio * norm_params.get('he_ratio', 0) +
            self.weights.beta_dust * norm_params.get('beta_dust', 0) +
            self.weights.s_yield * norm_params.get('s_yield', 0)
        )
        
        return float(np.clip(drgis, 0, 1))
    
    def _map_param_name(self, name: str) -> str:
        """Map parameter name to internal attribute name."""
        mapping = {
            'ΔΦ_th': 'delta_phi_th',
            'Ψ_crack': 'psi_crack',
            'Rn_pulse': 'rn_pulse',
            'Ω_arid': 'omega_arid',
            'Γ_geo': 'gamma_geo',
            'He_ratio': 'he_ratio',
            'β_dust': 'beta_dust',
            'S_yield': 's_yield'
        }
        return mapping.get(name, name)
    
    def apply_ai_adjustment(
        self,
        drgis_raw: float,
        craton: str = 'unknown',
        season: str = 'annual',
        depth_m: float = 0.0
    ) -> float:
        """
        Apply AI-based adjustment to DRGIS score.
        
        DRGIS_adj = sigmoid(DRGIS_raw + β_craton + β_season + β_depth)
        
        Args:
            drgis_raw: Raw DRGIS score
            craton: Craton name for baseline adjustment
            season: Season for seasonal adjustment
            depth_m: Borehole depth for depth adjustment
            
        Returns:
            Adjusted DRGIS score
        """
        # Craton-specific biases (from training)
        craton_bias = {
            'saharan': 0.02,
            'arabian': -0.01,
            'kaapvaal': 0.03,
            'yilgarn': 0.04,
            'atacama': -0.02,
            'tarim': 0.01,
            'scandinavian': 0.05
        }.get(craton.lower(), 0.0)
        
        # Seasonal biases
        seasonal_bias = {
            'winter': -0.02,
            'spring': 0.01,
            'summer': 0.03,
            'autumn': -0.01,
            'annual': 0.0
        }.get(season.lower(), 0.0)
        
        # Depth bias (deeper = more stable)
        depth_bias = 0.0
        if depth_m > 0:
            depth_bias = 0.01 * np.log(depth_m / 10)  # Log scaling
        
        # Combine biases
        x = drgis_raw + craton_bias + seasonal_bias + depth_bias
        
        # Sigmoid adjustment
        drgis_adj = 1 / (1 + np.exp(-10 * (x - 0.5)))
        
        return float(drgis_adj)
    
    def compute(
        self,
        params: Dict[str, float],
        station_id: Optional[str] = None,
        season: str = 'annual',
        depth_m: float = 0.0
    ) -> Dict[str, float]:
        """
        Complete DRGIS computation with all components.
        
        Args:
            params: Dictionary of parameter values
            station_id: Optional station ID
            season: Season for adjustment
            depth_m: Borehole depth for adjustment
            
        Returns:
            Complete DRGIS result with components
        """
        # Get craton if station ID provided
        craton = 'unknown'
        if station_id and station_id in self.backgrounds:
            craton = self.backgrounds[station_id].craton
        
        # Compute raw score
        drgis_raw = self.compute_raw(params, station_id)
        
        # Apply AI adjustment
        drgis_adj = self.apply_ai_adjustment(drgis_raw, craton, season, depth_m)
        
        # Determine alert level
        alert_level = self.thresholds.get_level(drgis_adj)
        
        # Calculate component contributions
        contributions = {}
        for p_name, p_value in params.items():
            norm_name = self._map_param_name(p_name)
            norm_value = p_value
            if station_id:
                norm_value = self.normalize_parameter(p_value, station_id, norm_name)
            
            weight = getattr(self.weights, norm_name, 0)
            contributions[p_name] = {
                'raw': p_value,
                'normalized': norm_value,
                'weight': weight,
                'contribution': weight * norm_value
            }
        
        return {
            'drgis_raw': round(drgis_raw, 4),
            'drgis_adjusted': round(drgis_adj, 4),
            'alert_level': alert_level.value,
            'craton': craton,
            'season': season,
            'contributions': contributions,
            'timestamp': np.datetime64('now').astype(str)
        }
    
    def batch_compute(
        self,
        measurements: List[Dict[str, float]],
        station_id: str
    ) -> List[Dict[str, float]]:
        """
        Compute DRGIS for batch of measurements.
        
        Args:
            measurements: List of parameter dictionaries
            station_id: Station ID
            
        Returns:
            List of DRGIS results
        """
        results = []
        for meas in measurements:
            result = self.compute(meas, station_id)
            results.append(result)
        return results
    
    def validate_accuracy(
        self,
        test_data: List[Dict[str, float]],
        true_labels: List[float]
    ) -> Dict[str, float]:
        """
        Validate DRGIS accuracy against test data.
        
        Args:
            test_data: List of parameter dictionaries
            true_labels: True DRGIS values
            
        Returns:
            Validation metrics
        """
        predictions = []
        for data in test_data:
            result = self.compute(data)
            predictions.append(result['drgis_adjusted'])
        
        predictions = np.array(predictions)
        true_labels = np.array(true_labels)
        
        # Calculate metrics
        errors = predictions - true_labels
        mae = np.mean(np.abs(errors))
        rmse = np.sqrt(np.mean(errors**2))
        r2 = 1 - np.sum(errors**2) / np.sum((true_labels - np.mean(true_labels))**2)
        
        # Classification accuracy (within 0.1)
        correct = np.sum(np.abs(errors) < 0.1)
        accuracy = correct / len(true_labels) * 100
        
        return {
            'mae': round(mae, 4),
            'rmse': round(rmse, 4),
            'r2': round(r2, 4),
            'accuracy': round(accuracy, 1),
            'n_samples': len(true_labels)
        }


# Factory function
def create_drgis_calculator(
    weights_file: Optional[Union[str, Path]] = None,
    thresholds_file: Optional[Union[str, Path]] = None
) -> DRGISCalculator:
    """
    Create DRGIS calculator with optional custom configuration.
    
    Args:
        weights_file: Optional file with custom weights
        thresholds_file: Optional file with custom thresholds
        
    Returns:
        Configured DRGISCalculator instance
    """
    weights = ParameterWeights()
    thresholds = AlertThresholds()
    
    if weights_file:
        path = Path(weights_file)
        with open(path, 'r') as f:
            if path.suffix in ['.yaml', '.yml']:
                data = yaml.safe_load(f)
            else:
                data = json.load(f)
        
        for key, value in data.get('weights', {}).items():
            if hasattr(weights, key):
                setattr(weights, key, value)
    
    if thresholds_file:
        path = Path(thresholds_file)
        with open(path, 'r') as f:
            if path.suffix in ['.yaml', '.yml']:
                data = yaml.safe_load(f)
            else:
                data = json.load(f)
        
        for key, value in data.get('thresholds', {}).items():
            if hasattr(thresholds, key):
                setattr(thresholds, key, value)
    
    return DRGISCalculator(weights, thresholds)
