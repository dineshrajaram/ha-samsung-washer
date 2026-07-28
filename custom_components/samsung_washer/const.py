"""Constants for Samsung Washer integration."""

DOMAIN = "samsung_washer"

# Config entry keys
CONF_CLIENT_ID     = "client_id"
CONF_CLIENT_SECRET = "client_secret"
CONF_DEVICE_ID     = "device_id"

# OAuth2 scopes required from SmartThings
OAUTH_SCOPES = "r:devices:* w:devices:* x:devices:*"

# Options keys
CONF_SCAN_INTERVAL   = "scan_interval"
CONF_DEFAULT_TEMP    = "default_temp"
CONF_DEFAULT_SPIN    = "default_spin"
CONF_DEFAULT_RINSE   = "default_rinse"
CONF_DEFAULT_DRY     = "default_dry_level"

# Defaults
DEFAULT_SCAN_INTERVAL = 30          # seconds
DEFAULT_DEVICE_ID     = ""   # pre-fill in config flow if you want; leave blank for prompt

DEFAULT_TEMP      = "40"
DEFAULT_SPIN      = "1200"
DEFAULT_RINSE     = "2"
DEFAULT_DRY_LEVEL = "cupboard"

# Cycle codes — verified from device discovery (Table_02, WW6600R)
CYCLE_ALL_IN_ONE  = "Course_20"   # Cotton — allInOne, temp cold–90, spin up to 1400
CYCLE_DRYING_ONLY = "Course_38"   # Cotton Dry — dryingOnly, level cupboard/30/60/90
# Quick 15 has no cycle code — uses hca.washerMode on hca.main component

# Human-readable cycle names shown in HA UI
CYCLE_ALL_IN_ONE_NAME  = "All-in-one"
CYCLE_DRYING_ONLY_NAME = "Drying only"
CYCLE_QUICK_15_NAME    = "Quick 15"

CYCLE_OPTIONS = [CYCLE_ALL_IN_ONE_NAME, CYCLE_DRYING_ONLY_NAME, CYCLE_QUICK_15_NAME]

# Valid option values (sourced from device supportedCycles / supportedXxx attributes)
VALID_TEMPS = ["cold", "20", "30", "40", "60", "90"]
VALID_SPINS = ["noSpin", "400", "800", "1000", "1200", "1400"]
VALID_RINSES = ["0", "1", "2", "3", "4", "5"]
VALID_DRY_LEVELS_AIO   = ["none", "cupboard", "30", "60", "90"]   # all-in-one
VALID_DRY_LEVELS_DRY   = ["cupboard", "30", "60", "90"]           # drying-only

# Device state values
STATE_STOP    = "stop"
STATE_RUN     = "run"
STATE_PAUSE   = "pause"
STATE_READY   = "ready"
STATE_RUNNING = "running"
STATE_PAUSED  = "paused"

# HA platforms this integration provides
PLATFORMS = ["sensor", "binary_sensor", "select", "button"]
