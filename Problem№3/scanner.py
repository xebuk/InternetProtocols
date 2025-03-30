import socket
import concurrent.futures
from argparse import ArgumentParser


def parse_ports(ports_str):
    if '-' in ports_str:
        start, end = map(int, ports_str.split('-'))
        return range(start, end + 1)
    else:
        return [int(ports_str)]


def check_tcp_port(host, port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex((host, port))
            return ('TCP', port) if result == 0 else None
    except Exception:
        return None


def check_udp_port(host, port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(1)
            s.sendto(b'', (host, port))
            s.recvfrom(1024)
            return ('UDP', port)
    except socket.timeout:
        return ('UDP', port)
    except ConnectionRefusedError:
        return None
    except Exception:
        return ('UDP', port)


def check_http(s):
    try:
        s.send(b'GET / HTTP/1.0\r\n\r\n')
        response = s.recv(1024)
        return b'HTTP/' in response
    except Exception:
        return False


def check_smtp(s):
    try:
        response = s.recv(1024)
        if response.startswith(b'220'):
            return True
        s.send(b'EHLO example.com\r\n')
        response = s.recv(1024)
        return response.startswith(b'250')
    except Exception:
        return False


def check_pop3(s):
    try:
        response = s.recv(1024)
        if response.startswith(b'+OK'):
            return True
        s.send(b'USER test\r\n')
        response = s.recv(1024)
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
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                s.connect((host, port))
                if checker(s):
                    return name
        except Exception:
            continue
    return 'Unknown'


def check_dns(host, port):
    try:
        query = b'\xab\xcd\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x07example\x03com\x00\x00\x01\x00\x01'
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(1)
            s.sendto(query, (host, port))
            data, _ = s.recvfrom(1024)
            return data[:2] == b'\xab\xcd' and len(data) >= 12
    except Exception:
        return False


def check_sntp(host, port):
    try:
        query = b'\x1b' + 47 * b'\x00'
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(1)
            s.sendto(query, (host, port))
            data, _ = s.recvfrom(1024)
            return len(data) == 48 and (data[0] & 0b11111000) == 0x18
    except Exception:
        return False


def detect_udp_protocol(host, port):
    protocols = [
        ('DNS', check_dns),
        ('SNTP', check_sntp),
    ]
    for name, checker in protocols:
        if checker(host, port):
            return name
    return 'Unknown'


def main():
    parser = ArgumentParser(description='Port Scanner')
    parser.add_argument('host', help='Host to scan')
    parser.add_argument('-p', '--ports', required=True, help='Port range (e.g. 1-100)')
    parser.add_argument('-t', '--tcp', action='store_true', help='Scan TCP ports')
    parser.add_argument('-u', '--udp', action='store_true', help='Scan UDP ports')
    args = parser.parse_args()

    if not args.tcp and not args.udp:
        print("Error: At least one of --tcp or --udp must be specified")
        return

    ports = parse_ports(args.ports)
    open_ports = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        futures = []
        if args.tcp:
            futures.extend(executor.submit(check_tcp_port, args.host, port) for port in ports)
        if args.udp:
            futures.extend(executor.submit(check_udp_port, args.host, port) for port in ports)

        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                proto, port = result
                if proto == 'TCP':
                    app_proto = detect_tcp_protocol(args.host, port)
                else:
                    app_proto = detect_udp_protocol(args.host, port)
                open_ports.append((proto, port, app_proto))

    for proto, port, app in sorted(open_ports, key=lambda x: (x[0], x[1])):
        print(f"{proto} port {port} is open. Protocol: {app}")


if __name__ == '__main__':
    main()
