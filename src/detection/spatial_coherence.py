"""
Spatial Coherence Analysis for Multi-Station Validation
Computes cross-station coherence metric g for anomaly validation

g = mean cross-station correlation of anomaly pattern within 100 km radius
Uses wavelet coherence analysis for time-frequency decomposition

Thresholds:
- g > 0.60: Required for ALERT level
- g > 0.75: Required for EMERGENCY level
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from scipy import signal, stats
import pywt
from sklearn.cluster import DBSCAN
import json
import yaml
from pathlib import Path


@dataclass
class CoherenceConfig:
    """Configuration for spatial coherence analysis."""
    station_id: str
    
    # Spatial parameters
    coherence_radius_km: float = 100.0
    min_stations_for_coherence: int = 3
    
    # Wavelet parameters
    wavelet: str = 'morl'  # Morlet wavelet
    scales: np.ndarray = None
    
    # Frequency bands of interest (Hz)
    tectonic_band_min: float = 1.0 / (30 * 24 * 3600)  # 30 days
    tectonic_band_max: float = 1.0 / (24 * 3600)       # 1 day
    
    # Coherence thresholds
    alert_threshold: float = 0.60
    emergency_threshold: float = 0.75
    
    # Clustering parameters
    eps_km: float = 100.0  # DBSCAN epsilon in km
    min_cluster_size: int = 3


class SpatialCoherence:
    """
    Spatial coherence analysis for multi-station validation.
    
    Computes cross-station coherence metric g using wavelet analysis
    to validate that anomalies are tectonic (spatially coherent)
    rather than local noise.
    """
    
    def __init__(self, config: CoherenceConfig):
        """
        Initialize spatial coherence analyzer.
        
        Args:
            config: Coherence configuration
        """
        self.config = config
        if config.scales is None:
            # Default scales for wavelet transform
            self.config.scales = np.arange(1, 128)
    
    def compute_wavelet_coherence(
        self,
        signal1: np.ndarray,
        signal2: np.ndarray,
        fs: float  # Sampling frequency in Hz
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute wavelet coherence between two signals.
        
        Args:
            signal1: First signal
            signal2: Second signal
            fs: Sampling frequency in Hz
            
        Returns:
            Tuple of (coherence, frequencies)
        """
        # Continuous wavelet transform
        coeffs1, freqs = pywt.cwt(
            signal1, self.config.scales, self.config.wavelet,
            sampling_period=1/fs
        )
        coeffs2, _ = pywt.cwt(
            signal2, self.config.scales, self.config.wavelet,
            sampling_period=1/fs
        )
        
        # Compute cross-wavelet spectrum
        Wxy = coeffs1 * np.conj(coeffs2)
        
        # Smooth in time and scale
        # Simplified: use moving average
        window = 5
        Wxy_smooth = np.zeros_like(Wxy, dtype=complex)
        for i in range(Wxy.shape[0]):
            for j in range(window, Wxy.shape[1] - window):
                Wxy_smooth[i, j] = np.mean(Wxy[i, j-window:j+window])
        
        # Compute auto-spectra
        Wxx = np.abs(coeffs1)**2
        Wyy = np.abs(coeffs2)**2
        
        Wxx_smooth = np.zeros_like(Wxx)
        Wyy_smooth = np.zeros_like(Wyy)
        for i in range(Wxx.shape[0]):
            for j in range(window, Wxx.shape[1] - window):
                Wxx_smooth[i, j] = np.mean(Wxx[i, j-window:j+window])
                Wyy_smooth[i, j] = np.mean(Wyy[i, j-window:j+window])
        
        # Wavelet coherence
        coherence = np.abs(Wxy_smooth)**2 / (Wxx_smooth * Wyy_smooth + 1e-10)
        
        return coherence, freqs
    
    def compute_pairwise_coherence(
        self,
        station_signals: Dict[str, np.ndarray],
        station_coords: Dict[str, Tuple[float, float]],
        fs: float,
        time_window: Optional[Tuple[int, int]] = None
    ) -> Dict[str, float]:
        """
        Compute pairwise coherence between all stations.
        
        Args:
            station_signals: Dictionary of station signals
            station_coords: Dictionary of station coordinates (lat, lon)
            fs: Sampling frequency
            time_window: Optional time window indices
            
        Returns:
            Dictionary of pairwise coherence values
        """
        results = {}
        
        # Get list of stations
        stations = list(station_signals.keys())
        n_stations = len(stations)
        
        if n_stations < 2:
            return results
        
        # Extract signals
        if time_window is not None:
            start, end = time_window
            signals = {s: station_signals[s][start:end] for s in stations}
        else:
            signals = station_signals
        
        # Compute pairwise coherence
        for i in range(n_stations):
            for j in range(i+1, n_stations):
                s1 = stations[i]
                s2 = stations[j]
                
                # Calculate distance
                lat1, lon1 = station_coords[s1]
                lat2, lon2 = station_coords[s2]
                distance = self._haversine_distance(lat1, lon1, lat2, lon2)
                
                # Skip if beyond coherence radius
                if distance > self.config.coherence_radius_km:
                    continue
                
                # Compute coherence
                sig1 = signals[s1]
                sig2 = signals[s2]
                
                # Ensure same length
                min_len = min(len(sig1), len(sig2))
                sig1 = sig1[:min_len]
                sig2 = sig2[:min_len]
                
                if min_len < 10:
                    continue
                
                # Wavelet coherence
                coherence, freqs = self.compute_wavelet_coherence(sig1, sig2, fs)
                
                # Average over tectonic band
                band_mask = (freqs >= self.config.tectonic_band_min) & (freqs <= self.config.tectonic_band_max)
                if np.any(band_mask):
                    band_coherence = np.mean(coherence[band_mask, :])
                else:
                    band_coherence = 0
                
                # Store result
                pair_key = f"{s1}_{s2}"
                results[pair_key] = {
                    'coherence': float(band_coherence),
                    'distance_km': float(distance),
                    'stations': (s1, s2)
                }
        
        return results
    
    def _haversine_distance(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float
    ) -> float:
        """Calculate great-circle distance between two points."""
        R = 6371  # Earth's radius in km
        
        lat1_rad = np.radians(lat1)
        lat2_rad = np.radians(lat2)
        dlat = np.radians(lat2 - lat1)
        dlon = np.radians(lon2 - lon1)
        
        a = np.sin(dlat/2)**2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon/2)**2
        c = 2 * np.arcsin(np.sqrt(a))
        
        return R * c
    
    def compute_coherence_metric(
        self,
        station_signals: Dict[str, np.ndarray],
        station_coords: Dict[str, Tuple[float, float]],
        fs: float,
        reference_station: Optional[str] = None,
        time_window: Optional[Tuple[int, int]] = None
    ) -> Dict[str, float]:
        """
        Compute spatial coherence metric g.
        
        g = mean cross-station correlation of anomaly pattern
        within coherence radius.
        
        Args:
            station_signals: Dictionary of station signals
            station_coords: Dictionary of station coordinates
            fs: Sampling frequency
            reference_station: Optional reference station
            time_window: Optional time window
            
        Returns:
            Coherence metrics
        """
        if reference_station is None:
            # Use station with strongest signal
            stations = list(station_signals.keys())
            if self.config.station_id in stations:
                reference_station = self.config.station_id
            else:
                reference_station = stations[0]
        
        if reference_station not in station_signals:
            raise ValueError(f"Reference station {reference_station} not found")
        
        # Get reference signal
        ref_signal = station_signals[reference_station]
        ref_coord = station_coords[reference_station]
        
        # Find nearby stations
        nearby_stations = []
        for station, coord in station_coords.items():
            if station == reference_station:
                continue
            
            distance = self._haversine_distance(
                ref_coord[0], ref_coord[1],
                coord[0], coord[1]
            )
            
            if distance <= self.config.coherence_radius_km:
                nearby_stations.append((station, distance))
        
        if len(nearby_stations) < self.config.min_stations_for_coherence - 1:
            return {
                'coherence_metric': 0.0,
                'n_stations': len(nearby_stations) + 1,
                'reference_station': reference_station,
                'warning': 'Insufficient stations for coherence calculation'
            }
        
        # Extract time window if specified
        if time_window is not None:
            start, end = time_window
            ref_window = ref_signal[start:end]
            nearby_signals = {
                s: station_signals[s][start:end]
                for s, _ in nearby_stations
            }
        else:
            ref_window = ref_signal
            nearby_signals = {
                s: station_signals[s]
                for s, _ in nearby_stations
            }
        
        # Compute coherence with each nearby station
        coherence_values = []
        station_distances = []
        
        for station, distance in nearby_stations:
            sig = nearby_signals[station]
            
            # Ensure same length
            min_len = min(len(ref_window), len(sig))
            if min_len < 10:
                continue
            
            sig1 = ref_window[:min_len]
            sig2 = sig[:min_len]
            
            # Compute wavelet coherence
            coherence, freqs = self.compute_wavelet_coherence(sig1, sig2, fs)
            
            # Average over tectonic band
            band_mask = (freqs >= self.config.tectonic_band_min) & (freqs <= self.config.tectonic_band_max)
            if np.any(band_mask):
                band_coherence = np.mean(coherence[band_mask, :])
                coherence_values.append(band_coherence)
                station_distances.append(distance)
        
        if not coherence_values:
            return {
                'coherence_metric': 0.0,
                'n_stations': len(nearby_stations) + 1,
                'reference_station': reference_station,
                'warning': 'No valid coherence calculations'
            }
        
        # Weight by distance (inverse distance weighting)
        weights = 1 / (np.array(station_distances) + 1)  # +1 to avoid division by zero
        weights = weights / np.sum(weights)
        
        coherence_metric = float(np.average(coherence_values, weights=weights))
        
        # Determine level
        if coherence_metric >= self.config.emergency_threshold:
            level = 'EMERGENCY'
        elif coherence_metric >= self.config.alert_threshold:
            level = 'ALERT'
        else:
            level = 'WATCH' if coherence_metric > 0.3 else 'BACKGROUND'
        
        return {
            'coherence_metric': coherence_metric,
            'n_stations': len(nearby_stations) + 1,
            'reference_station': reference_station,
            'coherence_level': level,
            'mean_coherence': float(np.mean(coherence_values)),
            'max_coherence': float(np.max(coherence_values)),
            'min_coherence': float(np.min(coherence_values)),
            'station_distances_km': [float(d) for d in station_distances],
            'station_coherence': coherence_values
        }
    
    def cluster_stations(
        self,
        station_coords: Dict[str, Tuple[float, float]]
    ) -> Dict[str, List[str]]:
        """
        Cluster stations spatially using DBSCAN.
        
        Args:
            station_coords: Dictionary of station coordinates
            
        Returns:
            Dictionary of clusters
        """
        if len(station_coords) < 2:
            return {'cluster_0': list(station_coords.keys())}
        
        # Prepare coordinates array
        stations = list(station_coords.keys())
        coords = np.array([
            [station_coords[s][0], station_coords[s][1]]
            for s in stations
        ])
        
        # Convert lat/lon to km for DBSCAN
        # Approximate: 1 degree lat = 111 km, 1 degree lon varies
        coords_km = np.zeros_like(coords)
        coords_km[:, 0] = coords[:, 0] * 111  # latitude to km
        coords_km[:, 1] = coords[:, 1] * 111 * np.cos(np.radians(np.mean(coords[:, 0])))  # longitude to km
        
        # DBSCAN clustering
        clustering = DBSCAN(
            eps=self.config.eps_km,
            min_samples=self.config.min_cluster_size
        ).fit(coords_km)
        
        # Group stations by cluster
        clusters = {}
        for i, label in enumerate(clustering.labels_):
            cluster_key = f"cluster_{label}" if label >= 0 else "noise"
            if cluster_key not in clusters:
                clusters[cluster_key] = []
            clusters[cluster_key].append(stations[i])
        
        return clusters
    
    def detect_coherent_anomaly(
        self,
        station_signals: Dict[str, np.ndarray],
        station_coords: Dict[str, Tuple[float, float]],
        fs: float,
        threshold: Optional[float] = None
    ) -> Dict[str, Union[bool, float]]:
        """
        Detect if there's a spatially coherent anomaly.
        
        Args:
            station_signals: Dictionary of station signals
            station_coords: Dictionary of station coordinates
            fs: Sampling frequency
            threshold: Coherence threshold
            
        Returns:
            Detection result
        """
        if threshold is None:
            threshold = self.config.alert_threshold
        
        # Cluster stations
        clusters = self.cluster_stations(station_coords)
        
        # Check each cluster for coherence
        best_cluster = None
        best_coherence = 0
        
        for cluster_name, station_list in clusters.items():
            if len(station_list) < self.config.min_stations_for_coherence:
                continue
            
            # Use first station as reference
            ref_station = station_list[0]
            
            # Compute coherence for this cluster
            cluster_signals = {s: station_signals[s] for s in station_list}
            cluster_coords = {s: station_coords[s] for s in station_list}
            
            result = self.compute_coherence_metric(
                cluster_signals, cluster_coords, fs, ref_station
            )
            
            coherence = result.get('coherence_metric', 0)
            if coherence > best_coherence:
                best_coherence = coherence
                best_cluster = cluster_name
        
        return {
            'coherent_anomaly_detected': best_coherence >= threshold,
            'best_coherence': float(best_coherence),
            'best_cluster': best_cluster,
            'threshold_used': threshold,
            'n_clusters': len(clusters)
        }


# Factory function
def create_spatial_coherence(
    station_id: str,
    config_file: Optional[Union[str, Path]] = None
) -> SpatialCoherence:
    """
    Create spatial coherence analyzer with configuration.
    
    Args:
        station_id: Station identifier
        config_file: Optional configuration file
        
    Returns:
        Configured SpatialCoherence instance
    """
    config = CoherenceConfig(station_id=station_id)
    
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
    
    return SpatialCoherence(config)
