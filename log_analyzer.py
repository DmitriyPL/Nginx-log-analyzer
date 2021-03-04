#!/usr/bin/env python
# -*- coding: utf-8 -*-


# log_format ui_short '$remote_addr  $remote_user $http_x_real_ip [$time_local] "$request" '
#                     '$status $body_bytes_sent "$http_referer" '
#                     '"$http_user_agent" "$http_x_forwarded_for" "$http_X_REQUEST_ID" "$http_X_RB_USER" '
#                     '$request_time';

import argparse
import pathlib
import logging.handlers
import logging
import string
import gzip
import json
import time
import sys
import os
import re


from collections import namedtuple
from datetime import datetime, date
from statistics import median
from shutil import copy2


TEST_CASE = 1000   # Для отладки на ограниченной выборке, чтобы все не лопатить
DEBUG_MODE = True  # Для отладки

config = {
    "TEMPLATE_PATH": "./reports/report.html",    # Шаблон исходного отчета
    "REPORT_SIZE": 1000,                         # Колво записей в итоговом отчете
    "REPORT_DIR": "./reports",                   # Путь куда пишется отчет
    "LOG_DIR": "./log",                          # Путь откуда читаются исходные логи
    "ERRORS_LIMIT_PERC": 5,                      # Допустимая ошибка парсинга в %
    "SELF_LOG_PATH": "./log/log_analyzer.log"  # Путь к собственныи логам программы
    # "SELF_LOG_PATH": None
}


def create_args_parser():
    '''
    Создаем парсер аргуметов и устанавливаем имя именованного параметра (путь до config файла)
    '''

    parser = argparse.ArgumentParser()

    parser.add_argument('--config', default=None)

    return parser


def get_config_file(default_config, logger):
    '''
    Получаем путь до config файла или его отсутствие. Сравниваем пользовательский и default config
    Возвращаем настроенный config файл
    '''

    arg_parser = create_args_parser()
    namespace = arg_parser.parse_args(sys.argv[1:])
    config_path = namespace.config

    if config_path is None:

        logger.info("Пользователь не указал config файл")

        return default_config

    else:

        if os.path.exists(config_path):

            try:

                with open(config_path, 'r') as config_file:

                    user_config = json.load(config_file)

                logger.info("Для настроек используется - {}".format(config_path))

                return compare_config(default_config, user_config, logger)

            except ValueError:

                logger.error("Не удалось десериализовать config файл")

                return None

        else:

            logger.error("Пользовательского config файла не существует!")

            return None


def compare_config(default_config, user_config, logger):
    '''
    Проверяем наличие ключей из default config в пользовательском.
    Если ключи в пользовательском от сутствуют добавляем.
    Возвращаем resul_config
    '''

    for key in default_config:

        if user_config.get(key) is None:

            logger.debug("В пользовательский config добавлен параметр {}".format(key))

            user_config[key] = default_config[key]

    return user_config


def get_date_from_name(file_name):
    '''
    Ищет в имени файла дату.
    Возвращает дату в формате '%Y%m%d'
    '''

    regex = re.compile(r'\d+')
    str_date = regex.search(file_name).group()

    return datetime.strptime(str_date, '%Y%m%d')


def find_latest_log(result_config, logger):
    '''
    Ищет в указанной дериктории (config["LOG_DIR"]) файл последнего лога:
        1. Выбирает все файлы начинающиеся с 'nginx-access-ui'
        2. Сортирует фалы по дате в имени, например из файлов
            .\nginx-access-ui.log-20170630
            .\nginx-access-ui.log-20180630
            .\nginx-access-ui.log-20180701.gz
    будет выбран "nginx-access-ui.log-20180701.gz" как самый свежий.
    Возвращает полный путь файла.
    '''

    log_dir = result_config["LOG_DIR"]

    if os.path.isdir(log_dir):
        logger.info("Директория для поиска лога: {}".format(log_dir))
    else:
        logger.info("Директории для поиска лога не существует: {}".format(log_dir))
        return None

    Subscribe = namedtuple('Subscribe', ['f_date', 'f_path', 'f_ext'])

    regex = re.compile(r'nginx-access-ui.log-[\d]{8}(.*)')

    f_date_max = datetime.combine(date.min, datetime.min.time())
    f_path_max = None
    f_ext_max = None

    for file_name in os.listdir(log_dir):

        res = regex.search(file_name)
        if (res is not None) and (res.group(1) == '.gz' or res.group(1) == ''):

            f_date = get_date_from_name(file_name)
            f_path = pathlib.Path(log_dir, file_name)
            f_ext = os.path.splitext(f_path)[1]

            if f_date > f_date_max:

                f_date_max = f_date
                f_path_max = f_path
                f_ext_max = f_ext

    if f_path_max is not None:

        logger.info("Найден лог: {}".format(f_path_max))

        return Subscribe(f_date_max, f_path_max, f_ext_max)

    else:

        logger.info("Файл лога не найден!")

        return None


