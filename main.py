import uvicorn, configparser, re, requests, asyncio, json
from fastapi import FastAPI, Request, BackgroundTasks
from transitions import Machine, State
from pydantic import BaseModel
from datetime import timedelta, datetime


cfg = configparser.ConfigParser()
cfg.read('.cfg')
app = FastAPI()
app.state.clients = {
    'telegram': {},
    'vk': {},
    'facebook': {},
    'skype': {},
}


def telegram_messenger(text: str, chat_id: int) -> requests.Response:
    return requests.get(
        f'http://api.telegram.org/bot{cfg["TELEGRAM"]["BOT_TOKEN"]}/sendMessage',
        params={'chat_id': chat_id, 'text': text}
    )

def read(file: str) -> str:
    with open(file) as f:
        return f.read()


class UnsupportedValue(Exception):

    def __init__(self, hint: str, *args: object) -> None:
        self.hint = hint
        super().__init__(*args)


class CustomState(State):

    def __init__(
        self,
        text: str,
        hint: str,
        possible_vals: list,
        vars={},
        *args,
        **kwargs
    ) -> None:
        self.vars = vars
        self.text = text
        self.hint = hint
        self.possible_vals = possible_vals
        super().__init__(*args, **kwargs)

    def get_val(self, text: str) -> str:
        for val in self.possible_vals:
            if text in val['interprirations']:
                return val['value']
        else:
            raise UnsupportedValue(
                self.hint,
                f'Invalid value "{text}"'
            )


class Dialog:

    current_bot_message = ''
    accept_message = 'Спасибо за заказ'
    cancel_message = 'Заказ отменен'
    cancel_phrases = ['отмена',]
    states = [
        State(name='sleep'),
        CustomState(**json.loads(read('states/size.json'))),
        CustomState(**json.loads(read('states/payment_type.json'))),
        CustomState(**json.loads(read('states/confirm.json')))
    ]

    def __init__(self, chat_id: int, messenger: callable) -> None:

        self.machine = Machine(
            model=self,
            states=Dialog.states,
            initial='sleep'
        )

        self.last_call = datetime.now()
        self.messenger = messenger
        self.chat_id = chat_id
        self._payment_type = 'unk'
        self._size = 'unk'
        self._confirm = 'unk'

        self.machine.add_transition(
            'ask',
            '*',
            'size',
            unless='size_known',
            after='_ask'
        )
        self.machine.add_transition(
            'ask',
            '*',
            'payment_type',
            after='_ask',
            unless='payment_type_known'
        )
        self.machine.add_transition(
            'ask',
            '*',
            'confirm',
            after=['set_confirm_text', '_ask'],
            unless='confirm_known',
            conditions=[
                'size_known',
                'payment_type_known'
            ]
        )
        self.machine.add_transition(
            'accept_order',
            'confirm',
            'sleep',
            after=[
                '_accept_order',
                'clear',
            ],
            conditions=[
                'size_known',
                'payment_type_known',
                'confirm_known'
            ]
        )
        self.machine.add_transition(
            'cancel_order',
            '*',
            'sleep',
            after=[
                'clear',
                '_cancel_order'
            ]
        )

    def __call__(self, client_text: str) -> str:
        self.last_call = datetime.now()
        self.current_bot_message = ''
        client_text = re.sub('[^а-я0-9\s]', '', client_text.lower())

        if self.state != 'sleep' and client_text in self.cancel_phrases:
            self.cancel_order()
            return self.current_bot_message

        try:
            if self.state == 'sleep':
                self.ask()

            elif self.state == 'size':
                self.size = client_text
                self.ask()

            elif self.state == 'payment_type':
                self.payment_type = client_text
                self.ask()

            elif self.state == 'confirm':
                self.confirm = client_text
                if self.confirm == 'yes':
                    self.accept_order()
                elif self.confirm == 'no':
                    self.cancel_order()

        except UnsupportedValue as e:
            self.send_message(text=e.hint)

        return self.current_bot_message

    def _accept_order(self) -> None:
        self.send_message(text=self.accept_message)

    def _cancel_order(self) -> None:
        self.send_message(text=self.cancel_message)

    def _ask(self) -> None:
        self.send_message(text=self.machine.get_state(self.state).text)

    def set_confirm_text(self) -> None:
        state = self.machine.get_state('confirm')
        state.text = state.text.format(
            state.vars.get(self.size),
            state.vars.get(self.payment_type)
        )
        print(state.text)

    def send_message(self, *args, **kwargs) -> None:
        self.current_bot_message = kwargs.get('text', '')
        kwargs['chat_id'] = self.chat_id
        res = self.messenger(*args, **kwargs)
        if not res.ok and self.state != 'sleep':
            self.cancel_order()

    def clear(self) -> None:
        del self.confirm
        del self.size
        del self.payment_type

    @property
    def size_known(self) -> bool:
        return False if self._size == 'unk' else True

    @property
    def size(self) -> str:
        return self._size

    @size.deleter
    def size(self) -> None:
        self._size = 'unk'

    @size.setter
    def size(self, text: str) -> None:
        self._size = self.machine.get_state(self.state).get_val(text)

    @property
    def payment_type_known(self) -> bool:
        return False if self._payment_type == 'unk' else True

    @property
    def payment_type(self) -> str:
        return self._payment_type

    @payment_type.deleter
    def payment_type(self) -> None:
        self._payment_type = 'unk'

    @payment_type.setter
    def payment_type(self, text: str) -> None:
        self._payment_type = self.machine.get_state(self.state).get_val(text)

    @property
    def confirm_known(self) -> bool:
        return True if self._confirm == 'yes' else False

    @property
    def confirm(self) -> str:
        return self._confirm

    @confirm.deleter
    def confirm(self) -> None:
        self._confirm = 'unk'

    @confirm.setter
    def confirm(self, text: str) -> None:
        self._confirm = self.machine.get_state(self.state).get_val(text)


