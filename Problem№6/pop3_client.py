import poplib
import email
from email.header import decode_header
import os


def decode_header_value(value):
    """Декодирует значение заголовка с учетом кодировки."""
    if value is None:
        return ""
    decoded_parts = decode_header(value)
    decoded_str = ""
    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            decoded_str += part.decode(encoding or 'utf-8', errors='replace')
        else:
            decoded_str += part
    return decoded_str


def save_attachments(msg, save_dir="."):
    """Сохраняет вложения из письма в указанную директорию."""
    attachment_count = 0
    for part in msg.walk():
        content_disposition = part.get("Content-Disposition", "")
        if "attachment" in content_disposition:
            filename = part.get_filename()
            if filename:
                filename = decode_header_value(filename)
                filepath = os.path.join(save_dir, filename)
                with open(filepath, "wb") as f:
                    content = part.get_payload(decode=True)
                    f.write(content)
                    attachment_count += 1
                    print(f"Сохранено вложение: {filename}")
    return attachment_count


def save_email_body(msg, save_dir="."):
    """Сохраняет текстовую часть письма в файл."""
    body = None
    for part in msg.walk():
        content_type = part.get_content_type()
        if content_type == "text/plain":
            body = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='replace')
            break
    if body:
        filepath = os.path.join(save_dir, "email_body.txt")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(body)
        print(f"Текст письма сохранен в {filepath}")
        return True
    return False


def main():
    print("POP3 Клиент для загрузки писем")
    # Выбор почтового сервиса
    print("Выберите почтовый сервис:")
    print("1. Gmail")
    print("2. Yandex")
    print("3. Другой")
    service_choice = input("Ваш выбор (1-3): ").strip()

    if service_choice == '1':
        server, port = 'pop.gmail.com', 995
    elif service_choice == '2':
        server, port = 'pop.yandex.ru', 995
    else:
        server = input("Введите адрес POP3 сервера (например, pop.example.com): ").strip()
        port = int(input("Введите порт (по умолчанию 995): ") or 995)

    username = input("Введите вашу почту: ").strip()
    password = input("Введите пароль: ").strip()

    try:
        # Подключение к серверу
        conn = poplib.POP3_SSL(server, port)
        conn.user(username)
        conn.pass_(password)
        print("Успешное подключение к серверу.")

        # Получение списка писем
        _, msg_list, _ = conn.list()
        num_messages = len(msg_list)
        print(f"Найдено писем: {num_messages}")
        if num_messages == 0:
            print("Нет писем для обработки.")
            conn.quit()
            return

        # Выбор последнего письма
        msg_index = num_messages
        print(f"Обрабатывается последнее письмо (номер {msg_index})")

        while True:
            print("\nДоступные действия:")
            print("1. Показать заголовки письма")
            print("2. Показать начало текста письма")
            print("3. Скачать письмо с вложениями")
            print("4. Выход")
            choice = input("Ваш выбор (1-4): ").strip()

            if choice == '1':
                # Получение заголовков
                _, headers, _ = conn.top(msg_index, 0)
                msg = email.message_from_bytes(b'\n'.join(headers))
                subject = decode_header_value(msg.get('Subject'))
                from_ = decode_header_value(msg.get('From'))
                date = decode_header_value(msg.get('Date'))
                print(f"\nТема: {subject}")
                print(f"Отправитель: {from_}")
                print(f"Дата: {date}")

            elif choice == '2':
                # Показать первые N строк тела
                try:
                    lines = int(input("Сколько строк вывести? "))
                except ValueError:
                    print("Ошибка: введите число.")
                    continue
                _, body_lines, _ = conn.top(msg_index, lines)
                print("\nНачало письма:")
                print(b'\n'.join(body_lines).decode('utf-8', errors='replace'))

            elif choice == '3':
                # Скачать полное письмо
                _, msg_data, _ = conn.retr(msg_index)
                msg = email.message_from_bytes(b'\n'.join(msg_data))

                # Создание директории для сохранения
                save_dir = input("Введите путь для сохранения (по умолчанию текущая папка): ").strip()
                if not save_dir:
                    save_dir = "."
                os.makedirs(save_dir, exist_ok=True)

                # Сохранение тела и вложений
                save_email_body(msg, save_dir)
                count = save_attachments(msg, save_dir)
                print(f"\nСохранено {count} вложений.")

            elif choice == '4':
                break
            else:
                print("Неверный ввод. Попробуйте снова.")

        conn.quit()
        print("Соединение закрыто.")
    except Exception as e:
        print(f"Произошла ошибка: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.quit()


if __name__ == "__main__":
    main()