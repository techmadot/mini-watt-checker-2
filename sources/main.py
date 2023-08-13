from TMiniWebServer import TMiniWebServer
from ble_plugmini import SwitchBotPlugMini
import ntptime, utime
from sensor_tasks import SensorTask

import uasyncio as asyncio
import sys, os, gc
from json import dumps

smartplugmini_addr = ''

## plugmini.txt からアドレス情報を読む
with open('plugmini.txt', 'rt') as f:
    while True:
        s = f.readline()
        if s.startswith('#'):
            continue
        smartplugmini_addr = str(s).strip()
        break

plugmini_sensor = SwitchBotPlugMini(targetAddr=smartplugmini_addr)

def current_time_str():
    tm = utime.localtime()
    s = f"{tm[0]}-{tm[1]:02}-{tm[2]:02} {tm[3]:02}:{tm[4]:02}:{tm[5]:02}"
    return s

## 時刻設定
ntptime.adjust_time()
adjust_time_base = utime.ticks_ms()

print(f"NOW:{current_time_str()}")
gc.collect()
print(f"FREE:{gc.mem_free()}")


@TMiniWebServer.with_websocket('/ws/')
async def read_sensor(websocket):
    minute, second = utime.localtime()[4:6]
    sleep_sec = 5 - (second % 5)
    await asyncio.sleep(sleep_sec)

    while not websocket.is_closed():
        starttime = utime.ticks_ms()
        try:
            current_power = sensor_task.sensor_value(5)
            data = { "value": current_power, "date": current_time_str()}
            text_json = str(dumps(data))
            
            await websocket.send(text_json)
        except Exception as ex:
            sys.print_exception(ex)

        minute, second = utime.localtime()[4:6]
        sleep_sec = (5+second) % 5
        if sleep_sec == 0:
            sleep_sec = 5
        else:
            sleep_sec = 5 - sleep_sec
        
        endtime = utime.ticks_ms()
        elapsed_time = utime.ticks_diff(endtime, starttime)

        ## 本関数での処理コスト分は減らして計算
        sleep_sec -= elapsed_time / 1000
        await asyncio.sleep(sleep_sec)

@TMiniWebServer.route('/api/daily', method = 'GET')
async def api_daily(client):
    try:
        lines = []
        try:
            with open('watt_data.csv', 'rt') as f:
                f.seek(0)
                lines = f.readlines()
            data = []
            for x in lines:
                records = x.strip().split(',')
                entry = {
                    "time" : records[0].strip(),
                    "value": records[1].strip()
                }
                data.append(entry)
            
            strjson = str(dumps({ "data": data }))
            await client.write_response(strjson, content_type="application/json")
        except:
            strjson = '{ "data" : [ ] }'
            await client.write_response(strjson, content_type="application/json")
    except Exception as ex:
        print(ex)

## Webサーバーの開始と定期的な掃除
async def main_task():
    webserver = TMiniWebServer()
    await webserver.start()

    while True:
        await asyncio.sleep(60)
        gc.collect()
        #print(f"GC&FREE:{gc.mem_free()}")


loop = asyncio.get_event_loop()

sensor_task = SensorTask(plugmini_addr=smartplugmini_addr)
sensor_task.start()

loop.run_until_complete(main_task())