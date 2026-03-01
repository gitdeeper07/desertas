#!/usr/bin/env python3
"""
تحليل نتائج DESERTAS وإحصائياتها
"""

import json
import os
from datetime import datetime
from pathlib import Path

def analyze_results():
    """تحليل نتائج التشغيل"""
    print("\n📊 تحليل نتائج DESERTAS")
    print("=" * 50)
    
    # قراءة آخر بيانات لوحة التحكم
    dashboard_files = list(Path('dashboard').glob('data_*.json'))
    if dashboard_files:
        latest = max(dashboard_files, key=os.path.getctime)
        with open(latest, 'r') as f:
            data = json.load(f)
        
        print(f"\n📁 آخر ملف: {latest}")
        print(f"⏰ وقت التشغيل: {data.get('timestamp', 'N/A')}")
        print(f"\n📈 إحصائيات:")
        print(f"   - إجمالي المحطات: {data['summary']['total_stations']}")
        print(f"   - الإنذارات النشطة: {data['summary']['active_alerts']}")
        print(f"   - متوسط DRGIS: {data['summary']['mean_drgis']}")
        
        print(f"\n🏭 حالة المحطات:")
        for station in data['stations']:
            alert_icon = "🔴" if station['alert'] == 'ALERT' else "🟡" if station['alert'] == 'WATCH' else "🟢"
            print(f"   {alert_icon} {station['id']}: DRGIS={station['drgis']} ({station['alert']})")
    
    # قراءة تقارير الإنذارات
    alert_dirs = ['reports/alerts/watch', 'reports/alerts/alert', 'reports/alerts/emergency']
    print(f"\n🚨 تقارير الإنذارات:")
    for alert_dir in alert_dirs:
        if os.path.exists(alert_dir):
            n_files = len(list(Path(alert_dir).glob('*.txt')))
            print(f"   - {alert_dir.split('/')[-1].upper()}: {n_files} تقرير")

if __name__ == '__main__':
    analyze_results()
