"""
XGBoost Classifier with SHAP Attribution for DRGIS
Part of DESERTAS AI Ensemble (35% ensemble weight)

Processes 8 tabular parameters with full SHAP decomposition:
- Feature importance analysis
- Per-parameter attribution for explainability
- Natural-language report generation

Output: Alert level classification and parameter contributions
"""

import numpy as np
import xgboost as xgb
import shap
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
import json
import yaml
import pickle
from pathlib import Path


@dataclass
class XGBConfig:
    """Configuration for XGBoost classifier."""
    n_estimators: int = 100
    max_depth: int = 6
    learning_rate: float = 0.1
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    min_child_weight: int = 1
    gamma: float = 0.1
    reg_alpha: float = 0.1
    reg_lambda: float = 1.0
    
    # Training parameters
    early_stopping_rounds: int = 10
    eval_metric: List[str] = field(default_factory=lambda: ['mlogloss', 'merror'])
    
    # SHAP parameters
    shap_background_size: int = 100
    
    # Parameter names
    param_names: List[str] = field(default_factory=lambda: [
        'ΔΦ_th', 'Ψ_crack', 'Rn_pulse', 'Ω_arid',
        'Γ_geo', 'He_ratio', 'β_dust', 'S_yield'
    ])
    
    # Target classes
    class_names: List[str] = field(default_factory=lambda: [
        'BACKGROUND', 'WATCH', 'ALERT', 'EMERGENCY', 'CRITICAL'
    ])


