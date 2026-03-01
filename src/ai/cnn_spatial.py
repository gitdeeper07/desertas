"""
CNN Spatial Pattern Recognizer for Fault Network Topology
Part of DESERTAS AI Ensemble (25% ensemble weight)

Processes 2D spatial patterns across station network:
- Fault network topology
- Stress propagation maps
- InSAR deformation stacks

Input: Multi-channel spatial grid (stations, features, time)
Output: Fault cluster identification and stress propagation patterns
"""

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
import json
import yaml
from pathlib import Path


@dataclass
class CNNConfig:
    """Configuration for CNN spatial model."""
    input_channels: int = 8  # 8 DRGIS parameters
    grid_size: Tuple[int, int] = (64, 64)  # Spatial grid dimensions
    conv_layers: List[int] = field(default_factory=lambda: [32, 64, 128])
    kernel_size: int = 3
    pooling_size: int = 2
    dropout: float = 0.2
    
    # Output heads
    n_fault_clusters: int = 10
    n_stress_levels: int = 5
    propagation_features: int = 32
    
    # Training
    learning_rate: float = 0.001
    batch_size: int = 16
    epochs: int = 100


class SpatialAttention(nn.Module):
    """Spatial attention mechanism for fault network focus."""
    
    def __init__(self, in_channels: int):
        super().__init__()
        self.conv1 = nn.Conv2d(in_channels, 1, kernel_size=1)
        self.sigmoid = nn.Sigmoid()
        
    def forward(self, x):
        # Calculate attention weights
        attention = self.conv1(x)
        attention = self.sigmoid(attention)
        
        # Apply attention
        return x * attention


