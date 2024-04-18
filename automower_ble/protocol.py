import binascii
from .helpers import crc

class Command:
    def __init__(
        self,
        channel_id: int,
        parameter: dict
    ):
        self.channel_id = channel_id

        self.major = parameter["major"]
        self.minor = parameter["minor"]

        if "requestType" in parameter:
            self.request_data_type = parameter["requestType"]
        else:
            self.request_data_type = None

        if type(parameter["responseType"]) is not dict:  # Always wrap in list
            self.response_data_type = {"response": parameter["responseType"]}
        else:
            self.response_data_type = parameter["responseType"]
        self.request_data = bytearray()

    def generate_request(self, **kwargs) -> bytearray:
        self.request_data = bytearray(18)
        self.request_data[0] = 0x02 # Hard coded value
        self.request_data[1] = 0xFD # Hard coded value
        self.request_data[2] = 0x00 # Length, Updated later
        self.request_data[3] = 0x00 # Hard coded value

        # ChannelID
        id = self.channel_id.to_bytes(4, byteorder="little")
        self.request_data[4] = id[0]
        self.request_data[5] = id[1]
        self.request_data[6] = id[2]
        self.request_data[7] = id[3]

        self.request_data[8]= 0x01 # The third argument to e(int i10, int i11, boolean z10, T t10). Almost always 1

        self.request_data[9]=0x00  # CRC, Updated later
        self.request_data[10]=0x00 # Hard coded value
        self.request_data[11]=0xAF # Hard coded value

        major_bytes = self.major.to_bytes(2, byteorder="little")

        self.request_data[12] = major_bytes[0]
        self.request_data[13] = major_bytes[1]
        self.request_data[14] = self.minor

        self.request_data[15] = 0x00 # Hard coded value

        # Byte 16 represents length of request data type
        request_length = 0
        request_data = bytearray()
        if self.request_data_type is not None:
            for request_name, request_type in self.request_data_type.items():
                if request_name not in kwargs:
                    raise ValueError("Missing request parameter: " + request_name + " for command (" + str(self.major) + ", " + str(self.minor)+")")

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

        self.request_data[17] = 0x00 # Hard coded value

        if request_length > 0:
            self.request_data += request_data

        self.request_data[2] = len(self.request_data) - 2  # Length

        self.request_data[9] = crc(self.request_data, 1, 8)# CRC

        # Two last bytes are crc and 0x03
        self.request_data.append(crc(self.request_data, 1, len(self.request_data) - 1))
        self.request_data.append(0x03)# Hard coded value

        return self.request_data

    def parse_response(self, response_data: bytearray) -> int | None:
        # Skip validation for bytes 0-16 for now
        response_length = response_data[17]
        data = response_data[19:19 + response_length]
        response = dict()
        dpos = 0 # data position
        for name, dtype in self.response_data_type.items(): 
            if (dtype == "no_response"):
                return None
            elif (dtype == "tUnixTime") or (dtype == "uint32"):
                response[name]=int.from_bytes(data[dpos : dpos + 4], byteorder="little")
                dpos += 4
            elif dtype == "uint16":
                response[name]=int.from_bytes(data[dpos : dpos + 2], byteorder="little")
                dpos += 2
            elif (dtype == "uint8") or (dtype == "bool"):
                response[name] = data[dpos]
                dpos += 1
            else:
                raise ValueError("Unknown data type: " + dtype)
        if dpos != len(data):
            raise ValueError("Data length mismatch. Read %d bytes of %d" % (dpos, len(data)))

        return response


def generate_request_setup_channel_id(channel_id: int) -> bytearray:
    """
    Setup the channelID with an Automower, this is the first
    command that should be sent
    """
    data = bytearray.fromhex("02fd160000000000002e1400000000000000004d61696e00")

    # New ChannelID
    id = channel_id.to_bytes(4, byteorder="little")
    data[11] = id[0]
    data[12] = id[1]
    data[13] = id[2]
    data[14] = id[3]

    # CRC and end byte
    data[9] = crc(data, 1, 8)
    data.append(crc(data, 1, len(data) - 1))
    data.append(0x03)

    return data


def generate_request_handshake(channel_id: int) -> bytearray:
    """
    Generate a request handshake. This should be called after
    the channel id is set up but before other commands
    """
    data = bytearray.fromhex("02fd0a000000000000d00801")

    id = channel_id.to_bytes(4, byteorder="little")
    data[4] = id[0]
    data[5] = id[1]
    data[6] = id[2]
    data[7] = id[3]

    # CRCs and end byte
    data[9] = crc(data, 1, 8)
    data.append(crc(data, 1, len(data) - 1))
    data.append(0x03)

    return data