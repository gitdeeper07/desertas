# 🏜️ DESERTAS Shell Completion

DESERTAS provides shell completion for bash, zsh, and fish shells.

---

## Installation

### Bash
```bash
eval "$(_DESERTAS_COMPLETE=bash_source desertas)"
```

Zsh

```zsh
eval "$(_DESERTAS_COMPLETE=zsh_source desertas)"
```

Fish

```fish
eval (env _DESERTAS_COMPLETE=fish_source desertas)
```

---

Available Commands

Core Commands

Command Description
desertas analyze Run DRGIS analysis
desertas monitor Monitor station activity
desertas dashboard Launch dashboard
desertas stations List monitoring stations
desertas alerts Check tectonic alerts

Parameter Commands

```bash
desertas analyze delta-phi-th    # Diurnal Thermal Flux
desertas analyze psi-crack       # Fissure Conductivity
desertas analyze rn-pulse        # Radon Spiking Index
desertas analyze omega-arid      # Desiccation Index
desertas analyze gamma-geo       # Migration Velocity
desertas analyze he-ratio        # Helium-4 Signature
desertas analyze beta-dust       # Particulate Coupling
desertas analyze s-yield         # Seismic Yield Potential
desertas analyze drgis           # Composite Score
```

Station Commands

```bash
desertas stations list                         # List all 36 stations
desertas stations show --id sahara-01          # Show station details
desertas stations compare --site1 a --site2 b  # Compare two stations
desertas stations craton --type saharan        # Filter by craton
```

Alert Levels

```bash
desertas alerts --status watch      # 2.0-3.0 sigma
desertas alerts --status alert      # 3.0-4.0 sigma
desertas alerts --status emergency  # 4.0-5.0 sigma
desertas alerts --status critical   # >5.0 sigma
```

---

Examples

```bash
# Analyze specific station
desertas analyze --station sahara-01 --parameters all

# Monitor radon activity
desertas monitor rn-pulse --station arabian-03 --duration 72h

# Check active alerts
desertas alerts --status alert --craton saharan

# List all stations in Saharan craton
desertas stations list --craton saharan --details

# Calculate DRGIS for specific DRGU
desertas drgis --drgu DRGU-2026-001 --verbose

# Run hypothesis test
desertas test --hypothesis H2 --verbose

# Launch dashboard
desertas dashboard --port 8501
```

---

Tab Completion Features

Station Name Completion

· Auto-completes from 36 monitored stations
· Groups by craton system

Parameter Completion

· All 8 DRGIS parameters
· Parameter groups

Craton Completion

· saharan-craton
· arabian-shield
· kaapvaal-craton
· yilgarn-craton
· atacama-pampean
· tarim-basin
· scandinavian-shield

---

Live Resources

· Dashboard: https://desertas.netlify.app
· Documentation: https://desertas.readthedocs.io

🏜️ The desert breathes. DESERTAS decodes.
