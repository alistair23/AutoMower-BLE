"""
    Example Mower = Gardena Silenio Minimo 400
    This test is an example script that you can use to execute the code against your Mower.
    This replays every step that has been transmitted from the mobile app towards the Mower.

    I had issues with the Mower accepting my commands to start / stop / ... That's why I created this
    so I could check against the app if everything was working or not.

    This is basically a generic test to start / stop the mower.
    But the intention is to get every feature from the Gardena app working in here (schedules,...)

"""

import argparse
import asyncio
import logging

from bleak import BleakScanner

import sys
sys.path.append('../')

from automower_ble.mower import Mower
from automower_ble.protocol import ModeOfOperation

logger = logging.getLogger(__name__)



logging.getLogger('automower_ble.protocol').setLevel(logging.WARN)
logging.getLogger('automower_ble.mower').setLevel(logging.WARN)

logging.getLogger('bleak.backends.bluezdbus.client').setLevel(logging.INFO)
logging.getLogger('bleak.backends.bluezdbus.manager').setLevel(logging.INFO)


async def main(mower:Mower, must_start:bool = False, must_stop:bool = False):
    device = None
    try:
            
        logger.info('Start test mower')
        device = await BleakScanner.find_device_by_address(mower.address)
        if device is None:
            print("Unable to connect to device address: " + mower.address)
            print("Please make sure the device address is correct, the device is powered on and nearby")
            return
        logger.info(f'Device found. Start connecting to device {mower.address}')
        await mower.connect(device)
        logger.info(f'Connected to device with address {mower.address}')
        logger.info(f'Mower : {mower}')

        model = await mower.get_model()
        logger.info(f'Model : {model} ')

        logger.info('Start sending keep Alive')
        keepalive_response = await mower.send_keepalive()
        if not keepalive_response:
            logger.error(f'Error sending keepalive request {keepalive_response}')

        enterOperatorPinRequestResult = await mower.send_operator_pin_request(mower.pin)
        logger.debug(f'Enter Operator Pin Request Result {enterOperatorPinRequestResult}')


        success = await mower.get_startupsequence_required_request()
        logger.debug(f'Startupsequence is required response {success}')

        operator_is_logged_in = await mower.is_operator_loggedin()
        logger.debug(f'Operator is logged in {operator_is_logged_in}')

        activity = await mower.mower_activity()
        logger.debug(f'Mower activity : {activity}')

        mode= await mower.get_mode_of_operation()
        logger.debug(f'Mower mode : {mode}')

        serial_number = await mower.get_serial_number()
        logger.debug(f'Serial number : {serial_number}')

        restriction_reason = await mower.get_restriction_reason()
        logger.debug(f'Restriction Reason : {restriction_reason}')

        next_start_time = await mower.mower_next_start_time()
        if next_start_time:
            logger.debug("Next start time: " + next_start_time.strftime("%Y-%m-%d %H:%M:%S"))
        else:
            logger.debug("No next start time")

        number_of_tasks = await mower.get_number_of_tasks()
        logger.debug(f'number of tasks : {number_of_tasks}')

        # TODO: implement get task functioality
        # for now : don't know how to parse "task number"
        task_number = 0
        logger.debug(f'Start requesting task {task_number}')
        task_response = await mower.get_task(task_number)
        logger.debug(f'Next task starts at {task_response.next_start_time.strftime("%H:%M:%S")}')
        logger.debug(f'Next task has a duration of {task_response.duration_in_seconds} seconds')
        logger.debug(f'Next task must run on MONDAY    {task_response.on_monday}')
        logger.debug(f'Next task must run on TUESDAY   {task_response.on_tuesday}')
        logger.debug(f'Next task must run on WEDNESDAY {task_response.on_wednesday}')
        logger.debug(f'Next task must run on THURSDAT  {task_response.on_thursday}')
        logger.debug(f'Next task must run on FRIDAY    {task_response.on_friday}')
        logger.debug(f'Next task must run on SATURDAY  {task_response.on_saturday}')
        logger.debug(f'Next task must run on SUNDAY    {task_response.on_sunday}')
        
        
        keepalive_response = await mower.send_keepalive()

        mower_state = await mower.mower_state()
        logger.debug(f'Mower state response {mower_state}')

        mower_activity = await mower.mower_activity()
        logger.debug(f'Mower activity : {mower_activity}')

        get_mode_response = await mower.get_mode_of_operation()
        logger.debug(f'Mode : {get_mode_response}')

        next_start_time = await mower.mower_next_start_time()
        logger.debug(f'Next Start Time : {next_start_time}')
        if next_start_time:
            logger.debug("Next start time: " + next_start_time.strftime("%Y-%m-%d %H:%M:%S"))
        else:
            logger.debug("No next start time")

        restriction_reason = await mower.get_restriction_reason()
        logger.debug(f'Restriction reason : {restriction_reason}')

        if must_start:
            # actually start mowing for 30 minutes

            logger.debug('--------------')
            logger.debug('start setting mode to manual')
            await mower.set_mode_of_operation(ModeOfOperation.MANUAL)
            logger.debug('Mode of operation set to manual')
            logger.debug('--------------')


            logger.debug('Overriding mow to 30 mins')
            await mower.set_mower_override_duration_in_seconds(30*60) # 30 minutes override mow
            logger.debug('override mow finished ')
            logger.debug('--------------')


            start_trigger = await mower.start_trigger_request()
            logger.debug(f'Start trigger response : {start_trigger}')
            
        if must_stop:
            logger.debug('Must stop mowing. Send Park command to mower')
            await mower.set_mode_of_operation(ModeOfOperation.MANUAL)
            logger.debug('Finished setting mode of operation to manual. Sending park command')
            await mower.mower_park()
            logger.debug('Finished sending park command')
            start_trigger = await mower.start_trigger_request()
            logger.debug(f'Start trigger response : {start_trigger}')

        keepalive_response = await mower.send_keepalive()

        mower_state = await mower.mower_state()
        logger.debug(f'Mower state response {mower_state}')

        mower_activity = await mower.mower_activity()
        logger.debug(f'Mower activity : {mower_activity}')

        logger.info('Finished testing mower')
        
        
    except Exception as e:
        logger.error('There was an issue communicating with the device')
        raise e
        
    finally:
        if device is not None:
            await mower.disconnect()
        logger.info('Disconnected from Mower')

if __name__ == "__main__":
    log_level = logging.DEBUG
    logging.basicConfig(
        level=log_level,
        format="%(asctime)-15s %(name)-8s %(levelname)s: %(message)s",
    )
    
    parser = argparse.ArgumentParser()

    device_group = parser.add_mutually_exclusive_group(required=False)

    device_group.add_argument(
        "--address",
        metavar="<address>",
        help="the Bluetooth address of the Automower device to connect to",
        default="d8:71:4d:7c:7a:36",
    )
    
    device_group.add_argument(
        '--start', action='store_true', help="start mowing"
    )
    device_group.add_argument(
        '--stop', action='store_true', help='stop mowing'
    )

    parser.add_argument(
        "--pin",
        metavar="<code>",
        type=int,
        default=None,
        help="Send PIN to authenticate. This feature is experimental and might not work.",
    )
    
    args = parser.parse_args()
    
    if args.start and not args.stop:
        logger.warn('Must start mowing')
    if args.stop and not args.start:
        logger.warn('Must stop mowing')
        
    if args.start and args.stop:
        logger.error('There is an issue. You cannot start and stop both at the same time')

    mower = Mower(0x13a51453, args.address, args.pin)
    
   

    asyncio.run(main(mower, must_start = args.start, must_stop = args.stop))
