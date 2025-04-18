import socket
import struct
from time import time
import datetime


def ntp_to_unix(seconds, fraction):
    return (seconds - 2208988800) + (fraction / 2 ** 32)


def sntp_client(server_host='localhost', server_port=123):
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client.settimeout(10)  # таймаут 10 секунд на запрос, чтобы клиент отключался при отсутствии ответа от сервера

        # Формируем SNTP-запрос
        data = bytearray(48)
        data[0] = 0x1B  # LI=0, версия=3, режим=3 (клиент)

        # фиксируем время отправки запроса (T1)
        t1 = time()
        client.sendto(data, (server_host, server_port))

        # получаем ответ от сервера
        data, addr = client.recvfrom(1024)
        t4 = time()  # фиксируем время получения ответа

        t2 = struct.unpack('!II', data[32:40])  # Receive time (T2)
        t3 = struct.unpack('!II', data[40:48])  # Transmit time (T3)

        # конвертируем NTP в Unix
        t2_unix = ntp_to_unix(*t2)
        t3_unix = ntp_to_unix(*t3)

        # смещение и задержка
        offset = ((t2_unix - t1) + (t3_unix - t4)) / 2
        delay = (t4 - t1) - (t3_unix - t2_unix)

        # время сервера (среднее между T2 и T3)
        server_time = (t2_unix + t3_unix) / 2
        local_time = time()

        # подробное описание для наглядности
        print(f"Сервер: {server_host}:{server_port}")
        print(f"Локальное время:  {datetime.datetime.fromtimestamp(local_time)}")
        print(f"Время сервера:    {datetime.datetime.fromtimestamp(server_time)}")
        print(f"Разница:          {server_time - local_time:.6f} секунд")
        print(f"Сетевая задержка: {delay:.6f} секунд")
        print(f"Корректировка:    {offset:.6f} секунд")

    except socket.timeout:
        print("Таймаут соединения. Сервер не ответил.")
    except Exception as e:
        print(f"Ошибка: {str(e)}")
    finally:
        client.close()


if __name__ == "__main__":
    sntp_client()
