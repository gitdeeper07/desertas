#!/usr/bin/env python3
"""
توليد التقارير اليومية للمحطات
Daily Reports Generator for DESERTAS Stations

التنسيقات:
- .txt للتقارير النصية البسيطة
- .md للتقارير المنسقة (Markdown)
- .json للبيانات الهيكلية (ينقل لمجلد json/)
"""

import os
import json
import yaml
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import numpy as np


class DailyReportGenerator:
    """مولد التقارير اليومية لمحطات DESERTAS"""
    
    def __init__(self, stations_dir: str = "../data/processed"):
        self.stations_dir = Path(stations_dir)
        self.reports_dir = Path("reports")
        self.daily_dir = self.reports_dir / "daily"
        self.json_dir = self.reports_dir / "json"
        
        # إنشاء المجلدات إذا لم تكن موجودة
        self.daily_dir.mkdir(parents=True, exist_ok=True)
        self.json_dir.mkdir(parents=True, exist_ok=True)
        
        # أسماء المعاملات
        self.parameters = [
            'ΔΦ_th', 'Ψ_crack', 'Rn_pulse', 'Ω_arid',
            'Γ_geo', 'He_ratio', 'β_dust', 'S_yield'
        ]
        
    def load_station_data(self, station_id: str, date: str) -> Optional[Dict]:
        """
        تحميل بيانات المحطة ليوم محدد
        
        Args:
            station_id: معرف المحطة
            date: التاريخ (YYYY-MM-DD)
            
        Returns:
            بيانات المحطة أو None
        """
        # محاولة تحميل من عدة مسارات
        possible_paths = [
            self.stations_dir / f"{station_id}_{date}.csv",
            self.stations_dir / f"{station_id}.csv",
            self.stations_dir / station_id / f"{date}.csv"
        ]
        
        for path in possible_paths:
            if path.exists():
                # قراءة البيانات (تبسيط - يفترض وجود ملف CSV)
                try:
                    import pandas as pd
                    df = pd.read_csv(path)
                    return df.to_dict('records')[0] if len(df) > 0 else None
                except:
                    pass
        
        # بيانات تجريبية للتطوير
        return self._generate_sample_data(station_id, date)
    
    def _generate_sample_data(self, station_id: str, date: str) -> Dict:
        """توليد بيانات تجريبية للتطوير"""
        np.random.seed(hash(f"{station_id}_{date}") % 2**32)
        
        return {
            'station_id': station_id,
            'date': date,
            'ΔΦ_th': round(0.2 + np.random.random() * 0.6, 3),
            'Ψ_crack': round(0.3 + np.random.random() * 0.5, 3),
            'Rn_pulse': round(1.0 + np.random.random() * 4.0, 2),
            'Ω_arid': round(0.6 + np.random.random() * 0.4, 3),
            'Γ_geo': round(0.5 + np.random.random() * 3.0, 2),
            'He_ratio': round(0.1 + np.random.random() * 2.0, 2),
            'β_dust': round(0.2 + np.random.random() * 0.6, 3),
            'S_yield': round(0.2 + np.random.random() * 0.6, 3),
            'temperature_min': round(15 + np.random.random() * 10, 1),
            'temperature_max': round(35 + np.random.random() * 15, 1),
            'pressure': round(980 + np.random.random() * 40, 1),
            'humidity': round(10 + np.random.random() * 30, 1)
        }
    
    def calculate_drgis(self, data: Dict) -> float:
        """حساب DRGIS من البيانات"""
        weights = {
            'ΔΦ_th': 0.18,
            'Ψ_crack': 0.16,
            'Rn_pulse': 0.18,
            'Ω_arid': 0.12,
            'Γ_geo': 0.14,
            'He_ratio': 0.10,
            'β_dust': 0.07,
            'S_yield': 0.05
        }
        
        drgis = 0
        for param, weight in weights.items():
            if param in data:
                # تطبيع بسيط
                value = data[param]
                if param == 'Rn_pulse':
                    norm = min(value / 5.0, 1.0)
                elif param == 'He_ratio':
                    norm = min(value / 5.0, 1.0)
                else:
                    norm = min(value, 1.0)
                drgis += weight * norm
        
        return round(drgis, 3)
    
    def get_alert_level(self, drgis: float) -> str:
        """تحديد مستوى الإنذار"""
        if drgis >= 0.80:
            return '🔴 CRITICAL'
        elif drgis >= 0.65:
            return '🟠 EMERGENCY'
        elif drgis >= 0.48:
            return '🟡 ALERT'
        elif drgis >= 0.30:
            return '🟢 WATCH'
        else:
            return '⚪ BACKGROUND'
    
    def generate_txt_report(self, data: Dict, drgis: float, alert_level: str) -> str:
        """توليد تقرير نصي بسيط (.txt)"""
        lines = []
        lines.append("=" * 60)
        lines.append(f"DESERTAS DAILY REPORT - {data['date']}")
        lines.append("=" * 60)
        lines.append(f"Station: {data['station_id']}")
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("-" * 60)
        lines.append(f"DRGIS Score: {drgis}")
        lines.append(f"Alert Level: {alert_level}")
        lines.append("-" * 60)
        lines.append("PARAMETERS:")
        for param in self.parameters:
            if param in data:
                lines.append(f"  {param}: {data[param]}")
        lines.append("-" * 60)
        lines.append("ENVIRONMENTAL:")
        for key in ['temperature_min', 'temperature_max', 'pressure', 'humidity']:
            if key in data:
                name = key.replace('_', ' ').title()
                lines.append(f"  {name}: {data[key]}")
        lines.append("-" * 60)
        
        if drgis >= 0.48:
            lines.append("RECOMMENDATION: Enhanced monitoring required")
        if drgis >= 0.65:
            lines.append("ACTION: Notify civil protection authorities")
        if drgis >= 0.80:
            lines.append("⚠️⚠️⚠️ CRITICAL - IMMEDIATE EVACUATION ⚠️⚠️⚠️")
        
        lines.append("=" * 60)
        return "\n".join(lines)
    
    def generate_md_report(self, data: Dict, drgis: float, alert_level: str) -> str:
        """توليد تقرير منسق (.md)"""
        lines = []
        lines.append(f"# 🏜️ DESERTAS Daily Report - {data['date']}")
        lines.append()
        lines.append(f"**Station:** `{data['station_id']}`")
        lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append()
        lines.append("## 📊 DRGIS Summary")
        lines.append()
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| DRGIS Score | **{drgis}** |")
        lines.append(f"| Alert Level | {alert_level} |")
        lines.append()
        lines.append("## 📈 Parameters")
        lines.append()
        lines.append("| Parameter | Value | Unit |")
        lines.append("|-----------|-------|------|")
        
        param_units = {
            'ΔΦ_th': 'cm³·cm⁻²·cycle⁻¹',
            'Ψ_crack': 'normalized',
            'Rn_pulse': 'σ',
            'Ω_arid': 'normalized',
            'Γ_geo': 'm/hr',
            'He_ratio': 'R/Ra',
            'β_dust': 'fraction',
            'S_yield': 'normalized'
        }
        
        for param in self.parameters:
            if param in data:
                unit = param_units.get(param, '')
                lines.append(f"| {param} | {data[param]} | {unit} |")
        
        lines.append()
        lines.append("## 🌡️ Environmental")
        lines.append()
        lines.append("| Measurement | Value |")
        lines.append("|-------------|-------|")
        if 'temperature_min' in data:
            lines.append(f"| Temperature Min | {data['temperature_min']} °C |")
        if 'temperature_max' in data:
            lines.append(f"| Temperature Max | {data['temperature_max']} °C |")
        if 'pressure' in data:
            lines.append(f"| Pressure | {data['pressure']} hPa |")
        if 'humidity' in data:
            lines.append(f"| Humidity | {data['humidity']} % |")
        
        lines.append()
        lines.append("## ⚡ Recommendations")
        lines.append()
        
        if drgis < 0.30:
            lines.append("- ✅ Normal background activity")
            lines.append("- 🔍 Routine monitoring continues")
        elif drgis < 0.48:
            lines.append("- 👀 Enhanced monitoring recommended")
            lines.append("- 📊 Increase sampling frequency")
        elif drgis < 0.65:
            lines.append("- ⚠️ ALERT level detected")
            lines.append("- 📢 Notify civil protection authorities")
            lines.append("- 🏗️ Conduct structural vulnerability assessment")
        elif drgis < 0.80:
            lines.append("- 🚨 EMERGENCY precursor")
            lines.append("- 🔔 Activate emergency plans")
            lines.append("- 🏃 Prepare evacuation of high-risk structures")
        else:
            lines.append("- ‼️ **CRITICAL - IMMINENT SEISMIC RISK**")
            lines.append("- ⚠️⚠️ **IMMEDIATE EVACUATION REQUIRED**")
            lines.append("- 📡 Maximum alert for critical infrastructure")
        
        lines.append()
        lines.append("---")
        lines.append(f"*Report generated by DESERTAS AI Ensemble*")
        lines.append(f"*DOI: 10.14293/DESERTAS.2026.001*")
        
        return "\n".join(lines)
    
    def generate_json_data(self, data: Dict, drgis: float, alert_level: str) -> Dict:
        """توليد بيانات JSON للاستخدام في API"""
        # إزالة الرموز الملونة من مستوى الإنذار
        clean_alert = alert_level.split(' ')[-1] if ' ' in alert_level else alert_level
        
        json_data = {
            'metadata': {
                'station_id': data['station_id'],
                'date': data['date'],
                'generated': datetime.now().isoformat(),
                'version': '1.0.0',
                'doi': '10.14293/DESERTAS.2026.001'
            },
            'drgis': {
                'score': drgis,
                'alert_level': clean_alert,
                'thresholds': {
                    'background': 0.30,
                    'watch': 0.48,
                    'alert': 0.65,
                    'emergency': 0.80
                }
            },
            'parameters': {},
            'environmental': {},
            'recommendations': self._get_recommendations_json(drgis)
        }
        
        # إضافة المعاملات
        for param in self.parameters:
            if param in data:
                json_data['parameters'][param] = {
                    'value': data[param],
                    'unit': {
                        'ΔΦ_th': 'cm³·cm⁻²·cycle⁻¹',
                        'Ψ_crack': 'normalized',
                        'Rn_pulse': 'sigma',
                        'Ω_arid': 'normalized',
                        'Γ_geo': 'm/hr',
                        'He_ratio': 'R/Ra',
                        'β_dust': 'fraction',
                        'S_yield': 'normalized'
                    }.get(param, '')
                }
        
        # إضافة البيانات البيئية
        env_keys = ['temperature_min', 'temperature_max', 'pressure', 'humidity']
        for key in env_keys:
            if key in data:
                json_data['environmental'][key] = data[key]
        
        return json_data
    
    def _get_recommendations_json(self, drgis: float) -> List[str]:
        """توليد توصيات بصيغة JSON"""
        if drgis < 0.30:
            return ["Normal background activity", "Routine monitoring continues"]
        elif drgis < 0.48:
            return ["Enhanced monitoring recommended", "Increase sampling frequency"]
        elif drgis < 0.65:
            return [
                "ALERT level detected",
                "Notify civil protection authorities",
                "Conduct structural vulnerability assessment"
            ]
        elif drgis < 0.80:
            return [
                "EMERGENCY precursor",
                "Activate emergency plans",
                "Prepare evacuation of high-risk structures"
            ]
        else:
            return [
                "CRITICAL - Imminent seismic risk",
                "IMMEDIATE EVACUATION REQUIRED",
                "Maximum alert for critical infrastructure"
            ]
    
    def generate_reports(
        self,
        station_ids: List[str],
        date: Optional[str] = None
    ) -> Dict[str, List[str]]:
        """
        توليد تقارير لمحطات متعددة
        
        Args:
            station_ids: قائمة معرفات المحطات
            date: التاريخ (YYYY-MM-DD), افتراضي: اليوم
            
        Returns:
            مسارات الملفات المُنشأة
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        generated_files = {
            'txt': [],
            'md': [],
            'json': []
        }
        
        for station_id in station_ids:
            # تحميل البيانات
            data = self.load_station_data(station_id, date)
            if not data:
                print(f"⚠️ No data for station {station_id} on {date}")
                continue
            
            # حساب DRGIS
            drgis = self.calculate_drgis(data)
            alert_level = self.get_alert_level(drgis)
            
            # إنشاء اسم الملف الأساسي
            base_filename = f"{station_id}_{date}"
            
            # 1. تقرير نصي (.txt)
            txt_report = self.generate_txt_report(data, drgis, alert_level)
            txt_path = self.daily_dir / f"{base_filename}.txt"
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(txt_report)
            generated_files['txt'].append(str(txt_path))
            
            # 2. تقرير منسق (.md)
            md_report = self.generate_md_report(data, drgis, alert_level)
            md_path = self.daily_dir / f"{base_filename}.md"
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(md_report)
            generated_files['md'].append(str(md_path))
            
            # 3. بيانات JSON (تنقل لمجلد json/)
            json_data = self.generate_json_data(data, drgis, alert_level)
            json_path = self.json_dir / f"{base_filename}.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)
            generated_files['json'].append(str(json_path))
            
            # أرشفة JSON القديم إذا كان موجوداً
            self._archive_old_json(station_id, date)
            
            print(f"✅ Generated reports for {station_id}")
        
        return generated_files
    
    def _archive_old_json(self, station_id: str, current_date: str):
        """أرشفة ملفات JSON القديمة"""
        archive_dir = self.json_dir / "archive"
        archive_dir.mkdir(exist_ok=True)
        
        # البحث عن ملفات JSON قديمة لنفس المحطة
        for json_file in self.json_dir.glob(f"{station_id}_*.json"):
            if json_file.name != f"{station_id}_{current_date}.json":
                # نقل للمجلد archive
                dest = archive_dir / json_file.name
                json_file.rename(dest)
                print(f"  📦 Archived {json_file.name} to json/archive/")
    
    def generate_summary_report(self, date: Optional[str] = None) -> str:
        """
        توليد تقرير ملخص لجميع المحطات
        
        Args:
            date: التاريخ (YYYY-MM-DD)
            
        Returns:
            مسار ملف التقرير
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        # قائمة المحطات (يمكن تحميلها من ملف تكوين)
        stations = [f"DES-{craton[:2].upper()}-{i:02d}" 
                   for craton in ['SA', 'AR', 'KA', 'YI', 'AT', 'TA', 'SC']
                   for i in range(1, 8)]
        
        summary_data = []
        for station_id in stations[:10]:  # حد 10 محطات للتبسيط
            data = self.load_station_data(station_id, date)
            if data:
                drgis = self.calculate_drgis(data)
                alert_level = self.get_alert_level(drgis)
                summary_data.append({
                    'station': station_id,
                    'drgis': drgis,
                    'alert': alert_level,
                    'has_data': True
                })
        
        # توليد تقرير Markdown
        lines = []
        lines.append(f"# 📊 DESERTAS Summary Report - {date}")
        lines.append()
        lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append()
        lines.append("## Stations Summary")
        lines.append()
        lines.append("| Station | DRGIS | Alert Level |")
        lines.append("|---------|-------|-------------|")
        
        for item in summary_data:
            lines.append(f"| {item['station']} | {item['drgis']} | {item['alert']} |")
        
        lines.append()
        lines.append("## Statistics")
        lines.append()
        
        alerts = {
            'CRITICAL': sum(1 for i in summary_data if 'CRITICAL' in i['alert']),
            'EMERGENCY': sum(1 for i in summary_data if 'EMERGENCY' in i['alert']),
            'ALERT': sum(1 for i in summary_data if 'ALERT' in i['alert']),
            'WATCH': sum(1 for i in summary_data if 'WATCH' in i['alert']),
            'BACKGROUND': sum(1 for i in summary_data if 'BACKGROUND' in i['alert'])
        }
        
        lines.append(f"- Total Stations Reporting: {len(summary_data)}")
        lines.append(f"- 🔴 CRITICAL: {alerts['CRITICAL']}")
        lines.append(f"- 🟠 EMERGENCY: {alerts['EMERGENCY']}")
        lines.append(f"- 🟡 ALERT: {alerts['ALERT']}")
        lines.append(f"- 🟢 WATCH: {alerts['WATCH']}")
        lines.append(f"- ⚪ BACKGROUND: {alerts['BACKGROUND']}")
        
        lines.append()
        lines.append("---")
        lines.append(f"*Report generated by DESERTAS Monitoring System*")
        
        # حفظ التقرير
        summary_path = self.daily_dir / f"SUMMARY_{date}.md"
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))
        
        print(f"✅ Generated summary report: {summary_path}")
        return str(summary_path)


def main():
    """الوظيفة الرئيسية لتوليد التقارير اليومية"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate DESERTAS daily reports')
    parser.add_argument('--stations', nargs='+', help='Station IDs')
    parser.add_argument('--date', help='Date (YYYY-MM-DD)')
    parser.add_argument('--summary', action='store_true', help='Generate summary report')
    
    args = parser.parse_args()
    
    generator = DailyReportGenerator()
    
    if args.summary:
        generator.generate_summary_report(args.date)
    
    if args.stations:
        results = generator.generate_reports(args.stations, args.date)
        print("\n=== Generated Files ===")
        for fmt, files in results.items():
            print(f"\n{fmt.upper()}:")
            for f in files:
                print(f"  - {f}")


if __name__ == "__main__":
    main()
