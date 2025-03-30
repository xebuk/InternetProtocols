import socket
from urllib.parse import urlparse
from http.client import HTTPResponse
from io import BytesIO
from socketserver import ThreadingMixIn, TCPServer, BaseRequestHandler
from bs4 import BeautifulSoup


class ThreadingTCPServer(ThreadingMixIn, TCPServer):
    pass


class ProxyHandler(BaseRequestHandler):
    def handle_request(self, host, port, request):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as target_sock:
            target_sock.settimeout(5)
            target_sock.connect((host, port))
            target_sock.sendall(request)

            response = b''
            while True:
                try:
                    part = target_sock.recv(4096)
                    if not part:
                        break
                    response += part
                except socket.timeout:
                    break
        return response

    def process_response(self, response, host):
        try:
            headers_end = response.find(b'\r\n\r\n')
            headers_part = response[:headers_end + 4] if headers_end != -1 else response
            body = response[headers_end + 4:] if headers_end != -1 else b''

            headers = headers_part.decode('latin-1').split('\r\n')
            content_type = next((h.split(': ')[1] for h in headers if h.lower().startswith('content-type:')), None)

            if content_type and 'text/html' in content_type[0]:
                soup = BeautifulSoup(body.decode('utf-8', errors='ignore'), 'html.parser')

                # Удаляем рекламные элементы
                for tag in soup.find_all(['img', 'script', 'iframe']):
                    if host == 'e1.ru' and 'ad' in tag.get('class', []):
                        tag.decompose()
                    elif host == 'vk.com' and tag.name == 'img':
                        tag.decompose()

                modified_body = str(soup).encode('utf-8')
                content_length = len(modified_body)

                # Обновляем заголовки
                new_headers = []
                for h in headers:
                    if h.lower().startswith('content-length'):
                        new_headers.append(f'Content-Length: {content_length}')
                    else:
                        new_headers.append(h)

                return '\r\n'.join(new_headers).encode('latin-1') + modified_body
        except Exception as e:
            print(f"Processing error: {e}")
        return response

    def handle(self):
        try:
            data = self.request.recv(4096)
            if not data:
                return

            first_line = data.split(b'\r\n')[0].decode()
            method, url, protocol = first_line.split()
            parsed_url = urlparse(url)

            host = parsed_url.hostname
            port = parsed_url.port or 80
            path = parsed_url.path + ('?' + parsed_url.query if parsed_url.query else '')

            # Модифицируем запрос
            new_request = b'\r\n'.join([
                f'{method} {path} {protocol}'.encode(),
                b'\r\n'.join([
                    h.encode() for h in data.decode().split('\r\n')[1:]
                    if not h.lower().startswith('host:') and h.strip()
                ]),
                f'Host: {host}'.encode(),
                b''
            ]) + b'\r\n'

            # Получаем ответ
            response = self.handle_request(host, port, new_request)

            # Обрабатываем ответ для определённых хостов
            if host in ['e1.ru', 'vk.com']:
                response = self.process_response(response, host)

            self.request.sendall(response)
        except Exception as e:
            print(f"Error handling request: {e}")


if __name__ == '__main__':
    HOST, PORT = '0.0.0.0', 8080
    server = ThreadingTCPServer((HOST, PORT), ProxyHandler)
    print(f"Proxy server started on port {PORT}")
    server.serve_forever()