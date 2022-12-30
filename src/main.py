
from functools import cache, partial
from typing import Callable
from telegram import CallbackQuery, Update, InlineKeyboardButton, InlineKeyboardMarkup
import yaml
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler
import openai
import os
TEMPERATURE = 0.5

def load_yml(file_name: str) -> dict[str, str]:
    # check if file exist
    if not os.path.exists(f"{file_name}.yml"):
        save_yml(f"{file_name}", {})
        return {}

    with open(f'{file_name}.yml', 'r') as f:
        data = yaml.safe_load(f)
        if not data:
            return {}
        return data

def save_yml(file_name: str, data: dict[str, str]):
    with open(f'{file_name}.yml', 'w') as f:
        yaml.dump(data, f)

def load_conversation_history()-> dict[str, list[str]]:
    # Load the conversation history from the YAML file
    return load_yml("conversation_history")

def save_conversation_history(data: dict[str, str]):
    return save_yml("conversation_history", data)


def load_temperature() -> dict[str, float]:
    return load_yml("temperature")


def save_temperature(data: dict[str, float]):
    save_yml("temperature", data)


conversation_history = load_conversation_history() # Create a dictionary to store the conversation history for each user
user_temperature = load_temperature()

def reset(update: Update, context: CallbackContext) -> None:
    # Reset the conversation history for the user
    conversation_history[update.effective_user.id] = []
    reply_query(update, 'Riwayat obrolan kamu sudah dihapus.')


def start(update: Update, context: CallbackContext) -> None:
    # Create an inline keyboard with buttons for the /reset and /temperature commands
    reply_text(update, 'Halo, saya Bapak Budi. hhehe. Bantu kamu dalam belajar IoT di Nusabot. Tekan tombol "Buat Topik Obrolan Baru" yah setiap kali kamu ingin membuat topik pertanyaan baru biar saya paham kalau obrolannya sudah selesai.')
    # Initialize the conversation history and temperature for the user if they do not exist
    if update.effective_user.id not in conversation_history:
        conversation_history[update.effective_user.id] = []
    if update.effective_user.id not in user_temperature:
        user_temperature[update.effective_user.id] = 0.5  # Set the default temperature to 0.5

@cache
def get_reply_markup():
        # Create an inline keyboard with buttons for the /reset, /temperature, and /gethistory commands
    keyboard = [[InlineKeyboardButton('Buat Topik Obrolan Baru', callback_data='reset'),
                #  InlineKeyboardButton('Set temperature', callback_data='temperature')
                 ]]
    return InlineKeyboardMarkup(keyboard)


def reply_text(update: Update, message: str):
    update.message.reply_text(message, reply_markup = get_reply_markup())


def reply_query(update: Update, message: str):
    update.callback_query.answer(message)


def generate_temperature_buttons(update: Update, context: CallbackContext) -> list[InlineKeyboardButton]:
    keyboard = [
        [
        InlineKeyboardButton(str(i/10), callback_data=f"temperature_{i}")
        for i in range(1, 10, 2)
        ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.callback_query.message.reply_text('Please select a temperature:', reply_markup=reply_markup)

def set_temperature(new_temp: int, update: Update, context: CallbackContext):
    # Set the temperature for the user based on the callback data
    user_temperature[update.callback_query.from_user.id] = new_temp / 10
    save_temperature(user_temperature)
    update.callback_query.answer(f'Temperature set to {new_temp/10}.')


def invalid_callback(update: Update, context: CallbackContext):
    update.callback_query.answer('Invalid option.')

@cache
def get_button_callback_fns() -> dict[str, Callable]:
    callbacks = {
        "reset": reset,
        "temperature": generate_temperature_buttons,
    }
    temperature_callbacks = {
        f"temperature_{i}": partial(set_temperature, i)
        for i in range(10)
    }
    callbacks.update(temperature_callbacks)
    return callbacks


def button_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    # Check the callback data to determine which command was clicked
    get_button_callback_fns().get(query.data, invalid_callback)(update, context)


def chat(update: Update, context: CallbackContext):
    if update.effective_user.id not in conversation_history:
        conversation_history[update.effective_user.id] = []
    prompt = "\n".join(conversation_history[update.effective_user.id] + [update.message.text])
    try:
        response = openai.Completion.create(
            engine="text-davinci-003",
            prompt=prompt,
            max_tokens=1024,
            temperature=0.5,
        )
        result = response.choices[0].text

        if not result:
            print("empty result")
            reply_text(update, "Yah maaf, saya tidak tahu kalau itu. Tempe ada sih. Mau?")
            return
        conversation_history[update.effective_user.id].append(update.message.text)

        conversation_history[update.effective_user.id].append(result)
        save_conversation_history(conversation_history)
        reply_text(update, result)
    except openai.error.InvalidRequestError:
        print("Jawaban akan terlalu panjang")
        reply_text(update, "Jawabannya akan panjang, coba beri saya pertanyaan lain deh yang lebih spesifik.")


def load_cred() -> dict[str, str]:
    if not os.path.exists("credentials.yml"):
        openai_api_key = input("input openai api key: ")
        telegram_token = input("input telegram token: ")
        admin_pw = input("input admin password: ")
        save_yml("credentials", {"openai_api_key": openai_api_key, "telegram_token": telegram_token})
        return {"openai_api_key": openai_api_key, "telegram_token": telegram_token}
    with open("credentials.yml") as f:
        return yaml.safe_load(f)


def main():
    cred = load_cred()
    TOKEN = cred["telegram_token"]
    openai.api_key = cred["openai_api_key"]
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler('start', start))
    dp.add_handler(MessageHandler(Filters.text, chat))
    dp.add_handler(CallbackQueryHandler(button_callback))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
