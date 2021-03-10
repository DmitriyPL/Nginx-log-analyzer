import unittest
import os
import re


from log_analyzer import create_logger
from log_analyzer import get_result_config
from log_analyzer import get_parsed_line
from log_analyzer import find_latest_log

from test_data import compare_tests
from test_data import parsed_line_tests

logger = create_logger("test")


class LogAnalyzerTest(unittest.TestCase):

    def test_get_result_config(self):

        for def_config, config_path, res_config in compare_tests:
            self.assertEqual(get_result_config(def_config, config_path), res_config)

    def test_get_parsed_line(self):

        regex = re.compile(r'(?:GET|POST|HEAD|PUT|OPTIONS|DELETE).(.*).HTTP/.* (\d{1,6}[.]\d+)')

        for log_str, tlp in parsed_line_tests:
            self.assertEqual(get_parsed_line(regex, log_str, logger), tlp)

    def test_find_latest_log(self):
        latest_log = find_latest_log("./tests/latest_log/", logger)
        self.assertEqual(os.path.basename(latest_log.f_path), "nginx-access-ui.log-20180730")


if __name__ == "__main__":
    unittest.main()

