# ha-samsung-washer

Home Assistant custom integration for Samsung Washer-Dryer via SmartThings REST API.

> **Device**: Samsung WW6600R (washer-dryer combo) · Table_02 cycles · tested on firmware `DA_WM_TP2_20_COMMON_30250414`

---

## Features

- **11 sensor entities** — machine state, job state, progress %, remaining time, current cycle, water temp, spin speed, rinse count, dry level, cycle type
- **1 binary sensor** — remote control enabled/disabled (prerequisite alert)
- **1 select entity** — cycle picker (All-in-one / Drying only / Quick 15)
- **3 button entities** — Start, Stop, Pause
- **3 services** — `samsung_washer.start_cycle`, `samsung_washer.stop`, `samsung_washer.pause`
- **Config UI** — PAT + device ID entered in HA UI, no YAML secrets
- **Options UI** — poll interval + all-in-one defaults (temp/spin/rinse/dry)
- **State restore** — selected cycle survives HA restarts

---

## Installation

### Manual

1. Copy `custom_components/samsung_washer/` into your HA config directory:
   ```
   <ha-config>/custom_components/samsung_washer/
   ```
2. Restart Home Assistant.
3. **Settings → Devices & Services → Add Integration → Samsung Washer**
4. Enter your SmartThings PAT and device ID.

### HACS (once published)

Add this repo as a custom HACS repository, then install via HACS.

---

## Setup

### SmartThings PAT

Generate at **https://account.smartthings.com/tokens** with scopes:
- `devices:read`
- `devices:write`
- `devices:execute`

### Device ID

Find yours at **https://account.smartthings.com** → Devices → click your washer → copy the ID from the URL.

It looks like: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`

---

## Entities

| Entity | Type | Description |
|---|---|---|
| `sensor.washing_machine_machine_state` | sensor | stop / ready / running / paused |
| `sensor.washing_machine_job_state` | sensor | wash / rinse / spin / drying / finish / none |
| `sensor.washing_machine_progress` | sensor | 0–100 % |
| `sensor.washing_machine_remaining_time` | sensor | minutes |
| `sensor.washing_machine_remaining_time_hh_mm` | sensor | HH:MM string |
| `sensor.washing_machine_current_cycle` | sensor | Course_XX (from device) |
| `sensor.washing_machine_cycle_type` | sensor | allInOne / washingOnly / dryingOnly |
| `sensor.washing_machine_water_temperature` | sensor | current wash temp |
| `sensor.washing_machine_spin_speed` | sensor | current spin RPM |
| `sensor.washing_machine_rinse_cycles` | sensor | current rinse count |
| `sensor.washing_machine_dry_level` | sensor | current dry level |
| `binary_sensor.washing_machine_remote_control` | binary_sensor | ON = remote enabled |
| `select.washing_machine_cycle` | select | cycle intent for next Start |
| `button.washing_machine_start` | button | start selected cycle |
| `button.washing_machine_stop` | button | stop / cancel |
| `button.washing_machine_pause` | button | pause |

---

## Services

### `samsung_washer.start_cycle`

```yaml
service: samsung_washer.start_cycle
data:
  cycle: "All-in-one"     # or "Drying only" / "Quick 15" — defaults to select entity
  temp: "40"              # all-in-one only: cold/20/30/40/60/90
  spin: "1200"            # all-in-one only: noSpin/400/800/1000/1200/1400
  rinse: "2"              # all-in-one only: 0–5
  dry_level: "cupboard"   # all-in-one: none/cupboard/30/60/90  |  drying-only: cupboard/30/60/90
```

### `samsung_washer.stop`
```yaml
service: samsung_washer.stop
```

### `samsung_washer.pause`
```yaml
service: samsung_washer.pause
```

---

## Companion app flow

The typical companion app (HA mobile) flow:

1. Notification fired when `binary_sensor.remote_control` turns **ON**
2. User taps notification → opens HA dashboard
3. User picks cycle on `select.washing_machine_cycle`
4. User taps `button.washing_machine_start`
5. Sensors update live (progress, remaining time)
6. Automation fires on `sensor.job_state == finish` → "Done" notification

### Example automation — "Done" notification

```yaml
automation:
  alias: Washing Machine Done
  trigger:
    - platform: state
      entity_id: sensor.washing_machine_job_state
      to: finish
  action:
    - service: notify.mobile_app_your_phone
      data:
        title: Washing Machine
        message: Cycle finished!
```

### Example automation — Remote Control alert

```yaml
automation:
  alias: Washer Remote Enabled
  trigger:
    - platform: state
      entity_id: binary_sensor.washing_machine_remote_control
      to: "on"
  action:
    - service: notify.mobile_app_your_phone
      data:
        title: Washing Machine
        message: Remote control is ON — ready to start remotely.
        data:
          url: /lovelace/washer
```

---

## Cycle reference (WW6600R, Table_02)

| Cycle | Code | Type | Notes |
|---|---|---|---|
| All-in-one | `Course_20` Cotton | allInOne | temp cold–90, spin up to 1400, dry up to 90 min |
| Drying only | `Course_38` Cotton Dry | dryingOnly | level cupboard/30/60/90 |
| Quick 15 | `hca.washerMode quickWash` | — | via HCA component, no cycle code |

> **⚠️ Remote Control prerequisite**: `remoteControlEnabled` must be `true` (press Smart Control on the machine) before any start command will work.

---

## Development

```bash
# Install dev dependencies
pip install homeassistant

# Run HA with this integration loaded
hass -c /path/to/ha-config
```
