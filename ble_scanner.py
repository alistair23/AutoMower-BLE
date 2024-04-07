"""
    Adopted from the example provided by the Bleak library:
    https://github.com/hbldh/bleak/blob/develop/examples/discover.py
"""

import argparse
import asyncio

from bleak import BleakScanner


async def main(args: argparse.Namespace):
    print(f"Scanning for {args.timeout} seconds, please wait...")

    devices = await BleakScanner.discover(
        timeout=args.timeout,
        return_adv=True,
        cb=dict(use_bdaddr=args.macos_use_bdaddr),
    )

    husqvarna_device_found = False
    for d, a in devices.values():

        # "Husqvarna AB" maps to "0x0426" for the manufacturer data
        # Please see: https://bitbucket.org/bluetooth-SIG/public/src/main/assigned_numbers/company_identifiers/company_identifiers.yaml
        if list(a.manufacturer_data.keys())[0]== 0x0426 or args.show_all:
            if not husqvarna_device_found and not args.show_all:
                print("Husqvarna device(s) found!")
                husqvarna_device_found = True

            print(f"\nAddress: {d.address}")
            print(f"\tName: {d.name}")
            print(f"\tSignal Strength: {a.rssi} dBm (closer to 0 is stronger)")
            if args.show_all:
                print(f"\tManufacturer Data: {a.manufacturer_data}")

    if not husqvarna_device_found and not args.show_all:
        print("No Husqvarna devices found!\nMake sure your Automower is powered on and nearby.")

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument(
       "--macos-use-bdaddr",
       action="store_true",
       help="when true use Bluetooth address instead of UUID on macOS",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="Duration (seconds) to scan for BLE devices. Default = 15 seconds",
    )
    parser.add_argument(
        "--show-all",
        action="store_true",
        help="Scan and show all devices found, not just only Husqvarna devices.",
    )
    args = parser.parse_args()
    asyncio.run(main(args))