class XGBoostClassifier:
    """
    XGBoost classifier with SHAP attribution for DRGIS.
    
    Provides:
    - Multi-class classification of alert levels
    - SHAP values for per-parameter attribution
    - Natural-language explanation generation
    """
    
    def __init__(self, config: Optional[XGBConfig] = None):
        """
        Initialize XGBoost classifier.
        
        Args:
            config: Configuration object
        """
        self.config = config or XGBConfig()
        self.model = None
        self.shap_explainer = None
        self.feature_importance = {}
        
    def build_model(self) -> xgb.XGBClassifier:
        """Build XGBoost model with configuration."""
        self.model = xgb.XGBClassifier(
            n_estimators=self.config.n_estimators,
            max_depth=self.config.max_depth,
            learning_rate=self.config.learning_rate,
            subsample=self.config.subsample,
            colsample_bytree=self.config.colsample_bytree,
            min_child_weight=self.config.min_child_weight,
            gamma=self.config.gamma,
            reg_alpha=self.config.reg_alpha,
            reg_lambda=self.config.reg_lambda,
            objective='multi:softprob',
            num_class=len(self.config.class_names),
            use_label_encoder=False,
            eval_metric=self.config.eval_metric
        )
        return self.model
    
    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        feature_names: Optional[List[str]] = None
    ) -> Dict[str, List[float]]:
        """
        Train the XGBoost model.
        
        Args:
            X_train: Training features (n_samples, 8)
            y_train: Training labels (0-4)
            X_val: Validation features
            y_val: Validation labels
            feature_names: Optional feature names
            
        Returns:
            Training history
        """
        if self.model is None:
            self.build_model()
        
        if feature_names is None:
            feature_names = self.config.param_names
        
        eval_set = [(X_train, y_train)]
        if X_val is not None and y_val is not None:
            eval_set.append((X_val, y_val))
        
        self.model.fit(
            X_train, y_train,
            eval_set=eval_set,
            early_stopping_rounds=self.config.early_stopping_rounds,
            verbose=False
        )
        
        # Extract training history
        history = {}
        if hasattr(self.model, 'evals_result'):
            history = self.model.evals_result()
        
        # Calculate feature importance
        importance = self.model.feature_importances_
        self.feature_importance = {
            name: float(imp)
            for name, imp in zip(feature_names, importance)
        }
        
        # Initialize SHAP explainer
        self._init_shap_explainer(X_train[:self.config.shap_background_size])
        
        return history
    
    def _init_shap_explainer(self, background_data: np.ndarray):
        """Initialize SHAP explainer with background data."""
        self.shap_explainer = shap.TreeExplainer(self.model)
        self.shap_background = background_data
    
    def predict(
        self,
        X: np.ndarray,
        return_proba: bool = False
    ) -> Union[np.ndarray, Tuple[np.ndarray, np.ndarray]]:
        """
        Make predictions.
        
        Args:
            X: Input features (n_samples, 8)
            return_proba: Whether to return probabilities
            
        Returns:
            Predictions or (predictions, probabilities)
        """
        if self.model is None:
            raise ValueError("Model not trained yet")
        
        preds = self.model.predict(X)
        
        if return_proba:
            proba = self.model.predict_proba(X)
            return preds, proba
        else:
            return preds
    
    def get_shap_values(
        self,
        X: np.ndarray
    ) -> Dict[str, Union[np.ndarray, List]]:
        """
        Calculate SHAP values for explainability.
        
        Args:
            X: Input features (n_samples, 8)
            
        Returns:
            Dictionary with SHAP values and metadata
        """
        if self.shap_explainer is None:
            raise ValueError("SHAP explainer not initialized. Train model first.")
        
        # Calculate SHAP values
        shap_values = self.shap_explainer.shap_values(X)
        
        # For multi-class, shap_values is list of arrays per class
        if isinstance(shap_values, list):
            # Average absolute SHAP values across classes
            mean_abs_shap = np.mean([np.abs(sv) for sv in shap_values], axis=0)
        else:
            mean_abs_shap = np.abs(shap_values)
        
        # Per-feature attribution
        feature_attribution = {}
        for i, name in enumerate(self.config.param_names):
            feature_attribution[name] = {
                'mean_abs_shap': float(np.mean(mean_abs_shap[:, i])),
                'mean_shap': float(np.mean([sv[:, i].mean() for sv in shap_values])) if isinstance(shap_values, list) else float(np.mean(shap_values[:, i])),
                'std_shap': float(np.std(mean_abs_shap[:, i]))
            }
        
        # Get predictions for context
        preds, proba = self.predict(X, return_proba=True)
        
        return {
            'shap_values': shap_values,
            'feature_attribution': feature_attribution,
            'predictions': preds.tolist(),
            'probabilities': proba.tolist(),
            'class_names': self.config.class_names,
            'feature_names': self.config.param_names
        }
    
    def generate_explanation(
        self,
        X: np.ndarray,
        station_id: str,
        timestamp: str
    ) -> Dict[str, Union[str, Dict]]:
        """
        Generate natural-language explanation for predictions.
        
        Args:
            X: Input features (single sample, shape (1,8))
            station_id: Station identifier
            timestamp: Timestamp string
            
        Returns:
            Dictionary with explanation and SHAP attribution
        """
        if self.model is None:
            raise ValueError("Model not trained yet")
        
        # Get SHAP values
        shap_data = self.get_shap_values(X)
        
        # Get prediction
        pred_class = int(shap_data['predictions'][0])
        proba = shap_data['probabilities'][0][pred_class]
        alert_level = self.config.class_names[pred_class]
        
        # Extract per-parameter contributions
        contributions = {}
        for i, name in enumerate(self.config.param_names):
            if isinstance(shap_data['shap_values'], list):
                # Multi-class: use average across classes
                shap_val = np.mean([sv[0, i] for sv in shap_data['shap_values']])
            else:
                shap_val = shap_data['shap_values'][0, i]
            
            contributions[name] = {
                'value': float(X[0, i]),
                'shap': float(shap_val),
                'impact': 'positive' if shap_val > 0 else 'negative',
                'magnitude': abs(float(shap_val))
            }
        
        # Sort by |SHAP| to identify primary drivers
        sorted_params = sorted(
            contributions.items(),
            key=lambda x: abs(x[1]['shap']),
            reverse=True
        )
        
        primary_driver = sorted_params[0][0] if sorted_params else None
        primary_shap = sorted_params[0][1]['shap'] if sorted_params else 0
        primary_value = sorted_params[0][1]['value'] if sorted_params else 0
        
        # Generate natural language explanation
        if pred_class <= 1:  # BACKGROUND or WATCH
            explanation = (
                f"Station {station_id} at {timestamp}: "
                f"{alert_level} level detected with {proba:.1%} confidence. "
                f"Primary driver: {primary_driver} ({primary_value:.2f}) "
                f"with {'positive' if primary_shap > 0 else 'negative'} contribution "
                f"of {abs(primary_shap):.3f}. No immediate action required."
            )
        elif pred_class == 2:  # ALERT
            explanation = (
                f"⚠️ ALERT at station {station_id} ({timestamp}). "
                f"DRGIS indicates tectonic precursor with {proba:.1%} confidence. "
                f"Primary driver: {primary_driver} ({primary_value:.2f}) "
                f"contributing {primary_shap:+.3f} to alert level. "
                f"Recommend: Enhanced monitoring and civil protection notification."
            )
        elif pred_class == 3:  # EMERGENCY
            explanation = (
                f"🚨 EMERGENCY at station {station_id} ({timestamp})! "
                f"Strong precursor confirmed with {proba:.1%} confidence. "
                f"Primary driver: {primary_driver} ({primary_value:.2f}) "
                f"with {primary_shap:+.3f} SHAP value. "
                f"Recommend: Activate emergency plans immediately."
            )
        else:  # CRITICAL
            explanation = (
                f"‼️ CRITICAL - IMMINENT SEISMIC RISK at {station_id} ({timestamp})! "
                f"Highest alert level with {proba:.1%} confidence. "
                f"Primary driver: {primary_driver} ({primary_value:.2f}) "
                f"dominant contribution of {primary_shap:+.3f}. "
                f"EVACUATE high-risk structures immediately."
            )
        
        return {
            'station_id': station_id,
            'timestamp': timestamp,
            'alert_level': alert_level,
            'confidence': float(proba),
            'explanation': explanation,
            'primary_driver': primary_driver,
            'contributions': contributions,
            'sorted_drivers': [
                {
                    'parameter': p[0],
                    'shap': p[1]['shap'],
                    'value': p[1]['value']
                }
                for p in sorted_params[:3]  # Top 3 drivers
            ],
            'raw_shap': shap_data['shap_values']
        }
    
    def save_model(self, path: Union[str, Path]):
        """Save model to file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'wb') as f:
            pickle.dump({
                'model': self.model,
                'config': self.config,
                'feature_importance': self.feature_importance
            }, f)
    
    def load_model(self, path: Union[str, Path]):
        """Load model from file."""
        path = Path(path)
        with open(path, 'rb') as f:
            data = pickle.load(f)
        
        self.model = data['model']
        self.config = data['config']
        self.feature_importance = data['feature_importance']
        
        # Reinitialize SHAP explainer
        if hasattr(self, 'shap_background'):
            self._init_shap_explainer(self.shap_background)
    
    def get_feature_importance_table(self) -> Dict[str, float]:
        """Get feature importance as formatted table."""
        return {
            'feature_importance': self.feature_importance,
            'top_features': sorted(
                self.feature_importance.items(),
                key=lambda x: x[1],
                reverse=True
            )[:3]
        }
    
    def validate_accuracy(
        self,
        X_test: np.ndarray,
        y_test: np.ndarray
    ) -> Dict[str, float]:
        """
        Validate model accuracy on test set.
        
        Args:
            X_test: Test features
            y_test: Test labels
            
        Returns:
            Accuracy metrics
        """
        preds = self.predict(X_test)
        
        # Overall accuracy
        accuracy = np.mean(preds == y_test)
        
        # Per-class accuracy
        class_accuracy = {}
        for i, class_name in enumerate(self.config.class_names):
            mask = y_test == i
            if np.any(mask):
                class_acc = np.mean(preds[mask] == y_test[mask])
                class_accuracy[class_name] = float(class_acc)
        
        # Confusion matrix
        from sklearn.metrics import confusion_matrix
        cm = confusion_matrix(y_test, preds)
        
        return {
            'overall_accuracy': float(accuracy),
            'per_class_accuracy': class_accuracy,
            'confusion_matrix': cm.tolist(),
            'n_samples': len(y_test)
        }


# Factory function
def create_xgboost_classifier(
    config_file: Optional[Union[str, Path]] = None
) -> XGBoostClassifier:
    """
    Create XGBoost classifier with optional configuration.
    
    Args:
        config_file: Optional configuration file
        
    Returns:
        Configured XGBoostClassifier instance
    """
    config = XGBConfig()
    
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
    
    return XGBoostClassifier(config)
