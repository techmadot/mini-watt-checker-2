import uasyncio as asyncio
import sys, os, gc
import ntptime, utime
from ble_plugmini import SwitchBotPlugMini


async def invoke_callback_after_seconds(seconds, callback):
    try:
        if callback is None:
            return
        await asyncio.sleep(seconds)
        await callback()
    except Exception as ex:
        sys.print_exception(ex)

def calc_remaining_seconds():
    '''次の、分単位、30分単位までの残り秒数を計算する'''
    minute, second = utime.localtime()[4:6]
    seconds_to_next_minute = 60 - second
    if minute < 30:
        seconds_to_next_half_hour = (30 - minute) * 60 - second
    else:
        seconds_to_next_half_hour = (60 - minute) * 60 - second
    return seconds_to_next_minute, seconds_to_next_half_hour

class SensorTask:

    def __init__(self, plugmini_addr):
        self._plugmini = SwitchBotPlugMini(targetAddr=plugmini_addr)
        self.realtime_sensor_values = [ ]
        self.aggregate_values_per_minute = [ ]
        self.aggregate_values_per_halfhour = [ ]

    def start(self):
        next_min, next_half_hour = calc_remaining_seconds()
        asyncio.create_task(invoke_callback_after_seconds(1, self.sense_sensor))
        self._setinvoke_aggregate_minute_data()
        self._setinvoke_callback_halfhour_interval(self.aggregate_halfhour_data)
        # self._setinvoke_callback_halfhour_interval(self.display_half_hour) # for Debug
    
    async def sense_sensor(self):
        while True:
            try:
                await self._plugmini.scan(1000)
                current_power = self._plugmini.currentPower()
                self.realtime_sensor_values.append(current_power)
                await asyncio.sleep(1.0)
                if len(self.realtime_sensor_values) > 1800:
                    self.realtime_sensor_values = self.realtime_sensor_values[1:]
            except Exception as ex:
                sys.print_exception(ex)
    
    def calc_buffer_average(self, target_buffer, request_count):
        count_len = request_count if len(target_buffer) >= request_count else len(target_buffer)
        average = 0
        if count_len > 0:
            average = sum(target_buffer[-count_len:])/count_len
        return average, count_len
    
    def _setinvoke_aggregate_minute_data(self):
        next_min, _ = calc_remaining_seconds()
        asyncio.create_task(invoke_callback_after_seconds(next_min, self.aggregate_minute_data))

    def _setinvoke_callback_halfhour_interval(self, callback):
        _, next_half_hour = calc_remaining_seconds()        
        asyncio.create_task(invoke_callback_after_seconds(next_half_hour, callback))

    async def aggregate_minute_data(self):
        try:
            sample_count = 60
            average, _  = self.calc_buffer_average(self.realtime_sensor_values, sample_count)
            self.aggregate_values_per_minute.append(average)
        except Exception as ex:
            sys.print_exception(ex)
        self._setinvoke_aggregate_minute_data()

    async def aggregate_halfhour_data(self):
        try:
            sample_count = 30
            average, consume_count = self.calc_buffer_average(self.aggregate_values_per_minute, sample_count)
            tm = utime.localtime()
            self.aggregate_values_per_halfhour.append(average)
            self.aggregate_values_per_minute = self.aggregate_values_per_minute[consume_count:]

            try:
                lines = [ ]
                with open('watt_data.csv', 'a+') as f:
                    f.seek(0)
                    lines = f.readlines()
                    if len(lines) > 144:
                        lines = lines[-144:]

                    value = f'{self.current_time_as_str()}, {average}'
                    lines.append(value)
                with open('watt_data.csv', "wt") as f:
                    for x in lines:
                        f.write(x.strip() + "\r\n")
            except Exception as ex:
                print(ex)
        except Exception as ex:
            sys.print_exception(ex)
        
        self._setinvoke_callback_halfhour_interval(self.aggregate_halfhour_data)

    async def display_half_hour(self):
        print(f'{self.current_time_as_str()} - Information half_hour_buffer: \r\n' + str(self.aggregate_values_per_halfhour))
        self._setinvoke_callback_halfhour_interval(self.display_half_hour)

    def current_time_as_str(self):
        tm = utime.localtime()
        s = f"{tm[0]}-{tm[1]:02}-{tm[2]:02} {tm[3]:02}:{tm[4]:02}:{tm[5]:02}"
        return s
    
    def sensor_value(self, count=1):
        '''最新のセンサーデータから指定された個数で平均をとって返却'''
        if count <= 0:
            return 0.0
        sampled_count = len(self.realtime_sensor_values)
        use_count = count if sampled_count >= count else sampled_count
        if use_count == 0:
            return 0.0
        ret_value = self.realtime_sensor_values[-use_count:]
        return sum(ret_value) / use_count
