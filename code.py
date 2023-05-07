"""ESPNow to MQTT Gateway

Asyncio:
Using circuitpython, we don't have an async espnow library and likely don't have an async MQTT
library (unless I can port the micropython one...). However, we can still use asyncio to
separate these polling tasks into async tasks that poll at a predefined interval. This should
help with the async design and allow for any future feature additions which is likely to happen.
Worse case scenario is I can't find an async MQTT library and our espnow client will be blocked
for the entire duration that an MQTT transaction is underway. This would be the case in a regular
polling design, so nothing is lost by an async design.

Async Tasks:
 * min_iot_task
    - asyncio.sleep(x) to poll if data is received.
    - use async queue to send rx'ed data to mqtt_send_task.
 * mqtt_loop_task
    - asyncio.sleep(x) to run mqtt loop fxn.
 * mqtt_send_task
    - block on async queue waiting to get data from min_iot_task

ESPNow and Wifi:
It turns out you can receive ESPNow messages while actively connected to a wifi AP, but it has some
caveats. First attempts at testing showed that I can do both protocols simultaneously if both
devices use the same wifi channel AND the device connected to an AP also has AP mode turned on in
order to disable power savings mode.
https://micropython-glenn20.readthedocs.io/en/latest/library/espnow.html#espnow-and-wifi-operation

TODO: Collect and send metrics
TODO: Can I use the mp mqtt async library with cp?
        No, it needs porting. Consider porting?
TODO: Custom time sync protocol with espnow clients...
"""
# Standard imports
# pylint: disable=no-name-in-module, import-error
import asyncio
import traceback
import wifi
from supervisor import reload

# Third party imports
import adafruit_logging as logging
import adafruit_minimqtt.adafruit_minimqtt as MQTT
import cp_libs.time
from cp_libs.async_primitives.queue import AsyncQueue
from cp_libs.network import Network

# Local imports
import peripherals
from config import config

# Constants

# Globals
periphs = peripherals.Peripherals()
event_queue = AsyncQueue()
logger = logging.getLogger("Gateway")
logger.setLevel(config["logging_level"])


# MQTT Callbacks
# pylint: disable=unused-argument
def mqtt_connected(client: MQTT.MQTT, user_data, flags: int, return_code: int) -> None:
    """Callback for when when MQTT client is connected to the broker"""
    logger.debug("MQTT connected callback")


def mqtt_disconnected(client: MQTT.MQTT, user_data, return_code: int) -> None:
    """Callback for when MQTT client is disconnected from the broker"""
    logger.debug("MQTT disconnected callback")


def mqtt_message(client: MQTT.MQTT, topic: str, message: str) -> None:
    """Callback for when MQTT client's subscribed topic receives new data"""
    logger.debug(f"New message on topic {topic}: {message}")


# Async tasks
async def min_iot_client(net: Network) -> None:
    """Async task to read incoming MinIoT messages.

    All received messages are loaded into the async event queue.

    Args:
        net (Network): Network interface protocol implementing MinIotProtocol
    """
    while True:
        msgs = []
        try:
            data_rxed = net.receive(msgs)
        except (OSError) as exc:
            logger.error("Handled exception in receiving min iot msg:")
            logger.error(f"{''.join(traceback.format_exception(exc, chain=True))}")
            data_rxed = False

        if data_rxed:
            logger.debug(f"Received {len(msgs)} min iot msgs")
            await event_queue.put(msgs)

        await asyncio.sleep(0)


async def mqtt_loop(net: Network) -> None:
    """Async task to run the MQTT loop.

    Will attempt to recover MQTT if loop failure occurs. However, if recovery fails,
    this function will reboot the device as a last effort to recover.

    Args:
        net (Network): Network interface protocol implementing MqttProtocol
    """
    while True:
        try:
            net.receive(rxed_data=None, recover=True)
        except Exception as exc:
            logger.critical("MQTT Loop failed:")
            logger.critical(f"{''.join(traceback.format_exception(exc, chain=True))}")
            logger.critical("Rebooting...")
            reload()

        await asyncio.sleep(1)


async def mqtt_send(net: Network) -> None:
    """Async task to send received MinIoT messages to MQTT broker.

    Blocks on async event queue to receive messages to send.
    Will attempt to recover MQTT if an error occurs on send. However, if recovery fails,
    this function will reboot the device as a last effort to recover.

    Args:
        net (Network): Network interface protocol implementing MqttProtocol
    """
    while True:
        success = True
        data = await event_queue.get()

        for msg in data:
            try:
                success = net.send(msg=msg["msg"], topic=msg["topic"], retain=True, qos=1, recover=True)
            except Exception as exc:
                logger.critical("MQTT send failed:")
                logger.critical(f"{''.join(traceback.format_exception(exc, chain=True))}")
                logger.critical("Rebooting...")
                reload()

            if not success:
                logger.error("MQTT send failed")


async def time_sync(net: Network, sync_interval_secs: float) -> None:
    """Async time synchronization task. Periodically runs ntp time sync.

    Args:
        net (Network): Network interface protocol with ntp implementation.
        sync_interval_secs (float): Time sync interval in seconds.
    """
    while True:
        net.ntp_time_sync()
        logger.info(f"Time: {cp_libs.time.get_fmt_time()}")
        logger.info(f"Date: {cp_libs.time.get_fmt_date()}")
        await asyncio.sleep(sync_interval_secs)


async def main() -> None:
    """Main Loop - Runs all async tasks."""

    mqtt_network = Network.create_mqtt("BPI",
                                       on_connect_cb=mqtt_connected,
                                       on_disconnect_cb=mqtt_disconnected,
                                       on_message_cb=mqtt_message)
    min_iot_network = Network.create_min_iot("BPI")

    # Work-around: enable AP to disable power saving mode
    wifi.radio.start_ap("noop", "12345678")

    if not mqtt_network.connect():
        logger.critical("Failed to connect to MQTT network. Rebooting...")
        reload()

    if not min_iot_network.connect():
        logger.critical("Failed to connect to MinIOT network. Rebooting...")
        reload()

    try:
        min_iot_task = asyncio.create_task(min_iot_client(min_iot_network))
        mqtt_loop_task = asyncio.create_task(mqtt_loop(mqtt_network))
        mqtt_send_task = asyncio.create_task(mqtt_send(mqtt_network))
        time_sync_task = asyncio.create_task(time_sync(mqtt_network, config["time_sync_rate_sec"]))

        await asyncio.gather(min_iot_task, mqtt_loop_task, mqtt_send_task, time_sync_task)
    except Exception as exc:
        logger.critical("Caught unexpected exception:")
        logger.critical(f"{''.join(traceback.format_exception(exc, chain=True))}")
        logger.critical("Rebooting...")
        reload()


asyncio.run(main())
