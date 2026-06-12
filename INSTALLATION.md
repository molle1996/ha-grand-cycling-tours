# Grand Cycling Tours – Installation Guide

## Prerequisites

- **Home Assistant** 2024.1 or later
- **HACS** (Home Assistant Community Store) – for easy installation
- **Network access** to ProcyclingStats.com (no API key required)

---

## Installation Methods

### Method 1: HACS (Recommended)

**Easiest installation method – recommended for most users.**

1. Ensure HACS is installed:
   - Go to **Settings → Devices & Services**
   - Search for "HACS"
   - If not found, install via [hacs.xyz](https://hacs.xyz)

2. Add the custom repository:
   - Click **HACS** in the sidebar
   - Click **Integrations** tab
   - Click the **⋮** (three dots) in the top right
   - Select **Custom repositories**
   - Paste: `https://github.com/yourusername/ha-grand-cycling-tours`
   - Category: **Integration**
   - Click **Create**

3. Install the integration:
   - Search for "Grand Cycling Tours" in HACS
   - Click it
   - Click **Install**

4. Restart Home Assistant:
   - **Settings → System → Restart Home Assistant**
   - Or restart via command line: `docker restart homeassistant` (Docker) or service restart command

5. Add the integration:
   - Go to **Settings → Devices & Services**
   - Click **Create Integration** (or **+ Create**) button
   - Search for "Grand Cycling Tours"
   - Follow the setup wizard

---

### Method 2: Manual Installation

**For advanced users or Docker environments without HACS.**

1. Access your Home Assistant config directory:
   ```bash
   # SSH to your HA system or use File Editor add-on
   cd /config/custom_components
   ```

2. Clone or download the integration:
   ```bash
   git clone https://github.com/yourusername/ha-grand-cycling-tours.git grand_cycling_tours
   # OR manually copy the `grand_cycling_tours` folder
   ```

3. Restart Home Assistant via Settings or command:
   ```bash
   # Via UI: Settings → System → Restart Home Assistant
   # Via command (SSH):
   ha core restart
   ```

4. Add the integration:
   - **Settings → Devices & Services → Create Integration**
   - Search for **Grand Cycling Tours**
   - Complete the setup

---

## Configuration

### Setup Wizard

After installation, a configuration dialog appears:

**Select races to track:**
- ☑ Tour de France
- ☑ Giro d'Italia
- ☑ Vuelta a España

**Set update interval** (minutes):
- Default: **15**
- Minimum: **5**
- Maximum: **60**

Click **Create** to confirm.

### Modify Configuration Later

1. **Settings → Devices & Services**
2. Find **Grand Cycling Tours**
3. Click **Configure** or the **⚙️** button
4. Update settings and save

---

## Verification

### Check Installation

After setup, verify sensors are created:

1. Go to **Settings → Devices & Services**
2. Click **Grand Cycling Tours** under **Integrations**
3. Click the **Grand Cycling Tours** device
4. You should see **9–27 entities** (9 per selected race)

### Sensor Examples

The following entities should exist (visible in **Developer Tools → States**):

```
sensor.tour_de_france_race_status
sensor.tour_de_france_gc_leader
sensor.giro_d_italia_race_status
sensor.giro_d_italia_gc_leader
sensor.vuelta_a_espana_race_status
sensor.vuelta_a_espana_gc_leader
```

---

## Troubleshooting

### Integration Not Appearing in Setup

**Problem:** "Grand Cycling Tours" doesn't show in integration search

**Solutions:**
1. Clear browser cache: Ctrl+F5 or Cmd+Shift+R
2. Check Home Assistant logs for errors:
   - **Settings → System → Logs** (look for `grand_cycling_tours`)
3. Restart Home Assistant
4. Re-check that `custom_components/grand_cycling_tours/` folder exists
5. Verify `manifest.json` is in the folder

### Sensors Show "Unknown" or "Unavailable"

**Problem:** Sensors exist but show no data

**Causes:**
- Race hasn't started yet (TDF in July, Giro in May, Vuelta in August)
- First update cycle hasn't completed (default 15 minutes)
- ProcyclingStats.com is temporarily down

**Solutions:**
1. Wait for the update interval to complete
2. Check that a race is actually in progress:
   - Visit [ProcyclingStats.com](https://www.procyclingstats.com)
3. Check Home Assistant logs for errors
4. Try reducing scan interval to 5 minutes for faster updates

### "Could Not Connect" Error

**Problem:** Integration shows error during setup

**Causes:**
- Network connectivity issue
- ProcyclingStats.com is unreachable
- Firewall blocking outbound HTTPS

**Solutions:**
1. Check internet connection
2. Visit [ProcyclingStats.com](https://www.procyclingstats.com) in a browser
3. Check firewall rules allow outbound HTTPS (port 443)
4. Try again after a few minutes
5. Check HA logs: **Settings → System → Logs**

### Performance Issues

**Problem:** Home Assistant becomes sluggish after adding integration

**Cause:** Scan interval too short causes excessive polling

**Solution:**
1. Increase scan interval to 30–60 minutes
2. Configure options: **Settings → Devices & Services → Grand Cycling Tours → Configure**

---

## Uninstallation

### Via HACS

1. Go to **HACS → Integrations**
2. Find **Grand Cycling Tours**
3. Click the **⋮** menu
4. Select **Uninstall**
5. Restart Home Assistant

### Manual Removal

1. Stop Home Assistant
2. Delete `/config/custom_components/grand_cycling_tours/` folder
3. Start Home Assistant
4. Go to **Settings → Devices & Services**
5. Find **Grand Cycling Tours** and remove the integration

---

## Next Steps

### Add to Dashboard

1. Copy the example dashboard from `Examples/dashboard.yaml`
2. **Edit Dashboard** → **Edit as YAML**
3. Paste the content
4. Save

### Create Automations

Use the example automations from `Examples/automations.yaml`:
- Alert when your favorite rider takes the lead
- Daily race summaries
- Stage winner notifications
- Ambient lighting during stages

### Explore Sensor Data

1. **Developer Tools → States**
2. Click on a sensor (e.g., `sensor.tour_de_france_gc_top5`)
3. View full data and attributes
4. Use these in templates for custom displays

---

## Getting Help

### Home Assistant Community

- [Home Assistant Discourse](https://community.home-assistant.io/)
- [GitHub Issues](https://github.com/yourusername/ha-grand-cycling-tours/issues)

### Check Logs

```yaml
# In Developer Tools → Services, use:
logger.set_level:
  homeassistant.components.grand_cycling_tours: debug
```

Then check **Settings → System → Logs** for detailed debugging info.

---

## Requirements Summary

This integration requires:

```
beautifulsoup4>=4.12.0  # HTML parsing
aiohttp>=3.9.0         # Async HTTP requests
```

These are automatically installed by Home Assistant when you add the integration. No manual `pip install` needed!

---

Enjoy tracking the Grand Tours! 🚴‍♂️🏆
