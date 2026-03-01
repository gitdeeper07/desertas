"""Command line interface for DESERTAS"""

import argparse

def cli():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description="DESERTAS - Desert Emission Sensing System")
    parser.add_argument("--version", action="version", version="desertas 1.0.0")
    parser.add_argument("--info", action="store_true", help="Show project information")
    
    args = parser.parse_args()
    
    if args.info:
        print("🏜️ DESERTAS v1.0.0")
        print("Desert Emission Sensing & Energetic Rock-Tectonic Analysis System")
        print("DOI: 10.14293/DESERTAS.2026.001")
        print("Dashboard: https://desertas.netlify.app")
        print("Documentation: https://desertas.readthedocs.io")
    
    return 0

if __name__ == "__main__":
    cli()
