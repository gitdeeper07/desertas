#!/usr/bin/env python3
"""
اختبارات AI Ensemble
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

import unittest
import numpy as np
import torch
from src.ai.ensemble import DESERTASEnsemble, EnsembleConfig
from src.ai.lstm_detector import LSTMPrecursorDetector, LSTMConfig
from src.ai.xgboost_classifier import XGBoostClassifier, XGBConfig
from src.ai.cnn_spatial import CNNSpatialDetector, CNNConfig


class TestAIEnsemble(unittest.TestCase):
    """اختبارات AI Ensemble"""
    
    def setUp(self):
        """إعداد بيئة الاختبار"""
        # تهيئة النماذج
        self.lstm = LSTMPrecursorDetector(LSTMConfig())
        self.xgb = XGBoostClassifier(XGBConfig())
        self.cnn = CNNSpatialDetector(CNNConfig())
        
        # تهيئة ensemble
        self.ensemble = DESERTASEnsemble(
            self.lstm,
            self.xgb,
            self.cnn
        )
        
        # بيانات اختبار
        self.lstm_input = torch.randn(1, 720, 1)  # (batch, seq, features)
        self.xgb_input = np.random.randn(1, 8)     # (batch, 8 parameters)
        self.cnn_input = torch.randn(1, 8, 64, 64) # (batch, channels, h, w)
    
    def test_initialization(self):
        """اختبار التهيئة"""
        self.assertEqual(self.ensemble.config.lstm_weight, 0.40)
        self.assertEqual(self.ensemble.config.xgb_weight, 0.35)
        self.assertEqual(self.ensemble.config.cnn_weight, 0.25)
        
        # مجموع الأوزان = 1
        total = (self.ensemble.config.lstm_weight +
                self.ensemble.config.xgb_weight +
                self.ensemble.config.cnn_weight)
        self.assertAlmostEqual(total, 1.0)
    
    def test_prediction(self):
        """اختبار التنبؤ"""
        result = self.ensemble.predict(
            self.lstm_input,
            self.xgb_input,
            self.cnn_input
        )
        
        self.assertIn('ensemble_prediction', result)
        self.assertIn('alert_level', result)
        self.assertIn('ensemble_probabilities', result)
        self.assertIn('confidence', result)
        self.assertIn('agreement_score', result)
    
    def test_prediction_with_components(self):
        """اختبار التنبؤ مع المكونات"""
        result = self.ensemble.predict(
            self.lstm_input,
            self.xgb_input,
            self.cnn_input,
            return_components=True
        )
        
        self.assertIn('components', result)
        self.assertIn('lstm', result['components'])
        self.assertIn('xgboost', result['components'])
        self.assertIn('cnn', result['components'])
    
    def test_agreement_calculation(self):
        """اختبار حساب الاتفاق"""
        predictions = [0, 0, 1]
        agreement = self.ensemble._calculate_agreement(predictions)
        
        # اثنان متفقان (0,0) والثالث مختلف
        self.assertAlmostEqual(agreement, 1/3)  # 1 من 3 أزواج متفق
        
        predictions = [1, 1, 1]
        agreement = self.ensemble._calculate_agreement(predictions)
        self.assertEqual(agreement, 1.0)
    
    def test_agreement_level(self):
        """اختبار مستوى الاتفاق"""
        self.assertEqual(
            self.ensemble._get_agreement_level(0.95),
            "STRONG_AGREEMENT"
        )
        self.assertEqual(
            self.ensemble._get_agreement_level(0.80),
            "MODERATE_AGREEMENT"
        )
        self.assertEqual(
            self.ensemble._get_agreement_level(0.50),
            "WEAK_AGREEMENT"
        )
    
    def test_weights_validation(self):
        """اختبار التحقق من الأوزان"""
        with self.assertRaises(ValueError):
            # أوزان مجموعها > 1
            config = EnsembleConfig(
                lstm_weight=0.5,
                xgb_weight=0.5,
                cnn_weight=0.5
            )
            DESERTASEnsemble(self.lstm, self.xgb, self.cnn, config)
    
    def test_custom_config(self):
        """اختبار تكوين مخصص"""
        config = EnsembleConfig(
            lstm_weight=0.5,
            xgb_weight=0.3,
            cnn_weight=0.2
        )
        
        ensemble = DESERTASEnsemble(
            self.lstm,
            self.xgb,
            self.cnn,
            config
        )
        
        self.assertEqual(ensemble.config.lstm_weight, 0.5)
        self.assertEqual(ensemble.config.xgb_weight, 0.3)
        self.assertEqual(ensemble.config.cnn_weight, 0.2)
    
    def test_prediction_consistency(self):
        """اختبار ثبات التنبؤ"""
        # تنبؤات متعددة يجب أن تكون متسقة
        results = []
        for _ in range(3):
            result = self.ensemble.predict(
                self.lstm_input,
                self.xgb_input,
                self.cnn_input
            )
            results.append(result['ensemble_prediction'])
        
        # النتائج يجب أن تكون متطابقة (نفس المدخلات)
        self.assertEqual(len(set(results)), 1)


if __name__ == '__main__':
    unittest.main()
