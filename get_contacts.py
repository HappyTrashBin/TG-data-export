from telethon.sync import TelegramClient
from telethon.network.connection import ConnectionTcpMTProxyRandomizedIntermediate
from telethon.errors.rpcerrorlist import FloodWaitError
import argparse, asyncio, os, logging, dotenv, json, unicodedata


# ----------------------------------------------------------------------------------------------------------------------

def args_parse(args_line: list[str] = None) -> argparse.Namespace:
    """
    Парсер аргументов командной строки

    Args:
        args_line: список аргументов формата ['-X', '...']
    """

    def normalize_session_path(path: str) -> str:
        return os.path.normpath(path)
            
    parser = argparse.ArgumentParser(description='Скрипт для выгрузки контактов с аккаунта Telegram',
                                     add_help=False)

    parser.add_argument('-h',
                        action='help', default=argparse.SUPPRESS,
                        help='Показать help сообщение и выйти')
    parser.add_argument('-q',
                        action='store_true', dest='QUIET',
                        help='Скрыть логи, оставить только вывод')
    parser.add_argument('-j',
                        action='store_true', dest='JSON',
                        help='Вывести результат в json формате')
    parser.add_argument('-f',
                        type=str, dest='FILE_NAME',
                        help='Записывать результат работы скрипта в указанный файл, а не в консоль')
    parser.add_argument('-s',
                        type=normalize_session_path, default='TG_Session.session', dest='SESSION_FILE',
                        help=r'Путь до файла Telegram сессии (default=.\TG_Session.session)')
    parser.add_argument('-t',
                        type=int, default=30, dest='TIMEOUT',
                        help='Таймаут подключения в секундах (default=30)')
    parser.add_argument('-c',
                        action='store_true', dest='COUNT',
                        help='Посчитать общее количество сообщений в переписке с контактом')

    return parser.parse_args(args_line)


def setup_logger(in_file: bool = True, is_quiet: bool = False) -> logging.Logger:
    """
    Создание логгера

    Args:
        in_file: записывать логи в файл (=true) или выводить в консоль (=false)
        is_quiet: подавить вывод (=true) или нет (=false)
    """
    if in_file:
        handlers = [logging.FileHandler('log.txt', mode='a', encoding='utf-8')]
    else:
        handlers = [logging.StreamHandler()]

    logging.basicConfig(format='[%(asctime)s] - %(levelname)s - %(funcName)s - %(message)s',
                        level=logging.INFO,
                        handlers=handlers)

    some_logger = logging.getLogger(__name__)

    if is_quiet:
        logging.disable(logging.CRITICAL)

    return some_logger


async def connect_to_tg(tg_client: TelegramClient, connection_timeout: int) -> None:
    """
    Подключение к серверам Telegram с использованием объекта типа TelegramClient из библиотеки telethon

    Args:
        tg_client: экзепляр объекта TelegramClient
        connection_timeout: время таймаута при подключении к серверам Telegram
    """
    logger.info('Попытка подключения к Telegram API')
    try:
        await asyncio.wait_for(tg_client.start(), timeout=connection_timeout)
    except asyncio.TimeoutError:
        logger.error(f'Таймаут при соединении с сервером (>{connection_timeout} секунд)')
        exit(-1)
    except asyncio.IncompleteReadError:
        logger.error(f'Файл сессии не подходит для установления соединения')
        exit(-1)
    except FloodWaitError:
        logger.error('Ошибка, Telegram блокирует подключение из-за прошлых неуспешных попыток, нужно подождать 1 час\n')
        exit(-1)
    logger.info('Успешная авторизация')


def replace_emoji(text: str, replacement: str = "#") -> str:
    """
    Замена в тексте всех эмодзи на заглушку

    Args:
        text: текст для обработки
        replacement: заглушка
    """
    result = []
    for char in text:
        if unicodedata.category(char) == 'So':
            result.append(replacement)
        else:
            result.append(char)
    return ''.join(result)


