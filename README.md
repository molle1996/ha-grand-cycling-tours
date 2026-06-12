# 🚴 Grand Cycling Tours – Home Assistant Integration

![Grand Cycling Tours Banner](https://raw.githubusercontent.com/molle1996/ha-grand-cycling-tours/main/banner.jpg)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=molle1996&repository=ha-grand-cycling-tours&category=integration)

Live **Tour de France**, **Giro d'Italia**, and **Vuelta a España** tracking directly in Home Assistant. Monitor race status, general classification standings, jersey leaders, and stage results in real-time.

Powered by [ProcyclingStats.com](https://www.procyclingstats.com) – no API key required!

---

## 🎯 Features

### Race Data
- **Live race status** (not started / in progress / finished)
- **Stage tracking** (current stage, next stage, completed stages)
- **General Classification (GC)** top 10 riders with time gaps
- **Jersey leaders** (points, mountains, youth/white jersey)
- **Stage winners** for completed stages
- **Race dates** and full stage list

### Sensors per Race
Each race creates up to 9 sensors:

| Sensor | Description |
|--------|-------------|
| `race_status` | Current race status + stage progress |
| `gc_leader` | Leader of the general classification |
| `last_stage_winner` | Winner of the most recent completed stage |
| `next_stage` | Details of upcoming stage |
| `current_stage` | Name/number of the current stage |
| `points_leader` | Leader of the points (sprint) jersey |
| `mountain_leader` | Leader of the mountain (KOM) jersey |
| `youth_leader` | Leader of the youth (white) jersey |
| `gc_top5` | Top 5 riders with gaps |
| `stages_completed` | Count of completed stages |

### Dashboard Ready
Includes a full Lovelace dashboard template with glance cards, entity cards, and markdown formatting for a clean display.

---

## 📦 Installation

### Via HACS (Recommended)

Click the button below to open this repository directly in HACS:

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=molle1996&repository=ha-grand-cycling-tours&category=integration)

Or add it manually:

1. Open **HACS** in Home Assistant
2. Click **Integrations**
3. Click the **⋮** (three dots) menu
4. Select **Custom repositories**
5. Add repository URL: `https://github.com/molle1996/ha-grand-cycling-tours`
6. Category: **Integration**
7. Search for **Grand Cycling Tours** and install
8. Restart Home Assistant

### Manual Installation

1. Copy `custom_components/grand_cycling_tours` to your `<config>/custom_components/` folder
2. Restart Home Assistant
3. Go to **Settings → Devices & Services → Integrations**
4. Click **Create Integration**
5. Search for **Grand Cycling Tours**

---

## ⚙️ Configuration

### Setup Steps

1. Navigate to **Settings → Devices & Services → Create Integration**
2. Search for **Grand Cycling Tours**
3. **Select races** to track:
   - ☑ Tour de France
   - ☑ Giro d'Italia
   - ☑ Vuelta a España
4. **Set update interval** (default: 15 minutes)
   - Minimum: 5 minutes
   - Maximum: 60 minutes

### Configuration Options

Edit options after setup:

1. Go to **Settings → Devices & Services**
2. Find **Grand Cycling Tours**
3. Click **Configure**
4. Update race selection or scan interval
5. Save

---

## 📊 Available Sensors

All sensors are grouped by race and automatically created:

### Tour de France
```
sensor.tour_de_france_race_status
sensor.tour_de_france_gc_leader
sensor.tour_de_france_last_stage_winner
sensor.tour_de_france_next_stage
sensor.tour_de_france_current_stage
sensor.tour_de_france_points_jersey_leader
sensor.tour_de_france_mountain_jersey_leader
sensor.tour_de_france_youth_jersey_leader
sensor.tour_de_france_gc_top5
sensor.tour_de_france_stages_completed
```

### Giro d'Italia
```
sensor.giro_d_italia_race_status
sensor.giro_d_italia_gc_leader
sensor.giro_d_italia_last_stage_winner
sensor.giro_d_italia_next_stage
sensor.giro_d_italia_current_stage
sensor.giro_d_italia_points_jersey_leader
sensor.giro_d_italia_mountain_jersey_leader
sensor.giro_d_italia_youth_jersey_leader
sensor.giro_d_italia_gc_top5
sensor.giro_d_italia_stages_completed
```

### Vuelta a España
```
sensor.vuelta_a_espana_race_status
sensor.vuelta_a_espana_gc_leader
sensor.vuelta_a_espana_last_stage_winner
sensor.vuelta_a_espana_next_stage
sensor.vuelta_a_espana_current_stage
sensor.vuelta_a_espana_points_jersey_leader
sensor.vuelta_a_espana_mountain_jersey_leader
sensor.vuelta_a_espana_youth_jersey_leader
sensor.vuelta_a_espana_gc_top5
sensor.vuelta_a_espana_stages_completed
```

---

## 📈 Entity Attributes

Each sensor provides rich attribute data. For example, `gc_leader` includes:

| Attribute | Description |
|-----------|-------------|
| `leader_name` | GC leader's name |
| `leader_team` | GC leader's team |
| `leader_time` | Leader's total time |
| `gc_standings` | Full top-10 standings (array) |
| `race_url` | URL to ProcyclingStats page |
| `year` | Race year |
| `total_stages` | Total number of stages |
| `stages_completed` | Stages finished so far |

---

## 🎨 Lovelace Dashboard

An example dashboard YAML is included in `Examples/dashboard.yaml`.

### Quick Setup

1. Open Home Assistant
2. Click **Edit Dashboard** (pencil icon)
3. Click **⋮ → Edit Dashboard as YAML**
4. Copy the content from `Examples/dashboard.yaml`
5. Save

### Dashboard Features

- **Status cards** showing race progress (stage X of Y)
- **Classification leaders** at a glance
- **Top 5 riders** with time gaps
- **Separate sections** for each Grand Tour
- **Color-coded** with race Jersey emojis (🟡 TDF, 🩷 Giro, 🔴 Vuelta)

---

## 🔄 Data Update Cycle

The integration polls ProcyclingStats.com on a schedule:

- **Default interval:** 15 minutes
- **Configurable:** 5–60 minutes
- **Data source:** Public HTML pages (no API required)
- **Scraping method:** BeautifulSoup4 HTML parsing
- **Performance:** Lightweight polling, respects robots.txt

---

## 📝 Notes

### Language Support
All text is in **English**. Sensor names, status values, and UI elements use English terminology.

### Data Availability
- Races are tracked from **start to finish** (typically 3 weeks each)
- 2024 races available throughout the year
- 2025 races available from their respective start dates
- Historical data: Best available through ProcyclingStats archive

### Accuracy
Data is scraped from the official ProcyclingStats.com website, which aggregates results from official race organizers.

### Rate Limiting
The integration respects website load and includes:
- User-Agent headers for transparency
- 20-second request timeout
- Configurable polling intervals (minimum 5 minutes)
- Graceful error handling with fallback values

---

## 🐛 Troubleshooting

### Sensors show "Unknown"
- **Cause:** Race may not have started yet, or data hasn't been scraped
- **Solution:** Wait for next update cycle (check your configured interval)
- **Check:** Visit [ProcyclingStats](https://www.procyclingstats.com) to verify current race data

### "Could not connect to data source"
- **Cause:** Network issue or website unavailable
- **Solution:** Check internet connection; website may be temporarily down
- **Retry:** Integration will automatically retry next cycle

### Missing sensor entity IDs
- **Cause:** Selected races may have unusual slugs on ProcyclingStats
- **Solution:** Verify race selection in integration settings
- **Debug:** Check Home Assistant logs for detailed error messages

### Data is stale
- **Cause:** Polling interval is too long
- **Solution:** Decrease scan interval in integration options (minimum 5 minutes)
- **Note:** Shorter intervals increase load; balance with your needs

---

## 🤝 Contributing

Contributions are welcome! Areas of interest:

- Support for additional races (monuments, one-day races)
- Alternative data sources or improved scraping
- Translation strings for other languages
- Dashboard templates and examples
- Bug reports and feature requests

---

## 📄 License

This integration is provided as-is for Home Assistant. Not affiliated with UCI, race organizers, or ProcyclingStats.

---

## 🙌 Credits

- **Data Source:** [ProcyclingStats.com](https://www.procyclingstats.com)
- **Built for:** [Home Assistant](https://www.home-assistant.io/)
- **Inspired by:** Similar sports integrations for HA
- **Icon:** <a href="https://www.flaticon.com/free-icons/tour-de-france" title="tour de france icons">Tour de france icons created by cube29 - Flaticon</a>

---

## ⚽ Similar Integration

Looking for football/soccer? Check out the [World Cup 2026 Integration](https://github.com/Adya84/ha-world-cup-2026) for live FIFA World Cup tracking!

---

Enjoy tracking your favorite Grand Tours! 🚴‍♂️ 🏆
