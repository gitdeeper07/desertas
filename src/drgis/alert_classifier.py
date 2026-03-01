"""
Alert Classifier for DRGIS - Converts DRGIS scores to operational alerts.
Implements 4-tier alert system with civil protection protocols.

Alert Levels:
- BACKGROUND: <0.30 - Normal activity
- WATCH: 0.30-0.48 - Enhanced monitoring
- ALERT: 0.48-0.65 - Civil protection notification
- EMERGENCY: 0.65-0.80 - Emergency plan activation
- CRITICAL: >0.80 - Evacuation of high-risk structures

Lead time mapping: 58-day mean, with phased response
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import json
import yaml
from pathlib import Path


class AlertStatus(Enum):
    """Alert status codes."""
    ACTIVE = "active"
    RESOLVED = "resolved"
    FALSE_ALARM = "false_alarm"
    VERIFIED = "verified"
    EXPIRED = "expired"


class ResponsePhase(Enum):
    """Civil protection response phases."""
    MONITORING = "monitoring"           # Days 58-31
    PREPARATION = "preparation"         # Days 31-14
    ACTIVATION = "activation"           # Days 14-7
    EVACUATION = "evacuation"           # Days 7-0
    IMMEDIATE = "immediate"             # < 24 hours


@dataclass
class AlertConfig:
    """Configuration for alert classification."""
    station_id: str
    craton: str
    
    # Thresholds (from Appendix B)
    background_max: float = 0.30
    watch_max: float = 0.48
    alert_max: float = 0.65
    emergency_max: float = 0.80
    
    # Rn_pulse specific thresholds
    rn_watch_sigma: float = 2.0
    rn_alert_sigma: float = 3.0
    rn_emergency_sigma: float = 4.0
    rn_critical_sigma: float = 5.0
    
    # Coherence thresholds
    coherence_alert: float = 0.60
    coherence_emergency: float = 0.75
    
    # Lead time mapping (days)
    mean_lead_time: int = 58
    max_lead_time: int = 134
    min_lead_time: int = 11
    
    # Alert expiration
    alert_duration_days: int = 90
    verification_window_days: int = 30


@dataclass
class AlertRecord:
    """Record of an alert event."""
    alert_id: str
    station_id: str
    timestamp: datetime
    drgis_value: float
    alert_level: str
    rn_pulse: float
    he_ratio: float
    lead_time_estimate: float
    confidence: float
    status: AlertStatus
    response_phase: Optional[ResponsePhase] = None
    verified_event: Optional[Dict] = None
    notes: str = ""


class AlertClassifier:
    """
    DRGIS Alert Classifier.
    
    Converts DRGIS scores to operational alerts with
    phased civil protection responses.
    
    Attributes:
        config: Alert configuration
        active_alerts: Currently active alerts
        alert_history: Historical alerts
    """
    
    def __init__(self, config: AlertConfig):
        """
        Initialize alert classifier.
        
        Args:
            config: Alert configuration
        """
        self.config = config
        self.active_alerts: Dict[str, AlertRecord] = {}
        self.alert_history: List[AlertRecord] = []
        
    def classify(
        self,
        drgis_value: float,
        rn_pulse: float,
        he_ratio: float,
        coherence: float = 0.0,
        station_name: Optional[str] = None
    ) -> Dict[str, Union[str, float]]:
        """
        Classify alert level from DRGIS and supporting parameters.
        
        Args:
            drgis_value: DRGIS score
            rn_pulse: Rn_pulse sigma value
            he_ratio: He_ratio value
            coherence: Spatial coherence metric
            station_name: Optional station name
            
        Returns:
            Alert classification with metadata
        """
        # Determine base alert level from DRGIS
        alert_level = self._get_alert_level(drgis_value)
        
        # Adjust based on Rn_pulse and coherence
        alert_level = self._adjust_alert_level(
            alert_level, rn_pulse, coherence
        )
        
        # Estimate lead time
        lead_time = self._estimate_lead_time(
            drgis_value, rn_pulse, he_ratio
        )
        
        # Determine response phase
        response_phase = self._get_response_phase(lead_time)
        
        # Calculate confidence
        confidence = self._calculate_confidence(
            drgis_value, rn_pulse, coherence
        )
        
        # Generate recommendation
        recommendation = self._generate_recommendation(
            alert_level, lead_time, response_phase
        )
        
        return {
            'alert_level': alert_level,
            'drgis_value': round(drgis_value, 3),
            'rn_pulse_sigma': round(rn_pulse, 2),
            'he_ratio': round(he_ratio, 2),
            'coherence': round(coherence, 2),
            'lead_time_days': round(lead_time, 1),
            'response_phase': response_phase.value,
            'confidence': round(confidence, 2),
            'recommendation': recommendation,
            'timestamp': datetime.now().isoformat()
        }
    
    def _get_alert_level(self, drgis: float) -> str:
        """Get alert level from DRGIS value."""
        if drgis >= self.config.emergency_max:
            return "CRITICAL"
        elif drgis >= self.config.alert_max:
            return "EMERGENCY"
        elif drgis >= self.config.watch_max:
            return "ALERT"
        elif drgis >= self.config.background_max:
            return "WATCH"
        else:
            return "BACKGROUND"
    
    def _adjust_alert_level(
        self,
        base_level: str,
        rn_pulse: float,
        coherence: float
    ) -> str:
        """Adjust alert level based on Rn_pulse and coherence."""
        # Level mapping for escalation
        levels = ["BACKGROUND", "WATCH", "ALERT", "EMERGENCY", "CRITICAL"]
        
        if base_level in ["WATCH", "ALERT"]:
            # Check for Rn_pulse confirmation
            if rn_pulse >= self.config.rn_alert_sigma and coherence >= self.config.coherence_alert:
                # Escalate one level
                current_idx = levels.index(base_level)
                if current_idx < len(levels) - 1:
                    return levels[current_idx + 1]
            
            # Check for weak signal
            elif rn_pulse < self.config.rn_watch_sigma:
                # De-escalate if appropriate
                current_idx = levels.index(base_level)
                if current_idx > 0:
                    return levels[current_idx - 1]
        
        elif base_level == "EMERGENCY":
            # EMERGENCY requires strong coherence
            if coherence < self.config.coherence_emergency:
                return "ALERT"
        
        return base_level
    
    def _estimate_lead_time(
        self,
        drgis: float,
        rn_pulse: float,
        he_ratio: float
    ) -> float:
        """
        Estimate pre-seismic lead time based on parameters.
        
        Uses multi-stage precursor sequence:
        He_ratio onset → Γ_geo acceleration → Rn_pulse threshold
        """
        # Base on DRGIS
        if drgis < 0.3:
            return 0.0
        
        # He_ratio provides earliest indication
        he_factor = 0.0
        if he_ratio > 2.0:
            he_factor = 31  # Mean He_ratio advantage
        elif he_ratio > 0.5:
            he_factor = 15
        
        # Rn_pulse indicates approaching event
        rn_factor = 0.0
        if rn_pulse >= self.config.rn_critical_sigma:
            rn_factor = 7  # Last week
        elif rn_pulse >= self.config.rn_emergency_sigma:
            rn_factor = 14  # Two weeks
        elif rn_pulse >= self.config.rn_alert_sigma:
            rn_factor = 30  # Month
        elif rn_pulse >= self.config.rn_watch_sigma:
            rn_factor = 45  # 45 days
        
        # DRGIS magnitude factor
        drgis_factor = 58 * drgis  # Scale by DRGIS
        
        # Combine factors (non-linear)
        if he_factor > 0 and rn_factor > 0:
            # Both indicators present - use maximum
            lead_time = max(he_factor, rn_factor, drgis_factor)
        elif he_factor > 0:
            # Only He_ratio
            lead_time = he_factor
        elif rn_factor > 0:
            # Only Rn_pulse
            lead_time = rn_factor
        else:
            # DRGIS only
            lead_time = drgis_factor
        
        # Clip to valid range
        return np.clip(lead_time, 0, self.config.max_lead_time)
    
    def _get_response_phase(self, lead_time_days: float) -> ResponsePhase:
        """Map lead time to response phase."""
        if lead_time_days >= 31:
            return ResponsePhase.MONITORING
        elif lead_time_days >= 14:
            return ResponsePhase.PREPARATION
        elif lead_time_days >= 7:
            return ResponsePhase.ACTIVATION
        elif lead_time_days > 0:
            return ResponsePhase.EVACUATION
        else:
            return ResponsePhase.IMMEDIATE
    
    def _calculate_confidence(
        self,
        drgis: float,
        rn_pulse: float,
        coherence: float
    ) -> float:
        """Calculate confidence in alert."""
        # Base confidence on DRGIS magnitude
        confidence = min(drgis * 1.2, 1.0)
        
        # Boost if Rn_pulse confirms
        if rn_pulse >= self.config.rn_alert_sigma:
            confidence = min(confidence * 1.3, 1.0)
        
        # Boost if spatial coherence is high
        if coherence >= self.config.coherence_emergency:
            confidence = min(confidence * 1.2, 1.0)
        
        # Reduce if coherence is low
        if coherence < self.config.coherence_alert and drgis > 0.5:
            confidence *= 0.8
        
        return confidence
    
    def _generate_recommendation(
        self,
        alert_level: str,
        lead_time: float,
        phase: ResponsePhase
    ) -> str:
        """Generate actionable recommendation based on alert."""
        if alert_level == "BACKGROUND":
            return "Continue routine monitoring. No action required."
        
        elif alert_level == "WATCH":
            return (f"Enhanced monitoring recommended. "
                   f"Estimated {lead_time:.0f} days until potential event. "
                   f"Increase sampling frequency and review station data.")
        
        elif alert_level == "ALERT":
            return (f"TECTONIC ALERT. Notify civil protection authorities. "
                   f"Estimated {lead_time:.0f} days lead time. "
                   f"Begin public communication planning. "
                   f"Conduct structural vulnerability assessment.")
        
        elif alert_level == "EMERGENCY":
            return (f"EMERGENCY PRECURSOR. Activate emergency plans. "
                   f"Estimated {lead_time:.0f} days until event. "
                   f"Prepare evacuation of high-risk structures. "
                   f"Maximum alert for critical infrastructure.")
        
        elif alert_level == "CRITICAL":
            return (f"CRITICAL - IMMINENT SEISMIC RISK. "
                   f"Immediate evacuation required. "
                   f"Estimated {lead_time:.0f} days lead time. "
                   f"This is the highest alert level.")
        
        return "No recommendation available."
    
    def create_alert(
        self,
        station_id: str,
        classification: Dict[str, Union[str, float]]
    ) -> AlertRecord:
        """Create a new alert record."""
        alert_id = f"ALT-{station_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        alert = AlertRecord(
            alert_id=alert_id,
            station_id=station_id,
            timestamp=datetime.now(),
            drgis_value=classification['drgis_value'],
            alert_level=classification['alert_level'],
            rn_pulse=classification['rn_pulse_sigma'],
            he_ratio=classification['he_ratio'],
            lead_time_estimate=classification['lead_time_days'],
            confidence=classification['confidence'],
            status=AlertStatus.ACTIVE,
            response_phase=classification.get('response_phase')
        )
        
        # Store alert
        self.active_alerts[alert_id] = alert
        self.alert_history.append(alert)
        
        return alert
    
    def resolve_alert(
        self,
        alert_id: str,
        event_occurred: bool = False,
        magnitude: Optional[float] = None,
        notes: str = ""
    ) -> AlertRecord:
        """Resolve an active alert."""
        if alert_id not in self.active_alerts:
            raise ValueError(f"Alert {alert_id} not found")
        
        alert = self.active_alerts[alert_id]
        
        if event_occurred:
            alert.status = AlertStatus.VERIFIED
            alert.verified_event = {
                'timestamp': datetime.now().isoformat(),
                'magnitude': magnitude
            }
        else:
            alert.status = AlertStatus.FALSE_ALARM
        
        alert.notes = notes
        
        # Remove from active alerts
        del self.active_alerts[alert_id]
        
        return alert
    
    def get_active_alerts(
        self,
        min_level: str = "WATCH"
    ) -> List[AlertRecord]:
        """Get currently active alerts above threshold."""
        levels = ["WATCH", "ALERT", "EMERGENCY", "CRITICAL"]
        min_idx = levels.index(min_level) if min_level in levels else 0
        
        active = []
        for alert in self.active_alerts.values():
            if alert.alert_level in levels[levels.index(min_level):]:
                active.append(alert)
        
        return sorted(active, key=lambda x: x.timestamp, reverse=True)
    
    def get_alert_statistics(self) -> Dict[str, float]:
        """Get statistics about alert performance."""
        total = len(self.alert_history)
        if total == 0:
            return {}
        
        verified = sum(1 for a in self.alert_history if a.status == AlertStatus.VERIFIED)
        false = sum(1 for a in self.alert_history if a.status == AlertStatus.FALSE_ALARM)
        active = len(self.active_alerts)
        
        return {
            'total_alerts': total,
            'verified_alerts': verified,
            'false_alarms': false,
            'active_alerts': active,
            'verification_rate': verified / total * 100 if total > 0 else 0,
            'false_alert_rate': false / total * 100 if total > 0 else 0,
            'mean_confidence': np.mean([a.confidence for a in self.alert_history])
        }
    
    def export_alerts(self, format: str = 'json') -> str:
        """Export alerts to JSON or YAML."""
        data = {
            'config': {
                'station_id': self.config.station_id,
                'craton': self.config.craton,
                'thresholds': {
                    'background_max': self.config.background_max,
                    'watch_max': self.config.watch_max,
                    'alert_max': self.config.alert_max,
                    'emergency_max': self.config.emergency_max
                }
            },
            'active_alerts': [
                {
                    'alert_id': a.alert_id,
                    'timestamp': a.timestamp.isoformat(),
                    'alert_level': a.alert_level,
                    'drgis_value': a.drgis_value,
                    'lead_time': a.lead_time_estimate,
                    'confidence': a.confidence
                }
                for a in self.active_alerts.values()
            ],
            'history': [
                {
                    'alert_id': a.alert_id,
                    'timestamp': a.timestamp.isoformat(),
                    'alert_level': a.alert_level,
                    'status': a.status.value,
                    'verified': a.verified_event is not None
                }
                for a in self.alert_history[-100:]  # Last 100
            ],
            'statistics': self.get_alert_statistics()
        }
        
        if format == 'json':
            return json.dumps(data, indent=2)
        elif format == 'yaml':
            return yaml.dump(data)
        else:
            raise ValueError(f"Unsupported format: {format}")


# Factory function
def create_alert_classifier(
    station_id: str,
    craton: str,
    config_file: Optional[Union[str, Path]] = None
) -> AlertClassifier:
    """
    Create alert classifier with configuration.
    
    Args:
        station_id: Station identifier
        craton: Craton name
        config_file: Optional configuration file
        
    Returns:
        Configured AlertClassifier instance
    """
    config = AlertConfig(
        station_id=station_id,
        craton=craton
    )
    
    if config_file:
        path = Path(config_file)
        with open(path, 'r') as f:
            if path.suffix in ['.yaml', '.yml']:
                data = yaml.safe_load(f)
            else:
                data = json.load(f)
        
        # Override config from file
        for key, value in data.items():
            if hasattr(config, key):
                setattr(config, key, value)
    
    return AlertClassifier(config)