def get_parsed_line(regex, line, logger):

    Subscribe = namedtuple('Subscribe', ['url', 'request_time', 'status'])

    try:
        res_regex = regex.search(line.decode("utf-8"))
    except UnicodeError:
        logger.exception("Не удалось декодировать запись: {}".format(line))
        return Subscribe(None, None, "error")

    if res_regex is None:
        logger.debug("Не удалось распарсить запись: {}".format(line))
        return Subscribe(None, None, "bad_log")

    url = res_regex.group(1).strip()
    request_time = res_regex.group(2).strip()

    return Subscribe(url, request_time, None)


def get_logs_statistics(result_config, latest_log, logger):
    '''
    Обрабатываем фал лога:
        1. Читаем строку лога
        2. Парсим строку регуляркой
        3. Ищем url в словаре по ключу! Добавляем строку в словарь с первичной статистикой если такой url еще нет.
           Обновляем статистику если строка с таким url уже есть в словаре
           Cтруктура словаря {url1:{stat1}, url2:{stat2}, url3:{stat3} ...}
        4. Чекаем на колво ошибо парсинга. Если ошибок больше установленого ERRORS_LIMIT_PERC в config выходим
        5. Выгружаем из dict.values() -> list
        6. Дописываем статистику
        7. Сортируем list
        8. Возвращаем статистику по логам
    '''

    common_stat = {}
    time_sum_all_req = 0
    bad_logs = 0
    number_of_logs = 0

    regex = re.compile(r'(?:GET|POST|HEAD|PUT|OPTIONS|DELETE).(.*).HTTP/.* (\d{1,6}[.]\d+)')

    log_path = latest_log.f_path

    try:
        log_file = gzip.open(log_path, 'rb') if latest_log.f_ext == ".gz" else open(log_path, 'rb')
    except OSError:
        logger.error("Не удалось открыть файл лога: {}".format(log_path))
        return None

    for line in log_file:

        if DEBUG_MODE and number_of_logs == TEST_CASE:  # Использую для отладки на частичной выборке
            break

        number_of_logs += 1

        parsed_line = get_parsed_line(regex, line, logger)

        status = parsed_line.status
        if status == "bad_log":
            bad_logs += 1
            continue
        elif status == "error":
            return None

        url = parsed_line.url
        request_time = float(parsed_line.request_time)

        time_sum_all_req += request_time

        url_stat = common_stat.get(url)

        if url_stat is not None:
            url_stat["count"] += 1
            url_stat["time_sum"] = round(url_stat["time_sum"] + request_time, 3)
            url_stat["time_max"] = round(request_time if request_time > url_stat["time_max"] else
                                         url_stat["time_max"], 3)
            url_stat["time_lst"].append(request_time)
            url_stat["time_med"] = round(median(url_stat["time_lst"]), 3)
        else:
            common_stat[url] = {
                "url": url,
                "count": 1,
                "count_perc": round((1 / number_of_logs) * 100, 3),
                "time_avg": round(request_time, 3),
                "time_max": round(request_time, 3),
                "time_med": round(median([request_time]), 3),
                "time_perc": round(request_time / time_sum_all_req * 100, 3),
                "time_sum": round(request_time, 3),
                "time_lst": [request_time]
            }

    log_file.close()

    logger.debug("{} : логов прочитано".format(number_of_logs))
    logger.debug("{} : логов не удалось обработать".format(bad_logs))

    if (bad_logs / number_of_logs) * 100 > result_config["ERRORS_LIMIT_PERC"]:
        logger.error("Сменился формат логирования!")
        return None

    common_stat_as_lst = list(common_stat.values())

    for url_stat in common_stat_as_lst:
        url_stat["count_perc"] = round((url_stat["count"] / number_of_logs) * 100, 3)
        url_stat["time_perc"] = round(url_stat["time_sum"] / time_sum_all_req * 100, 3)
        url_stat["time_avg"] = round(url_stat["time_sum"] / url_stat["count"], 3)
        del url_stat["time_lst"]

    return sorted(common_stat_as_lst, key=lambda x: x["time_sum"], reverse=True)


