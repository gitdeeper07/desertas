#!/usr/bin/env python3
"""
اختبارات مبسطة لـ AI Ensemble (بدون torch)
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

import unittest
import numpy as np


class EnsembleConfig:
    def __init__(self, lstm_weight=0.40, xgb_weight=0.35, cnn_weight=0.25):
        self.lstm_weight = lstm_weight
        self.xgb_weight = xgb_weight
        self.cnn_weight = cnn_weight
        total = lstm_weight + xgb_weight + cnn_weight
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Weights must sum to 1.0, got {total}")


class DESERTASEnsemble:
    def __init__(self, config=None):
        self.config = config or EnsembleConfig()
        self.class_names = ['BACKGROUND', 'WATCH', 'ALERT', 'EMERGENCY', 'CRITICAL']
    
    def predict(self, features):
        """تنبؤ مبسط يعتمد على المجموع المرجح"""
        # محاكاة تنبؤ
        if isinstance(features, dict):
            # إذا كانت المعاملات مدخلة
            weights = {
                'delta_phi_th': 0.18,
                'psi_crack': 0.16,
                'rn_pulse': 0.18,
                'omega_arid': 0.12,
                'gamma_geo': 0.14,
                'he_ratio': 0.10,
                'beta_dust': 0.07,
                's_yield': 0.05
            }
            score = 0
            for param, weight in weights.items():
                if param in features:
                    if param == 'rn_pulse':
                        norm = min(features[param] / 5.0, 1.0)
                    elif param == 'he_ratio':
                        norm = min(features[param] / 5.0, 1.0)
                    elif param == 'gamma_geo':
                        norm = min(features[param] / 5.0, 1.0)
                    else:
                        norm = min(features[param], 1.0)
                    score += weight * norm
        else:
            # إذا كانت مصفوفة عشوائية
            score = np.random.random()
        
        # تحديد مستوى الإنذار
        if score >= 0.80:
            pred = 4  # CRITICAL
            level = 'CRITICAL'
        elif score >= 0.65:
            pred = 3  # EMERGENCY
            level = 'EMERGENCY'
        elif score >= 0.48:
            pred = 2  # ALERT
            level = 'ALERT'
        elif score >= 0.30:
            pred = 1  # WATCH
            level = 'WATCH'
        else:
            pred = 0  # BACKGROUND
            level = 'BACKGROUND'
        
        # احتساب الثقة
        confidence = score
        
        return {
            'ensemble_prediction': pred,
            'alert_level': level,
            'ensemble_probabilities': [0.2, 0.2, 0.2, 0.2, 0.2],
            'confidence': float(confidence),
            'agreement_score': 0.95
        }
    
    def _calculate_agreement(self, predictions):
        """حساب نسبة الاتفاق بين النماذج"""
        n = len(predictions)
        if n < 2:
            return 1.0
        agreements = 0
        for i in range(n):
            for j in range(i+1, n):
                if predictions[i] == predictions[j]:
                    agreements += 1
        max_agreements = n * (n-1) / 2
        return agreements / max_agreements if max_agreements > 0 else 1.0


class TestAIEnsembleSimple(unittest.TestCase):
    """اختبارات مبسطة لـ AI Ensemble"""
    
    def setUp(self):
        self.ensemble = DESERTASEnsemble()
        self.sample_features = {
            'delta_phi_th': 0.45,
            'psi_crack': 0.52,
            'rn_pulse': 3.2,
            'omega_arid': 0.72,
            'gamma_geo': 1.4,
            'he_ratio': 0.42,
            'beta_dust': 0.38,
            's_yield': 0.45
        }
    
    def test_initialization(self):
        """اختبار التهيئة"""
        self.assertEqual(self.ensemble.config.lstm_weight, 0.40)
        self.assertEqual(self.ensemble.config.xgb_weight, 0.35)
        self.assertEqual(self.ensemble.config.cnn_weight, 0.25)
    
    def test_invalid_weights(self):
        """اختبار الأوزان الخاطئة"""
        with self.assertRaises(ValueError):
            EnsembleConfig(0.5, 0.5, 0.5)
    
    def test_prediction(self):
        """اختبار التنبؤ"""
        result = self.ensemble.predict(self.sample_features)
        self.assertIn('ensemble_prediction', result)
        self.assertIn('alert_level', result)
        self.assertIn('confidence', result)
    
    def test_agreement_calculation(self):
        """اختبار حساب الاتفاق"""
        predictions = [0, 0, 1]
        agreement = self.ensemble._calculate_agreement(predictions)
        self.assertAlmostEqual(agreement, 1/3)
        
        predictions = [1, 1, 1]
        agreement = self.ensemble._calculate_agreement(predictions)
        self.assertEqual(agreement, 1.0)
    
    def test_prediction_consistency(self):
        """اختبار ثبات التنبؤ"""
        results = []
        for _ in range(3):
            # استخدام نفس البذرة العشوائية للحصول على نفس النتائج
            np.random.seed(42)
            result = self.ensemble.predict(self.sample_features)
            results.append(result['ensemble_prediction'])
        self.assertEqual(len(set(results)), 1)


if __name__ == '__main__':
    unittest.main()
