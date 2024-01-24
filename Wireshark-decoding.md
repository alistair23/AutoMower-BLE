# Decoding data in Wireshark

This repo provides lua scripts to help decode BLE communication in Wireshark.

## Installing scripts

```shell
mkdir -p ~/.config/wireshark/plugins
cp *.lua ~/.config/wireshark/plugins/
```

Then restart Wireshark

## Monitoring requests

To monitor requests enter this in the filter

```
btatt.opcode == 0x52
```

That will display all requests from the application to the mower. You should
see a field called `Husqvarna AutoMower Protocol`. That should help decode
packets and debug issues/new requests.
