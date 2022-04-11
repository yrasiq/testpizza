import unittest
from main import *
from fastapi.testclient import TestClient
from unittest import mock


client = TestClient(app)


class TestMain(unittest.TestCase):

    request_data_example = {
        'update_id': 778806239,
        'message': {
            'message_id': 527,
            'from': {
                'id': 450566440,
                'is_bot': False,
                'first_name': 'Юрий',
                'last_name': 'Андреевич',
                'language_code': 'ru'
            },
            'chat': {
                'id': 450566440,
                'first_name': 'Юрий',
                'last_name': 'Андреевич',
                'type': 'private'
            }, 'date': 1649671682,
            'text': 'проверка проверка'
        }
    }
    test_response = type('TestResponse', (object,), {'ok': True})

    @mock.patch('main.BackgroundTasks.add_task')
    @mock.patch('main.telegram_messenger')
    def test_telegram(self, mock_tg_messenger, mock_add_task) -> None:
        mock_tg_messenger.return_value = self.test_response()
        mock_add_task.return_value = None

        resp = client.post(
            f'/{cfg["TELEGRAM"]["BOT_TOKEN"]}/',
            json=self.request_data_example
        )
        self.assertEqual(
            resp.json(),
            {'bot_text': 'Какую вы хотите пиццу?  Большую или маленькую?'}
        )
