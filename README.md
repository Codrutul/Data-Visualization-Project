# The Global Data Center Boom — Interactive Visualization

An interactive data visualization dashboard exploring the explosive growth of global data center infrastructure, its geographic concentration, the economic factors driving placement, and the correlation with AI company market capitalizations.

## 🚀 Quick Start

### Option 1: Python HTTP Server (Recommended)

```bash
# Navigate to the project directory
cd "data visualization mock"

# Start a local HTTP server on port 8080
python -m http.server 8080
```

Then open **http://localhost:8080** in your browser.

### Option 2: Open Directly

Double-click `index.html` to open it in your default browser. Most features work offline since data is embedded inline, but the Leaflet geographic maps require an internet connection for map tiles.

### Option 3: Node.js

```bash
npx serve -l 8080
```

## 📊 Dashboard Panels

| Panel | Title | Description |
|-------|-------|-------------|
| 1 | **Data Centers Across the Globe** | Proportional flag tile map showing global data center density. Each tile represents ~50 facilities. Includes geographic choropleth and bubble map views. |
| 2 | **United States: The World's Data Center Hub** | US state-level choropleth map with facility counts and ranking. |
| 3 | **Why These States?** | Grouped bar chart comparing the top 10 US data center states across 4 placement factors: electricity cost, tax incentives, fiber connectivity, and land affordability. |
| 4 | **The AI Gold Rush** | Interactive time-scrubber (2019–2026) showing the correlation between worldwide hyperscale data center growth and the market cap explosion of major AI/tech companies. |

## 📁 Project Structure

```
data visualization mock/
├── index.html                          # Single-page dashboard (all HTML, CSS, JS inline)
├── README.md                           # This file
└── data/
    ├── dc-count-by-country.json        # Data center facility counts by country (ISO 3-letter codes)
    ├── dc-count-by-state.json          # Data center facility counts by US state (2-letter abbr)
    ├── world-continent-tiles.json      # Tile grid coordinates for the proportional flag map
    ├── market-caps.json                # Monthly market cap data (Jan 2019 – Aug 2026) for public companies
    ├── openai-valuation.json           # OpenAI private valuation milestones
    ├── anthropic-valuation.json        # Anthropic private valuation milestones
    ├── hyperscale-growth.json          # Annual worldwide hyperscale data center counts (2015–2026)
    ├── dc-locations-sample.json        # Sample data center locations (lat/lng) for bubble map
    ├── flags/                          # 40px country flag PNGs (cached from flagcdn.com)
    │   ├── us.png
    │   ├── de.png
    │   ├── gb.png
    │   └── ... (49 country flags)
    └── (other data files)
```

## 🛠️ Tech Stack

- **HTML/CSS/JS** — Single-file dashboard, no build step required
- **[Chart.js 4](https://www.chartjs.org/)** — Bar charts (Panel 3 & 4)
- **[Leaflet 1.9](https://leafletjs.com/)** — Interactive geographic maps (Panel 1 & 2)
- **[Inter](https://rsms.me/inter/)** — Typography
- **[Carto](https://carto.com/basemaps/)** — Map tile layer (dark positron)
- **[FlagCDN](https://flagcdn.com/)** — Country flag images (cached locally as base64 Data URIs)

## 📊 Data Sources

| Dataset | Source | Notes |
|---------|--------|-------|
| Global DC counts by country | Cloudscene, datacentermap.com | Facility-level counts of colocation and hyperscale data centers |
| US DC counts by state | datacentermap.com | State-level aggregation |
| Market capitalizations | Yahoo Finance, CompaniesMarketCap | Monthly closing market cap for NVIDIA, Microsoft, Alphabet, Amazon, Meta |
| OpenAI valuations | Public funding round announcements | Private company — valuations from reported funding rounds |
| Anthropic valuations | Public funding round announcements | Private company — valuations from reported funding rounds |
| Hyperscale DC growth | Synergy Research Group | Annual worldwide hyperscale data center counts |
| Placement factors (Panel 3) | EIA, state tax authority websites | Electricity rates, tax incentive scores, fiber density, land costs |

## 📋 Requirements

- **Python 3.x** (for the HTTP server) — or any static file server
- **Modern web browser** (Chrome, Firefox, Edge, Safari)
- **Internet connection** (only needed for Leaflet map tiles; tile grid and charts work offline)
