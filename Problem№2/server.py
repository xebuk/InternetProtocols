import socket
import time
import struct

def read_delta():
    """Читает значение коррекции времени из файла config.txt."""
    try:
        with open('config.txt', 'r') as f:
            return int(f.read().strip())
    except:
        return 0  # Значение по умолчанию, если файл не найден

DELTA = read_delta()

def get_ntp_time(real_time, delta):
    """Преобразует реальное время в NTP-формат с учетом коррекции."""
    server_time = real_time + delta
    ntp_epoch = server_time + 2208988800  # Конвертация в эпоху NTP (1900)
    seconds = int(ntp_epoch)
    fraction = int((ntp_epoch - seconds) * 2**32)
    return (seconds, fraction)

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind(('0.0.0.0', 123))
    print(f"SNTP Server запущен с коррекцией {DELTA} секунд.")

    while True:
        try:
            data, addr = server.recvfrom(1024)
            print(f"Получен запрос от {addr}")

            # Фиксируем время получения запроса
            received_real_time = time.time()
            recv_ntp = get_ntp_time(received_real_time, DELTA)

            # Время отправки ответа
            transmit_real_time = time.time()
            transmit_ntp = get_ntp_time(transmit_real_time, DELTA)

            # Формируем ответный пакет
            response = bytearray(48)
            # Заголовок: LI=0, версия=4, режим=4 (сервер)
            response[0] = 0x24
            response[1] = 1  # Stratum 1
            response[2] = 0   # Poll interval
            response[3] = 0xEC  # Precision (-20 в 8-битном формате)

            # Корневая задержка и дисперсия (нули)
            response[4:8] = struct.pack('!I', 0)
            response[8:12] = struct.pack('!I', 0)

            # Идентификатор источника
            response[12:16] = b'SELF'

            # Метки времени
            response[16:24] = struct.pack('!II', *transmit_ntp)  # Reference
            response[24:32] = data[24:32]  # Originate (из запроса)
            response[32:40] = struct.pack('!II', *recv_ntp)      # Receive
            response[40:48] = struct.pack('!II', *transmit_ntp)  # Transmit

            server.sendto(response, addr)
            print("Ответ отправлен")

        except Exception as e:
            print(f"Ошибка: {e}")

if __name__ == "__main__":
    main()