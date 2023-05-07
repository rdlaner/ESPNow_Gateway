"""Gateway Config File"""
# Standard imports
from micropython import const

# Third party imports
import adafruit_logging as logging


config = {
    "time_sync_rate_sec": const(600),
    "logging_level": logging.DEBUG,

    # wifi configuration parameters

    # mqtt configuration parameters
    "pressure_topic": "homeassistant/aranet/pressure",
    "cmd_topic": "homeassistant/number/generic-device/cmd",
    "keep_alive_sec": const(60),
    "connect_retries": const(5),
    "recv_timeout_sec": const(10),

    # espnow configuration parameters
    "epn_peer_mac": b'|\xdf\xa1\x1a\xb1\xba'
}
