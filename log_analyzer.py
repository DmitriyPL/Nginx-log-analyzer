#!/usr/bin/env python
# -*- coding: utf-8 -*-


# log_format ui_short '$remote_addr  $remote_user $http_x_real_ip [$time_local] "$request" '
#                     '$status $body_bytes_sent "$http_referer" '
#                     '"$http_user_agent" "$http_x_forwarded_for" "$http_X_REQUEST_ID" "$http_X_RB_USER" '
#                     '$request_time';

import collections
import statistics
import argparse
import datetime
import pathlib
import logging
import string
import gzip
import json
import time
import sys
import os
import re


TEST_CASE = 100000   # Для отладки на ограниченной выборке, чтобы все не лопатить
DEBUG_MODE = False    # Для отладки

config = {
    "TEMPLATE_PATH": "./reports/report.html",    # Шаблон исходного отчета
    "REPORT_SIZE": 1000,                         # Колво записей в итоговом отчете
    "REPORT_DIR": "./reports",                   # Путь куда пишется отчет
    "LOG_DIR": "./log",                          # Путь откуда читаются исходные логи
    "ERRORS_LIMIT_PERC": 5,                      # Допустимая ошибка парсинга в %
    "SELF_LOG_PATH": "./log/log_analyzer.log"    # Путь к собственныи логам программы
}

FileSubscribe = collections.namedtuple('Subscribe', ['f_date', 'f_path', 'f_ext'])
LogSubscribe = collections.namedtuple('Subscribe', ['url', 'request_time', 'status'])


def get_sys_args():
    '''
    1. Создаем парсер аргуметов
    2. Задаем именованный параметр --config: путь до config файла
    3. Возвращаем путь до config файла либо по default, либо пользовательский
    '''

    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default="./config.json", help="Set path to 'config' file")
    args = parser.parse_args()

    return args.config


def get_result_config(default_config, config_path):
    '''
    1. Пытаемся десериализовать пользовательский config
    2. Если удачно, объединяем пользовательский config и config по дефолту
    '''

    try:
        with open(config_path, 'r') as config_file:
            result_config = json.load(config_file)
        for key in default_config:
            if result_config.get(key) is None:
                result_config[key] = default_config[key]
        return result_config
    except ValueError:
        return None


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


def result_config_is_ok(result_config, logger):

    is_ok = True

    log_dir = result_config.get("LOG_DIR")
    if not os.path.isdir(log_dir):
        logger.info("Директории для поиска лога не существует: {}".format(log_dir))
        is_ok = False

    report_dir = result_config.get("REPORT_DIR")
    if not os.path.isdir(report_dir):
        logger.error("Указанная директория для записи отчета не существует: {}".format(report_dir))
        is_ok = False

    error_limits = result_config.get("ERRORS_LIMIT_PERC")
    if error_limits is None:
        logger.error("Не указан процент ошибок парсинга: ERRORS_LIMIT_PERC")
        is_ok = False

    report_size = result_config.get("REPORT_SIZE")
    if report_size is None:
        logger.error("Не задан размер отчета: REPORT_SIZE")
        is_ok = False

    template_path = result_config.get("TEMPLATE_PATH")
    if not os.path.exists(template_path):
        logger.error("Шаблон отчета по указонному пути не найден: {}".format(template_path))
        is_ok = False

    return is_ok


def find_latest_log(log_dir, logger):
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

    logger.info("Директория для поиска лога: {}".format(log_dir))

    regex = re.compile(r'nginx-access-ui.log-([\d]{8})(.*)')

    f_date_max = datetime.datetime.combine(datetime.date.min, datetime.datetime.min.time())
    f_path_max = None
    f_ext_max = None

    for file_name in os.listdir(log_dir):
        res = regex.search(file_name)
        if (res is not None) and (res.group(2) == '.gz' or res.group(2) == ''):
            f_date = datetime.datetime.strptime(res.group(1), '%Y%m%d')
            f_path = pathlib.Path(log_dir, file_name)
            f_ext = os.path.splitext(f_path)[1]
            if f_date > f_date_max:
                f_date_max = f_date
                f_path_max = f_path
                f_ext_max = f_ext

    if f_path_max is not None:
        logger.info("Найден лог: {}".format(f_path_max))
        return FileSubscribe(f_date_max, f_path_max, f_ext_max)
    else:
        logger.info("Файл лога не найден!")
        return None


