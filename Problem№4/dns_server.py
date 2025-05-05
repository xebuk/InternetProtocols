import argparse
import socket
import struct
import time
import signal
import sys
import pickle
from collections import defaultdict


class DNSCache:
    def __init__(self):
        self.records = defaultdict(list)

    def add_record(self, name, rtype, data, ttl):
        self.records[(name, rtype)].append({
            'data': data,
            'expired': time.time() + ttl
        })

    def get_records(self, name, rtype):
        current_time = time.time()
        return [r for r in self.records.get((name, rtype), []) if r['expired'] > current_time]

    def cleanup(self):
        current_time = time.time()
        removed = 0

        for key in list(self.records.keys()):
            self.records[key] = [r for r in self.records[key] if r['expired'] > current_time]
            if not self.records[key]:
                self.records.pop(key)
                removed += 1

        if removed > 0:
            print(f"Убрал {removed} просроченные записи")

        return removed

    def save_to_file(self, filename):
        try:
            with open(filename, 'wb') as cache:
                pickle.dump(dict(self.records), cache)
            print(f"Кэш сохранен в {filename}")
            return True
        except Exception as e:
            print(f"Процесс сохранения был прерван: {e}")
            return False

    def load_from_file(self, filename):
        try:
            with open(filename, 'rb') as f:
                data = pickle.load(f)
                if not isinstance(data, dict):
                    raise ValueError("Невалидный формат кэша")

                self.records.clear()
                for key, records in data.items():
                    if isinstance(records, list):
                        self.records[key].extend(records)

            print(f"Кэш загружен из {filename}")
            self.cleanup()
            return True
        except FileNotFoundError:
            print("Файл кэша не был найден, кэш пуст")
            return True
        except Exception as e:
            print(f"Процесс загрузки прерван: {e}")
            return False


def parse_dns_query(data):
    try:
        if len(data) < 12:
            raise ValueError("Пакет слишком короткий")

        header = struct.unpack('!6H', data[:12])
        query_id = header[0]
        qdcount = header[2]

        questions = []
        offset = 12

        for _ in range(qdcount):
            if offset >= len(data):
                raise ValueError("Вопрос секции усечен")

            name, offset = decode_name(data, offset)

            if offset + 4 > len(data):
                raise ValueError("Вопрос типа/класса усечен")

            qtype, qclass = struct.unpack('!2H', data[offset:offset + 4])
            questions.append({
                'name': name,
                'type': qtype,
                'class': qclass
            })
            offset += 4

        return {
            'id': query_id,
            'questions': questions,
            'header': header
        }
    except Exception as e:
        print(f"Попытка обработки запроса провалена: {e}")
        return None


def build_dns_response(query, answers):
    try:
        if not query or not answers:
            raise ValueError("Неправильный ввод")

        question = query['questions'][0]

        flags = 0x8180
        header = struct.pack('!6H', query['id'], flags, 1, len(answers), 0, 0)

        encoded_question = encode_name(question['name'])
        encoded_question += struct.pack('!2H', question['type'], question['class'])

        response = bytearray()
        response.extend(header)
        response.extend(encoded_question)

        for answer in answers:
            encoded_name = encode_name(answer['name'])
            response.extend(encoded_name)

            response.extend(struct.pack('!2HIH', answer['type'], 1, answer['ttl'], len(answer['data'])))

            response.extend(answer['data'])

        return bytes(response)
    except Exception as e:
        print(f"Не получилось составить ответ: {e}")
        return None


