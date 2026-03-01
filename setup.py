#!/usr/bin/env python3
"""🏜️ DESERTAS: Desert Emission Sensing & Energetic Rock-Tectonic Analysis System.

A quantitative framework for decoding geogenic gas emissions, tectonic pulse detection,
and pre-seismic geochemical forecasting in hyperarid cratons.

Dashboard: https://desertas.netlify.app
API: https://desertas.netlify.app/api
Documentation: https://desertas.readthedocs.io
DOI: 10.14293/DESERTAS.2026.001
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="desertas",
    version="1.0.0",
    author="Samir Baladi",
    author_email="gitdeeper@gmail.com",
    description="DESERTAS: Desert Emission Sensing & Energetic Rock-Tectonic Analysis System",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://gitlab.com/gitdeeper4/desertas",
    project_urls={
        "Bug Tracker": "https://gitlab.com/gitdeeper4/desertas/-/issues",
        "Documentation": "https://desertas.readthedocs.io",
        "Dashboard": "https://desertas.netlify.app",
        "API": "https://desertas.netlify.app/api",
        "DOI": "https://doi.org/10.14293/DESERTAS.2026.001",
        "Source Code": "https://gitlab.com/gitdeeper4/desertas",
        "GitHub": "https://github.com/gitdeeper4/desertas",
    },
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering",
        "Topic :: Scientific/Engineering :: Atmospheric Science",
        "Topic :: Scientific/Engineering :: Geology",
        "Topic :: Scientific/Engineering :: Physics",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "ml": [
            "tensorflow>=2.8.0",
            "torch>=1.10.0",
            "pytorch-lightning>=1.6.0",
        ],
        "viz": [
            "streamlit>=1.15.0",
            "plotly>=5.5.0",
            "dash>=2.0.0",
        ],
        "web": [
            "flask>=2.0.0",
            "flask-cors>=3.0.0",
            "flask-restful>=0.3.9",
            "fastapi>=0.85.0",
            "uvicorn>=0.18.0",
            "gunicorn>=20.1.0",
        ],
        "geo": [
            "geopandas>=0.10.0",
            "shapely>=1.8.0",
            "rasterio>=1.3.0",
            "pyproj>=3.3.0",
        ],
        "field": [
            "pyserial>=3.5",
            "pymodbus>=3.0.0",
            "minimalmodbus>=2.0.0",
        ],
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=22.0.0",
            "ruff>=0.0.260",
            "mypy>=0.990",
            "pre-commit>=2.20.0",
            "mkdocs>=1.4.0",
            "mkdocs-material>=9.0.0",
            "sphinx>=5.0.0",
            "sphinx-rtd-theme>=1.0.0",
        ],
        "all": [
            "tensorflow>=2.8.0",
            "torch>=1.10.0",
            "pytorch-lightning>=1.6.0",
            "streamlit>=1.15.0",
            "plotly>=5.5.0",
            "dash>=2.0.0",
            "flask>=2.0.0",
            "flask-cors>=3.0.0",
            "flask-restful>=0.3.9",
            "fastapi>=0.85.0",
            "uvicorn>=0.18.0",
            "gunicorn>=20.1.0",
            "geopandas>=0.10.0",
            "shapely>=1.8.0",
            "rasterio>=1.3.0",
            "pyproj>=3.3.0",
            "pyserial>=3.5",
            "pymodbus>=3.0.0",
            "minimalmodbus>=2.0.0",
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=22.0.0",
            "ruff>=0.0.260",
            "mypy>=0.990",
            "pre-commit>=2.20.0",
            "mkdocs>=1.4.0",
            "mkdocs-material>=9.0.0",
            "sphinx>=5.0.0",
            "sphinx-rtd-theme>=1.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "desertas = desertas.cli.main:cli",
        ],
    },
    include_package_data=True,
    zip_safe=False,
    keywords=[
        "geogas",
        "radon-precursors",
        "tectonic-breathing",
        "arid-craton",
        "fissure-conductivity",
        "helium-4",
        "diurnal-thermal-flux",
        "desert-geochemistry",
        "seismic-forecasting",
        "earthquake-prediction",
    ],
)

# 🏜️ The desert breathes. DESERTAS decodes.
