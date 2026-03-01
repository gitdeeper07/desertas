#!/usr/bin/env python3
"""
تشغيل جميع اختبارات DESERTAS
"""

import unittest
import sys
import os
from pathlib import Path


def run_all_tests():
    """تشغيل جميع الاختبارات"""
    print("\n" + "="*70)
    print("🏜️  DESERTAS TEST SUITE")
    print("="*70)
    
    # اكتشاف جميع الاختبارات
    test_loader = unittest.TestLoader()
    test_suite = test_loader.discover(
        start_dir=os.path.dirname(__file__),
        pattern='test_*.py'
    )
    
    # تشغيل الاختبارات
    test_runner = unittest.TextTestRunner(verbosity=2)
    result = test_runner.run(test_suite)
    
    # عرض الملخص
    print("\n" + "="*70)
    print("📊 TEST SUMMARY")
    print("="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    
    if result.wasSuccessful():
        print("\n✅ ALL TESTS PASSED!")
    else:
        print("\n❌ SOME TESTS FAILED")
        sys.exit(1)
    
    return result


def run_hypothesis_tests():
    """تشغيل اختبارات الفرضيات فقط"""
    print("\n" + "="*70)
    print("🔬 DESERTAS HYPOTHESIS TESTS (H1-H8)")
    print("="*70)
    
    from hypothesis.test_hypotheses import TestHypotheses
    
    suite = unittest.TestLoader().loadTestsFromTestCase(TestHypotheses)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result


def run_unit_tests():
    """تشغيل اختبارات الوحدات"""
    print("\n" + "="*70)
    print("🧪 DESERTAS UNIT TESTS")
    print("="*70)
    
    loader = unittest.TestLoader()
    suite = loader.discover(
        start_dir=os.path.join(os.path.dirname(__file__), 'unit'),
        pattern='test_*.py'
    )
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Run DESERTAS tests')
    parser.add_argument('--type', choices=['all', 'unit', 'hypothesis', 'integration'],
                       default='all', help='Type of tests to run')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    
    args = parser.parse_args()
    
    if args.type == 'all':
        result = run_all_tests()
    elif args.type == 'unit':
        result = run_unit_tests()
    elif args.type == 'hypothesis':
        result = run_hypothesis_tests()
    elif args.type == 'integration':
        print("Integration tests not yet implemented")
        sys.exit(0)
    
    sys.exit(0 if result.wasSuccessful() else 1)
