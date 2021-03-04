import re
import unittest

from log_analyzer import create_logger
from log_analyzer import compare_config
from log_analyzer import get_date_from_name
from log_analyzer import get_parsed_line

from test_data import compare_tests
from test_data import date_from_name_tests
from test_data import parsed_line_tests

logger = create_logger("test")


class LogAnalyzerTest(unittest.TestCase):

    def test_compare_config(self):

        for def_config, user_config, res_config in compare_tests:
            self.assertEqual(compare_config(def_config, user_config, logger), res_config)

    def test_get_date_from_name(self):

        for file_name, str_date in date_from_name_tests:
            self.assertEqual(get_date_from_name(file_name), str_date)

    def test_get_parsed_line(self):

        regex = re.compile(r'(?:GET|POST|HEAD|PUT|OPTIONS|DELETE).(.*).HTTP/.* (\d{1,6}[.]\d+)')

        for log_str, tlp in parsed_line_tests:
            self.assertEqual(get_parsed_line(regex, log_str, logger), tlp)


if __name__ == "__main__":
    unittest.main()

