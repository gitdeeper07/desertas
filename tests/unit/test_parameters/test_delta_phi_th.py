#!/usr/bin/env python3
"""
اختبارات معامل ΔΦ_th - Diurnal Thermal Flux
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

import unittest
import numpy as np
from src.drgis.parameters.delta_phi_th import (
    DiurnalThermalFlux, ThermalFluxConfig, create_delta_phi_th
)


class TestDeltaPhiTh(unittest.TestCase):
    """اختبارات معامل التدفق الحراري اليومي"""
    
    def setUp(self):
        """إعداد بيئة الاختبار"""
        self.config = ThermalFluxConfig(
            station_id="TEST-01",
            lithology="granite",
            alpha_rock=2.4e-5,
            fracture_pore_volume=0.5,
            elevation_m=500,
            calibration_date="2026-01-01"
        )
        self.calculator = DiurnalThermalFlux(self.config)
    
    def test_initialization(self):
        """اختبار تهيئة المعامل"""
        self.assertEqual(self.calculator.config.station_id, "TEST-01")
        self.assertEqual(self.calculator.config.lithology, "granite")
        self.assertEqual(self.calculator.config.alpha_rock, 2.4e-5)
    
    def test_invalid_lithology(self):
        """اختبار خطأ في نوع الصخر"""
        with self.assertRaises(ValueError):
            config = ThermalFluxConfig(
                station_id="TEST-02",
                lithology="invalid_rock",
                alpha_rock=2.4e-5,
                fracture_pore_volume=0.5,
                elevation_m=500,
                calibration_date="2026-01-01"
            )
            DiurnalThermalFlux(config)
    
    def test_compute_normal(self):
        """اختبار الحساب العادي"""
        result = self.calculator.compute(
            T_min=20.0,
            T_max=40.0,
            P_atm=101325
        )
        
        self.assertIn('delta_phi_th', result)
        self.assertIn('classification', result)
        self.assertGreater(result['delta_phi_th'], 0)
        self.assertLess(result['delta_phi_th'], 1)
    
    def test_compute_extreme_range(self):
        """اختبار نطاق حراري شديد"""
        result = self.calculator.compute(
            T_min=0.0,
            T_max=50.0,
            P_atm=101325
        )
        
        self.assertGreater(result['delta_T'], 40)
        self.assertGreater(result['delta_phi_th'], 0.1)
    
    def test_classification(self):
        """اختبار تصنيف القيم"""
        test_cases = [
            (0.15, 'BACKGROUND'),
            (0.25, 'WATCH'),
            (0.45, 'ALERT'),
            (0.70, 'EMERGENCY'),
            (0.85, 'CRITICAL')
        ]
        
        for value, expected in test_cases:
            with self.subTest(value=value):
                classification = self.calculator._classify(value)
                self.assertEqual(classification, expected)
    
    def test_factory_function(self):
        """اختبار دالة المصنع"""
        calculator = create_delta_phi_th(
            station_id="TEST-03",
            lithology="sandstone",
            fracture_pore_volume=0.3
        )
        
        self.assertEqual(calculator.config.lithology, "sandstone")
        self.assertEqual(calculator.config.alpha_rock, 3.1e-5)


if __name__ == '__main__':
    unittest.main()
