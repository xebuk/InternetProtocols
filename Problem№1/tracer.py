import re
import subprocess
import argparse
from ipwhois import IPWhois
from ipwhois.exceptions import IPDefinedError, ASNRegistryError


MAX_TIMEOUT = 150


def trace_route(addr: str) -> list[str]:
    try:
        result = subprocess.run(
            f"tracert -d -h 50 {addr}",
            capture_output=True,
            text=True,
            encoding='cp866',
            timeout=MAX_TIMEOUT,
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"Ошибка трассировки:\n{e.stderr}")
        exit(0)
    except subprocess.TimeoutExpired:
        print("Превышено время ожидания.")
        exit(0)
    except subprocess.SubprocessError as e:
        print(f"Ошибка подпроцесса:\n{str(e)}")
        exit(0)

    ips = list()
    for line in result.stdout.splitlines():
        ip = extract_ip(line)
        if ip:
            ips.append(ip)
    return ips


def extract_ip(line):
    matches = re.findall(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', line)
    return matches[-1] if matches else None


def get_asn_info(ip):
    try:
        ipwhois_instance = IPWhois(ip)
        result = ipwhois_instance.lookup_rdap()

        provider = "Неизвестно"
        if 'entities' in result and result['entities']:
            provider = result['entities'][0].split(' ')[-1]

        return {
            'asn': f"AS{result['asn']}" if result.get('asn') else 'Неизвестно',
            'provider': provider,
            'country': result.get('asn_country_code', 'Неизвестно')
        }

    except IPDefinedError:
        return {'error': 'Приватный IP или локальный адрес'}
    except (ASNRegistryError, KeyError):
        return {'error': 'Данные не найдены'}
    except Exception as e:
        return {'error': f'Ошибка: {str(e)}'}


def main():
    parser = argparse.ArgumentParser(
        description="Трассировщик автономных систем - осуществляет трассировку до указанного узла и для каждого из посещенных узлов выводит его IP-адрес, номер автономной системы, страну и провайдера.",
        epilog="Для работы требуется установленный модуль ipwhois (pip install ipwhois)"
    )
    parser.add_argument(
        dest="addr",
        help="IP-адрес или доменное имя, до которого будет выполняться трассировка"
    )

    args = parser.parse_args()

    print(f"Трассировка до {args.addr}...")
    ips = trace_route(args.addr)

    if not ips:
        print("Маршрут не найден или цель недостижима")
        return

    print("\nРезультат трассировки:")
    print(f"{'Хоп':<5}{'IP':<16}{'ASN':<10}{'Страна':<8}{'Провайдер':<21}")
    print("-" * 60)

    for hop, ip in enumerate(ips[1:], 1):
        info = get_asn_info(ip)
        if 'error' in info:
            status = info['error']
            print(f"{hop:<5}{ip:<16}{status:<10}")
        else:
            print(f"{hop:<5}{ip:<16}{info['asn']:<10}{info['country']:<8}{info['provider']}")


if __name__ == "__main__":
    main()