def render_html_report(result_config, report_path, logs_statistic, logger):
    '''
    Дампим статистику в json строку.
    Копируем шаблон отчета в указанную в config dir уже с нужным именем
    Рендерим отчет
    '''

    table_json = json.dumps(logs_statistic[:result_config["REPORT_SIZE"]])

    template_path = result_config["TEMPLATE_PATH"]
    if not os.path.exists(template_path):
        logger.error("Шаблон отчета по указонному пути не найден: {}".format(template_path))

    try:
        copy2(template_path, report_path)
    except Exception:
        logger.error("Не удалось скопировать шаблон отчета!")
        return False

    with open(report_path, 'w', encoding='utf-8') as report, open(template_path, 'r', encoding='utf-8') as tmpl:

        tmpl_obj = string.Template(tmpl.read())

        try:
            render_html = tmpl_obj.safe_substitute(table_json=table_json)
        except Exception:
            logger.error("Не удалось отрендерить шаблон!")
            return False

        report.write(render_html)

    return True


def report_exist(result_config, latest_log, logger):
    '''
    Проверяем, существует ли отчет с таким именем в указанной dir.
    Если да, да парсинг выполнялся и прошел успешно. Заканчиваем работу
    Если нет, возвращаем dir для записи лога
    '''

    report_dir = result_config["REPORT_DIR"]

    if not os.path.isdir(report_dir):
        logger.error("Указанная директория для записи отчета не существует: {}".format(report_dir))
        return None

    report_name = "report-{}.html".format(latest_log.f_date.strftime('%Y.%m.%d'))

    report_path = pathlib.Path(report_dir, report_name)

    if os.path.exists(report_path):
        logger.info("Файл отчета уже существует: {}".format(report_path))
        return None
    else:
        logger.info("Отчет будет записан в файл: {}".format(report_path))
        return report_path


def create_logger(name, log_level=logging.DEBUG, stdout=True, file=None):
    '''
    Создает логера, есть возможность создать логера с выводом в stdout или в файл или туда и туда.
    '''

    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    formatter = logging.Formatter('[%(asctime)s] - %(name)s - %(levelname).1s - %(message)s')

    if file is not None:
        fh = logging.FileHandler(file)
        fh.setLevel(log_level)
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    if stdout:
        ch = logging.StreamHandler()
        ch.setLevel(log_level)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

    return logger


def main():
    '''
    1. Генерим config
    2. Проверяем есть ли уже отчет в указанной папке
    3. Находим последний лог для парсинга
    4. Проверяем нет ли уже созданого отчета по данному логу
    5. Создаем отчет
    '''

    str_start = "*************** Программа запущена ***************"
    str_finish = "********************* Конец **********************"

    star_time = time.time()

    log_path = config.get('SELF_LOG_PATH')
    if log_path is None:
        pass
    else:
        if not os.path.exists(log_path):
            log_path = None

    logger = create_logger(__name__, file=log_path)

    logger.info(str_start)

    result_config = get_config_file(config, logger)

    if result_config is None:
        logger.info(str_finish)
        sys.exit(1)

    latest_log = find_latest_log(result_config, logger)

    if latest_log is None:
        logger.info(str_finish)
        sys.exit(1)

    report_path = report_exist(result_config, latest_log, logger)

    if report_path is None:
        logger.info(str_finish)
        sys.exit(1)

    try:
        logs_statistic = get_logs_statistics(result_config, latest_log, logger)
    except BaseException:
        logger.error("Аварийное завершение программы!!!")
        logger.info(str_finish)
        sys.exit(1)

    if logs_statistic is None:
        logger.info(str_finish)
        sys.exit(1)

    if not render_html_report(result_config, report_path, logs_statistic, logger):
        logger.info(str_finish)
        sys.exit(1)

    logger.info(str_finish)

    logger.debug("Время выполнения программы: {}".format(time.time() - star_time))


if __name__ == "__main__":

    main()
