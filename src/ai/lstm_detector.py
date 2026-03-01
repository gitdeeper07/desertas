"""
LSTM Anomaly Detector for Rn_pulse Time Series
Part of DESERTAS AI Ensemble (40% ensemble weight)

Processes multi-year Rn_pulse time series to detect:
- Temporal patterns of tectonic precursor anomalies
- Critical slowing down indicators
- Barometric detrending effects

Architecture:
- Input: 720-hour windows (30 days) of Rn_pulse data
- 2 LSTM layers (128 units) with dropout
- Attention mechanism for precursor timing
- Output: Anomaly probability and lead time estimate
"""

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import yaml
from pathlib import Path


@dataclass
class LSTMConfig:
    """Configuration for LSTM detector."""
    input_window: int = 720  # 30 days * 24 hours
    lstm_units: int = 128
    num_layers: int = 2
    dropout: float = 0.2
    learning_rate: float = 0.001
    batch_size: int = 32
    epochs: int = 100
    attention_units: int = 64
    
    # Data parameters
    sampling_rate: str = '1H'
    prediction_horizon: int = 168  # 7 days ahead
    
    # Thresholds
    anomaly_threshold: float = 0.7
    critical_slowdown_threshold: float = 0.85


class AttentionLayer(nn.Module):
    """Attention mechanism for focusing on precursor patterns."""
    
    def __init__(self, lstm_units: int, attention_units: int):
        super().__init__()
        self.attention = nn.Sequential(
            nn.Linear(lstm_units, attention_units),
            nn.Tanh(),
            nn.Linear(attention_units, 1)
        )
    
    def forward(self, lstm_output):
        # lstm_output shape: (batch, seq_len, lstm_units)
        attention_weights = self.attention(lstm_output)
        attention_weights = torch.softmax(attention_weights, dim=1)
        
        # Apply attention weights
        context = torch.sum(attention_weights * lstm_output, dim=1)
        return context, attention_weights


