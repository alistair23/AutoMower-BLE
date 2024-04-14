import binascii
from helpers import crc

class Command:

    def __init__(
        self,
        name: str,
        command: tuple[int, int],
        response_data_type: str | dict | None = None,
        payload: bytearray = b"\x00\x00\x00",
        request_data_type: str | None = None,
    ):
        self.name = name
        self.command = command
        self.payload = payload
        self.request_data_type = request_data_type

        if type(response_data_type) is not dict: # Always wrap in list
            self.response_data_type = {self.name:response_data_type}
        else:
            self.response_data_type = response_data_type
        self.request_data = bytearray()

    def generate_request(self, channel_id, extra_payload=None) -> None:
        self.request_data = bytearray(15)
        self.request_data[0] = 0x02 # Hard coded value
        self.request_data[1] = 0xFD # Hard coded value
        self.request_data[2] = 0x00 # Length, Updated later
        self.request_data[3] = 0x00 # Hard coded value

        # ChannelID
        id = channel_id.to_bytes(4, byteorder="little")
        self.request_data[4] = id[0]
        self.request_data[5] = id[1]
        self.request_data[6] = id[2]
        self.request_data[7] = id[3]

        self.request_data[8]= 0x01 # The third argument to e(int i10, int i11, boolean z10, T t10). Almost always 1

        self.request_data[9]=0x00  # CRC, Updated later
        self.request_data[10]=0x00 # Hard coded value
        self.request_data[11]=0xAF # Hard coded value

        major = self.command[0].to_bytes(2, byteorder="little")
        minor = self.command[1]

        self.request_data[12] = major[0]
        self.request_data[13] = major[1]
        self.request_data[14] = minor

        self.request_data += self.payload

        if extra_payload:
            self.request_data += extra_payload

        self.request_data[2] = len(self.request_data) - 2  # Length

        self.request_data[9] = crc(self.request_data, 1, 8)# CRC
        
        # Two last bytes are crc and 0x03
        self.request_data.append(crc(self.request_data, 1, len(self.request_data) - 1))
        self.request_data.append(0x03)# Hard coded value

        print(str(binascii.hexlify(self.request_data)))

    def parse_response(self, response_data: bytearray) -> int | None:
        # Skip validation for bytes 0-16 for now
        response_length = response_data[17]
        data = response_data[19:19 + response_length]
        response = dict()
        dpos = 0 # data position
        for name, dtype in self.response_data_type.items(): 
            if (dtype == "tUnixTime") or (dtype == "uint32"):
                response[name]=int.from_bytes(data[dpos : dpos + 4], byteorder="little")
                
                dpos += 4
            elif dtype == "uint8":
                response[name] = data[dpos]
                dpos += 1
            else:
                raise ValueError("Unknown data type: " + dtype)
        if dpos != len(data):
            raise ValueError("Data length mismatch. Read %d bytes of %d" % (dpos, len(data)))
        
        return response

    def __str__(self):
        return "Command: %s, %s" % (self.name, self.command)

cmd = Command("nextStartTime", (4658, 1), "tUnixTime")
print(
    cmd.parse_response(
        binascii.a2b_hex("02fd1500b63b6047016801af3212010000040000000000aa03")
    )
)
print(
    cmd.parse_response(
        binascii.a2b_hex('02fd1500b63b6047016801af32120100000400204c1e66d803')
    )
)
cmd = Command("numberOfMessages", (4730, 0), "uint32")
cmd = Command("batteryLevel", (4106, 20), "uint8")
cmd = Command("getMessage", (4730, 1), {"messageTime":"tUnixTime", "code":"uint32", "severity":"uint8"})

print(
    cmd.parse_response(
        binascii.a2b_hex('02fd1a00b63b6047012a01af7a120100000900a06c5e6432000000035903')
    )
)
cmd = Command(
    "getStatuses",
    (4726, 0),
    {
        "totalRunningTime": "uint32",
        "totalCuttingTime": "uint32",
        "totalChargingTime": "uint32",
        "totalSearchingTime": "uint32",
        "numberOfCollisions": "uint32",
        "numberOfChargingCycles": "uint32",
        "cuttingBladeUsageTime": "uint32",
    },
)


print(
    cmd.parse_response(
        binascii.a2b_hex(
            "02fd2d00b63b6047018d01af76120000001c009af32a00b8082800ebc01b00e2ea02008005000069020000b9082800f703"
        )
    )
)
