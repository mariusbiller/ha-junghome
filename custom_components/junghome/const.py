DOMAIN = "junghome"
MANUFACTURER = "Albrecht JUNG"

CONF_IP_ADDRESS = "ip"
CONF_TOKEN = "token"

ROCKER_SWITCH_TYPES = ["Rocker Switch", "RockerSwitch"]

# Request datapoint per rocker direction, and the suffix used to name its entity.
ROCKER_DIRECTIONS = {
    "up_request": "Up",
    "down_request": "Down",
}

# Status LED built into the rocker face.
ROCKER_LED_DATAPOINT = "status_led"