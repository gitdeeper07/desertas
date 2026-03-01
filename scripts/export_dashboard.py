#!/usr/bin/env python3
"""
تصدير بيانات لوحة التحكم
"""

import argparse
import json
import sys
from datetime import datetime

def export_dashboard(output_file):
    """تصدير البيانات للوحة التحكم"""
    print(f"\n📊 تصدير بيانات لوحة التحكم إلى {output_file}")
    
    # بيانات تجريبية
    data = {
        'timestamp': datetime.now().isoformat(),
        'stations': [
            {'id': 'DES-MA-02', 'drgis': 0.596, 'alert': 'ALERT'},
            {'id': 'DES-SA-01', 'drgis': 0.412, 'alert': 'WATCH'},
            {'id': 'DES-CL-03', 'drgis': 0.338, 'alert': 'WATCH'},
        ],
        'summary': {
            'total_stations': 36,
            'active_alerts': 12,
            'mean_drgis': 0.44
        }
    }
    
    # حفظ الملف
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"✅ تم التصدير بنجاح إلى {output_file}")
    return True

def main():
    parser = argparse.ArgumentParser(description='تصدير بيانات لوحة التحكم')
    parser.add_argument('--output', default='dashboard/data.json', help='ملف الإخراج')
    
    args = parser.parse_args()
    export_dashboard(args.output)

if __name__ == '__main__':
    main()
