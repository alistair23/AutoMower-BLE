import binascii
from automower_ble.helpers import crc
from enum import IntEnum
import asyncio
import logging
import json
from importlib.resources import files
from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic

logger = logging.getLogger(__name__)


class ModeOfOperation(IntEnum):
    # ProtocolTypes$IMowerAppMowerMode, used in modeOfOperation: 4586, 1
    # Comments from: https://developer.husqvarnagroup.cloud/apis/Automower+Connect+API?tab=status%20description%20and%20error%20codes#user-content-mode
    AUTO = 0
    MANUAL = 1
    HOME = 2  # Mower goes home and parks forever. Week schedule is not used. Cannot be overridden with forced mowing.
    DEMO = 3  # Same as main area, but shorter times. No blade operation
    POI = 4


class MowerState(IntEnum):
    # ProtocolTypes$IMowerAppState, used in mowerState: 4586, 2
    # Comments from: https://developer.husqvarnagroup.cloud/apis/Automower+Connect+API?tab=status%20description%20and%20error%20codes#user-content-state
    OFF = 0  # Mower is turned off.
    WAIT_FOR_SAFETYPIN = 1
    STOPPED = 2  # Mower is stopped requires manual action.
    FATAL_ERROR = 3
    PENDING_START = 4
    PAUSED = 5  # Mower has been paused by user.
    IN_OPERATION = 6  # See value in activity for status.
    RESTRICTED = (
        7  # Mower can currently not mow due to week calender, or override park.
    )
    ERROR = 8  # An error has occurred. Check errorCode. Mower requires manual action.


class MowerActivity(IntEnum):
    # ProtocolTypes$IMowerAppActivity, used in mowerActivity: 4586, 3
    # Comments from: https://developer.husqvarnagroup.cloud/apis/Automower+Connect+API?tab=status%20description%20and%20error%20codes#user-content-activity
    NONE = 0
    CHARGING = 1  # Mower is charging in station due to low battery.
    GOING_OUT = 2
    MOWING = 3  # Mower is mowing lawn. If in demo mode the blades are not in operation.
    GOING_HOME = 4  # Mower is going home to the charging station.
    PARKED = 5
    STOPPED_IN_GARDEN = 6  # Mower has stopped. Needs manual action to resume


class OverrideAction(IntEnum):
    NONE = 0
    FORCEDPARK = 1
    FORCEDMOW = 2


class TaskInformation(object):
    def __init__(
        self,
        next_start_time,
        duration_in_seconds,
        on_monday,
        on_tuesday,
        on_wednesday,
        on_thursday,
        on_friday,
        on_saturday,
        on_sunday,
    ):
        self.next_start_time = next_start_time
        self.duration_in_seconds = duration_in_seconds
        self.on_monday = on_monday
        self.on_tuesday = on_tuesday
        self.on_wednesday = on_wednesday
        self.on_thursday = on_thursday
        self.on_friday = on_friday
        self.on_saturday = on_saturday
        self.on_sunday = on_sunday


