from socket import socket, AF_INET, SOCK_STREAM, SOCK_DGRAM, timeout
from concurrent.futures import ThreadPoolExecutor, as_completed
from argparse import ArgumentParser


def parse_ports(ports: str) -> list[int]:
    if '-' in ports:
        start, end = map(int, ports.split('-'))
        return list(range(start, end + 1))
    else:
        return [int(ports)]


def check_tcp_port(host: str, port: int) -> tuple[str, int] | None:
    with socket(AF_INET, SOCK_STREAM) as tcp:
        tcp.settimeout(1)
        result = tcp.connect_ex((host, port))
        return ('TCP', port) if result == 0 else None


def check_udp_port(host: str, port: int) -> tuple[str, int] | None:
    try:
        with socket(AF_INET, SOCK_DGRAM) as udp:
            udp.settimeout(3)
            udp.sendto(b'', (host, port))
            udp.recvfrom(1024)
            return 'UDP', port
    except timeout:
        return 'UDP', port
    except Exception:
        return None


def check_http(tcp_socket: socket) -> bool:
    try:
        tcp_socket.send(b'GET / HTTP/1.0\r\n\r\n')
        response = tcp_socket.recv(1024)
        return b'HTTP/' in response
    except Exception:
        return False


def check_smtp(tcp_socket: socket) -> bool:
    try:
        response = tcp_socket.recv(1024)
        if response.startswith(b'220'):
            return True
        tcp_socket.send(b'EHLO example.com\r\n')
        response = tcp_socket.recv(1024)
        return response.startswith(b'250')
    except Exception:
        return False


def check_pop3(tcp_socket: socket) -> bool:
    try:
        response = tcp_socket.recv(1024)
        if response.startswith(b'+OK'):
            return True
        tcp_socket.send(b'USER test\r\n')
        response = tcp_socket.recv(1024)
        return response.startswith(b'+OK')
    except Exception:
        return False


def detect_tcp_protocol(host, port):
    protocols = [
        ('HTTP', check_http),
        ('SMTP', check_smtp),
        ('POP3', check_pop3),
    ]
    for name, checker in protocols:
        try:
            with socket(AF_INET, SOCK_STREAM) as tcp:
                tcp.settimeout(1)
                tcp.connect((host, port))
                if checker(tcp):
                    return name
        except Exception:
            continue
    return 'Unknown'


def check_dns(host: str, port: int) -> bool:
    try:
        query = b'\xab\xcd\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x07example\x03com\x00\x00\x01\x00\x01'
        with socket(AF_INET, SOCK_DGRAM) as udp:
            udp.settimeout(1)
            udp.sendto(query, (host, port))
            data, _ = udp.recvfrom(1024)
            return data[:2] == b'\xab\xcd' and len(data) >= 12
    except Exception:
        return False


def check_sntp(host: str, port: int) -> bool:
    try:
        query = b'\x1b' + 47 * b'\x00'
        with socket(AF_INET, SOCK_DGRAM) as udp:
            udp.settimeout(1)
            udp.sendto(query, (host, port))
            data, _ = udp.recvfrom(1024)
            return len(data) == 48 and (data[0] & 0b11111000) == 0x18
    except Exception:
        return False


def detect_udp_protocol(host: str, port: int) -> str:
    protocols = [
        ('DNS', check_dns),
        ('SNTP', check_sntp),
    ]
    for name, checker in protocols:
        if checker(host, port):
            return name
    return 'Unknown'


def main():
    parser = ArgumentParser(description='Сканер портов')
    parser.add_argument('host', help='Хост для сканирования', default="localhost")
    parser.add_argument('ports', help='Набор портов (пример: 1-100)', default="1-1000")

    args = parser.parse_args()
    ports = parse_ports(args.ports)

    with ThreadPoolExecutor(max_workers=100) as executor:
        futures = []
        futures.extend(executor.submit(check_tcp_port, args.host, port) for port in ports)
        futures.extend(executor.submit(check_udp_port, args.host, port) for port in ports)

        for future in as_completed(futures):
            result = future.result()
            if result:
                proto, port = result
                if proto == 'TCP':
                    app_proto = detect_tcp_protocol(args.host, port)
                else:
                    app_proto = detect_udp_protocol(args.host, port)
                print(f"{proto} порт {port} открыт. Протокол: {app_proto}")


if __name__ == '__main__':
    main()
