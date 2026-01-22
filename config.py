
# main.py
import asyncio
import logging
import os
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import CommandStart, Command

# --- Конфигурация и инициализация ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

if not BOT_TOKEN:
    raise ValueError("Токен бота не найден. Убедитесь, что BOT_TOKEN установлен в .env")
if not ADMIN_CHAT_ID:
    raise ValueError("ID чата администратора не найден. Убедитесь, что ADMIN_CHAT_ID установлен в .env")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# --- Определение состояний для FSM ---
class PostCreation(StatesGroup):
    waiting_for_title = State()
    waiting_for_text = State()
    waiting_for_contact = State()
    waiting_for_photos = State()
    confirm_post = State()

# --- Обработчики команд и сообщений ---

@dp.message(CommandStart())
async def command_start_handler(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Привет! Я бот для принятия постов.\n\n"
        "<b>1. Введите заголовок для вашего поста:</b>"
    )
    await state.set_state(PostCreation.waiting_for_title)

@dp.message(Command("cancel"))
@dp.message(F.text.lower() == "отмена")
async def cmd_cancel(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Вы не в процессе создания поста.")
        return

    logging.info("Отмена состояния %s", current_state)
    await state.clear()
    await message.answer("Создание поста отменено. Вы можете начать заново с /start.")

@dp.message(PostCreation.waiting_for_title, F.text)
async def process_title(message: types.Message, state: FSMContext) -> None:
    await state.update_data(title=message.text)
    await message.answer("<b>2. Отлично! Теперь введите основной текст вашего поста:</b>")
    await state.set_state(PostCreation.waiting_for_text)

@dp.message(PostCreation.waiting_for_title)
async def process_title_invalid(message: types.Message):
    await message.answer("Пожалуйста, введите заголовок в виде текста.")


@dp.message(PostCreation.waiting_for_text, F.text)
async def process_text(message: types.Message, state: FSMContext) -> None:
    await state.update_data(text=message.text)
    await message.answer("<b>3. Укажите ваши контактные данные</b> (например, username Telegram, номер телефона, ссылка):")
    await state.set_state(PostCreation.waiting_for_contact)

@dp.message(PostCreation.waiting_for_text)
async def process_text_invalid(message: types.Message):
    await message.answer("Пожалуйста, введите основной текст в виде текста.")


@dp.message(PostCreation.waiting_for_contact, F.text)
async def process_contact(message: types.Message, state: FSMContext) -> None:
    await state.update_data(contact=message.text)

    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Пропустить фото")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    await message.answer(
        "<b>4. Прикрепите фотографии к посту</b> (до 10 штук). "
        "Когда закончите или если фото не нужны, нажмите 'Пропустить фото'.",
        reply_markup=keyboard
    )
    await state.set_state(PostCreation.waiting_for_photos)
    await state.update_data(photos=[])

@dp.message(PostCreation.waiting_for_contact)
async def process_contact_invalid(message: types.Message):
    await message.answer("Пожалуйста, введите контактные данные в виде текста.")


@dp.message(PostCreation.waiting_for_photos, F.photo)
async def process_photos(message: types

Сэм – ChatGPT нейросеть 🧠, [21.01.2026 23:36]
.Message, state: FSMContext) -> None:
    data = await state.get_data()
    photos = data.get('photos', [])

    if len(photos) >= 10:
        await message.answer("Вы уже прикрепили максимальное количество фотографий (10). "
                             "Нажмите 'Пропустить фото', чтобы завершить.")
        return

    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)
    await message.answer(f"Фотография добавлена. Всего {len(photos)} фото.")


@dp.message(PostCreation.waiting_for_photos, F.text == "Пропустить фото")
@dp.message(PostCreation.waiting_for_photos, F.text == "Продолжить")
async def process_skip_photos(message: types.Message, state: FSMContext) -> None:
    await _send_review_post(message, state)


