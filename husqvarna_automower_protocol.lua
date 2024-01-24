do
	automower_request = Proto("automower_request", "Husqvarna AutoMower Request Protocol")

	automower_data = ProtoField.new("Data", "btatt.value", ftypes.BYTES, nil, base.NONE)
	automower_header = ProtoField.new("Header", "automower.header", ftypes.UINT16, nil, base.HEX)
	automower_length = ProtoField.new("Length", "automower.length", ftypes.UINT8, nil, base.HEX)
	automower_channel_id = ProtoField.new("ChannelId", "automower.channel_id", ftypes.UINT8, nil, base.HEX)
	automower_bool = ProtoField.new("Unknown Bool", "automower.bool", ftypes.UINT8, nil, base.HEX)
	automower_first_crc = ProtoField.new("First CRC", "automower.first_crc", ftypes.UINT8, nil, base.HEX)
	automower_request_major = ProtoField.new("Request Major", "automower.request_major", ftypes.UINT8, nil, base.DEC)
	automower_request_minor = ProtoField.new("Request Minor", "automower.request_minor", ftypes.UINT8, nil, base.DEC)
	automower_request_data = ProtoField.new("Request Data", "automower.request_data", ftypes.UINT8, nil, base.HEX)
	automower_full_crc = ProtoField.new("Full CRC", "automower.full_crc", ftypes.UINT8, nil, base.HEX)
	automower_footer = ProtoField.new("Footer", "automower.footer", ftypes.UINT8, nil, base.HEX)

	automower_request.fields = { automower_data, automower_header, automower_length, automower_channel_id, automower_bool, automower_first_crc, automower_request_major, automower_request_minor, automower_request_data, automower_full_crc, automower_footer }

	function undecoded_automower_request(tvb, pinfo, tree)
		pinfo.cols.protocol = "HCI_EVT"
		subtree = tree:add_le(btcommon_eir_ad_entry_data, tvb())
		subtree:add_proto_expert_info(btcommon_eir_ad_entry_data_undecoded, "Undecoded")
	end

	function automower_request.dissector(tvb, pinfo, tree)
		if tvb:len() == 0 then return end

		pinfo.cols.protocol = automower_request.name

		subtree = tree:add(automower_request, tvb(), "Husqvarna AutoMower Protocol")

		if not tvb(0,2):uint() == 0xFD02 then
			undecoded_automower_request(tvb, pinfo, tree)
			return
		end
		subtree:add_le(automower_header, tvb(0,2))

		subtree:add_le(automower_length, tvb(2,1))

		if not tvb(3,1):uint() == 0x00 then
			undecoded_automower_request(tvb, pinfo, tree)
			return
		end

		if tvb(4,4):uint() == 0x00 then
			undecoded_automower_request(tvb, pinfo, tree)
			return
		end
		subtree:add_le(automower_channel_id, tvb(4,4))

		subtree:add_le(automower_bool, tvb(8,1))

		subtree:add_le(automower_first_crc, tvb(9,1))

		if not tvb(10,1):uint() == 0x00 then
			undecoded_automower_request(tvb, pinfo, tree)
			return
		end

		if not tvb(11,1):uint() == 0xAF then
			undecoded_automower_request(tvb, pinfo, tree)
			return
		end

		subtree:add_le(automower_request_major, tvb(12,2))
		subtree:add_le(automower_request_minor, tvb(14,1))

		subtree:add_le(automower_request_data, tvb(15,tvb:len() - 17))

		subtree:add_le(automower_full_crc, tvb(tvb:len() - 2,1))

		if not tvb(tvb:len() - 1,1):uint() == 0x03 then
			undecoded_automower_request(tvb, pinfo, tree)
			return
		end
		subtree:add_le(automower_footer, tvb(tvb:len() - 1,1))
	end

	ble_dis_table = DissectorTable.get("btatt.handle")
	ble_dis_table:add(0x000b,automower_request) -- Husqvarna --
end