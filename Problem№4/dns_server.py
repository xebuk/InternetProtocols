import socket
import threading
import time
import signal
import sys
import pickle
from typing import Any

import dns.message
import dns.query
import dns.rdatatype
import dns.rdataclass
import dns.rrset


class DNSCache:
    def __init__(self):
        self.cache: dict[Any, dict[Any, Any]] = dict()
        self.on_deletion_entries = set()
        self.on_deletion_keys = set()
        self.lock = threading.Lock()

    def add_record(self, name, rtype, data, ttl):
        with self.lock:
            key = (name.lower(), rtype)
            expired = time.time() + ttl
            if key not in self.cache.keys():
                self.cache[key] = dict()
            self.cache[key][data] = (ttl, expired)

    def get_records(self, name, rtype):
        key = (name.lower(), rtype)
        current_time = time.time()
        with self.lock:
            if key not in self.cache.keys():
                return None
            valid = []
            expired = []
            for entry in self.cache[key].items():
                if entry[1][1] > current_time:
                    valid.append((entry[0], entry[1][0]))
                else:
                    expired.append(entry[0])
            for e in expired:
                self.cache[key].pop(e)
            if not self.cache[key]:
                self.cache.pop(key)
            return valid if valid else None

    def cleanup(self):
        current_time = time.time()
        with self.lock:
            for key in self.cache.keys():
                for entry in self.cache[key].items():
                    if entry[1][1] < current_time:
                        self.on_deletion_entries.add(entry[0])
                for entry in self.on_deletion_entries:
                    self.cache[key].pop(entry)
                self.on_deletion_entries.clear()

                if not self.cache[key]:
                    self.on_deletion_keys.add(key)
            for key in self.on_deletion_keys:
                self.cache.pop(key)
            self.on_deletion_keys.clear()

    def save(self, filename):
        with self.lock:
            with open(filename, 'wb') as f:
                pickle.dump(self.cache.copy(), f)
            print("Кэш был сохранен")

    def load(self, filename):
        with self.lock:
            try:
                with open(filename, 'rb') as f:
                    data = pickle.load(f)
                    current_time = time.time()
                    for (name, rtype), entries in data.items():
                        for entry in entries.items():
                            if entry[1][1] > current_time:
                                self.add_record(name, rtype, entry[0], entry[1][0])
                print("Kэш был загружен")
            except FileNotFoundError:
                print("Файл не был найден")
            except Exception as e:
                print(f"Произошла ошибка: {e}")


cache = DNSCache()


def handle_query(data, addr, sock):
    try:
        request = dns.message.from_wire(data)
        if len(request.question) == 0:
            return
        question = request.question[0]
        qname = question.name.to_text()
        qtype = dns.rdatatype.to_text(question.rdtype)

        cached = cache.get_records(qname, qtype)
        if cached:
            response = dns.message.make_response(request)
            for data_entry, ttl in cached:
                rrset = dns.rrset.from_text(qname, ttl, dns.rdataclass.IN, qtype, data_entry)
                response.answer.append(rrset)
            sock.sendto(response.to_wire(), addr)
            return

        response = recursive_resolve(qname, qtype)
        if response:
            for section in [response.answer, response.authority, response.additional]:
                for rrset in section:
                    name = rrset.name.to_text()
                    rtype = dns.rdatatype.to_text(rrset.rdtype)
                    for rdata in rrset:
                        data_entry = rdata.to_text()
                        cache.add_record(name, rtype, data_entry, rrset.ttl)
            sock.sendto(response.to_wire(), addr)
    except Exception as e:
        print(f"Ошибка обработки запроса: {e}")


def recursive_resolve(qname, qtype):
    nameservers = ['198.41.0.4', '199.9.14.201', '192.33.4.12', '199.7.91.13']  # Корневые сервера A-D
    depth = 0
    while depth < 15:
        for ns in nameservers.copy():
            try:
                query = dns.message.make_query(qname, qtype)
                response = dns.query.udp(query, ns, timeout=2)
                if response.rcode() == dns.rcode.NOERROR:
                    if response.answer:
                        return response
                    new_ns = []
                    for rrset in response.authority:
                        if rrset.rdtype == dns.rdatatype.NS:
                            for rdata in rrset:
                                nsname = rdata.target.to_text()
                                for add_rrset in response.additional:
                                    if add_rrset.name == rdata.target:
                                        for addr in add_rrset:
                                            if addr.rdtype == dns.rdatatype.A:
                                                new_ns.append(addr.address)
                    nameservers = new_ns if new_ns else []
                    depth += 1
                    break
            except Exception as e:
                print(f"Запрос провалился: {e}")
                nameservers.remove(ns)
    return None


def cache_cleaner():
    while True:
        time.sleep(60)
        cache.cleanup()


def shutdown(sig, frame):
    cache.save('dns_cache.pkl')
    sys.exit(0)


def main():
    cache.load('dns_cache.pkl')
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    cleaner = threading.Thread(target=cache_cleaner, daemon=True)
    cleaner.start()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', 53))

    while True:
        data, addr = sock.recvfrom(512)
        print("Получил запрос")
        threading.Thread(target=handle_query, args=(data, addr, sock)).start()


if __name__ == '__main__':
    main()
