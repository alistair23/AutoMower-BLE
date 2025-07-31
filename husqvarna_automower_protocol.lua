do
	automower_reassembler = Proto("automower_reassembler", "Husqvarna AutoMower Reassembler")
	automower_reassembler_full_data = ProtoField.bytes("automower_reassembler.full_data", "Reassembled Data")
	automower_reassembler.fields = { automower_reassembler_full_data }

	automower_protocol = Proto("automower_protocol", "Husqvarna AutoMower Protocol")

	automower_header = ProtoField.new("Header", "automower.header", ftypes.UINT16, nil, base.HEX)
	automower_length = ProtoField.new("Length", "automower.length", ftypes.UINT8, nil, base.DEC)
	automower_channel_id = ProtoField.new("ChannelId", "automower.channel_id", ftypes.UINT8, nil, base.HEX)
	automower_bool = ProtoField.new("Unknown Bool", "automower.bool", ftypes.UINT8, nil, base.HEX)
	automower_first_crc = ProtoField.new("First CRC", "automower.first_crc", ftypes.UINT8, nil, base.HEX)
	automower_protocol_major = ProtoField.new("Request Major", "automower.request_major", ftypes.UINT8, nil, base.DEC)
	automower_protocol_major_text = ProtoField.new("Req Major", "automower.req_major", ftypes.STRING, nil, base.NONE)
	automower_protocol_minor_text = ProtoField.new("Req Minor", "automower.req_minor", ftypes.STRING, nil, base.NONE)
	automower_protocol_minor = ProtoField.new("Request Minor", "automower.request_minor", ftypes.UINT8, nil, base.DEC)
	automower_request_length = ProtoField.new("Request Length", "automower.request_length", ftypes.UINT8, nil, base.DEC)
	automower_response_length = ProtoField.new("Response Length", "automower.response_length", ftypes.UINT8, nil, base.DEC)
	automower_request_data = ProtoField.bytes("automower.request_data", "Request Data")
	automower_response_data = ProtoField.bytes("automower.response_data", "Response Data")
	automower_full_crc = ProtoField.new("Full CRC", "automower.full_crc", ftypes.UINT8, nil, base.HEX)
	automower_footer = ProtoField.new("Footer", "automower.footer", ftypes.UINT8, nil, base.HEX)

	automower_protocol.fields = { automower_header, automower_length, automower_channel_id, automower_bool, automower_first_crc,
			automower_protocol_major, automower_protocol_major_text, automower_protocol_minor,automower_protocol_minor_text,
			automower_request_length, automower_response_length, automower_request_data, automower_response_data, automower_full_crc, automower_footer }

	do
		local buffers = {}
		buffers[0x000b] = {} -- Request
		buffers[0x000e] = {} -- Response

		function find_packet_bounds(att_handle, current_num)
			local keys = {}
			for k in pairs(buffers[att_handle]) do
				table.insert(keys, k)
			end
			table.sort(keys)

			local start_index = nil
			local end_index = nil
			local concat = ByteArray.new()

			for _, num in ipairs(keys) do
				local tvb = buffers[att_handle][num]:tvb()
				if num <= current_num then
					if tvb:len() >= 2 and tvb(0,2):le_uint() == 0xFD02 then
						start_index = num
						concat = ByteArray.new()
					end
				end
				concat:append(buffers[att_handle][num])
				if num >= current_num then
					if tvb:len() >= 1 and tvb(tvb:len() - 1, 1):uint() == 0x03 then
						end_index = num
						return start_index, end_index, concat
					end
				end
			end

			return start_index, end_index, concat
		end

		function automower_reassembler.dissector(buffer, pinfo, tree)
			if buffer:len() < 13 then return end
			if buffer(7, 2):le_uint() ~= 0x0004 then return end -- Bluetooth L2CAP CID

			local att_handle = buffer(10, 2):le_uint()
			if (att_handle ~= 0x000b) and (att_handle ~= 0x000e) then return end
			local is_request = att_handle == 0x000b

			if buffers[att_handle][pinfo.number] == nil then
				buffers[att_handle][pinfo.number] = ByteArray.new()
				buffers[att_handle][pinfo.number]:append(buffer(12, buffer:len() - 12):bytes())
			end

			local start_index, end_index, concat = find_packet_bounds(att_handle, pinfo.number)
			if start_index and end_index then
				local reassembled_tvb = ByteArray.tvb(concat, "Reassembled Data")

				subtree = tree:add(automower_reassembler, buffer(), "Husqvarna AutoMower Reassembler")
				subtree:add(automower_reassembler_full_data, reassembled_tvb:range())

				automower_protocol_dissector(reassembled_tvb, pinfo, tree, is_request)
			end
		end
	end

	function undecoded_automower_protocol(tvb, pinfo, tree)
		pinfo.cols.protocol = "HCI_EVT"
		subtree = tree:add_le(btcommon_eir_ad_entry_data, tvb())
		subtree:add_proto_expert_info(btcommon_eir_ad_entry_data_undecoded, "Undecoded")
	end

	function automower_protocol_dissector(tvb, pinfo, tree, is_request)
		if tvb:len() == 0 then return end

		pinfo.cols.protocol = automower_protocol.name

		subtree = tree:add(automower_protocol, tvb(), "Husqvarna AutoMower Protocol")

		if not tvb(0,2):uint() == 0xFD02 then
			undecoded_automower_protocol(tvb, pinfo, tree)
			return
		end
		subtree:add_le(automower_header, tvb(0,2))

		subtree:add_le(automower_length, tvb(2,1))

		if not tvb(3,1):uint() == 0x00 then
			undecoded_automower_protocol(tvb, pinfo, tree)
			return
		end

		if tvb(4,4):uint() == 0x00 then
			undecoded_automower_protocol(tvb, pinfo, tree)
			return
		end
		subtree:add_le(automower_channel_id, tvb(4,4))

		subtree:add_le(automower_bool, tvb(8,1))

		subtree:add_le(automower_first_crc, tvb(9,1))

		if not tvb(10,1):uint() == 0x00 then
			undecoded_automower_protocol(tvb, pinfo, tree)
			return
		end

		if not tvb(11,1):uint() == 0xAF then
			undecoded_automower_protocol(tvb, pinfo, tree)
			return
		end

		minorText = ""
		maj = tvb(12, 2):uint()
		min = tvb(14, 1):uint()

		subtree:add_le(automower_protocol_major, tvb(12,2))
		if maj == 0x0A10 then -- BatteryCommands 4106
			subtree:add(automower_protocol_major_text, "BatteryCommands")
			if min == 0x00 then
				minorText = "getCapacityRequest"
			elseif min == 0x01 then
				minorText = "getEnergyLevelRequest"
			elseif min == 0x02 then
				minorText = "setSimulatedEnergyLevelRequest"
			elseif min == 0x03 then
				minorText = "getSimulatedEnergyLevelRequest"
			elseif min == 0x04 then
				minorText = "setSimulationRequest"
			elseif min == 0x05 then
				minorText = "getSimulationRequest"
			elseif min == 0x14 then
				minorText = "getBatteryLevelRequest"
			--elseif min == 0x01 => weird voltage request /
			elseif min == 0x15 then
				minorText = "isChargingRequest"
			elseif min == 0x16 then
				minorText = "getRemainingChargingTimeRequest"
			elseif min == 0x08 then
				minorText = "getBatteryCurrentRequest"
			elseif min == 0x09 then
				minorText = "getBatteryTemperatureRequest"
			elseif min == 0x0A then
				minorText = "getBatteryNbrChargingCyclesRequest"
			end
		elseif maj == 0xB010 then -- TemperatureCommands 4272
			subtree:add(automower_protocol_major_text, "TemperatureCommands")
			if min == 0x00 then
				minorText = "getTemperatureRequest"
			end
		elseif maj == 0x4611 then -- CuttingHeightCommands 4422
			subtree:add(automower_protocol_major_text, "CuttingHeightCommands")
			if min == 0x00 then
				minorText = "subscribeAllEventsRequest"
			elseif min == 0x01 then
				minorText = "subscribeEventChannelRequest"
			elseif min == 0x02 then
				minorText = "getCuttingHeightRequest"
			elseif min == 0x03 then
				minorText = "setCuttingHeightRequest"
			elseif min == 0x04 then
				minorText = "getAllSettingsRequest"
			elseif min == 0x05 then
				minorText = "getAvailableRequest"
			elseif min == 0x06 then
				minorText = "getHeightPercentageRequest"
			elseif min == 0x07 then
				minorText = "setHeightPercentageRequest"
			elseif min == 0x08 then
				minorText = "getDownCuttingEnabledRequest"
			elseif min == 0x09 then
				minorText = "setDownCuttingEnabledRequest"
			elseif min == 0x0A then
				minorText = "getDownCuttingAvailableRequest"
			elseif min == 0x0C then
				minorText = "getDownCuttingStatusRequest"
			elseif min == 0x0F then
				minorText = "getMinimumHeightRequest"
			elseif min == 0x11 then
				minorText = "getMaximumHeightRequest"
			elseif min == 0x13 then
				minorText = "getCurrentHeightPercentageRequest"
			elseif min == 0x19 then
				minorText = "getRaiseDistanceRequest"
			end
		elseif maj == 0x6C11 then -- AutotimerCommands 4460
			subtree:add(automower_protocol_major_text, "AutotimerCommands")
			if min == 0x00 then
				minorText = "subscribeAllEventsRequest"
			elseif min == 0x01 then
				minorText = "subscribeEventChannelRequest"
			elseif min == 0x02 then
				minorText = "getAvailableRequest"
			elseif min == 0x04 then
				minorText = "getEnabledRequest"
			elseif min == 0x05 then
				minorText = "setEnabledRequest"
			elseif min == 0x06 then
				minorText = "getSensitivityRequest"
			elseif min == 0x07 then
				minorText = "setSensitivityRequest"
			elseif min == 0x08 then
				minorText = "getAllSettingsRequest"
			end
		elseif maj == 0xEA11 then -- MowerAppCommands 4586
			subtree:add(automower_protocol_major_text, "MowerAppCommands")
			if  min == 0x0 then
				minorText = "modeOfOperation"
			elseif min == 0x01 then
				minorText = "getModeRequest"
			elseif min == 0x02 then
				minorText = "getStateRequest"
			elseif min == 0x03 then
				minorText = "getActivityRequest"
			elseif min == 0x04 then
				minorText = "startTriggerRequest"
			elseif min == 0x05 then
				minorText = "pauseRequest"
			elseif min == 0x06 then
				minorText = "getErrorRequest"
			elseif min == 0x07 then
				minorText = "subscribeAllEventsRequest"
			elseif min == 0x08 then
				minorText = "isErrorConfirmableRequest"
			elseif min == 0x09 then
				minorText = "confirmErrorRequest"
			elseif min == 0x0D then
				minorText = "getMissionRequest"
			elseif min == 0x0F then
				minorText = "abortStartTriggerRequest"
			elseif min == 0x13 then
				minorText = "getInactiveReasonRequest"
			end
		elseif maj == 0x3212 then -- PlannerCommands 4658
			subtree:add(automower_protocol_major_text, "PlannerCommands")
			if min == 0x00 then
				minorText = "getRestrictionReasonRequest"
			elseif min == 0x01 then
				minorText = "getNextStartTimeRequest"
			elseif min == 0x02 then
				minorText = "getOverrideRequest"
			elseif min == 0x03 then
				minorText = "setOverrideMowRequest"
			elseif min == 0x04 then
				minorText = "setOverrideParkRequest"
			elseif min == 0x05 then
				minorText = "setOverrideParkUntilNextStartRequest"
			elseif min == 0x06 then
				minorText = "clearOverrideRequest"
			end
		elseif maj == 0x3812 then -- AuthenticationCommands 4664
			subtree:add(automower_protocol_major_text, "AuthenticationCommands")
			if min == 0x00 then
				minorText = "getLoginLevelRequest"
			elseif min == 0x01 then
				minorText = "isBlockedRequest"
			elseif min == 0x02 then
				minorText = "getBlockedTimeRequest"
			elseif min == 0x03 then
				minorText = "isOperatorLoggedInRequest"
			elseif min == 0x04 then
				minorText = "enterOperatorPinRequest"
			elseif min == 0x05 then
				minorText = "setOperatorPinRequest"
			elseif min == 0x08 then
				minorText = "isTrustedToEnterSafetyPinRequest"
			elseif min == 0x0A then
				minorText = "initiateAuthenticationV2Request"
			elseif min == 0x0B then
				minorText = "challengeResponseV2Request"
			elseif min == 0x0E then
				minorText= "getSecurityCodeV2Request"
			elseif min == 0x0F then
				minorText = "logoutRequest"
			elseif min == 0x11 then
				minorText = "subscribeAllEventsRequest"
			elseif min == 0x17 then
				minorText = "isOperatorPinUserSelectedRequest"
			end
		elseif maj == 0x4212 then -- SystemPowerCommands 4674
			subtree:add(automower_protocol_major_text, "SystemPowerCommands")
			if min == 0x00 then
				minorText = "enableEventsRequest"
			elseif min == 0x01 then
				minorText = "getPowerModeRequest"
			elseif min == 0x02 then
				minorText = "keepAliveRequest"
			end
		elseif maj == 0x5212 then -- CalendarCommands 4690
			subtree:add(automower_protocol_major_text, "CalendarCommands")
			if min == 0x00 then
				minorText = "subscribeAllEventsRequest"
			elseif min == 0x01 then
				minorText = "subscribeEventChannelRequest"
			elseif min == 0x02 then
				minorText = "getTimeRequest"
			elseif min == 0x03 then
				minorText = "setTimeRequest"
			elseif min == 0x04 then
				minorText = "getNumberOfTasksRequest"
			elseif min == 0x05 then
				minorText = "getTaskRequest"
			elseif min == 0x06 then
				minorText = "setTaskRequest"
			elseif min == 0x07 then
				minorText= "addTaskRequest"
			elseif min == 0x08 then
				minorText = "deleteTaskRequest"
			elseif min == 0x09 then
				minorText = "deleteAllTaskRequest"
			elseif min == 0x0A then
				minorText = "startTaskTransactionRequest"
			elseif min == 0x0B then
				minorText = "commitTaskTransactionRequest"
			end
		elseif maj == 0x5412 then -- ChargingStationCommands 4692
			subtree:add(automower_protocol_major_text, "ChargingStationCommands")
			if min == 0x00 then
				minorText = "subscribeAllEventsRequest"
			elseif min == 0x01 then
				minorText = "subscribeEventChannelRequest"
			elseif min == 0x02 then
				minorText = "initiateNewPairingRequest"
			elseif min == 0x03 then
				minorText = "setMowerHouseInstalledRequest"
			elseif min == 0x04 then
				minorText = "getMowerHouseInstalledRequest"
			elseif min == 0x05 then
				minorText = "setEcoModeEnabledRequest"
			elseif min == 0x06 then
				minorText = "getEcoModeEnabledRequest"
			elseif min == 0x07 then
				minorText = "getAllSettingsRequest"
			end
		elseif maj == 0x5A12 then -- SystemCommands 4698
			subtree:add(automower_protocol_major_text, "SystemCommands")
			if min == 0x0 then
				minorText = "ClearStartupSequenceRequiredRequest"
			elseif min == 0x01 then
				minorText = "setStartupSequenceRequiredRequest"
			elseif min == 0x02 then
				minorText = "getStartupSequenceRequiredRequest"
			elseif min == 0x03 then
				minorText = "getUserMowerNameRequest"
			elseif min == 0x04 then
				minorText = "setUserMowerNameRequest"
			elseif min == 0x05 then
				minorText = "getUserMowerNameAsAciiStringRequest"
			elseif min == 0x06 then
				minorText = "setUserMowerNameAsAciiStringRequest"
			elseif min == 0x07 then
				minorText = "getLocalHmiAvailableRequest"
			elseif min == 0x08 then
				minorText = "resetToUserDefaultRequest"
			elseif min == 0x09 then
				minorText = "getModelRequest"
			elseif min == 0x0A then
				minorText = "getSerialNumberRequest"
			elseif min == 0x0C then
				minorText = "getConfigVersionStringRequest"
			elseif min == 0x0E then
				minorText = "getProductionTimeRequest"
			elseif min == 0x14 then
				minorText = "getSwUpdateRequiredRequest"
			elseif min == 0x16 then
				minorText = "getSwPackageVersionStringRequest"
			elseif min == 0x27 then
				minorText = "getForcedSwUpdateRequiredRequest"
			end
		elseif maj == 0x6212 then -- FollowWireCommands 4706
			subtree:add(automower_protocol_major_text, "FollowWireCommands")
			if min == 0x00 then
				minorText = "getBoundaryCorridorRequest"
			elseif min == 0x01 then
				minorText = "setBoundaryCorridorRequest"
			elseif min == 0x02 then
				minorText = "getGuideCorridorRequest"
			elseif min == 0x03 then
				minorText = "setGuideCorridorRequest"
			elseif min == 0x06 then
				minorText = "getStartingPointEnabledRequest"
			elseif min == 0x07 then
				minorText = "setStartingPointEnabledRequest"
			elseif min == 0x08 then
				minorText = "getStartingPointWireRequest"
			elseif min == 0x09 then
				minorText = "setStartingPointWireRequest"
			elseif min == 0x0A then
				minorText = "getStartingPointDistanceRequest"
			elseif min == 0x0B then
				minorText = "setStartingPointDistanceRequest"
			elseif min == 0x0C then
				minorText = "getStartingPointProportionRequest"
			elseif min == 0x0D then
				minorText = "setStartingPointProportionRequest"
			elseif min == 0x0E then
				minorText = "getNumberOfGuidesRequest"
			elseif min == 0x0F then
				minorText = "testStartingPointRequest"
			elseif min == 0x10 then
				minorText = "getCurrentDistanceRequest"
			elseif min == 0x11 then
				minorText = "testFollowInRequest"
			elseif min == 0x12 then
				minorText = "testAbortRequest"
			elseif min == 0x13 then
				minorText = "subscribeAllEventsRequest"
			elseif min == 0x14 then
				minorText = "subscribeEventChannelRequest"
			elseif min == 0x15 then
				minorText = "getStartingPointSettingsRequest"
			elseif min == 0x16 then
				minorText = "getTestModeRequest"
			elseif min == 0x17 then
				minorText = "getTestStateRequest"
            elseif min == 0x18 then
				minorText = "getBoundaryCorridorRequestG4"
			elseif min == 0x19 then
				minorText = "setBoundaryCorridorRequestG4"
			elseif min == 0x1A then
				minorText = "getPassageCuttingEnabledRequestG4"
			elseif min == 0x1B then
				minorText = "setPassageCuttingEnabledRequestG4"
			elseif min == 0x1C then
				minorText = "getStartingPointMaxRequest"
			elseif min == 0x1D then
				minorText = "getTestErrorRequest"
			end
		elseif maj == 0x6412 then -- SearchChargingStationCommands 4708
			subtree:add(automower_protocol_major_text, "SearchChargingStationCommands")
			if min == 0x00 then
				minorText = "getSearchTypeAvailableRequest"
			elseif min == 0x01 then
				minorText = "getEnabledRequest"
			elseif min == 0x02 then
				minorText = "setEnabledRequest"
			elseif min == 0x03 then
				minorText = "getDelayTimeRequest"
			elseif min == 0x04 then
				minorText = "setDelayTimeRequest"
			elseif min == 0x05 then
				minorText = "getDirectSearchChargingStationRangeRequest"
			elseif min == 0x06 then
				minorText = "setDirectSearchChargingStationRangeRequest"
			elseif min == 0x07 then
				minorText = "getAllSettingsRequest"
			elseif min == 0x08 then
				minorText = "subscribeAllEventsRequest"
			elseif min == 0x09 then
				minorText = "subscribeEventChannelRequest"
			end
		elseif maj == 0x6612 then -- SpotCuttingCommands 4710
			subtree:add(automower_protocol_major_text, "SpotCuttingCommands")
			if min == 0x00 then
				minorText = "getAvailableRequest"
			elseif min == 0x01 then
				minorText = "getEnabledRequest"
			elseif min == 0x02 then
				minorText = "setEnabledRequest"
			elseif min == 0x03 then
				minorText = "getSensitivityRequest"
			elseif min == 0x04 then
				minorText = "setSensitivityRequest"
			elseif min == 0x05 then
				minorText = "getAllSettingsRequest"
			elseif min == 0x06 then
				minorText = "setAvailableRequest"
			elseif min == 0x07 then
				minorText = "startTriggerRequest"
			elseif min == 0x08 then
				minorText = "abortRequest"
			elseif min == 0x09 then
				minorText = "getStatusRequest"
			elseif min == 0x0A then
				minorText = "subscribeAllEventsRequest"
			end
		elseif maj == 0x6812 then -- DrivingSettingsCommands 4712
			subtree:add(automower_protocol_major_text, "DrivingSettingsCommands")
			if min == 0x00 then
				minorText = "getDrivePastWireRequest"
			elseif min == 0x01 then
				minorText = "setDrivePastWireRequest"
			elseif min == 0x02 then
				minorText = "getAllSettingsRequest"
			elseif min == 0x09 then
				minorText = "subscribeAllEventsRequest"
			elseif min == 0x0A then
				minorText = "subscribeEventChannelRequest"
			elseif min == 0x0B then
				minorText = "getBounceEnabledRequest"
			elseif min == 0x0C then
				minorText = "setBounceEnabledRequest"
			elseif min == 0x0D then
				minorText = "getBounceSlopeOnlyRequest"
			elseif min == 0x0E then
				minorText = "setBounceSlopeOnlyRequest"
			end
		elseif maj == 0x6C12 then -- LeaveChargingStationCommands 4716
			subtree:add(automower_protocol_major_text, "LeaveChargingStationCommands")
			if min == 0x00 then
				minorText = "getReversingDistanceRequest"
			elseif min == 0x01 then
				minorText = "setReversingDistanceRequest"
			elseif min == 0x03 then
				minorText = "setMinAngleSector1Request"
			elseif min == 0x05 then
				minorText = "setMaxAngleSector1Request"
			elseif min == 0x07 then
				minorText = "setMinAngleSector2Request"
			elseif min == 0x09 then
				minorText = "setMaxAngleSector2Request"
			elseif min == 0x0B then
				minorText = "setSector1ProportionRequest"
			elseif min == 0x0C then
				minorText = "getAllSettingsRequest"
			elseif min == 0x0F then
				minorText = "getAllSettingsRequestG4"
			elseif min == 0x10 then
				minorText = "subscribeAllEventsRequest"
			elseif min == 0x11 then
				minorText = "subscribeEventChannelRequest"
			end
		elseif maj == 0x7612 then -- StatisticsCommands 4726
			subtree:add(automower_protocol_major_text, "StatisticsCommands")
			if min == 0x00 then
				minorText = "getAllStatisticsRequest"
			elseif min == 0x01 then
				minorText = "getTotalRunningTimeRequest"
			elseif min == 0x02 then
				minorText = "getTotalCuttingTimeRequest"
			elseif min == 0x03 then
				minorText = "getTotalChargingTimeRequest"
			elseif min == 0x04 then
				minorText = "getTotalSearchingTimeRequest"
			elseif min == 0x05 then
				minorText = "getNumberOfCollisionsRequest"
			elseif min == 0x06 then
				minorText = "getNumberOfChargingCyclesRequest"
			elseif min == 0x07 then
				minorText = "getCuttingBladeUsageTimeRequest"
			elseif min == 0x08 then
				minorText = "resetCuttingBladeUsageTimeRequest"
			elseif min == 0x0A then
				minorText = "subscribeAllStatisticsRequest"
			end
		elseif maj == 0x7812 then -- UltrasonicCommands 4728
			subtree:add(automower_protocol_major_text, "UltrasonicCommands")
			if min == 0x00 then
				minorText = "getAvailableRequest"
			elseif min == 0x01 then
				minorText = "getEnabledRequest"
			elseif min == 0x02 then
				minorText = "setEnabledRequest"
			elseif min == 0x03 then
				minorText = "subscribeAllEventsRequest"
			elseif min == 0x04 then
				minorText = "getAllSettingsRequest"
			end
		elseif maj == 0x7A12 then -- MessagesCommands 4730
			subtree:add(automower_protocol_major_text, "MessagesCommands")
			if min == 0x00 then
				minorText = "getNumberOfMessagesRequest"
			elseif min == 0x01 then
				minorText = "getMessageRequest"
			end
		elseif maj == 0x7C12 then -- GpsNavigationCommands 4732
			subtree:add(automower_protocol_major_text, "GpsNavigationCommands")
			if min == 0x00 then
				minorText = "getAvailableRequest"
			elseif min == 0x01 then
				minorText = "getEnabledRequest"
			elseif min == 0x02 then
				minorText = "setEnabledRequest"
			elseif min == 0x03 then
				minorText = "getStatusRequest"
			end
		elseif maj == 0x7E12 then -- GeoFenceCommands 4734
			subtree:add(automower_protocol_major_text, "GeoFenceCommands")
			if min == 0x00 then
				minorText = "getAvailableRequest"
			end
		elseif maj == 0x8212 then -- AutomowerConnectCommands 4738
			subtree:add(automower_protocol_major_text, "AutomowerConnectCommands")
			if min == 0x00 then
				minorText = "getAvailableRequest"
			elseif min == 0x02 then
				minorText = "setEnabledNoPinRequest"
			elseif min == 0x03 then
				minorText = "initiateNewPairingRequest"
			elseif min == 0x04 then
				minorText = "removeAllPairingsRequest"
			elseif min == 0x05 then
				minorText = "getPairingStatusRequest"
			elseif min == 0x06 then
				minorText = "getPairingCodeRequest"
			elseif min == 0x07 then
				minorText = "getConnectionStatusRequest"
			elseif min == 0x08 then
				minorText = "getSignalStrengthRequest"
			elseif min == 0x10 then
				minorText = "getConnectionStatsRequest"
			end
		elseif maj == 0x5413 then -- ModemCommands 4948
			subtree:add(automower_protocol_major_text, "ModemCommands")
			if min == 0x02 then
				minorText = "getAvailableRequest"
			end
		elseif maj == 0x0414 then -- AuthenticationCommands 5124
			subtree:add(automower_protocol_major_text, "AuthenticationCommands")
			if min == 0x0A then
				minorText = "getRemainingLoginAttemptsRequest"
			end
		elseif maj == 0x9014 then -- PositionCommands 5264
			subtree:add(automower_protocol_major_text, "PositionCommands")
			if min == 0x04 then
				minorText = "getAvailableRequest"
			end
		elseif maj == 0xEC14 then -- ObstacleAvoidance 5356
			subtree:add(automower_protocol_major_text, "ObstacleAvoidance")
			if min == 0x00 then
				minorText = "subscribeSettingsEventsRequest"
			elseif min == 0x02 then
				minorText = "getAvailableRequest"
			elseif min == 0x03 then
				minorText = "setEnabledRequest"
			elseif min == 0x04 then
				minorText = "getEnabledRequest"
			elseif min == 0x05 then
				minorText = "setUseAtBoundaryRequest"
			elseif min == 0x06 then
				minorText = "getUseAtBoundaryRequest"
			elseif min == 0x07 then
				minorText = "getAllSettingsRequest"
			end
		elseif maj == 0xFA14 then -- FrostSensorCommands 5370
			subtree:add(automower_protocol_major_text, "FrostSensorCommands")
			if min == 0x00 then
				minorText = "getAvailableRequest"
			elseif min == 0x01 then
				minorText = "getEnabledRequest"
			elseif min == 0x02 then
				minorText = "setEnabledRequest"
			elseif min == 0x03 then
				minorText = "getSleepTimeRequest"
			elseif min == 0x04 then
				minorText = "setSleepTimeRequest"
			end
		elseif maj == 0xCE15 then -- SystematicMissions 5582
			subtree:add(automower_protocol_major_text, "SystematicMissions")
			if min == 0x00 then
				minorText = "getAvailableRequest"
			elseif min == 0x03 then
				minorText = "setOrientationRequest"
			elseif min == 0x04 then
				minorText = "getOrientationRequest"
			elseif min == 0x05 then
				minorText = "setOrientationShiftRequest"
			elseif min == 0x06 then
				minorText = "getOrientationShiftRequest"
			elseif min == 0x07 then
				minorText = "getCurrentOrientationRequest"
			elseif min == 0x0A then
				minorText = "getBoundaryMowingEnabledRequest"
			elseif min == 0x0B then
				minorText = "getBoundaryMowingEnabledRequest"
			end
		elseif maj == 0xE815 then -- RandomMissionsCommands 5608
			subtree:add(automower_protocol_major_text, "RandomMissionsCommands")
			if min == 0x00 then
				minorText = "getAvailableRequest"
			end
		elseif maj == 0x8C16 then -- SpotcuttingCommands 5772
			subtree:add(automower_protocol_major_text, "SpotCuttingCommands")
			if min == 0x00 then
				minorText = "getStateRequest"
			elseif min == 0x01 then
				minorText = "getDetailedLogEnabledRequest"
			elseif min == 0x02 then
				minorText = "setDetailedLogEnabledRequest"
			elseif min == 0x03 then
				minorText = "getUseCurrentEnabledRequest"
			elseif min == 0x04 then
				minorText = "setUseCurrentEnabledRequest"
			elseif min == 0x05 then
				minorText = "getMeanCutCurrentRequest"
			elseif min == 0x06 then
				minorText = "getMeanCutIntensityRequest"
			elseif min == 0x07 then
				minorText = "setMeanCutCurrentRequest"
			elseif min == 0x08 then
				minorText = "setMeanCutIntensityRequest"
			elseif min == 0x09 then
				minorText = "getAutoTrigCurrentRequest"
			elseif min == 0x0A then
				minorText = "getAutoTrigIntensityRequest"
			end
		elseif maj == 0x0C17 then -- SiteManagerCommands 5900
			subtree:add(automower_protocol_major_text, "SiteManagerCommands")
			if min == 0x05 then
				minorText = "getSiteNameRequest"
			elseif min == 0x09 then
				minorText = "getSiteUuidRequest"
			elseif min == 0x0C then
				minorText = "getCurrentSiteIdRequest"
			elseif min == 0x11 then
				minorText = "getAvailableRequest"
			end
		elseif maj == 0x1C17 then -- WifiCommands 5916
			subtree:add(automower_protocol_major_text, "WifiCommands")
			if min == 0x00 then
				minorText = "getAvailableRequest"
			elseif min == 0x01 then
				minorText = "getEnabledRequest"
			elseif min == 0x02 then
				minorText = "setEnabledRequest"
			end
		elseif maj == 0x2617 then -- MobileLoopCommands 5926
			subtree:add(automower_protocol_major_text, "MobileLoopCommands")
			if min == 0x00 then
				minorText = "getAvailableRequest"
			elseif min == 0x01 then
				minorText = "setAvailableRequest"
			elseif min == 0x02 then
				minorText = "getEnabledRequest"
			elseif min == 0x03 then
				minorText = "setEnabledRequest"
			elseif min == 0x04 then
				minorText = "getAllSettingsRequest"
			elseif min == 0x05 then
				minorText = "subscribeSettingsEventsRequest"
			end
		elseif maj == 0xA217 then -- MobileLoopCommands 6050
			subtree:add(automower_protocol_major_text, "MobileLoopCommands")
			if min == 0x00 then
				minorText = "getAvailableRequest"
			elseif min == 0x01 then
				minorText = "setAvailableRequest"
			elseif min == 0x02 then
				minorText = "getEnabledRequest"
			elseif min == 0x03 then
				minorText = "setEnabledRequest"
			end
		elseif maj == 0x1A18 then -- EposCommands 6170
			subtree:add(automower_protocol_major_text, "EposCommands")
			if min == 0x01 then
				minorText = "getAvailableRequest"
			end
		else
			subtree:add(automower_protocol_major_text,  "NotImplementedYet")
		end

		subtree:add_le(automower_protocol_minor, tvb(14,1))
		if minorText ~= "" then
			subtree:add(automower_protocol_minor_text, minorText)
		end

		if is_request then
			subtree:add_le(automower_request_length, tvb(16,1))
			subtree:add(automower_request_data, tvb(17, tvb:len() - 20))

			local automower_request_data_le = ""
			for i = tvb:len() - 4, 17, -1 do
				automower_request_data_le = automower_request_data_le .. string.format("%02x", tvb(i, 1):uint())
			end
			subtree:add(tvb(17, tvb:len() - 20), "Request Data (Little Endian): " .. automower_request_data_le)
		else
			subtree:add_le(automower_response_length, tvb(17,1))
			subtree:add(automower_response_data, tvb(19, tvb:len() - 21))

			local automower_response_data_le = ""
			for i = tvb:len() - 3, 19, -1 do
				automower_response_data_le = automower_response_data_le .. string.format("%02x", tvb(i, 1):uint())
			end
			subtree:add(tvb(19, tvb:len() - 21), "Response Data (Little Endian): " .. automower_response_data_le)
		end

		subtree:add_le(automower_full_crc, tvb(tvb:len() - 2,1))

		if not tvb(tvb:len() - 1,1):uint() == 0x03 then
			undecoded_automower_protocol(tvb, pinfo, tree)
			return
		end
		subtree:add_le(automower_footer, tvb(tvb:len() - 1,1))
	end

    register_postdissector(automower_reassembler)
end
