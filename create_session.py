from opentele2.td import TDesktop
from opentele2.api import API, CreateNewSession
from opentele2.exception import TFileNotFound
from telethon.sync import TelegramClient
from telethon.network.connection import ConnectionTcpMTProxyRandomizedIntermediate
from telethon.errors.rpcerrorlist import FloodWaitError
import argparse, asyncio, os, logging, dotenv, random


# ----------------------------------------------------------------------------------------------------------------------

def args_parse(args_line: list[str] = None) -> argparse.Namespace:
    """
    Парсер аргументов командной строки

    Args:
        args_line: список аргументов формата ['-X', '...']
    """

    def normalize_tdata_path(path: str) -> str:
        if path[-1] == "\"":
            path = path[:-1]
        return os.path.normpath(path)

    def normalize_session_path(path: str) -> str:
        return os.path.normpath(path)
            
    parser = argparse.ArgumentParser(description='Скрипт для создания файла сессии Telegram, используя только '
                                                 'содержимое папки tdata',
                                     add_help=False)

    parser.add_argument('-h',
                        action='help', default=argparse.SUPPRESS,
                        help='Показать help сообщение и выйти')
    parser.add_argument('-q',
                        action='store_true', dest='QUIET',
                        help='Скрыть логи')
    parser.add_argument('-s',
                        type=normalize_session_path, default='TG_Session.session', dest='SESSION_FILE',
                        help=r'Путь до файла Telegram сессии (default=.\TG_Session.session)')
    parser.add_argument('-t',
                        type=int, default=30, dest='TIMEOUT',
                        help='Таймаут подключения в секундах (default=30)')
    parser.add_argument('-r',
                        action='store_true', dest='REWRITE',
                        help='Принудительное пересоздание файла Telegram сессии')
    parser.add_argument('-T',
                        type=normalize_tdata_path, default='tdata', dest='TDATA_FOLDER',
                        help=r'Путь до папки tdata (default=.\tdata)')

    return parser.parse_args(args_line)


def setup_logger(in_file: bool = True, is_quiet: bool = False) -> logging.Logger:
    """
    Создание логгера

    Args:
        in_file: записывать логи в файл (=true) или выводить в консоль (=false)
        is_quiet: подавить вывод (=true) или нет (=false)
    """
    some_logger = logging.getLogger(__name__)
    some_logger.setLevel(logging.INFO)
    if in_file:
        info_handler = logging.FileHandler('log.txt', mode='a', encoding='utf-8')
    else:
        info_handler = logging.StreamHandler()
    info_handler.setLevel(logging.INFO)
    info_formatter = logging.Formatter('[%(asctime)s] - %(levelname)s - %(funcName)s - %(message)s')
    info_handler.setFormatter(info_formatter)
    some_logger.addHandler(info_handler)
    if is_quiet:
        logging.disable(logging.CRITICAL)

    return some_logger


async def create_session(tdata_folder: str,
                         session_file: str,
                         connection_timeout: int,
                         proxy_data: tuple) -> None:
    """
    Создание файла сессии, который используется при подключении к серверам Telegram в библиотеке telethon
    из содержимого папки tdata

    Args:
        tdata_folder: путь до папки tdata
        session_file: файл сессии
        connection_timeout: время таймаута при подключении к серверам Telegram
        proxy_data: набор параметров для подключения к прокси - (ip, port, secret)
    """
    try:
        tg_desktop_instance = TDesktop(tdata_folder)

        api = random.choice([API.TelegramDesktop.Generate,
                             API.TelegramIOS.Generate,
                             API.TelegramAndroid.Generate,
                             API.TelegramMacOS.Generate])()
        tg_client = await asyncio.wait_for(
            tg_desktop_instance.ToTelethon(session_file, CreateNewSession, api,
                                           connection=ConnectionTcpMTProxyRandomizedIntermediate,
                                           proxy=proxy_data
                                           ),
            timeout=connection_timeout
        )
    except TFileNotFound:
        logger.error(f'Содержимое папки {tdata_folder} не подходит для создания файла сессии\n')
        exit(-1)
    except asyncio.TimeoutError:
        logger.error(f'Таймаут при создании сессии (>{connection_timeout} секунд)\n')
        exit(-1)
    except FloodWaitError:
        logger.error('Ошибка, Telegram блокирует подключение из-за прошлых неуспешных попыток, нужно подождать 1 час')
        logger.info('При следующей попытке лучше включить флаг -r\n')
        exit(-1)
    finally:
        if tg_client:
            await tg_client.disconnect()
    logger.info(f'Создан файл сессии {session_file}')


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
        logger.error(f'Таймаут при соединении с сервером (>{connection_timeout} секунд)\n')
        exit(-1)
    except asyncio.IncompleteReadError:
        logger.error(f'Файл сессии не подходит для установления соединения\n')
        exit(-1)
    except FloodWaitError:
        logger.error('Ошибка, Telegram блокирует подключение из-за прошлых неуспешных попыток, нужно подождать 1 час\n')
        exit(-1)
    logger.info('Успешная авторизация')


async def main(some_arguments: argparse.Namespace,
               some_api_id: int | str,
               some_api_hash: str,
               some_proxy: tuple) -> None:
    logger.info('Скрипт запущен')

    # Проверка наличия папки tdata
    if not os.path.exists(some_arguments.TDATA_FOLDER):
        logger.error('Не найдена папка tdata, укажите путь до неё с помощью флага -T')
        exit(-1)

    # При отсутствии указанного файла Telegram сессии и отсутствии флага -r создаётся новая сессия
    if os.path.exists(some_arguments.SESSION_FILE) and not some_arguments.REWRITE:
        logger.info(f'Файл сессии {some_arguments.SESSION_FILE} уже существует')
    else:
        logger.info('Создаётся новый файл формата Telegram сессии')
        await create_session(tdata_folder=some_arguments.TDATA_FOLDER,
                             session_file=some_arguments.SESSION_FILE,
                             connection_timeout=some_arguments.TIMEOUT,
                             proxy_data=some_proxy)

    # Создание экзепляра объекта TelegramClient с использованием TG API и прокси
    # (при написании использовался TG WS Proxy, с ним всё работает, остальное не факт)
    client = TelegramClient(some_arguments.SESSION_FILE, int(some_api_id), some_api_hash,
                            connection=ConnectionTcpMTProxyRandomizedIntermediate,
                            proxy=some_proxy)

    # Проверка работы полученного файла Telegram сессии
    await connect_to_tg(tg_client=client, connection_timeout=some_arguments.TIMEOUT)

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