class CNNSpatialDetector(nn.Module):
    """
    CNN-based spatial pattern detector for fault networks.
    
    Identifies:
    - Fault-parallel stress propagation signatures
    - Spatial clustering of anomalies
    - Stress front propagation patterns
    """
    
    def __init__(self, config: CNNConfig):
        super().__init__()
        self.config = config
        
        # Build convolutional layers
        self.conv_layers = nn.ModuleList()
        self.bn_layers = nn.ModuleList()
        
        in_channels = config.input_channels
        for out_channels in config.conv_layers:
            self.conv_layers.append(
                nn.Conv2d(
                    in_channels, out_channels,
                    kernel_size=config.kernel_size,
                    padding=config.kernel_size // 2
                )
            )
            self.bn_layers.append(nn.BatchNorm2d(out_channels))
            in_channels = out_channels
        
        # Spatial attention
        self.attention = SpatialAttention(in_channels)
        
        # Calculate flattened size after convolutions and pooling
        self._calculate_flattened_size()
        
        # Fully connected layers
        self.fc1 = nn.Linear(self.flattened_size, 256)
        self.fc2 = nn.Linear(256, 128)
        self.dropout = nn.Dropout(config.dropout)
        
        # Output heads
        self.cluster_head = nn.Linear(128, config.n_fault_clusters)
        self.stress_head = nn.Linear(128, config.n_stress_levels)
        self.propagation_head = nn.Linear(128, config.propagation_features)
        
    def _calculate_flattened_size(self):
        """Calculate size after convolutions and pooling."""
        # Simulate forward pass through conv layers
        h, w = self.config.grid_size
        for _ in self.config.conv_layers:
            h = h // self.config.pooling_size
            w = w // self.config.pooling_size
        
        self.flattened_size = h * w * self.config.conv_layers[-1]
    
    def forward(self, x):
        """
        Forward pass.
        
        Args:
            x: Input tensor (batch, channels, height, width)
            
        Returns:
            Dictionary with predictions
        """
        # Convolutional layers with pooling
        for conv, bn in zip(self.conv_layers, self.bn_layers):
            x = conv(x)
            x = bn(x)
            x = F.relu(x)
            x = F.max_pool2d(x, self.config.pooling_size)
        
        # Apply spatial attention
        x = self.attention(x)
        
        # Flatten
        x = x.view(x.size(0), -1)
        
        # Fully connected layers
        x = F.relu(self.fc1(x))
        x = self.dropout(x)
        x = F.relu(self.fc2(x))
        x = self.dropout(x)
        
        # Outputs
        clusters = self.cluster_head(x)
        stress_levels = self.stress_head(x)
        propagation_features = self.propagation_head(x)
        
        return {
            'fault_clusters': F.log_softmax(clusters, dim=1),
            'stress_levels': F.log_softmax(stress_levels, dim=1),
            'propagation_features': propagation_features,
            'stress_probs': F.softmax(stress_levels, dim=1)
        }
    
    def detect_stress_propagation(
        self,
        station_grid: torch.Tensor,
        fault_map: torch.Tensor
    ) -> Dict[str, torch.Tensor]:
        """
        Detect stress propagation patterns along fault network.
        
        Args:
            station_grid: Grid of station measurements
            fault_map: Binary fault network map
            
        Returns:
            Stress propagation metrics
        """
        # Get model predictions
        outputs = self.forward(station_grid)
        
        # Extract stress probabilities
        stress_probs = outputs['stress_probs']
        
        # Weight by fault proximity
        # Simplified: convolve fault map with stress field
        fault_weighted = stress_probs * fault_map
        
        # Detect propagation direction
        # Find gradient of stress field
        if station_grid.dim() == 4:
            # batch mode
            batch_size = station_grid.size(0)
            propagation_dirs = []
            
            for i in range(batch_size):
                stress_slice = stress_probs[i, 0]  # Take first stress level
                grad_y, grad_x = torch.gradient(stress_slice)
                propagation_dirs.append(torch.atan2(grad_y, grad_x))
            
            propagation_dir = torch.stack(propagation_dirs)
        else:
            stress_slice = stress_probs[0]
            grad_y, grad_x = torch.gradient(stress_slice)
            propagation_dir = torch.atan2(grad_y, grad_x)
        
        return {
            'stress_field': stress_probs,
            'fault_weighted_stress': fault_weighted,
            'propagation_direction': propagation_dir,
            'fault_clusters': outputs['fault_clusters'],
            'propagation_features': outputs['propagation_features']
        }
    
    def identify_fault_clusters(
        self,
        station_grid: torch.Tensor,
        threshold: float = 0.5
    ) -> Dict[str, torch.Tensor]:
        """
        Identify active fault clusters from spatial pattern.
        
        Args:
            station_grid: Grid of station measurements
            threshold: Confidence threshold
            
        Returns:
            Cluster assignments and confidence
        """
        outputs = self.forward(station_grid)
        
        # Get cluster probabilities
        cluster_probs = torch.exp(outputs['fault_clusters'])
        
        # Get most likely cluster
        cluster_assignments = torch.argmax(cluster_probs, dim=1)
        
        # Get confidence (probability of assigned cluster)
        confidence = torch.gather(
            cluster_probs, 1,
            cluster_assignments.unsqueeze(1)
        ).squeeze(1)
        
        return {
            'cluster_assignments': cluster_assignments,
            'cluster_probs': cluster_probs,
            'confidence': confidence,
            'active_clusters': (confidence > threshold).sum().item()
        }
    
    def estimate_lead_time_from_pattern(
        self,
        stress_pattern: torch.Tensor,
        fault_map: torch.Tensor,
        station_coords: torch.Tensor
    ) -> Dict[str, float]:
        """
        Estimate lead time from spatial stress pattern.
        
        Uses propagation speed along fault network.
        
        Args:
            stress_pattern: Current stress field
            fault_map: Fault network map
            station_coords: Station coordinates
            
        Returns:
            Lead time estimates per station
        """
        # Get stress propagation direction and speed
        propagation = self.detect_stress_propagation(
            stress_pattern.unsqueeze(0),
            fault_map.unsqueeze(0)
        )
        
        propagation_dir = propagation['propagation_direction'][0]
        
        # Calculate distance from stress front for each station
        # This is a simplified version
        n_stations = station_coords.size(0)
        lead_times = []
        
        for i in range(n_stations):
            station = station_coords[i]
            
            # Get stress at station location
            x, y = station.long(), station.lat()
            if 0 <= x < stress_pattern.size(-1) and 0 <= y < stress_pattern.size(-2):
                station_stress = stress_pattern[0, y, x].item()
            else:
                station_stress = 0
            
            # Estimate lead time based on stress and propagation
            if station_stress > 0.7:
                lead_time = 7  # Days
            elif station_stress > 0.5:
                lead_time = 14
            elif station_stress > 0.3:
                lead_time = 30
            else:
                lead_time = 58  # Background mean
            
            lead_times.append(lead_time)
        
        return {
            'lead_times': lead_times,
            'mean_lead_time': float(np.mean(lead_times)),
            'min_lead_time': float(np.min(lead_times)),
            'max_lead_time': float(np.max(lead_times))
        }


