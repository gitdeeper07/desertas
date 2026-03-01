#!/usr/bin/env python3
"""
تشغيل جميع مراحل معالجة بيانات DESERTAS تلقائياً
"""

import subprocess
import sys
from datetime import datetime, timedelta
import os

def run_pipeline():
    """تشغيل جميع السكربتات بالتسلسل"""
    print("=" * 60)
    print("🚀 DESERTAS PIPELINE - التشغيل الآلي")
    print("=" * 60)
    
    # تاريخ اليوم والأمس
    today = datetime.now().strftime('%Y-%m-%d')
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    # قائمة المحطات
    stations = ['DES-MA-02', 'DES-SA-01', 'DES-CL-03', 'DES-AU-06', 'DES-KA-04', 'DES-TA-02', 'DES-SC-01']
    
    # 1️⃣ استيراد البيانات
    print(f"\n📥 1️⃣ استيراد بيانات المحطات ليوم {yesterday}")
    for station in stations[:3]:  # أول 3 محطات للاختبار
        cmd = f"python scripts/ingest_station_data.py --station {station} --start-date {yesterday} --end-date {today}"
        print(f"   تشغيل: {cmd}")
        subprocess.run(cmd, shell=True)
    
    # 2️⃣ تشغيل DRGIS
    print(f"\n⚙️ 2️⃣ تشغيل حسابات DRGIS")
    subprocess.run("python scripts/run_drgis_batch.py --config configs/drgis_weights.yaml", shell=True)
    
    # 3️⃣ توليد الإنذارات
    print(f"\n🚨 3️⃣ توليد الإنذارات")
    subprocess.run("python scripts/generate_alerts.py --threshold ALERT --output reports/alerts/daily/", shell=True)
    
    # 4️⃣ تصدير البيانات
    print(f"\n📊 4️⃣ تصدير بيانات لوحة التحكم")
    subprocess.run(f"python scripts/export_dashboard.py --output dashboard/data_{today}.json", shell=True)
    
    print("\n" + "=" * 60)
    print("✅ PIPELINE COMPLETED SUCCESSFULLY")
    print("=" * 60)

if __name__ == '__main__':
    run_pipeline()