class Command:
    def __init__(self, channel_id: int, parameter: dict):
        self.channel_id = channel_id

        self.major = parameter["major"]
        self.minor = parameter["minor"]

        if "requestType" in parameter:
            self.request_data_type = parameter["requestType"]
        else:
            self.request_data_type = None

        if "responseType" not in parameter:
            parameter["responseType"] = "no_response"

        if not isinstance(parameter["responseType"], dict):  # Always wrap in list
            self.response_data_type = {"response": parameter["responseType"]}
        else:
            self.response_data_type = parameter["responseType"]
        self.request_data = bytearray()

    def generate_request(self, **kwargs) -> bytearray:
        self.request_data = bytearray(18)
        self.request_data[0] = 0x02  # Hard coded value (start of packet)
        self.request_data[1] = 0xFD  # 0xFD = LINKED_PACKET_TYPE
        self.request_data[2] = 0x00  # Length, low byte, updated later
        self.request_data[3] = 0x00  # Length, high byte, updated later

        # ChannelID
        id = self.channel_id.to_bytes(4, byteorder="little")
        self.request_data[4] = id[0]
        self.request_data[5] = id[1]
        self.request_data[6] = id[2]
        self.request_data[7] = id[3]

        self.request_data[8] = 0x01  # is_linked (usually 0x01)

        self.request_data[9] = 0x00  # CRC, Updated later
        self.request_data[10] = (
            0x00  # Packet type (0x00 = request, 0x01 = response, 0x02 = event)
        )
        self.request_data[11] = 0xAF  # Hard coded value

        major_bytes = self.major.to_bytes(2, byteorder="little")

        self.request_data[12] = major_bytes[0]  # low byte of 'module'
        self.request_data[13] = major_bytes[1]  # high byte of 'module'
        self.request_data[14] = self.minor  # low byte of 'command'
        self.request_data[15] = 0x00  # high byte of 'command'

        # Byte 16 represents length of request data type
        request_length = 0
        request_data = bytearray()
        if self.request_data_type is not None:
            for request_name, request_type in self.request_data_type.items():
                if request_name not in kwargs:
                    raise ValueError(
                        "Missing request parameter: "
                        + request_name
                        + " for command ("
                        + str(self.major)
                        + ", "
                        + str(self.minor)
                        + ")"
                    )

                if request_type == "uint32":
                    request_length += 4
                    request_data += kwargs[request_name].to_bytes(4, byteorder="little")
                elif request_type == "uint16":
                    request_length += 2
                    request_data += kwargs[request_name].to_bytes(2, byteorder="little")
                elif request_type == "uint8":
                    request_length += 1
                    request_data += kwargs[request_name].to_bytes(1, byteorder="little")
                else:
                    raise ValueError("Unknown request type: " + self.request_type)
        self.request_data[16] = request_length

        self.request_data[17] = 0x00  # high byte of request_length
        if request_length > 0:
            self.request_data += request_data

        self.request_data[2] = len(self.request_data) - 2  # Length

        self.request_data[9] = crc(self.request_data, 1, 8)  # CRC

        # Two last bytes are crc and 0x03
        self.request_data.append(crc(self.request_data, 1, len(self.request_data) - 1))
        self.request_data.append(0x03)  # Hard coded value

        return self.request_data

    def parse_response(self, response_data: bytearray) -> int | str | dict | None:
        response_length = response_data[17]
        data = response_data[19 : 19 + response_length]
        response = dict()
        dpos = 0  # data position
        for name, dtype in self.response_data_type.items():
            if dtype == "no_response":
                return None
            elif (dtype == "tUnixTime") or (dtype == "uint32"):
                response[name] = int.from_bytes(
                    data[dpos : dpos + 4], byteorder="little"
                )
                dpos += 4
            elif dtype == "uint16":
                response[name] = int.from_bytes(
                    data[dpos : dpos + 2], byteorder="little"
                )
                dpos += 2
            elif (dtype == "uint8") or (dtype == "bool"):
                response[name] = data[dpos]
                dpos += 1
            elif dtype == "ascii":
                if len(self.response_data_type) != 1:
                    raise ValueError(
                        "ASCII response type can currently only be used when there is only one response type"
                    )
                response[name] = data.decode("ascii").rstrip(
                    "\x00"
                )  # Remove trailing null bytes
                dpos += len(data)
            else:
                raise ValueError("Unknown data type: " + dtype)
        if dpos != len(data):
            raise ValueError(
                "Data length mismatch. Read %d bytes of %d" % (dpos, len(data))
            )
        return response

    def validate_response(self, response_data: bytearray) -> bool:
        if response_data[0] != 0x02:
            return False

        if response_data[1] != 0xFD:
            return False

        if response_data[3] != 0x00:  # high byte of length
            return False

        id = self.channel_id.to_bytes(4, byteorder="little")
        if response_data[4] != id[0]:
            return False
        if response_data[5] != id[1]:
            return False
        if response_data[6] != id[2]:
            return False
        if response_data[7] != id[3]:
            return False

        if response_data[8] != 0x01:
            # This is a valid config, but we don't support it
            # return m1656b(decodeState, c10786f);
            return False

        if response_data[9] != crc(response_data, 1, 8):
            return False

        if response_data[10] != 0x01:  # packet type is not 0x01 = response
            return False

        if response_data[11] != 0xAF:
            return False

        major_bytes = self.major.to_bytes(4, byteorder="little")
        if response_data[12] != major_bytes[0]:
            return False
        if response_data[13] != major_bytes[1]:
            return False
        if response_data[14] != self.minor:
            return False

        if response_data[15] != 0x00:  # high byte of 'command' (self.minor)
            return False

        if (
            response_data[16] != 0x00
        ):  # result: OK(0), UNKNOWN_ERROR(1), INVALID_VALUE(2), OUT_OF_RANGE(3), NOT_AVAILABLE(4), NOT_ALLOWED(5), INVALID_GROUP(6), INVALID_ID(7), DEVICE_BUSY(8), INVALID_PIN(9), MOWER_BLOCKED(10);
            return False

        return True


