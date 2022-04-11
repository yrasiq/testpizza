import unittest
from main import *
from fastapi.testclient import TestClient
from unittest import mock


client = TestClient(app)


class TestMain(unittest.TestCase):

    @mock.patch('main.telegram_messenger')
    def test(self, mock_tg_messenger) -> None:
        mock_tg_messenger.return_value = None
