# TG tdata session and API requests

Репозиторий содержит набор Python скриптов, которые выполняют следующее:
- create_session.py - конвертирует данные локальной папки tdata (используется в Telegram Desktop) в файл формата .session, который используется библиотекой Telethon для подключения к серверам Telegram (также требуются параметры API id и API hash)
- get_contacts.py - выгружает все контакты пользователя, их внутренние ID, пользовательские имена и ссылки формата @user в порядке последнего взаимодействия
- get_dialogs.py - выгружает все пользовательские переписки с конкретным контактом. Показывает текст сообщений, отправителя, наличие вложений и является ли сообщение пересланным. Дополнительно может выгружать вложения, а также конвертировать время отправки в нужный часовой пояс

## Нюансы

### API ключи

Нужно создать своё Telegram приложение на сайте https://my.telegram.org/apps, оно нужно для получения собственных API_ID и API_HASH

### Прокси

Для успешного подключения используется локальный прокси https://github.com/Flowseal/tg-ws-proxy, параметры "PROXY_\*" относятся к нему

### Создание сессии

Скрипт create_session.py может потребовать включённый VPN для работы. Так же при частых запросах на создание сессии Telegram может начать блокировать такие попытки и выдавать ошибку FloodWaitError, в скрипте она сопровождается логом 'Ошибка, Telegram блокирует подключение из-за прошлых неуспешных попыток, нужно подождать 1 час'

### Установка

```bash
git clone https://github.com/HappyTrashBin/TG-tdata-session-and-API-requests
cd TG-tdata-session-and-API-requests
chmod +x *.py
touch .env
  # Содержимое .env файла, значения нужно дописать свои:
  # API_ID =  
  # API_HASH =   
  # PROXY_SECRET =  
  # PROXY_IP =  
  # PROXY_PORT = 
```

## Зависимости

- telethon
- opentele2
- tgcrypto
- python-dotenv

## Пример использования

```powershell
python.exe create_session.py
python.exe get_contacts.py -q
 ID         | Type | Username   | Name
----------------------------------------------
 1000000000 | User | @Vasya_Pyp | Вася Пупкин

python.exe get_dialogs.py "@Vasya_Pyp" -q -l 1
ВЫГРУЗКА КОНТАКТА:

 ID: 1000000000 | Type: User | Username: @Vasya_Pyp | Name: Вася Пупкин

СООБЩЕНИЯ:

 ID: 1000000000 | Type: User | Username: @Vasya_Pyp | Name: Вася Пупкин
-------------------------------------------------------------------------------
Date: 2026-04-29 21:33:44
Have media: False
Is forwarded: False
Text:
     Some text to yourself

```
