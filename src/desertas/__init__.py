"""DESERTAS - Desert Emission Sensing & Energetic Rock-Tectonic Analysis System"""

__version__ = "1.0.0"
__author__ = "Samir Baladi"
__email__ = "gitdeeper@gmail.com"
__doi__ = "10.14293/DESERTAS.2026.001"

# معلومات المشروع
PROJECT_URL = "https://desertas.netlify.app"
API_URL = "https://desertas.netlify.app/api"
DOCS_URL = "https://desertas.readthedocs.io"
GITLAB_URL = "https://gitlab.com/gitdeeper4/desertas"
GITHUB_URL = "https://github.com/gitdeeper4/desertas"

# إحصائيات
DRGIS_ACCURACY = 90.6
TOTAL_STATIONS = 36
TOTAL_CRATONS = 7
MEAN_LEAD_TIME_DAYS = 58

# المعاملات الثمانية
PARAMETERS = [
    "ΔΦ_th (Diurnal Thermal Flux)",
    "Ψ_crack (Fissure Conductivity)",
    "Rn_pulse (Radon Spiking Index)",
    "Ω_arid (Desiccation Index)",
    "Γ_geo (Geogenic Migration Velocity)",
    "He_ratio (Helium-4 Signature)",
    "β_dust (Particulate Coupling Index)",
    "S_yield (Seismic Yield Potential)"
]
