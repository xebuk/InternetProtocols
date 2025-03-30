import smtplib
import configparser
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from email.header import Header
import mimetypes

# Чтение конфигурационного файла
config = configparser.ConfigParser()
config.read('config.ini')

recipients = [r.strip() for r in config.get('settings', 'recipients').split(',')]
subject = config.get('settings', 'subject')
attachments = [a.strip() for a in config.get('settings', 'attachments').split(',')]

# Чтение тела письма
with open('message.txt', 'r', encoding='utf-8') as f:
    body = f.read()

# Запрос данных отправителя
sender_email = input("Введите ваш email: ")
password = input("Введите пароль: ")

# Определение SMTP сервера
domain = sender_email.split('@')[-1].lower()
smtp_servers = {
    'gmail.com': {'host': 'smtp.gmail.com', 'port': 587, 'ssl': False},
    'yandex.ru': {'host': 'smtp.yandex.ru', 'port': 465, 'ssl': True},
    'mail.ru': {'host': 'smtp.mail.ru', 'port': 465, 'ssl': True},
}

if domain not in smtp_servers:
    supported = ", ".join(smtp_servers.keys())
    print(f"Домен {domain} не поддерживается. Поддерживаемые домены: {supported}.")
    exit()

server_info = smtp_servers[domain]

# Создание сообщения
msg = MIMEMultipart()
msg['From'] = sender_email
msg['To'] = ', '.join(recipients)
msg['Subject'] = Header(subject, 'utf-8')

msg.attach(MIMEText(body, 'plain', 'utf-8'))

# Добавление вложений
for file in attachments:
    if not os.path.isfile(file):
        print(f"Ошибка: файл {file} не найден.")
        exit()

    mime_type, _ = mimetypes.guess_type(file)
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

    filename = Header(os.path.basename(file), 'utf-8').encode()
    part.add_header('Content-Disposition', 'attachment', filename=filename)
    msg.attach(part)

# Отправка письма
try:
    if server_info['ssl']:
        server = smtplib.SMTP_SSL(server_info['host'], server_info['port'])
    else:
        server = smtplib.SMTP(server_info['host'], server_info['port'])
        server.starttls()

    server.login(sender_email, password)
    server.sendmail(sender_email, recipients, msg.as_string())
    print("✅ Письмо успешно отправлено!")
except Exception as e:
    print(f"❌ Ошибка при отправке: {str(e)}")
finally:
    if 'server' in locals():
        server.quit()