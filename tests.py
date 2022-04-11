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
    url = f'/{cfg["TELEGRAM"]["BOT_TOKEN"]}/'

    async def iterate(self, dialog: list) -> None:
        for i in dialog:
            self.request_data_example['message']['text'] = i['req']
            resp = client.post(self.url, json=self.request_data_example)
            self.assertEqual(
                resp.json(),
                {'bot_text': i['res']}
            )

    @mock.patch('main.BackgroundTasks.add_task')
    @mock.patch('main.telegram_messenger')
    async def test_dialog(self, mock_tg_messenger, mock_add_task) -> None:
        mock_tg_messenger.return_value = self.test_response()
        mock_add_task.return_value = None

        dialog = [
            {'req': 'проверка проверка', 'res': 'Какую вы хотите пиццу?  Большую или маленькую?'},
            {'req': 'asdasfa/12312 - абвыв', 'res': 'Большую или маленькую?'},
            {'req': 'Большую!', 'res': 'Как вы будете платить?'},
            {'req': 'asdasfa/12312 - абвыв', 'res': 'Наличными или картой?'},
            {'req': 'КАРТА!', 'res': 'Вы хотите большую пиццу, оплата - по карте?'},
            {'req': 'asdasfa/12312 - абвыв', 'res': 'Да или нет?'},
            {'req': 'да', 'res': 'Спасибо за заказ'},
            {'req': 'Хочу пиццу!', 'res': 'Какую вы хотите пиццу?  Большую или маленькую?'},
            {'req': 'маленькую', 'res': 'Как вы будете платить?'},
            {'req': 'нал', 'res': 'Вы хотите маленькую пиццу, оплата - наличными?'},
            {'req': 'нет', 'res': 'Заказ отменен'},
            {'req': 'проверка проверка', 'res': 'Какую вы хотите пиццу?  Большую или маленькую?'},
            {'req': 'отмена', 'res': 'Заказ отменен'},
        ]

        await self.iterate(dialog)