@dp.message(PostCreation.waiting_for_photos)
async def process_photos_invalid(message: types.Message):
    await message.answer("Пожалуйста, присылайте фотографии или нажмите 'Пропустить фото'.")


async def _send_review_post(message: types.Message, state: FSMContext) -> None:
    user_data = await state.get_data()
    title = user_data.get('title')
    text = user_data.get('text')
    contact = user_data.get('contact')
    photos = user_data.get('photos', [])

    review_text = (
        "<b>Предварительный просмотр вашего поста:</b>\n\n"
        f"<b>Заголовок:</b> {title}\n"
        f"<b>Текст:</b> {text}\n"
        f"<b>Контакты:</b> {contact}\n"
    )
    if photos:
        review_text += f"Прикреплено <b>{len(photos)}</b> фото.\n\n"
    else:
        review_text += "Фотографий нет.\n\n"

    review_text += "Все верно? Нажмите 'Отправить пост' или 'Редактировать'."

    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Отправить пост")],
            [types.KeyboardButton(text="Редактировать")],
            [types.KeyboardButton(text="Отмена")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    if photos:
        media_group = []
        media_group.append(types.InputMediaPhoto(media=photos[0], caption=review_text))
        for photo_file_id in photos[1:]:
            media_group.append(types.InputMediaPhoto(media=photo_file_id))
        await message.answer_media_group(media=media_group)
        await message.answer("Проверьте информацию выше и выберите действие:", reply_markup=keyboard)
    else:
        await message.answer(review_text, reply_markup=keyboard)

    await state.set_state(PostCreation.confirm_post)


@dp.message(PostCreation.confirm_post, F.text == "Отправить пост")
async def process_send_post(message: types.Message, state: FSMContext) -> None:
    user_data = await state.get_data()
    title = user_data.get('title')
    text = user_data.get('text')
    contact = user_data.get('contact')
    photos = user_data.get('photos', [])
    user_name = message.from_user.full_name
    user_id = message.from_user.id

    admin_post_text = (
        f"<b>Новый пост от пользователя <a href='tg://user?id={user_id}'>{user_name}</a> (ID: <code>{user_id}</code>):</b>\n\n"
        f"<b>Заголовок:</b> {title}\n"
        f"<b>Текст:</b> {text}\n"
        f"<b>Контакты:</b> {contact}\n"
    )

    try:
        if photos:
            media_group = []
            media_group.append(types.InputMediaPhoto(media=photos[0], caption=admin_post_text))
            for photo_file_id in photos[1:]:
                media_group.append(types.InputMediaPhoto(media=photo_file_id))
            await bot.send_media_group(chat_id=ADMIN_CHAT_ID, media=media_group)
        else:
            await bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_post_text)

        await message.answer("Ваш пост успешно отправлен на модерацию! Спасибо!",
                             reply_markup=types.ReplyKeyboardRemove())
        logging.info(f"Пост от пользователя {user_id} успешно отправлен администратору.")

    except Exception as e:
        logging.error(f"Ошибка при отправке поста администратору от пользователя {user_id}: {e}")
        await message.answer("Произошла ошибка при отправке поста. Пожалуйста, попробуйте еще раз

Сэм – ChatGPT нейросеть 🧠, [21.01.2026 23:36]
позже.",
                             reply_markup=types.ReplyKeyboardRemove())

    await state.clear()

@dp.message(PostCreation.confirm_post, F.text == "Редактировать")
async def process_edit_post(message: types.Message, state: FSMContext) -> None:
    await message.answer("Хорошо, давайте начнем редактирование. \n\n<b>1. Введите новый заголовок:</b>",
                         reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(PostCreation.waiting_for_title)

@dp.message(PostCreation.confirm_post)
async def process_confirm_invalid(message: types.Message):
    await message.answer("Пожалуйста, выберите действие на клавиатуре: 'Отправить пост', 'Редактировать' или 'Отмена'.")


# --- Запуск бота ---
async def main() -> None:
    logging.info("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
```