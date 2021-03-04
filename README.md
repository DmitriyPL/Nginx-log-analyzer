# home_work_1
**nginx_log_analyzer**

1. Скрипт парсит логи **nginx** и выдает отчет со статистикой по запросам ввиде **.html** файла

2. Структура лога:

  log_format ui_short '$remote_addr  $remote_user $http_x_real_ip [$time_local] "$request" '
                      '$status $body_bytes_sent "$http_referer" '
                      '"$http_user_agent" "$http_x_forwarded_for" "$http_X_REQUEST_ID" "$http_X_RB_USER" '
                      '$request_time';

3. При запуске скрипта можно указать путь до config файла:
  python log_analyzer.py --config "Путь"
  
- Файл config-a имеет формат .json и следующую структуру:

{
***
    - "TEMPLATE_PATH": "./reports/report.html",    # Шаблон исходного отчета
    - "REPORT_SIZE": 1000,                         # Колво записей в итоговом отчете
    - "REPORT_DIR": "./reports",                   # Путь куда пишется отчет
    - "LOG_DIR": "./log",                          # Путь откуда читаются исходные логи
    - "ERRORS_LIMIT_PERC": 5,                      # Допустимая ошибка парсинга в %
    - "SELF_LOG_PATH": "./log/log_analyzer.log"    # Путь к собственныи логам программы
    -  "SELF_LOG_PATH": None                      # Вывод логов в stdout
- }

- Название логов имеет структуру:
    - nginx-access-ui.log-20170630 (меняется только дата)
    - nginx-access-ui.log-20170630.gz (лог может быть запакован)

- Парсер возьмет из указаном папки последний лог (определить по названию файла)

- Для запуска тестов ипользуйте
    - python test_log_analyzer.py -v
  
- Данные для тестов в 
    - test_data.py
  