async def get_contacts(tg_client: TelegramClient, is_json: bool, to_count: bool) -> str:
    """
    Получение всех контактов переданного в функцию объекта TelegramClient, полученные данные форматируются либо в
    человекочитаемую таблицу, либо в json словарь

    Args:
        tg_client: экзепляр объекта TelegramClient
        is_json: флаг включения json формата (=true), иначе формируется таблица (=false)
        to_count: флаг включения пересчёта общего количества сообщений в переписке с контактом
    """
    contacts = {}
    # Дефолтный формат словаря contacts после завершения работы функции:
    # {
    #   'id контакта' (int):
    #                        {
    #                          'Тип контакта' (str): _
    #                          '@ссылка контакта' (str): _
    #                          'Имя контакта' (str): _
    #                        }
    # }
    async for contact in tg_client.iter_dialogs():

        contact_username = None
        if hasattr(contact.entity, 'username'):
            if contact.entity.username:
                contact_username = f'@{contact.entity.username}'
        # Если нужно изменить состав полей, то достаточно изменить строку ниже, остальные структуры функции адаптируются
        # Можно добавлять, переставлять или убирать любые поля, например:
        #                                                  'Folder': contact.folder_id
        entry = {'Type': type(contact.entity).__name__,
                 'Username': contact_username,
                 # Поле Name часто содержит эмодзи, они занимают пространство в два символа,
                 # и это ломает форматирование таблицы, поэтому эмодзи заменяются заглушкой
                 'Name': replace_emoji(contact.name) if contact.name else contact.name}

        # Пересчёт общего количества сообщений в диалоге с контактом
        if to_count:
            all_messages = await tg_client.get_messages(contact, limit=0)
            entry['Messages'] = all_messages.total

        contacts[contact.id] = entry
        # Путь до описания класса message, экзепляры которого итерируются в tg_client.iter_dialogs():
        # ./venv/Lib/site-packeges/telethon/tl/custom/dialog.py
        # тут можно подсмотреть дополнительные поля для добавления их в entry

    # Формирование вывода
    data: str = ''
    if is_json:
        data = json.dumps(obj=contacts, indent=4, ensure_ascii=False)
    else:
        # Вычисление выравнивания для столбцов таблицы, в словаре contacts предполагается максимум 2 уровня вложенности,
        # где каждый ключ словаря contacts хранит свой словарь (словари в словаре)

        # Получаем ключи словаря contacts, преобразуем в список и берём самый первый ключ словаря contacts
        null_key = list(contacts.keys())[0]
        # Полученный первый ключ (как и любой другой) хранит свой словарь, получаем его и достаём уже его ключи
        null_key_dict = contacts[null_key].keys()
        # Прибавляем 1 за первый ключ словаря contacts и количество ключей словаря, который этот первый ключ хранит
        count = 1 + len(list(null_key_dict))

        sizes = [0 for _ in range(count)]
        for contact_id in contacts:
            # Ширина столбца с ID
            if len(str(contact_id)) > sizes[0]:
                sizes[0] = len(str(contact_id))

            for contact_field in contacts[contact_id]:
                # Получаем позицию поля в словаре
                position = 1 + list(contacts[contact_id].keys()).index(contact_field)
                # Получаем длину значения поля
                field_value_len = len(str(contacts[contact_id][contact_field]))
                # Ширина столбца с обрабатываемым полем
                if field_value_len > sizes[position]:
                    sizes[position] = field_value_len

        # Заголовок таблицы
        title_string = f' {"ID":<{sizes[0]}} '
        for number, contact_field in enumerate(contacts[list(contacts.keys())[0]]):
            title_string += f'| {contact_field:<{sizes[number + 1]}} '
        data += title_string + '\n'
        data += '-' * len(title_string)

        # Строки таблицы
        for contact_id in contacts:
            output = f' {contact_id:<{sizes[0]}} '
            for number, contact_field in enumerate(contacts[contact_id]):
                output += f'| {str(contacts[contact_id][contact_field]):<{sizes[number + 1]}} '
            data += '\n' + output

    return data


async def main(some_arguments: argparse.Namespace,
               some_api_id: int | str,
               some_api_hash: str,
               some_proxy: tuple) -> None:
    logger.info('Скрипт запущен')

    # При отсутствии файла Telegram сессии скрипт прерывается
    if os.path.exists(some_arguments.SESSION_FILE):
        logger.info(f'Используется сессия {some_arguments.SESSION_FILE}')
    else:
        logger.error(f'Не найден файл сессии {some_arguments.SESSION_FILE}, используйте скрипт create_session.py')
        exit(-1)

    # Создание экзепляра объекта TelegramClient с использованием TG API и прокси
    # (при написании использовался TG WS Proxy, с ним всё работает, остальное не факт)
    client = TelegramClient(some_arguments.SESSION_FILE, int(some_api_id), some_api_hash,
                            connection=ConnectionTcpMTProxyRandomizedIntermediate,
                            proxy=some_proxy)

    await connect_to_tg(tg_client=client, connection_timeout=some_arguments.TIMEOUT)

    result = await get_contacts(tg_client=client, is_json=some_arguments.JSON, to_count=some_arguments.COUNT)

    # Вывод result в консоль или в файл
    if some_arguments.FILE_NAME:
        file_name = some_arguments.FILE_NAME
        with open(file=file_name, mode='w', encoding='utf-8') as some_file:
            some_file.write(result)
    else:
        print(result)

    # Завершение соединения
    if client:
        await client.disconnect()
    logger.info('Скрипт успешно завершён\n')


# ----------------------------------------------------------------------------------------------------------------------

# Смена директории исполнения скрипта
os.chdir(path=os.path.dirname(__file__))

# Подгрузка секретов из файла .env, создание экзепляра прокси и парсинг аргументов
dotenv.load_dotenv('.env')
api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')
proxy = (os.getenv('PROXY_IP'), int(os.getenv('PROXY_PORT')), os.getenv('PROXY_SECRET'))
arguments = args_parse()

# Создание логгера
logger = setup_logger(in_file=False, is_quiet=arguments.QUIET)

# Запуска основной функции
asyncio.run(
    main(some_arguments=arguments, some_api_id=api_id, some_api_hash=api_hash, some_proxy=proxy)
)