def forward_query(query_data, upstream_dns, upstream_port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(2.0)
            sock.sendto(query_data, (upstream_dns, upstream_port))
            response, _ = sock.recvfrom(512)
            return response
    except socket.timeout:
        print("Запрос к вышестоящему DNS серверу превысил время ожидания")
        return None
    except Exception as e:
        print(f"Запрос в старший DNS сервер провален: {e}")
        return None


def parse_dns_response(response):
    if not response or len(response) < 12:
        return None

    try:
        header = struct.unpack('!6H', response[:12])
        ancount = header[3]
        nscount = header[4]
        arcount = header[5]

        offset = 12
        for _ in range(header[2]):
            _, offset = decode_name(response, offset)
            offset += 4

        records = []

        for _ in range(ancount + nscount + arcount):
            if offset >= len(response):
                break

            name, offset = decode_name(response, offset)

            if offset + 10 > len(response):
                break

            rtype, rclass, ttl, rdlength = struct.unpack('!2HIH', response[offset:offset + 10])
            offset += 10

            if offset + rdlength > len(response):
                break

            rdata = response[offset:offset + rdlength]
            offset += rdlength

            if rclass == 1:
                records.append({
                    'name': name,
                    'type': rtype,
                    'data': rdata,
                    'ttl': ttl
                })

        return records
    except Exception as e:
        print(f"Не получилось обработать ответ: {e}")
        return None


# Доподнительные функции
def decode_name(data, offset):
    name = []
    processed_pointers = set()

    while True:
        if offset >= len(data):
            raise ValueError("Сдвиг выходит за пределы запроса")

        length = data[offset]

        if (length & 0xc0) == 0xc0:  # Компрессия
            if offset + 1 >= len(data):
                raise ValueError("Неправильный указатель сжатия")

            pointer = struct.unpack('!H', data[offset:offset + 2])[0] & 0x3fff
            if pointer in processed_pointers:
                raise ValueError("Засечен цикл сжатия")

            processed_pointers.add(pointer)
            part, _ = decode_name(data, pointer)
            name.append(part)
            return '.'.join(name), offset + 2

        elif length > 0:  # Обычная метка
            if offset + 1 + length > len(data):
                raise ValueError("Метка превышает длину пакета")

            name.append(data[offset + 1:offset + 1 + length].decode('ascii',
                                                                    'replace'))
            offset += 1 + length
        else:  # Конец имени
            return '.'.join(name), offset + 1


def encode_name(name):
    encoded = bytearray()
    for part in name.split('.'):
        encoded.append(len(part))
        encoded.extend(part.encode('ascii', 'replace'))
    encoded.append(0)
    return bytes(encoded)


def process_dns_query(data, cache, upstream_dns, upstream_port):
    try:
        query = parse_dns_query(data)
        if not query or not query['questions']:
            return None

        question = query['questions'][0]
        print(f"Обрабатываю запрос: {question['name']} типа {question['type']}")

        cached_records = cache.get_records(question['name'], question['type'])
        if cached_records:
            print(f"Использую кэшированный ответ для {question['name']}")
            answers = [{
                'name': question['name'],
                'type': question['type'],
                'ttl': int(record['expired'] - time.time()),
                'data': record['data']
            } for record in cached_records]
            return build_dns_response(query, answers)

        print(f"Перенаправляю запрос в старший DNS сервер для {question['name']}")
        response = forward_query(data, upstream_dns, upstream_port)
        if not response:
            return None

        records = parse_dns_response(response)
        if records:
            for record in records:
                if record['type'] in {1, 2, 12, 28}:
                    cache.add_record(record['name'], record['type'], record['data'], record['ttl'])
        return response
    except Exception as e:
        print(f"Обработка кэша закончилась с ошибкой: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description='Кэширующий DNS сервер')
    parser.add_argument('--upstream-dns', default='1.1.1.1',
                        help='Старший DNS сервер')
    parser.add_argument('--upstream-port', type=int, default=53,
                        help='Порт вышестоящего DNS сервера')
    parser.add_argument('--listen-addr', default='0.0.0.0',
                        help="Aдрес для прослушки")
    parser.add_argument('--cache-ttl', type=int, default=300,
                        help='TTL кэша в секундах')
    parser.add_argument('--backup-file', default='dns_cache.pkl',
                        help="Файл для сохранения кэша")
    args = parser.parse_args()

    cache = DNSCache()

    if not cache.load_from_file(args.backup_file):
        print("Произошла ошибка при загрузке кэша, кэш пуст")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((args.listen_addr, 53))
    sock.settimeout(1.0)

    print(f"DNS сервер запущен на {args.listen_addr}:53")
    print(f"Использую старший DNS: {args.upstream_dns}:{args.upstream_port}")

    def shutdown(signum, frame):
        print("Выключаю сервер...")
        cache.save_to_file(args.backup_file)
        sock.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    last_cleanup = time.time()

    try:
        while True:
            try:
                data, addr = sock.recvfrom(512)
                print(f"Получил запрос от {addr}")

                response = process_dns_query(
                    data,
                    cache,
                    args.upstream_dns,
                    args.upstream_port
                )

                if response:
                    sock.sendto(response, addr)

                if time.time() - last_cleanup > 60:
                    cache.cleanup()
                    last_cleanup = time.time()

            except socket.timeout:
                continue
            except Exception as e:
                print(f"Непредвиденная ошибка: {e}")
                continue

    except Exception as e:
        print(f"Критическая ошибка: {e}")
    finally:
        cache.save_to_file(args.backup_file)
        sock.close()
        print("Сервер выключен")


if __name__ == '__main__':
    main()