class SpatialDataset(torch.utils.data.Dataset):
    """Dataset for spatial CNN training."""
    
    def __init__(
        self,
        station_grids: np.ndarray,
        fault_maps: np.ndarray,
        cluster_labels: Optional[np.ndarray] = None,
        stress_labels: Optional[np.ndarray] = None
    ):
        """
        Initialize dataset.
        
        Args:
            station_grids: Gridded station data (n_samples, channels, h, w)
            fault_maps: Fault network maps (n_samples, h, w)
            cluster_labels: Fault cluster labels
            stress_labels: Stress level labels
        """
        self.station_grids = torch.FloatTensor(station_grids)
        self.fault_maps = torch.FloatTensor(fault_maps).unsqueeze(1)
        self.cluster_labels = torch.LongTensor(cluster_labels) if cluster_labels is not None else None
        self.stress_labels = torch.LongTensor(stress_labels) if stress_labels is not None else None
    
    def __len__(self):
        return len(self.station_grids)
    
    def __getitem__(self, idx):
        result = {
            'station_grid': self.station_grids[idx],
            'fault_map': self.fault_maps[idx]
        }
        
        if self.cluster_labels is not None:
            result['cluster_label'] = self.cluster_labels[idx]
        
        if self.stress_labels is not None:
            result['stress_label'] = self.stress_labels[idx]
        
        return result


class CNNTrainer:
    """Trainer for CNN spatial model."""
    
    def __init__(
        self,
        model: CNNSpatialDetector,
        config: CNNConfig,
        device: str = 'cuda' if torch.cuda.is_available() else 'cpu'
    ):
        self.model = model.to(device)
        self.config = config
        self.device = device
        
        self.optimizer = torch.optim.Adam(
            model.parameters(),
            lr=config.learning_rate
        )
        
        self.criterion_cluster = nn.NLLLoss()
        self.criterion_stress = nn.NLLLoss()
    
    def train_epoch(self, train_loader: torch.utils.data.DataLoader) -> float:
        """Train for one epoch."""
        self.model.train()
        total_loss = 0
        
        for batch in train_loader:
            station_grid = batch['station_grid'].to(self.device)
            fault_map = batch['fault_map'].to(self.device)
            
            self.optimizer.zero_grad()
            
            outputs = self.model(station_grid)
            
            loss = 0
            
            # Cluster loss if labels available
            if 'cluster_label' in batch:
                cluster_label = batch['cluster_label'].to(self.device)
                loss += self.criterion_cluster(
                    outputs['fault_clusters'],
                    cluster_label
                )
            
            # Stress loss if labels available
            if 'stress_label' in batch:
                stress_label = batch['stress_label'].to(self.device)
                loss += self.criterion_stress(
                    outputs['stress_levels'],
                    stress_label
                )
            
            loss.backward()
            self.optimizer.step()
            
            total_loss += loss.item()
        
        return total_loss / len(train_loader)
    
    def validate(
        self,
        val_loader: torch.utils.data.DataLoader
    ) -> Dict[str, float]:
        """Validate model."""
        self.model.eval()
        cluster_correct = 0
        stress_correct = 0
        total = 0
        
        with torch.no_grad():
            for batch in val_loader:
                station_grid = batch['station_grid'].to(self.device)
                outputs = self.model(station_grid)
                
                if 'cluster_label' in batch:
                    cluster_label = batch['cluster_label'].to(self.device)
                    cluster_pred = outputs['fault_clusters'].argmax(dim=1)
                    cluster_correct += (cluster_pred == cluster_label).sum().item()
                
                if 'stress_label' in batch:
                    stress_label = batch['stress_label'].to(self.device)
                    stress_pred = outputs['stress_levels'].argmax(dim=1)
                    stress_correct += (stress_pred == stress_label).sum().item()
                
                total += len(station_grid)
        
        metrics = {}
        if 'cluster_label' in batch:
            metrics['cluster_accuracy'] = cluster_correct / total
        if 'stress_label' in batch:
            metrics['stress_accuracy'] = stress_correct / total
        
        return metrics


# Factory function
def create_cnn_spatial(
    config_file: Optional[Union[str, Path]] = None,
    weights_file: Optional[Union[str, Path]] = None
) -> CNNSpatialDetector:
    """
    Create CNN spatial detector with optional configuration.
    
    Args:
        config_file: Optional configuration file
        weights_file: Optional pre-trained weights
        
    Returns:
        Configured CNNSpatialDetector instance
    """
    config = CNNConfig()
    
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
    
    model = CNNSpatialDetector(config)
    
    if weights_file:
        model.load_state_dict(torch.load(weights_file, map_location='cpu'))
    
    return model
