from datetime import datetime

compare_tests = [
    (
        {
            "TEMPLATE_PATH": "./reports/report.html",
            "REPORT_SIZE": 1000,
            "REPORT_DIR": "./reports",
            "LOG_DIR": "./log",
            "ERRORS_LIMIT_PERC": 5,
            "SELF_LOG_PATH": None
        },
        "./tests/user_config/user_config_1.json",
        {
            "REPORT_SIZE": 10,
            "REPORT_DIR": "C:\\reports",
            "LOG_DIR": "C:\\logs",
            "TEMPLATE_PATH": "./reports/report.html",
            "ERRORS_LIMIT_PERC": 5,
            "SELF_LOG_PATH": None
        }
    ),
    (
        {
            "TEMPLATE_PATH": "./reports/report.html",
            "REPORT_SIZE": 1000,
            "REPORT_DIR": "./reports",
            "LOG_DIR": "./log",
            "ERRORS_LIMIT_PERC": 5,
            "SELF_LOG_PATH": "./log/log_analyzer.log"

        },
        "./tests/user_config/user_config_2.json",
        {
            "TEMPLATE_PATH": "./reports/report.html",
            "REPORT_SIZE": 1000,
            "REPORT_DIR": "./reports",
            "LOG_DIR": "./log",
            "ERRORS_LIMIT_PERC": 5,
            "SELF_LOG_PATH": "./log/log_analyzer.log"
        }
    )
]

parsed_line_tests = [
    (b'1.196.116.32 -  - [29/Jun/2017:03:50:22 +0300] "GET /api/v2/banner/25019354 HTTP/1.1" 200 927 "-" "Lynx/2.8.8dev.9 libwww-FM/2.14 SSL-MM/1.4.1 GNUTLS/2.10.5" "-" "1498697422-2190034393-4708-9752759" "dc7161be3" 0.390',
        ("/api/v2/banner/25019354", "0.390", None)),
    (b'1.196.116.32 -  - [29/Jun/2017:03:50:22 +0300] "GET - HTTP/1.1" 200 927 "-" "Lynx/2.8.8dev.9 libwww-FM/2.14 SSL-MM/1.4.1 GNUTLS/2.10.5" "-" "1498697422-2190034393-4708-9752759" "dc7161be3" 0.390',
        ('-', "0.390", None)),
    (b'1.196.116.32 -  - [29/Jun/2017:03:50:22 +0300] "-" 200 927 "-" "Lynx/2.8.8dev.9 libwww-FM/2.14 SSL-MM/1.4.1 GNUTLS/2.10.5" "-" "1498697422-2190034393-4708-9752759" "dc7161be3" 0.390',
        (None, None, "bad_log")),
    (b'1.196.116.32 -  - [29/Jun/2017:03:50:22 +0300] "-" 200 927 "-" "Lynx/2.8.8dev.9 libwww-FM/2.14 SSL-MM/1.4.1 GNUTLS/2.10.5" "-" "1498697422-2190034393-4708-9752759" "dc7161be3" -',
        (None, None, "bad_log"))
]
