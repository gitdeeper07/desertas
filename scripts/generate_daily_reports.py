#!/usr/bin/env python3
"""
توليد التقارير اليومية وحفظها في المجلد المناسب
"""

import os
import json
from datetime import datetime, timedelta
from pathlib import Path

class DailyReportGenerator:
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent
        self.daily_dir = self.base_dir / 'reports' / 'daily'
        self.json_dir = self.base_dir / 'reports' / 'json'
        self.alerts_dir = self.base_dir / 'reports' / 'alerts'
        
        # إنشاء المجلدات إذا لم تكن موجودة
        self.daily_dir.mkdir(parents=True, exist_ok=True)
        self.json_dir.mkdir(parents=True, exist_ok=True)
        self.alerts_dir.mkdir(parents=True, exist_ok=True)
        
    def generate_daily_report(self, station_id, date=None):
        """توليد تقرير يومي لمحطة محددة"""
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        # بيانات تجريبية للمحطة
        stations_data = {
            'DES-MA-02': {'name': 'Saharan Craton', 'drgis': 0.596, 'alert': 'ALERT', 'lead_time': 58},
            'DES-SA-01': {'name': 'Arabian Shield', 'drgis': 0.412, 'alert': 'WATCH', 'lead_time': 63},
            'DES-CL-03': {'name': 'Atacama-Pampean', 'drgis': 0.338, 'alert': 'WATCH', 'lead_time': 71},
            'DES-AU-06': {'name': 'Yilgarn Craton', 'drgis': 0.284, 'alert': 'BACKGROUND', 'lead_time': 38},
            'DES-KA-04': {'name': 'Kaapvaal Craton', 'drgis': 0.445, 'alert': 'WATCH', 'lead_time': 44},
            'DES-TA-02': {'name': 'Tarim Basin', 'drgis': 0.512, 'alert': 'ALERT', 'lead_time': 52},
            'DES-SC-01': {'name': 'Scandinavian Shield', 'drgis': 0.623, 'alert': 'EMERGENCY', 'lead_time': 29}
        }
        
        if station_id not in stations_data:
            print(f"⚠️ محطة غير معروفة: {station_id}")
            return None
        
        data = stations_data[station_id]
        
        # إنشاء التقرير النصي
        txt_content = self._generate_txt_report(station_id, data, date)
        txt_file = self.daily_dir / f"{station_id}_{date}.txt"
        with open(txt_file, 'w') as f:
            f.write(txt_content)
        
        # إنشاء التقرير بصيغة Markdown
        md_content = self._generate_md_report(station_id, data, date)
        md_file = self.daily_dir / f"{station_id}_{date}.md"
        with open(md_file, 'w') as f:
            f.write(md_content)
        
        # إنشاء ملف JSON
        json_content = self._generate_json_report(station_id, data, date)
        json_file = self.json_dir / f"{station_id}_{date}.json"
        with open(json_file, 'w') as f:
            json.dump(json_content, f, indent=2)
        
        print(f"✅ Generated reports for {station_id} in {self.daily_dir}/")
        return txt_file
    
    def _generate_txt_report(self, station_id, data, date):
        """توليد تقرير نصي"""
        lines = []
        lines.append("=" * 60)
        lines.append(f"DESERTAS DAILY REPORT - {date}")
        lines.append("=" * 60)
        lines.append(f"Station: {station_id} ({data['name']})")
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("-" * 60)
        lines.append(f"DRGIS Score: {data['drgis']}")
        
        alert_icon = "🔴" if data['alert'] == 'CRITICAL' else "🟠" if data['alert'] == 'EMERGENCY' else "🟡" if data['alert'] == 'ALERT' else "🟢" if data['alert'] == 'WATCH' else "⚪"
        lines.append(f"Alert Level: {alert_icon} {data['alert']}")
        lines.append(f"Estimated Lead Time: {data['lead_time']} days")
        lines.append("-" * 60)
        lines.append("PARAMETERS:")
        lines.append(f"  ΔΦ_th: 0.265")
        lines.append(f"  Ψ_crack: 0.457")
        lines.append(f"  Rn_pulse: 3.84")
        lines.append(f"  Ω_arid: 0.848")
        lines.append(f"  Γ_geo: 2.23")
        lines.append(f"  He_ratio: 1.92")
        lines.append(f"  β_dust: 0.294")
        lines.append(f"  S_yield: 0.723")
        lines.append("-" * 60)
        lines.append("RECOMMENDATIONS:")
        if data['alert'] == 'CRITICAL':
            lines.append("  • IMMEDIATE EVACUATION REQUIRED")
        elif data['alert'] == 'EMERGENCY':
            lines.append("  • Activate emergency protocols")
        elif data['alert'] == 'ALERT':
            lines.append("  • Enhanced monitoring required")
        elif data['alert'] == 'WATCH':
            lines.append("  • Schedule maintenance")
        else:
            lines.append("  • Continue routine monitoring")
        lines.append("=" * 60)
        return "\n".join(lines)
    
    def _generate_md_report(self, station_id, data, date):
        """توليد تقرير Markdown"""
        lines = []
        lines.append(f"# 🏜️ DESERTAS Daily Report - {station_id}")
        lines.append(f"\n**Date:** {date}")
        lines.append(f"**Craton:** {data['name']}")
        lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("\n## 📊 Summary")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| DRGIS Score | {data['drgis']} |")
        lines.append(f"| Alert Level | {data['alert']} |")
        lines.append(f"| Lead Time | {data['lead_time']} days |")
        lines.append("\n## 📈 Parameters")
        lines.append("| Parameter | Value | Unit |")
        lines.append("|-----------|-------|------|")
        lines.append("| ΔΦ_th | 0.265 | cm³·cm⁻²·cycle⁻¹ |")
        lines.append("| Ψ_crack | 0.457 | normalized |")
        lines.append("| Rn_pulse | 3.84 | σ |")
        lines.append("| Ω_arid | 0.848 | normalized |")
        lines.append("| Γ_geo | 2.23 | m/hr |")
        lines.append("| He_ratio | 1.92 | R/Ra |")
        lines.append("| β_dust | 0.294 | fraction |")
        lines.append("| S_yield | 0.723 | normalized |")
        return "\n".join(lines)
    
    def _generate_json_report(self, station_id, data, date):
        """توليد بيانات JSON"""
        return {
            "metadata": {
                "station": station_id,
                "craton": data['name'],
                "date": date,
                "generated": datetime.now().isoformat()
            },
            "drgis": {
                "score": data['drgis'],
                "alert_level": data['alert'],
                "lead_time_days": data['lead_time']
            },
            "parameters": {
                "ΔΦ_th": 0.265,
                "Ψ_crack": 0.457,
                "Rn_pulse": 3.84,
                "Ω_arid": 0.848,
                "Γ_geo": 2.23,
                "He_ratio": 1.92,
                "β_dust": 0.294,
                "S_yield": 0.723
            }
        }
    
    def generate_all_daily_reports(self, date=None):
        """توليد تقارير لجميع المحطات"""
        stations = ['DES-MA-02', 'DES-SA-01', 'DES-CL-03', 'DES-AU-06', 
                   'DES-KA-04', 'DES-TA-02', 'DES-SC-01']
        
        print(f"\n📊 Generating daily reports for {len(stations)} stations...")
        for station in stations:
            self.generate_daily_report(station, date)
        
        # إنشاء تقرير ملخص
        self.generate_summary_report(date)
    
    def generate_summary_report(self, date=None):
        """توليد تقرير ملخص لجميع المحطات"""
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        stations_data = {
            'DES-MA-02': {'name': 'Saharan Craton', 'drgis': 0.596, 'alert': 'ALERT'},
            'DES-SA-01': {'name': 'Arabian Shield', 'drgis': 0.412, 'alert': 'WATCH'},
            'DES-CL-03': {'name': 'Atacama-Pampean', 'drgis': 0.338, 'alert': 'WATCH'},
            'DES-AU-06': {'name': 'Yilgarn Craton', 'drgis': 0.284, 'alert': 'BACKGROUND'},
            'DES-KA-04': {'name': 'Kaapvaal Craton', 'drgis': 0.445, 'alert': 'WATCH'},
            'DES-TA-02': {'name': 'Tarim Basin', 'drgis': 0.512, 'alert': 'ALERT'},
            'DES-SC-01': {'name': 'Scandinavian Shield', 'drgis': 0.623, 'alert': 'EMERGENCY'}
        }
        
        lines = []
        lines.append(f"# 📊 DESERTAS Daily Summary - {date}")
        lines.append(f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("\n## Station Status")
        lines.append("\n| Station | Craton | DRGIS | Alert Level |")
        lines.append("|---------|--------|-------|-------------|")
        
        for station, data in stations_data.items():
            lines.append(f"| {station} | {data['name']} | {data['drgis']} | {data['alert']} |")
        
        summary_file = self.daily_dir / f"SUMMARY_{date}.md"
        with open(summary_file, 'w') as f:
            f.write("\n".join(lines))
        
        print(f"✅ Summary report created: {summary_file}")

def main():
    generator = DailyReportGenerator()
    
    # توليد تقارير لليوم
    today = datetime.now().strftime('%Y-%m-%d')
    generator.generate_all_daily_reports(today)
    
    # عرض إحصائيات المجلدات
    print("\n📁 Directory Structure:")
    print(f"   Daily reports: {generator.daily_dir}")
    print(f"   JSON reports: {generator.json_dir}")
    print(f"   Alerts: {generator.alerts_dir}")
    
    # عرض الملفات المُنشأة
    print("\n📄 Generated files:")
    for file in sorted(generator.daily_dir.glob("*.txt"))[:3]:
        print(f"   • {file.name}")
    print("   ...")

if __name__ == '__main__':
    main()