def report_exist(report_dir, latest_log, logger):
    '''
    Проверяем, существует ли отчет с таким именем в указанной dir.
    Если да, да парсинг выполнялся и прошел успешно. Заканчиваем работу
    Если нет, возвращаем dir для записи лога
    '''

    report_name = "report-{}.html".format(latest_log.f_date.strftime('%Y.%m.%d'))
    report_path = pathlib.Path(report_dir, report_name)
    if os.path.exists(report_path):
        logger.info("Файл отчета уже существует: {}".format(report_path))
        return None
    else:
        logger.info("Отчет будет записан в файл: {}".format(report_path))
        return report_path


def get_parsed_line(regex, line, logger):

    try:
        res_regex = regex.search(line.decode("utf-8"))
    except UnicodeError:
        logger.exception("Не удалось декодировать запись: {}".format(line))
        return LogSubscribe(None, None, "error")

    if res_regex is None:
        logger.debug("Не удалось распарсить запись: {}".format(line))
        return LogSubscribe(None, None, "bad_log")

    url = res_regex.group(1).strip()
    request_time = res_regex.group(2).strip()

    return LogSubscribe(url, request_time, None)


def get_logs_statistics(error_limits, latest_log, logger):
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
            url_stat["time_med"] = round(statistics.median(url_stat["time_lst"]), 3)
        else:
            common_stat[url] = {
                "url": url,
                "count": 1,
                "count_perc": round((1 / number_of_logs) * 100, 3),
                "time_avg": round(request_time, 3),
                "time_max": round(request_time, 3),
                "time_med": round(statistics.median([request_time]), 3),
                "time_perc": round(request_time / time_sum_all_req * 100, 3),
                "time_sum": round(request_time, 3),
                "time_lst": [request_time]
            }

    log_file.close()
    logger.debug("{} : логов прочитано".format(number_of_logs))
    logger.debug("{} : логов не удалось обработать".format(bad_logs))

    if (bad_logs / number_of_logs) * 100 > error_limits:
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

    with open(report_path, 'w', encoding='utf-8') as report, open(template_path, 'r', encoding='utf-8') as tmpl:
        tmpl_obj = string.Template(tmpl.read())
        try:
            render_html = tmpl_obj.safe_substitute(table_json=table_json)
        except Exception:
            logger.error("Не удалось отрендерить шаблон!")
            return False
        report.write(render_html)
    return True


def main():
    '''
    1. Получаем результирующий config
    2. Создаем логера
    3. Проверяем параметры результирующего config
    4. Ищем файл последнего лога, если не находим конец
    5. Проверяем есть ли уже отчет в указанной папке, если находим конец
    6. Получаем статистику по логам
    7. Создаем отчет
    '''

    str_start = "*************** Программа запущена ***************"
    str_finish = "********************* Конец **********************"
    star_time = time.time()

    config_path = get_sys_args()
    if not os.path.exists(config_path):
        sys.exit(1)

    result_config = get_result_config(config, config_path)
    if result_config is None:
        sys.exit(1)

    log_path = result_config.get('SELF_LOG_PATH')
    if not os.path.exists(log_path):
        log_path = None

    logger = create_logger(__name__, file=log_path)
    logger.info(str_start)

    if not result_config_is_ok(result_config, logger):
        logger.info(str_finish)
        sys.exit(1)

    latest_log = find_latest_log(result_config["LOG_DIR"], logger)
    if latest_log is None:
        logger.info(str_finish)
        sys.exit(0)

    report_path = report_exist(result_config["REPORT_DIR"], latest_log, logger)
    if report_path is None:
        logger.info(str_finish)
        sys.exit(0)

    try:
        logs_statistic = get_logs_statistics(result_config["ERRORS_LIMIT_PERC"], latest_log, logger)
    except Exception:
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
    logger.debug("Время выполнения программы: {}".format(datetime.timedelta(seconds=(time.time() - star_time))))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt as err:
        logging.exception(err)
    except Exception as err:
        logging.exception(err)
