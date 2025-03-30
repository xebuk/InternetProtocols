import socket
import struct
import time
import datetime


def sntp_client(server_host='localhost', server_port=123):
    try:
        # Создаем UDP-сокет
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client.settimeout(5)  # Таймаут 5 секунд

        # Формируем SNTP-запрос
        data = bytearray(48)
        data[0] = 0x1B  # LI=0, версия=3, режим=3 (клиент)

        # Записываем время отправки запроса (T1)
        t1 = time.time()
        client.sendto(data, (server_host, server_port))

        # Получаем ответ
        data, addr = client.recvfrom(1024)
        t4 = time.time()  # Время получения ответа (T4)

        # Извлекаем временные метки из ответа
        t2 = struct.unpack('!II', data[32:40])  # Receive time (T2)
        t3 = struct.unpack('!II', data[40:48])  # Transmit time (T3)

        # Конвертируем NTP-время в Unix-время
        def ntp_to_unix(seconds, fraction):
            return (seconds - 2208988800) + (fraction / 2 ** 32)

        t2_unix = ntp_to_unix(*t2)
        t3_unix = ntp_to_unix(*t3)

        # Рассчитываем смещение и задержку
        offset = ((t2_unix - t1) + (t3_unix - t4)) / 2
        delay = (t4 - t1) - (t3_unix - t2_unix)

        # Время сервера (среднее между T2 и T3)
        server_time = (t2_unix + t3_unix) / 2
        local_time = time.time()

        # Выводим результаты
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
    # Пример использования:
    sntp_client(server_host='localhost')  # Для теста на локальной машине
    # sntp_client(server_host='time.example.com')  # Для внешнего сервера
