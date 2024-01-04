# AutoMower-BLE

This is an unofficial reverse engineered Husqvarna Automower Connect BLE library. This allows connecting and controlling an Automower without any accounts, cloud or network connection.

<noscript><a href="https://liberapay.com/alistair23/donate"><img alt="Donate using Liberapay" src="https://liberapay.com/assets/widgets/donate.svg"></a></noscript>

This library is written with the intent of integrating into Home Assistant, but it can be used independently as well.

Details on how this was developed are available at: https://www.alistair23.me/2024/01/06/reverse-engineering-automower-ble

This was developed and tested against a Automower 305, but it should work on all Automowers. If you are able to test on different models please do and report any results back.

## Testing Requests

You can run the request unit tests with

```shell
python3 ./request.py
```

## Testing Responses

You can run the response unit tests with

```shell
python3 ./response.py
```
## Testing Connections

You can test querying data and sending commands with the following

```shell
python3 ./mower.py --address D8:B6:73:40:07:37
```

You can uncomment parts of `async def main(mower)` to send commands
