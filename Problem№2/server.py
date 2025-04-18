import socket
from time import time
import struct


def read_delta():
    try:
        with open('config.txt', 'r') as f:
            return int(f.read().strip())
    except:
        return 0


DELTA = read_delta()


def get_ntp_time():
    ntp_epoch = time() + DELTA + 2208988800
    seconds = int(ntp_epoch)
    fraction = int((ntp_epoch - seconds) * 2 ** 32)
    return seconds, fraction


def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind(('localhost', 123))
    print(f"SNTP Server запущен с коррекцией {DELTA} секунд.")

    while True:
        try:
            data, addr = server.recvfrom(1024)
            print(f"Получен запрос от {addr}")

            recv_ntp = get_ntp_time()  # время получения
            transmit_ntp = get_ntp_time()  # время отправки

            response = bytearray(48)  # ответ

            # заголовок: LI=0, версия=4, режим=4 (сервер)
            response[0] = 0x24
            response[1] = 1  # Stratum 1
            response[2] = 0  # Poll interval
            response[3] = 0xEC  # Precision (-20 в 8-битном формате)

            # корневая задержка и дисперсия (нули)
            response[4:12] = struct.pack('!II', 0, 0)

            response[12:16] = b'SELF'  # источник

            # метки времени
            response[16:24] = struct.pack('!II', *transmit_ntp)  # Reference
            response[24:32] = data[24:32]  # Originate (из запроса)
            response[32:40] = struct.pack('!II', *recv_ntp)  # Receive
            response[40:48] = struct.pack('!II', *transmit_ntp)  # Transmit

            server.sendto(response, addr)
            print("Ответ отправлен")

        except Exception as e:
            print(f"Ошибка: {e}")


if __name__ == "__main__":
    main()
