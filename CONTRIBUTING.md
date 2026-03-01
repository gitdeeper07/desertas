# 🏜️ CONTRIBUTING TO DESERTAS

First off, thank you for considering contributing to DESERTAS! We welcome contributions from geochemists, geophysicists, seismologists, data scientists, software engineers, Indigenous knowledge holders, and anyone passionate about understanding desert gas emissions and seismic precursors.

---

## Code of Conduct

This project adheres to a [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

---

## Types of Contributions

### 🧪 Scientific Contributions
- New station data and DRGU recordings
- Validation studies in unrepresented cratons
- Parameter refinement suggestions
- Hypothesis testing and experimental design

### 💻 Code Contributions
- DRGIS calculation engine improvements
- AI ensemble architecture enhancements
- Signal processing algorithms for Rn_pulse
- Fracture mechanics modeling (Ψ_crack)
- Dashboard and visualization tools

### 📊 Data Contributions
- Radon time series (Rn_pulse)
- Helium isotope ratios (He_ratio)
- Thermal flux recordings (ΔΦ_th)
- Dust aerosol measurements (β_dust)
- Seismic event catalogs

### 🌍 Indigenous Knowledge
- Traditional rock-breath observations
- Seismic precursor indicators
- Gas venting location knowledge

---

## Getting Started

### Prerequisites
- **Python 3.8–3.11**
- **Git**
- **Basic knowledge of geochemistry or geophysics**

### Setup Development Environment

```bash
# Fork the repository, then clone
git clone https://gitlab.com/YOUR_USERNAME/desertas.git
cd desertas

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install development dependencies
pip install -e ".[dev]"
pre-commit install
```

Verify Setup

```bash
# Run basic validation
python scripts/validate_environment.py

# Run tests
pytest tests/unit/ -v

# Check parameter correlations
python scripts/check_correlation.py
```

---

Development Workflow

1. Create an issue describing your proposed changes
2. Fork and branch:
   ```bash
   git checkout -b feature/your-feature-name
   git checkout -b fix/issue-description
   git checkout -b station/new-location-name
   ```
3. Make changes following our standards
4. Write/update tests
5. Run tests locally
6. Commit with clear messages
7. Push to your fork
8. Open a Merge Request

---

Coding Standards

Python

· Format: Black (line length 88)
· Imports: isort with black profile
· Type Hints: Required for all public functions
· Docstrings: Google style

Example Parameter Module

```python
"""Rn_pulse - Radon Spiking Index parameter."""

from typing import Optional
import numpy as np

from desertas.core import ParameterBase


class RadonSpikingIndex(ParameterBase):
    """Rn_pulse: Radon Spiking Index.
    
    Measures anomalous radon emission preceding tectonic slip.
    
    Attributes:
        rn_obs: Measured ²²²Rn activity (Bq·m⁻³)
        rn_background: Rolling 30-day median
    """
    
    def compute(self) -> float:
        """Compute normalized Rn_pulse value."""
        # Implementation
        pass
```

---

Testing Guidelines

Test Structure

```
tests/
├── unit/                    # Unit tests
│   ├── parameters/
│   │   ├── test_rn_pulse.py
│   │   └── test_he_ratio.py
├── integration/             # Integration tests
├── hypothesis/              # Hypothesis validation (H1-H8)
└── fixtures/                # Test data
```

Running Tests

```bash
# All tests
pytest

# Hypothesis tests (H1-H8)
pytest tests/hypothesis/ -v

# With coverage
pytest --cov=desertas --cov-report=html
```

---

Data Contributions

New Station Data

When adding data from a new monitoring station, include:

1. Station metadata (coordinates, craton, lithology)
2. Radon time series (hourly .csv files)
3. Helium isotope samples (if available)
4. Thermal flux recordings
5. Site photos

Data Format Requirements

Parameter Format Min Samples
Rn_pulse .csv with timestamps 30 days
He_ratio .csv with R/Ra values 3 replicates
ΔΦ_th .csv with temperature 7 days
Ψ_crack .csv with aperture 10 measurements

---

Indigenous Knowledge Protocol

Any contribution involving Indigenous knowledge must:

1. Obtain FPIC - Document consent from community leadership
2. Provide attribution - Credit knowledge holders appropriately
3. Ensure benefit-sharing - Community should benefit
4. Respect data sovereignty - Community controls their knowledge

Contact: indigenous@desertas.org

---

Adding New Parameters

If you propose a new parameter for DRGIS:

1. Literature review - Demonstrate scientific basis
2. Physical independence - Show minimal correlation with existing parameters
3. Measurement protocol - Define how to measure it
4. Validation data - Provide dataset showing predictive power
5. Weight proposal - Suggest initial weight

---

Reporting Issues

Bug Reports

Include:

· Clear title and description
· Steps to reproduce
· Expected vs actual behavior
· Environment details
· Logs or screenshots

Feature Requests

Include:

· Use case description
· Expected behavior
· Scientific justification
· References to similar work

---

Contact

Purpose Contact
General inquiries gitdeeper@gmail.com
Code of Conduct conduct@desertas.org
Indigenous knowledge indigenous@desertas.org
Data contributions data@desertas.org

Repository: https://gitlab.com/gitdeeper4/desertas
Dashboard: https://desertas.netlify.app
DOI: 10.14293/DESERTAS.2026.001

---

"The desert breathes. DESERTAS decodes." 🏜️

Last Updated: March 2026
