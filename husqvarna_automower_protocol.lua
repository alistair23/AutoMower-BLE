do
	automower_request = Proto("automower_request", "Husqvarna AutoMower Request Protocol")

	automower_data = ProtoField.new("Data", "btatt.value", ftypes.BYTES, nil, base.NONE)
	automower_header = ProtoField.new("Header", "automower.header", ftypes.UINT16, nil, base.HEX)
	automower_length = ProtoField.new("Length", "automower.length", ftypes.UINT8, nil, base.HEX)
	automower_channel_id = ProtoField.new("ChannelId", "automower.channel_id", ftypes.UINT8, nil, base.HEX)
	automower_bool = ProtoField.new("Unknown Bool", "automower.bool", ftypes.UINT8, nil, base.HEX)
	automower_first_crc = ProtoField.new("First CRC", "automower.first_crc", ftypes.UINT8, nil, base.HEX)
	automower_request_major = ProtoField.new("Request Major", "automower.request_major", ftypes.UINT8, nil, base.DEC)
	automower_request_major_text = ProtoField.new("Req Major", "automower.req_major", ftypes.STRING, nil, base.NONE)
	automower_request_minor_text = ProtoField.new("Req Minor", "automower.req_minor", ftypes.STRING, nil, base.NONE)
	automower_request_minor = ProtoField.new("Request Minor", "automower.request_minor", ftypes.UINT8, nil, base.DEC)
	automower_request_data = ProtoField.new("Request Data", "automower.request_data", ftypes.UINT8, nil, base.HEX)
	automower_full_crc = ProtoField.new("Full CRC", "automower.full_crc", ftypes.UINT8, nil, base.HEX)
	automower_footer = ProtoField.new("Footer", "automower.footer", ftypes.UINT8, nil, base.HEX)

	automower_request.fields = { automower_data, automower_header, automower_length, automower_channel_id, automower_bool, automower_first_crc,
			automower_request_major, automower_request_major_text, automower_request_minor,automower_request_minor_text,
			automower_request_data, automower_full_crc, automower_footer }

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

		minorText = ""
		maj = tvb(12, 2):uint()
		min = tvb(14, 1):uint()

		subtree:add_le(automower_request_major, tvb(12,2))
		if maj == 0x0A10 then -- BatteryCommands 4106
			subtree:add(automower_request_major_text, "BatteryCommands")
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
		elseif maj == 0xEA11 then -- MowerAppCommands 4586
			subtree:add(automower_request_major_text, "MowerAppCommands")
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
			end
		elseif maj == 0x3212 then -- PlannerCommands 4658
			subtree:add(automower_request_major_text, "PlannerCommands")
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
			subtree:add(automower_request_major_text, "AuthenticationCommands")
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
			end
		elseif maj == 0x4212 then -- SystemPowerCommands 4674
			subtree:add(automower_request_major_text, "SystemPowerCommands")
			if min == 0x00 then
				minorText = "enableEventsRequest"
			elseif min == 0x01 then
				minorText = "getPowerModeRequest"
			elseif min == 0x02 then
				minorText = "keepAliveRequest"
			end
		elseif maj == 0x5212 then -- CalendarCommands 4690
			subtree:add(automower_request_major_text, "CalendarCommands")
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
		elseif maj == 0x5A12 then -- SystemCommands 4698
			subtree:add(automower_request_major_text, "SystemCommands")
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
			elseif min == 0x16 then
				minorText = "getSwPackageVersionStringRequest"
			end
		elseif maj == 0x6612 then -- SpotCuttingCommands 4710
			subtree:add(automower_request_major_text, "SpotCuttingCommands")
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
		elseif maj == 0x0414 then -- AuthenticationCommands 5124
			subtree:add(automower_request_major_text, "AuthenticationCommands")
			if min == 0x0A then
				minorText = "getRemainingLoginAttemptsRequest"
			end
		elseif maj == 0x8C16 then -- SpotcuttingCommands 5772
			subtree:add(automower_request_major_text, "SpotCuttingCommands")
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
		else
			subtree:add(automower_request_major_text,  "NotImplementedYet")
		end

		subtree:add_le(automower_request_minor, tvb(14,1))
		if minorText ~= "" then
			subtree:add(automower_request_minor_text, minorText)
		end



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