class LSTMPrecursorDetector(nn.Module):
    """
    LSTM-based detector for seismic precursor patterns in Rn_pulse time series.
    
    Detects characteristic signatures:
    - Rapid onset (τ_onset < 72 hours for tectonic anomalies)
    - Multi-week duration
    - Critical slowing down before events
    """
    
    def __init__(self, config: LSTMConfig):
        super().__init__()
        self.config = config
        
        # LSTM layers
        self.lstm = nn.LSTM(
            input_size=1,  # Rn_pulse only
            hidden_size=config.lstm_units,
            num_layers=config.num_layers,
            batch_first=True,
            dropout=config.dropout if config.num_layers > 1 else 0
        )
        
        # Attention mechanism
        self.attention = AttentionLayer(
            config.lstm_units,
            config.attention_units
        )
        
        # Output layers
        self.fc1 = nn.Linear(config.lstm_units, 64)
        self.fc2 = nn.Linear(64, 32)
        
        # Multiple outputs
        self.anomaly_head = nn.Linear(32, 1)  # Binary anomaly detection
        self.lead_time_head = nn.Linear(32, 1)  # Lead time regression
        self.slowdown_head = nn.Linear(32, 1)  # Critical slowing down
        
        self.dropout = nn.Dropout(config.dropout)
        self.relu = nn.ReLU()
        self.sigmoid = nn.Sigmoid()
        
    def forward(self, x):
        """
        Forward pass.
        
        Args:
            x: Input tensor (batch, seq_len, 1)
            
        Returns:
            Dictionary with predictions
        """
        # LSTM
        lstm_out, (hidden, cell) = self.lstm(x)
        
        # Attention
        context, attention_weights = self.attention(lstm_out)
        
        # Dense layers
        x = self.fc1(context)
        x = self.relu(x)
        x = self.dropout(x)
        x = self.fc2(x)
        x = self.relu(x)
        
        # Outputs
        anomaly = self.sigmoid(self.anomaly_head(x))
        lead_time = self.lead_time_head(x)  # Raw value (will be scaled)
        slowdown = self.sigmoid(self.slowdown_head(x))
        
        return {
            'anomaly_prob': anomaly.squeeze(-1),
            'lead_time_raw': lead_time.squeeze(-1),
            'slowdown_prob': slowdown.squeeze(-1),
            'attention_weights': attention_weights
        }
    
    def predict_lead_time(self, lead_time_raw: torch.Tensor) -> torch.Tensor:
        """Convert raw lead time to days (0-100 days range)."""
        return torch.sigmoid(lead_time_raw) * 100
    
    def detect_critical_slowing_down(
        self,
        rn_series: torch.Tensor,
        threshold: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Detect critical slowing down indicators.
        
        Critical slowing down precedes tipping points:
        - Increased variance
        - Increased autocorrelation
        - Slower recovery rates
        """
        if threshold is None:
            threshold = self.config.critical_slowdown_threshold
        
        # Convert to numpy for analysis
        if torch.is_tensor(rn_series):
            series = rn_series.detach().cpu().numpy()
        else:
            series = rn_series
        
        # Calculate variance in rolling windows
        window = 168  # 7 days
        variances = []
        for i in range(len(series) - window):
            variances.append(np.var(series[i:i+window]))
        
        # Calculate lag-1 autocorrelation
        autocorr = []
        for i in range(len(series) - window):
            seg = series[i:i+window]
            autocorr.append(np.corrcoef(seg[:-1], seg[1:])[0, 1])
        
        # Detect trends
        if len(variances) > 1:
            var_trend = np.polyfit(range(len(variances)), variances, 1)[0]
            ac_trend = np.polyfit(range(len(autocorr)), autocorr, 1)[0]
        else:
            var_trend = 0
            ac_trend = 0
        
        # Critical slowing down score
        csd_score = (np.tanh(var_trend * 10) + np.tanh(ac_trend * 10)) / 2
        
        return {
            'csd_score': float(csd_score),
            'var_trend': float(var_trend),
            'ac_trend': float(ac_trend),
            'csd_detected': csd_score > threshold,
            'current_variance': float(np.var(series[-window:])) if len(series) > window else 0,
            'current_autocorr': float(np.corrcoef(series[-window:-1], series[-window+1:])[0, 1]) 
                if len(series) > window else 0
        }


class RnPulseDataset(Dataset):
    """Dataset for Rn_pulse time series with sliding windows."""
    
    def __init__(
        self,
        rn_series: np.ndarray,
        labels: Optional[np.ndarray] = None,
        lead_times: Optional[np.ndarray] = None,
        window_size: int = 720,
        stride: int = 24
    ):
        """
        Initialize dataset.
        
        Args:
            rn_series: Rn_pulse time series
            labels: Anomaly labels (0/1)
            lead_times: Lead times in days
            window_size: Sliding window size
            stride: Stride between windows
        """
        self.window_size = window_size
        self.stride = stride
        
        # Create sliding windows
        self.windows = []
        self.window_labels = []
        self.window_lead_times = []
        
        for i in range(0, len(rn_series) - window_size, stride):
            window = rn_series[i:i+window_size]
            self.windows.append(window)
            
            if labels is not None and i + window_size < len(labels):
                # Label is 1 if anomaly occurs in next prediction_horizon
                horizon = 168  # 7 days
                future = labels[i+window_size:i+window_size+horizon]
                self.window_labels.append(1 if np.any(future) else 0)
                
                # Lead time to first anomaly
                if lead_times is not None:
                    self.window_lead_times.append(lead_times[i+window_size])
        
        self.windows = np.array(self.windows)
        self.window_labels = np.array(self.window_labels) if labels is not None else None
        self.window_lead_times = np.array(self.window_lead_times) if lead_times is not None else None
    
    def __len__(self):
        return len(self.windows)
    
    def __getitem__(self, idx):
        window = self.windows[idx]
        
        # Normalize
        window_mean = np.mean(window)
        window_std = np.std(window) + 1e-8
        window_norm = (window - window_mean) / window_std
        
        x = torch.FloatTensor(window_norm).unsqueeze(-1)
        
        result = {'input': x}
        
        if self.window_labels is not None:
            result['label'] = torch.FloatTensor([self.window_labels[idx]])
        
        if self.window_lead_times is not None:
            # Normalize lead time to [0, 1]
            lead_norm = min(self.window_lead_times[idx] / 100, 1.0)
            result['lead_time'] = torch.FloatTensor([lead_norm])
        
        return result


class LSTMTrainer:
    """Trainer for LSTM precursor detector."""
    
    def __init__(
        self,
        model: LSTMPrecursorDetector,
        config: LSTMConfig,
        device: str = 'cuda' if torch.cuda.is_available() else 'cpu'
    ):
        self.model = model.to(device)
        self.config = config
        self.device = device
        
        self.optimizer = optim.Adam(
            model.parameters(),
            lr=config.learning_rate
        )
        
        self.criterion_anomaly = nn.BCELoss()
        self.criterion_lead = nn.MSELoss()
        
    def train_epoch(self, train_loader: DataLoader) -> Dict[str, float]:
        """Train for one epoch."""
        self.model.train()
        total_loss = 0
        anomaly_loss_sum = 0
        lead_loss_sum = 0
        
        for batch in train_loader:
            x = batch['input'].to(self.device)
            
            self.optimizer.zero_grad()
            
            outputs = self.model(x)
            
            loss = 0
            
            # Anomaly loss
            if 'label' in batch:
                y = batch['label'].to(self.device)
                anomaly_loss = self.criterion_anomaly(
                    outputs['anomaly_prob'],
                    y.squeeze(-1)
                )
                loss += anomaly_loss
                anomaly_loss_sum += anomaly_loss.item()
            
            # Lead time loss
            if 'lead_time' in batch:
                lead_true = batch['lead_time'].to(self.device)
                lead_pred = outputs['lead_time_raw']
                lead_loss = self.criterion_lead(lead_pred, lead_true.squeeze(-1))
                loss += lead_loss * 0.3  # Lower weight for lead time
                lead_loss_sum += lead_loss.item()
            
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
            self.optimizer.step()
            
            total_loss += loss.item()
        
        n_batches = len(train_loader)
        return {
            'loss': total_loss / n_batches,
            'anomaly_loss': anomaly_loss_sum / n_batches if 'label' in batch else 0,
            'lead_loss': lead_loss_sum / n_batches if 'lead_time' in batch else 0
        }
    
    def validate(self, val_loader: DataLoader) -> Dict[str, float]:
        """Validate model."""
        self.model.eval()
        correct = 0
        total = 0
        anomaly_preds = []
        anomaly_true = []
        
        with torch.no_grad():
            for batch in val_loader:
                x = batch['input'].to(self.device)
                outputs = self.model(x)
                
                if 'label' in batch:
                    y = batch['label'].to(self.device)
                    pred = (outputs['anomaly_prob'] > 0.5).float()
                    correct += (pred == y.squeeze(-1)).sum().item()
                    total += len(y)
                    
                    anomaly_preds.extend(outputs['anomaly_prob'].cpu().numpy())
                    anomaly_true.extend(y.cpu().numpy())
        
        accuracy = correct / total if total > 0 else 0
        
        return {
            'accuracy': accuracy,
            'predictions': anomaly_preds,
            'true_labels': anomaly_true
        }
    
    def train(
        self,
        train_loader: DataLoader,
        val_loader: DataLoader,
        epochs: Optional[int] = None
    ) -> Dict[str, List[float]]:
        """Full training loop."""
        if epochs is None:
            epochs = self.config.epochs
        
        history = {
            'train_loss': [],
            'val_accuracy': []
        }
        
        for epoch in range(epochs):
            train_metrics = self.train_epoch(train_loader)
            val_metrics = self.validate(val_loader)
            
            history['train_loss'].append(train_metrics['loss'])
            history['val_accuracy'].append(val_metrics['accuracy'])
            
            if (epoch + 1) % 10 == 0:
                print(f"Epoch {epoch+1}/{epochs}")
                print(f"  Train Loss: {train_metrics['loss']:.4f}")
                print(f"  Val Accuracy: {val_metrics['accuracy']:.4f}")
        
        return history


# Factory function
def create_lstm_detector(
    config_file: Optional[Union[str, Path]] = None,
    weights_file: Optional[Union[str, Path]] = None
) -> LSTMPrecursorDetector:
    """
    Create LSTM detector with optional configuration.
    
    Args:
        config_file: Optional configuration file
        weights_file: Optional pre-trained weights
        
    Returns:
        Configured LSTMPrecursorDetector instance
    """
    config = LSTMConfig()
    
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
    
    model = LSTMPrecursorDetector(config)
    
    if weights_file:
        model.load_state_dict(torch.load(weights_file, map_location='cpu'))
    
    return model
