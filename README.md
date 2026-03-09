# Fuel Stations Around an Address (France)
Created by Veronica Taurino.
If you reuse or adapt this project, please keep attribution to the original repository.
Last update: 2026-03-09

A lightweight Python script to query nearby fuel stations in France starting from a plain-text address.

The script uses:

- the **French BAN geocoding API** to convert an address into coordinates
- the **2aaz Fuel Prices API** to retrieve nearby stations and fuel prices

It then:

- finds stations around the target address
- filters them by distance
- extracts fuel prices
- keeps only stations with a recent update
- highlights the cheapest station for a selected fuel type
- prints a compact summary and a full comparison table

## Configuration

Before running the script, edit the configuration section in the Python file.
Main variables to customize:

- ADDRESS: target address in France
- DAYS_SINCE_LAST_UPDATE: maximum accepted age of the fuel price update
- FAV_FUEL_TYPE: fuel type used for the "cheapest station" search

Example:
ADDRESS = "XXX chemin de cheminchemin, Nice", 
DAYS_SINCE_LAST_UPDATE = 1, 
FAV_FUEL_TYPE = "gazole"

You may also adjust:
- RADIUS_KM: search radius around the address
- TIMEOUT: HTTP request timeout

## Features

- Address-based search
- Nearby station lookup
- Distance filtering
- Fuel price extraction
- Favorite fuel type selection
- Update recency filtering
- Compact "best option" summary
- Full tabular comparison for all detected fuels
- No ads, no signup, local execution

## Supported fuel labels

The script currently maps these fuel types:

- `gazole` → Diesel
- `sp95` → Petrol 95
- `sp95-e10` → Petrol 95 E10
- `sp98` → Petrol 98
- `e85` → Ethanol E85
- `gplc` → LPG

## Requirements

- Python 3.9+
- `requests`

Install dependency:
`pip install requests`

## Usage

Run the script locally with:
`python fuel_stations_france.py`

## Output

The script prints:

- the resolved address and coordinates
- the number of stations found within the selected radius
- the cheapest station for the selected fuel type
- a comparison table for recently updated stations
