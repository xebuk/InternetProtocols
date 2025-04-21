from getpass import getpass
from smtplib import SMTP, SMTP_SSL
from configparser import ConfigParser
from os.path import isfile, basename
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from email.header import Header
from mimetypes import guess_type

config = ConfigParser()
config.read('config.ini', encoding="utf-8")

recipients = [r.strip() for r in config.get('settings', 'recipients').split(',')]
subject = config.get('settings', 'subject')
attachments = [a.strip() for a in config.get('settings', 'attachments').split(',')]

with open('message.txt', 'r', encoding='utf-8') as f:
    body = f.read()

sender_email = input("Введите ваш email: ")
password = getpass("Введите пароль: ")

domain = sender_email.split('@')[-1].lower()
smtp_servers = {
    'gmail.com': {'host': 'smtp.gmail.com', 'port': 587, 'ssl': False},
    'yandex.ru': {'host': 'smtp.yandex.ru', 'port': 465, 'ssl': True},
    'mail.ru': {'host': 'smtp.mail.ru', 'port': 465, 'ssl': True},
}

if domain not in smtp_servers:
    supported = ", ".join(smtp_servers.keys())
    print(f"Домен {domain} не поддерживается. Поддерживаемые домены: {supported}.")
    exit(0)

server_info = smtp_servers[domain]

msg = MIMEMultipart()
msg['From'] = sender_email
msg['To'] = ', '.join(recipients)
msg['Subject'] = Header(subject, 'utf-8')

msg.attach(MIMEText(body, 'plain', 'utf-8'))

for file in attachments:
    if not isfile(file):
        print(f"Ошибка: файл {file} не найден.")
        exit()

    mime_type, _ = guess_type(file)
    if mime_type is None:
        mime_type = 'application/octet-stream'
    main_type, sub_type = mime_type.split('/', 1)

    with open(file, 'rb') as f:
        if main_type == 'text':
            part = MIMEText(f.read().decode(), _subtype=sub_type)
        else:
            part = MIMEBase(main_type, sub_type)
            part.set_payload(f.read())
            encoders.encode_base64(part)

    filename = Header(basename(file), 'utf-8').encode()
    part.add_header('Content-Disposition', 'attachment', filename=filename)
    msg.attach(part)

try:
    if server_info['ssl']:
        server = SMTP_SSL(server_info['host'], server_info['port'], timeout=5)
    else:
        server = SMTP(server_info['host'], server_info['port'], timeout=5)
        server.starttls()

    server.login(sender_email, password)
    server.sendmail(sender_email, recipients, msg.as_string())

    print("Письмо успешно отправлено!")
except Exception as e:
    print(f"Ошибка при отправке: {str(e)}")
finally:
    if 'server' in locals():
        server.quit()
