import argparse
import asyncio
import logging
from datetime import datetime, timezone

from automower_ble.mower import Mower
from automower_ble.error_codes import ErrorCodes
from bleak import BleakScanner


async def main(mower: Mower):
    device = await BleakScanner.find_device_by_address(mower.address)

    if device is None:
        print("Unable to connect to device address: " + mower.address)
        print(
            "Please make sure the device address is correct, the device is powered on and nearby"
        )
        return

    await mower.connect(device)

    manufacturer = await mower.get_manufacturer()
    print("Mower manufacturer: " + manufacturer)

    model = await mower.get_model()
    print("Mower model: " + model)

    charging = await mower.is_charging()
    if charging:
        print("Mower is charging")
    else:
        print("Mower is not charging")

    battery_level = await mower.battery_level()
    print("Battery is: " + str(battery_level) + "%")

    state = await mower.mower_state()
    if state is not None:
        print("Mower state: " + state.name)

    activity = await mower.mower_activity()
    if activity is not None:
        print("Mower activity: " + activity.name)

    next_start_time = await mower.mower_next_start_time()
    if next_start_time:
        print("Next start time: " + next_start_time.strftime("%Y-%m-%d %H:%M:%S"))
    else:
        print("No next start time")

    statuses = await mower.command("GetAllStatistics")
    for status, value in statuses.items():
        print(status, value)

    serial_number = await mower.command("GetSerialNumber")
    print("Serial number: " + str(serial_number))

    mower_name = await mower.command("GetUserMowerNameAsAsciiString")
    print("Mower name: " + mower_name)

    # print("Running for 3 hours")
    # await mower.mower_override()

    # print("Pause")
    # await mower.mower_pause()

    # print("Resume")
    # await mower.mower_resume()

    # activity = await mower.mower_activity()
    # print("Mower activity: " + activity)

    # If command argument passed then send command
    if args.command:
        print("Sending command to control mower (" + args.command + ")")
        match args.command:
            case "park":
                print("command=park")
                cmd_result = await mower.mower_park()
            case "pause":
                print("command=pause")
                cmd_result = await mower.mower_pause()
            case "resume":
                print("command=resume")
                cmd_result = await mower.mower_resume()
            case "override":
                print("command=override")
                cmd_result = await mower.mower_override()
            case _:
                print("command=??? (Unknown command: " + args.command + ")")
        print("command result = " + str(cmd_result))

    # moved last message after command, this seems to cause all future commands/queries to fail
    last_message = await mower.command("GetMessage", messageId=0)
    print("Last message: ")
    print(
        "\t"
        + datetime.fromtimestamp(last_message["time"], timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )
    print("\t" + ErrorCodes(last_message["code"]).name)

    await mower.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    device_group = parser.add_mutually_exclusive_group(required=True)

    device_group.add_argument(
        "--address",
        metavar="<address>",
        help="the Bluetooth address of the Automower device to connect to",
    )

    parser.add_argument(
        "--pin",
        metavar="<code>",
        type=int,
        default=None,
        help="Send PIN to authenticate. This feature is experimental and might not work.",
    )

    parser.add_argument(
        "--command",
        metavar="<command>",
        default=None,
        help="Send command to control mower (one of resume, pause, park or override)",
    )

    args = parser.parse_args()

    mower = Mower(1197489078, args.address, args.pin)

    log_level = logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)-15s %(name)-8s %(levelname)s: %(message)s",
    )

    asyncio.run(main(mower))
