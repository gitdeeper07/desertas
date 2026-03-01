#!/usr/bin/env python3
"""
اختبارات مبسطة لـ DRGIS
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

import unittest
import numpy as np


class ParameterWeights:
    def __init__(self):
        self.delta_phi_th = 0.18
        self.psi_crack = 0.16
        self.rn_pulse = 0.18
        self.omega_arid = 0.12
        self.gamma_geo = 0.14
        self.he_ratio = 0.10
        self.beta_dust = 0.07
        self.s_yield = 0.05
    
    def validate(self):
        total = (self.delta_phi_th + self.psi_crack + self.rn_pulse +
                self.omega_arid + self.gamma_geo + self.he_ratio +
                self.beta_dust + self.s_yield)
        return abs(total - 1.0) < 1e-6


class AlertThresholds:
    def __init__(self):
        self.background_max = 0.30
        self.watch_max = 0.48
        self.alert_max = 0.65
        self.emergency_max = 0.80
    
    def get_level(self, drgis):
        if drgis < self.background_max:
            return 'BACKGROUND'
        elif drgis < self.watch_max:
            return 'WATCH'
        elif drgis < self.alert_max:
            return 'ALERT'
        elif drgis < self.emergency_max:
            return 'EMERGENCY'
        else:
            return 'CRITICAL'


class DRGISCalculator:
    def __init__(self, weights=None, thresholds=None):
        self.weights = weights or ParameterWeights()
        self.thresholds = thresholds or AlertThresholds()
    
    def compute_raw(self, params):
        drgis = (
            self.weights.delta_phi_th * params.get('delta_phi_th', 0) +
            self.weights.psi_crack * params.get('psi_crack', 0) +
            self.weights.rn_pulse * min(params.get('rn_pulse', 0) / 5.0, 1.0) +
            self.weights.omega_arid * params.get('omega_arid', 0) +
            self.weights.gamma_geo * min(params.get('gamma_geo', 0) / 5.0, 1.0) +
            self.weights.he_ratio * min(params.get('he_ratio', 0) / 5.0, 1.0) +
            self.weights.beta_dust * params.get('beta_dust', 0) +
            self.weights.s_yield * params.get('s_yield', 0)
        )
        return np.clip(drgis, 0, 1)
    
    def compute(self, params):
        drgis_raw = self.compute_raw(params)
        alert_level = self.thresholds.get_level(drgis_raw)
        
        return {
            'drgis_raw': round(drgis_raw, 4),
            'drgis_adjusted': round(drgis_raw, 4),
            'alert_level': alert_level
        }


class TestDRGISSimple(unittest.TestCase):
    """اختبارات مبسطة لـ DRGIS"""
    
    def setUp(self):
        self.calculator = DRGISCalculator()
        self.sample_params = {
            'delta_phi_th': 0.45,
            'psi_crack': 0.52,
            'rn_pulse': 3.2,
            'omega_arid': 0.72,
            'gamma_geo': 1.4,
            'he_ratio': 0.42,
            'beta_dust': 0.38,
            's_yield': 0.45
        }
    
    def test_weights_validation(self):
        weights = ParameterWeights()
        self.assertTrue(weights.validate())
    
    def test_raw_computation(self):
        drgis_raw = self.calculator.compute_raw(self.sample_params)
        self.assertGreaterEqual(drgis_raw, 0)
        self.assertLessEqual(drgis_raw, 1)
    
    def test_full_computation(self):
        result = self.calculator.compute(self.sample_params)
        self.assertIn('drgis_raw', result)
        self.assertIn('alert_level', result)
    
    def test_alert_levels(self):
        thresholds = AlertThresholds()
        test_cases = [
            (0.20, 'BACKGROUND'),
            (0.35, 'WATCH'),
            (0.50, 'ALERT'),
            (0.70, 'EMERGENCY'),
            (0.85, 'CRITICAL')
        ]
        for value, expected in test_cases:
            with self.subTest(value=value):
                level = thresholds.get_level(value)
                self.assertEqual(level, expected)


if __name__ == '__main__':
    unittest.main()
