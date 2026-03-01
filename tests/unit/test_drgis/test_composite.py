#!/usr/bin/env python3
"""
اختبارات DRGIS Composite Score
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

import unittest
import numpy as np
import tempfile
import json
import yaml
from src.drgis.composite import (
    DRGISCalculator, ParameterWeights, AlertThresholds, StationBackground
)


class TestDRGISCalculator(unittest.TestCase):
    """اختبارات حاسبة DRGIS"""
    
    def setUp(self):
        """إعداد بيئة الاختبار"""
        self.calculator = DRGISCalculator()
        
        # بيانات معاملات نموذجية
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
        """اختبار صحة الأوزان"""
        weights = ParameterWeights()
        self.assertTrue(weights.validate())
        
        # أوزان خاطئة
        weights.delta_phi_th = 0.5
        self.assertFalse(weights.validate())
    
    def test_raw_computation(self):
        """اختبار الحساب الخام"""
        drgis_raw = self.calculator.compute_raw(self.sample_params)
        
        self.assertGreaterEqual(drgis_raw, 0)
        self.assertLessEqual(drgis_raw, 1)
        self.assertAlmostEqual(drgis_raw, 0.47, places=2)
    
    def test_ai_adjustment(self):
        """اختبار تعديل AI"""
        drgis_raw = 0.47
        
        # تعديل بدون تصحيح
        adjusted = self.calculator.apply_ai_adjustment(drgis_raw)
        self.assertNotEqual(adjusted, drgis_raw)
        
        # تعديل مع تصحيح الكراتون
        adjusted_saharan = self.calculator.apply_ai_adjustment(
            drgis_raw, craton='saharan'
        )
        adjusted_arabian = self.calculator.apply_ai_adjustment(
            drgis_raw, craton='arabian'
        )
        self.assertNotEqual(adjusted_saharan, adjusted_arabian)
    
    def test_full_computation(self):
        """اختبار الحساب الكامل"""
        result = self.calculator.compute(self.sample_params)
        
        self.assertIn('drgis_raw', result)
        self.assertIn('drgis_adjusted', result)
        self.assertIn('alert_level', result)
        self.assertIn('contributions', result)
        
        self.assertGreater(result['drgis_adjusted'], 0)
        self.assertLess(result['drgis_adjusted'], 1)
    
    def test_alert_levels(self):
        """اختبار مستويات الإنذار"""
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
                self.assertEqual(level.value, expected)
    
    def test_background_normalization(self):
        """اختبار تطبيع الخلفية"""
        # إنشاء خلفية محطة
        bg = StationBackground(
            station_id="TEST-01",
            craton="saharan"
        )
        
        # إضافة إحصائيات
        bg.delta_phi_th = {'background': 0.2, 'threshold': 0.4}
        bg.rn_pulse = {'background': 1.0, 'threshold': 3.0}
        
        # إضافة للآلة الحاسبة
        self.calculator.backgrounds["TEST-01"] = bg
        
        # حساب مع التطبيع
        result = self.calculator.compute(
            self.sample_params,
            station_id="TEST-01"
        )
        
        self.assertIn('drgis_adjusted', result)
    
    def test_batch_computation(self):
        """اختبار الحساب الجماعي"""
        measurements = [self.sample_params] * 5
        
        results = self.calculator.batch_compute(
            measurements,
            station_id="TEST-01"
        )
        
        self.assertEqual(len(results), 5)
        for result in results:
            self.assertIn('drgis_adjusted', result)
    
    def test_validation_accuracy(self):
        """اختبار دقة التحقق"""
        # بيانات اختبار
        n_samples = 10
        test_data = [self.sample_params] * n_samples
        true_labels = [0.5] * n_samples
        
        metrics = self.calculator.validate_accuracy(test_data, true_labels)
        
        self.assertIn('accuracy', metrics)
        self.assertIn('mae', metrics)
        self.assertIn('rmse', metrics)
        self.assertIn('r2', metrics)
    
    def test_save_load_backgrounds(self):
        """اختبار حفظ وتحميل الخلفيات"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({
                'stations': [
                    {
                        'station_id': 'TEST-01',
                        'craton': 'saharan',
                        'delta_phi_th': {'background': 0.2, 'threshold': 0.4}
                    }
                ]
            }, f)
            temp_file = f.name
        
        # تحميل الخلفيات
        self.calculator.load_backgrounds(temp_file)
        
        self.assertIn('TEST-01', self.calculator.backgrounds)
        
        # تنظيف
        os.unlink(temp_file)


if __name__ == '__main__':
    unittest.main()
