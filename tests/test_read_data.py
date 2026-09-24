import unittest

from automower_ble.protocol import BLEClient


class TestReadData(unittest.IsolatedAsyncioTestCase):
    async def test_disconnect_mid_response(self):
        client = BLEClient(1197489078, "00:00:00:00:00:00")
        # First chunk announces more data, then disconnect() enqueues None
        await client.queue.put(bytearray.fromhex("02fd1100b63b6047"))
        await client.queue.put(None)
        self.assertIsNone(await client._read_data())


if __name__ == "__main__":
    unittest.main()