class TelegramUser(BaseModel):
    id: int
    is_bot: bool
    first_name: str
    last_name: str
    language_code: str


class TelegramChat(BaseModel):
    id: int
    first_name: str
    last_name: str
    type: str


class TelegramMessage(BaseModel):
    message_id: int
    from_: TelegramUser
    chat: TelegramChat
    date: int
    text: str

    class Config:
        fields = {
            'from_': 'from'
        }


class TelegramHook(BaseModel):
    update_id: int
    message: TelegramMessage


async def dialog_deleter(
    interval: timedelta,
    timeout: timedelta,
    messenger: str,
    chat_id: int
) -> None:
    interval = interval.total_seconds()
    dialog = app.state.clients[messenger][chat_id]
    while True:
        await asyncio.sleep(interval)
        if datetime.now() - dialog.last_call > timeout:
            if dialog.state != 'sleep':
                dialog.cancel_order()
            app.state.clients[messenger].pop(chat_id)
            return

@app.post(f'/{cfg["TELEGRAM"]["BOT_TOKEN"]}/')
async def telegram_webhook(data: TelegramHook, background_tasks: BackgroundTasks):
    clients = app.state.clients['telegram']
    chat_id = str(data.message.chat.id)
    dialog = clients.get(chat_id)

    if dialog is None:
        dialog = Dialog(chat_id, telegram_messenger)
        clients[chat_id] = dialog
        background_tasks.add_task(
            dialog_deleter,
            timedelta(seconds=int(cfg['DIALOG_DELETER']['INTERVAL'])),
            timedelta(seconds=int(cfg['DIALOG_DELETER']['TIMEOUT'])),
            'telegram',
            chat_id
        )

    bot_text = dialog(data.message.text)

    return {'bot_text': bot_text}


if __name__ == '__main__':
    uvicorn.run(
        'main:app',
        port=int(cfg['UVICORN']['PORT']),
        host=cfg['UVICORN']['HOST']
    )
