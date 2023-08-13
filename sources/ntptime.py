import usocket as socket
import ustruct as struct
import utime
import machine

JP_OFFSET = 9 * 60 * 60 ## JST 用のオフセット

def adjust_time(host="ntp.nict.jp"):
    ntp_query = bytearray(48)
    ntp_query[0] = 0x1b
    addr = socket.getaddrinfo(host,123)[0][-1]
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        res = s.sendto(ntp_query, addr)
        msg = s.recv(48)
    except Exception as ex:
        print(ex)
    finally:
        s.close()

    val = struct.unpack("!I", msg[40:44])[0]
    year = utime.gmtime(0)[0]
    if year == 2000:
        ntp_delta = 3155673600
    elif year == 1970:
        ntp_delta = 2208988800
    else:
        raise Exception(f"unsupported epoch: {year}")
    
    val = val - ntp_delta
    val += JP_OFFSET
    tm = utime.gmtime(val)
    machine.RTC().datetime((tm[0], tm[1], tm[2], tm[6] + 1, tm[3], tm[4], tm[5], 0))
