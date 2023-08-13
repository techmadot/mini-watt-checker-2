import ubluetooth
import ubinascii
from micropython import const
import uasyncio as asyncio
from utime import sleep

_IRQ_SCAN_RESULT = const(5)
_IRQ_SCAN_DONE = const(6)

isScanEnd = False
wattValue = 0

class BLEScanner:
    def __init__(self, ble, targetAddr):
        self.ble = ble
        self.ble.active(True)
        self.ble.irq(self._irq_handler)
        self.targetAddr = targetAddr

    def _irq_handler(self, event, data):
        if event == _IRQ_SCAN_RESULT:
            # A single scan result.
            addr_type, addr, adv_type, rssi, adv_data = data
            addr_str = ':'.join(['{:02x}'.format(b) for b in addr])
            #print(addr_str)
            if addr_str == self.targetAddr:
                #print('Device found:', ubinascii.hexlify(addr))
                #print('Data:', ubinascii.hexlify(adv_data))
                self._parseData(adv_data)
                self.ble.gap_scan(None)

        elif event == _IRQ_SCAN_DONE:
            # Scan duration finished or manually stopped.
            global isScanEnd
            isScanEnd = True


    def _parseData(self, data):
        companyId, manufacturerData = self.get_manufacturer_specific_data(data)
        if companyId == '0969' and manufacturerData is not None:
            '''SwitchBot スマートプラグミニのワット情報を読み取とる'''
            # https://github.com/OpenWonderLabs/SwitchBotAPI-BLE/blob/latest/devicetypes/plugmini.md
            power = ((manufacturerData[12] << 8) + manufacturerData[13] & 0x7fff) / 10
            global wattValue
            wattValue = power
        pass

    def get_manufacturer_specific_data(self, adv_data):
        i = 0
        while i < len(adv_data):
            # extract length and type
            length = adv_data[i]
            type = adv_data[i + 1]

            # check if this is a manufacturer specific data AD structure
            if type == 0xFF:
                manufacturerData = adv_data[i + 2:i + length + 1]
                companyId = bytes(reversed(manufacturerData[:2])).hex()                
                return companyId, manufacturerData

            i += length + 1
        # no manufacturer specific data found
        return None, None

    def scan(self, duration_ms):
        global isScanEnd
        isScanEnd = False
        self.ble.gap_scan(duration_ms, 30000,30000)
        pass


class SwitchBotPlugMini:
    def __init__(self, targetAddr):
        ble = ubluetooth.BLE()
        self.scanner = BLEScanner(ble, targetAddr)

    async def scan(self, duration):
        self.scanner.scan(duration)

        global isScanEnd
        while isScanEnd == False:
            await asyncio.sleep(0.5)

    def currentPower(self):
        global wattValue
        return wattValue