class BLEClient:
    def __init__(self, channel_id: int, address, pin=None):
        self.channel_id = channel_id
        self.address = address
        self.pin = pin
        self.MTU_SIZE = 20

        self.queue = asyncio.Queue()

        self.protocol = None

    async def get_protocol(self):
        if self.protocol is None:

            def read_protocol_file():
                with files("automower_ble").joinpath("protocol.json").open("r") as f:
                    return json.load(f)

            self.protocol = await asyncio.get_running_loop().run_in_executor(
                None, read_protocol_file
            )
        return self.protocol

    async def _get_response(self):
        try:
            data = await asyncio.wait_for(self.queue.get(), timeout=10)

        except TimeoutError:
            logger.error("Unable to get response from device: '%s'", self.address)
            if self.is_connected():
                await self.disconnect()
            return None

        return data

    async def _write_data(self, data):
        logger.info("Writing: " + str(binascii.hexlify(data)))

        chunk_size = self.MTU_SIZE - 3
        for chunk in (
            data[i : i + chunk_size] for i in range(0, len(data), chunk_size)
        ):
            await self.client.write_gatt_char(self.write_char, chunk, response=False)

        logger.debug("Finished writing")

    async def _read_data(self):
        data = await self._get_response()

        if data is None:
            return None

        if len(data) < 3:
            # We got such a small amount of data, let's try again
            data = data + await self._get_response()

            if len(data) < 3:
                # Something is wrong
                return None

        length = data[2] + 4

        logger.debug("Waiting for %d bytes", length)

        while len(data) < length:
            try:
                data = data + await asyncio.wait_for(self.queue.get(), timeout=5)
            except TimeoutError:
                logger.error(
                    "Unable to get full response from device: '%s', currently have"
                    + str(binascii.hexlify(data)),
                    self.address,
                )
                logger.error("Expecting %d bytes, only have %d", length, len(data))
                return None

        logger.info("Final response: " + str(binascii.hexlify(data)))

        return data

    async def _request_response(self, request_data):
        i = 5
        while i > 0:
            try:
                # If there are previous responses, flush them out
                while not self.queue.empty():
                    await self.queue.get()

                await self._write_data(request_data)

                response_data = await self._read_data()
                if response_data is None:
                    i = i - 1
                    continue

            except asyncio.exceptions.CancelledError:
                logger.debug("Received CancelledError")
                i = i - 1
                continue

            break

        if i == 0:
            logger.error("Unable to communicate with device: '%s'", self.address)
            if self.is_connected():
                await self.disconnect()
            return None

        return response_data

    async def connect(self, device) -> bool:
        """
        Connect to a device and setup the channel

        Returns True on success
        """
        logger.info("starting scan...")

        if device is None:
            logger.error("could not find device with address '%s'", self.address)
            return False

        logger.info("connecting to device...")
        self.client = BleakClient(
            device, services=["98bd0001-0b0e-421a-84e5-ddbf75dc6de4"], use_cached=True
        )
        await self.client.connect()
        logger.info("connected")

        logger.info("pairing device...")
        await self.client.pair()
        logger.info("paired")

        self.client._backend._mtu_size = self.MTU_SIZE

        for service in self.client.services:
            logger.info("[Service] %s", service)

            for char in service.characteristics:
                if "read" in char.properties:
                    try:
                        value = await self.client.read_gatt_char(char.uuid)
                        logger.debug(
                            "  [Characteristic] %s (%s), Value: %r",
                            char,
                            ",".join(char.properties),
                            value,
                        )
                    except Exception as e:
                        logger.error(
                            "  [Characteristic] %s (%s), Error: %s",
                            char,
                            ",".join(char.properties),
                            e,
                        )

                else:
                    logger.debug(
                        "  [Characteristic] %s (%s)", char, ",".join(char.properties)
                    )
                if char.uuid == "98bd0002-0b0e-421a-84e5-ddbf75dc6de4":
                    self.write_char = char

                if char.uuid == "98bd0003-0b0e-421a-84e5-ddbf75dc6de4":
                    self.read_char = char

        async def notification_handler(
            characteristic: BleakGATTCharacteristic, data: bytearray
        ):
            logger.info("Received: " + str(binascii.hexlify(data)))
            await self.queue.put(data)

        await self.client.start_notify(self.read_char, notification_handler)

        await asyncio.sleep(5.0)

        request = self.generate_request_setup_channel_id()
        response = await self._request_response(request)
        if response is None:
            return False

        ### TODO: Check response

        request = self.generate_request_handshake()
        response = await self._request_response(request)
        if response is None:
            return False

        ### TODO: Check response

        if self.pin is not None:
            command = Command(
                self.channel_id, (await self.get_protocol())["EnterOperatorPin"]
            )
            request = command.generate_request(code=self.pin)
            response = await self._request_response(request)
            if response is None:
                return False

        return True

    def is_connected(self) -> bool:
        return self.client.is_connected

    async def probe_gatts(self, device):
        logger.info("connecting to device...")
        client = BleakClient(
            device, services=["98bd0001-0b0e-421a-84e5-ddbf75dc6de4"], use_cached=True
        )

        await client.connect()
        logger.info("connected")

        manufacture = None
        model = None
        device_type = None

        for service in client.services:
            logger.debug("[Service] %s", service)

            if service.uuid == "98bd0001-0b0e-421a-84e5-ddbf75dc6de4":
                manufacture = service.description

            for char in service.characteristics:
                if "read" in char.properties:
                    try:
                        value = await client.read_gatt_char(char.uuid)
                        logger.debug(
                            "  [Characteristic] %s (%s), Value: %r",
                            char,
                            ",".join(char.properties),
                            value,
                        )
                    except Exception as e:
                        logger.error(
                            "  [Characteristic] %s (%s), Error: %s",
                            char,
                            ",".join(char.properties),
                            e,
                        )

                else:
                    logger.debug(
                        "  [Characteristic] %s (%s)", char, ",".join(char.properties)
                    )

                if char.uuid == "00002a00-0000-1000-8000-00805f9b34fb":
                    model = (await client.read_gatt_char(char)).decode()

                if char.uuid == "98bd0004-0b0e-421a-84e5-ddbf75dc6de4":
                    device_type = (await client.read_gatt_char(char)).decode()

        await client.disconnect()

        return (manufacture, device_type, model)

    async def disconnect(self):
        """
        Disconnect from the mower, this should be called after every
        `connect()` before the Python script exits
        """

        await self.client.stop_notify(self.read_char)
        await self.queue.put(None)

        logger.info("disconnecting...")
        await self.client.disconnect()
        logger.info("disconnected")

    def generate_request_setup_channel_id(self) -> bytearray:
        """
        Setup the channelID with an Automower, this is the first
        command that should be sent
        """
        data = bytearray.fromhex("02fd160000000000002e1400000000000000004d61696e00")

        # New ChannelID
        id = self.channel_id.to_bytes(4, byteorder="little")
        data[11] = id[0]
        data[12] = id[1]
        data[13] = id[2]
        data[14] = id[3]

        # CRC and end byte
        data[9] = crc(data, 1, 8)
        data.append(crc(data, 1, len(data) - 1))
        data.append(0x03)

        return data

    def generate_request_handshake(self) -> bytearray:
        """
        Generate a request handshake. This should be called after
        the channel id is set up but before other commands
        """
        data = bytearray.fromhex("02fd0a000000000000d00801")

        id = self.channel_id.to_bytes(4, byteorder="little")
        data[4] = id[0]
        data[5] = id[1]
        data[6] = id[2]
        data[7] = id[3]

        # CRCs and end byte
        data[9] = crc(data, 1, 8)
        data.append(crc(data, 1, len(data) - 1))
        data.append(0x03)

        return data
