# 📊 DESERTAS Reports

## Directory Structure

```

reports/
├── daily/           # Daily reports (.txt, .md)
├── weekly/          # Weekly summary reports (.md)
├── monthly/         # Monthly analysis reports (.md)
├── alerts/          # Alert reports (.txt, .md)
├── json/            # JSON data for API
│   └── archive/     # Archived JSON files (>30 days)
├── generate_daily_report.py
├── generate_alert_report.py
├── reports_config.yaml
└── README.md

```

## Report Formats

### 📄 Text Reports (.txt)
- Simple, readable format
- Suitable for quick viewing
- Includes all essential data

### 📝 Markdown Reports (.md)
- Formatted with tables and sections
- Suitable for documentation
- Can be converted to HTML/PDF

### 🔧 JSON Data (.json)
- Structured data for API
- Used by dashboard
- Archived after 30 days

## Daily Reports

Generated at 23:59 each day:
- `{STATION}_{YYYY-MM-DD}.txt` - Plain text report
- `{STATION}_{YYYY-MM-DD}.md` - Formatted report
- `{STATION}_{YYYY-MM-DD}.json` - JSON data

## Alert Reports

Generated immediately when alert triggered:
- `ALERT_{STATION}_{YYYYMMDD_HHMMSS}.txt`
- `ALERT_{STATION}_{YYYYMMDD_HHMMSS}.md`
- `ALERT_{STATION}_{YYYYMMDD_HHMMSS}.json`

## Usage

Generate daily reports:
```bash
python reports/generate_daily_report.py --stations DES-MA-02 DES-SA-01
```

Generate summary report:

```bash
python reports/generate_daily_report.py --summary
```

Generate alert report:

```bash
python reports/generate_alert_report.py
```

JSON Archive

JSON files older than 30 days are automatically moved to:
reports/json/archive/

This keeps the main JSON folder clean for API access.

Report Contents

Each report includes:

· Station ID and date
· DRGIS score and alert level
· All 8 parameter values
· Environmental data (T, P, RH)
· Recommendations
· Timestamp and version

DOI

All reports reference:
10.14293/DESERTAS.2026.001

---

🏜️ The desert breathes. DESERTAS decodes.
