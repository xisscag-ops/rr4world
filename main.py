import asyncio
import logging
import os
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import CommandStart, Command
from aiogram.client.default import DefaultBotProperties

# --- Конфигурация и инициализация ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_IDS_STR = os.getenv("ADMIN_CHAT_IDS")
OFFER_POST_CHANNEL_URL = os.getenv("OFFER_POST_CHANNEL_URL", "https://t.me/your_channel_link") # <-- ОБЯЗАТЕЛЬНО ИЗМЕНИТЕ ЭТО ЗНАЧЕНИЕ В .env или ЗДЕСЬ

if not BOT_TOKEN:
    raise ValueError("Токен бота не найден. Убедитесь, что BOT_TOKEN установлен в .env")
if not ADMIN_CHAT_IDS_STR:
    raise ValueError("ID чатов администраторов не найдены. Убедитесь, что ADMIN_CHAT_IDS установлен в .env")

try:
    ADMIN_CHAT_IDS = [int(id_str.strip()) for id_str in ADMIN_CHAT_IDS_STR.split(',')]
except ValueError:
    raise ValueError("Некорректный формат ADMIN_CHAT_IDS. Ожидается строка с ID, разделенными запятыми (например, '12345,67890').")


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- Определение состояний для FSM ---
class PostCreation(StatesGroup):
    waiting_for_waterbody_selection = State() # 1. Ожидание выбора водоема
    waiting_for_fish_name = State()           # 2. Ожидание названия рыбы
    waiting_for_coordinates = State()         # 3. Ожидание координат
    waiting_for_tackle_choice = State()       # 4. Выбор снасти
    waiting_for_clip = State()                # 5a. Ввод клипсы (только если нужно)
    waiting_for_depth = State()               # 5b. Ввод глубины (только если нужно)
    waiting_for_comment_choice = State()      # 6. Выбор: добавить комментарий или пропустить
    waiting_for_comment = State()             # 6a. Ввод комментария
    waiting_for_game_nickname = State()       # 7. Ожидание игрового ника
    waiting_for_temperature = State()         # 8. Ожидание температуры (условное для оз.Медное)
    waiting_for_photos = State()              # 9. Ожидание фотографий
    confirm_post = State()                    # 10. Подтверждение поста

# --- Вспомогательные данные для водоемов ---
WATERBODY_MAPPING = {
    "оз.Комариное": "комариное",
    "оз.Лосиное": "лосиное",
    "р.Вьюнок": "вьюнок",
    "оз.Старый Острог": "старый_острог",
    "р.Белая": "белая",
    "оз.Куори": "куори",
    "оз.Медвежье": "медвежье",
    "р.Волхов": "волхов",
    "р.Северный Донец": "северный_донец",
    "р.Сура": "сура",
    "Ладожское оз.": "ладожское",
    "оз.Янтарное": "янтарное",
    "Ладожский архипелаг": "ладожский_архипелаг",
    "р.Ахтуба": "ахтуба",
    "оз.Медное": "медное",
    "р.Нижняя Тунгуска": "нижняя_тунгуска",
    "р.Яма": "яма",
    "Норвежское море": "норвежское_море"
}

# --- Вспомогательные функции для клавиатур ---
def get_waterbody_keyboard():
    """Возвращает клавиатуру с 18 водоемами, разбитыми по 2 кнопки в ряд."""
    buttons = []
    waterbodies = list(WATERBODY_MAPPING.keys())
    for i in range(0, len(waterbodies), 2):
        row = [types.KeyboardButton(text=waterbodies[i])]
        if i + 1 < len(waterbodies):
            row.append(types.KeyboardButton(text=waterbodies[i+1]))
        buttons.append(row)
    return types.ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_tackle_keyboard():
    """Возвращает клавиатуру для выбора снасти."""
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Мах"), types.KeyboardButton(text="Спиннинг"), types.KeyboardButton(text="Донка")],
            [types.KeyboardButton(text="Матч"), types.KeyboardButton(text="Морская ловля")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_clip_skip_keyboard():
    """Возвращает клавиатуру для ввода клипсы скнопкой 'Пропустить'."""
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Пропустить клипсу")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_comment_choice_keyboard():
    """Возвращает клавиатуру для выбора 'Добавить комментарий' или 'Пропустить'."""
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Добавить комментарий")],
            [types.KeyboardButton(text="Пропустить комментарий")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_photo_keyboard(has_photos: bool):
    """Возвращает клавиатуру для выбора фото."""
    buttons = []
    if has_photos:
        buttons.append([types.KeyboardButton(text="Готово")])
    buttons.append([types.KeyboardButton(text="Пропустить фото")])

    return types.ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        one_time_keyboard=True
    )

# --- Обработчики команд и сообщений ---

@dp.message(CommandStart())
async def command_start_handler(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Привет! Я бот для записи ваших уловов.\n\n"
        "<b>1. Выберите водоем, где ловили:</b>",
        reply_markup=get_waterbody_keyboard()
    )
    await state.set_state(PostCreation.waiting_for_waterbody_selection)

@dp.message(Command("cancel"))
@dp.message(F.text.lower() == "отмена")
async def cmd_cancel(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Вы не в процессе создания поста.")
        return

    logging.info("Отмена состояния %s", current_state)
    await state.clear()
    await message.answer("Создание поста отменено. Вы можете начать заново с /start.",
                         reply_markup=types.ReplyKeyboardRemove())

@dp.message(PostCreation.waiting_for_waterbody_selection, F.text)
async def process_waterbody_selection(message: types.Message, state: FSMContext) -> None:
    selected_waterbody = message.text

    if selected_waterbody not in WATERBODY_MAPPING:
        await message.answer("Пожалуйста, выберите водоем из предложенных кнопок.")
        return

    waterbody_base_name = WATERBODY_MAPPING[selected_waterbody]
    waterbody_hashtag = f"#{waterbody_base_name}@rr4world"
    await state.update_data(waterbody_name=selected_waterbody, waterbody_hashtag=waterbody_hashtag)

    await message.answer("<b>2. Какую рыбу ловили?</b>",
                         reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(PostCreation.waiting_for_fish_name)

@dp.message(PostCreation.waiting_for_waterbody_selection)
async def process_waterbody_invalid(message: types.Message):
    await message.answer("Пожалуйста, выберите водоем, нажав на кнопку.")


@dp.message(PostCreation.waiting_for_fish_name, F.text)
async def process_fish_name(message: types.Message, state: FSMContext) -> None:
    await state.update_data(fish_name=message.text)
    await message.answer("<b>3. Введите координаты:</b>",
                         reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(PostCreation.waiting_for_coordinates)

@dp.message(PostCreation.waiting_for_fish_name)
async def process_fish_name_invalid(message: types.Message):
    await message.answer("Пожалуйста, введите название рыбы в виде текста.")

@dp.message(PostCreation.waiting_for_coordinates, F.text)
async def process_coordinates(message: types.Message, state: FSMContext) -> None:
    await state.update_data(coordinates=message.text)
    await message.answer("<b>4. На что ловили (выберите снасть):</b>",
                         reply_markup=get_tackle_keyboard())
    await state.set_state(PostCreation.waiting_for_tackle_choice)

@dp.message(PostCreation.waiting_for_coordinates)
async def process_coordinates_invalid(message: types.Message):
    await message.answer("Пожалуйста, введите координаты в виде текста.")


@dp.message(PostCreation.waiting_for_tackle_choice, F.text.in_({"Мах", "Спиннинг", "Донка", "Матч", "Морская ловля"}))
async def process_tackle_choice(message: types.Message, state: FSMContext) -> None:
    selected_tackle = message.text
    await state.update_data(tackle=selected_tackle)

    if selected_tackle == "Мах":
        await state.update_data(clip=None)
        await message.answer("<b>5. Укажите глубину:</b>", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(PostCreation.waiting_for_depth)
    elif selected_tackle in ["Донка", "Спиннинг", "Mорская ловля"]:
        await state.update_data(depth=None)
        await message.answer("<b>5. Укажите значение клипсы</b> (например, 20м). "
                             "Если клипсы нет, нажмите 'Пропустить клипсу'.",
                             reply_markup=get_clip_skip_keyboard())

        await state.set_state(PostCreation.waiting_for_clip)
    elif selected_tackle == "Матч":
        await state.update_data(depth=None) # Для Матча тоже нужно сбросить глубину, если она есть
        await message.answer("<b>5. Укажите значение клипсы</b> (например, 20м). "
                             "Если клипсы нет, нажмите 'Пропустить клипсу'.",
                             reply_markup=get_clip_skip_keyboard())
        await state.set_state(PostCreation.waiting_for_clip)
    else:
        await message.answer("Пожалуйста, выберите снасть из предложенных кнопок.")


@dp.message(PostCreation.waiting_for_tackle_choice)
async def process_tackle_choice_invalid(message: types.Message):
    await message.answer("Пожалуйста, выберите снасть, нажав на кнопку.")


@dp.message(PostCreation.waiting_for_clip, F.text)
async def process_clip(message: types.Message, state: FSMContext) -> None:
    if message.text == "Пропустить клипсу":
        await state.update_data(clip="Нет клипсы")
    else:
        await state.update_data(clip=message.text)

    user_data = await state.get_data()
    selected_tackle = user_data.get('tackle')

    if selected_tackle == "Матч":
        await message.answer("<b>Теперь укажите глубину:</b>", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(PostCreation.waiting_for_depth)
    else:
        await _check_waterbody_for_temperature_or_comment_choice(message, state, next_step_number=6)


@dp.message(PostCreation.waiting_for_clip)
async def process_clip_invalid(message: types.Message):
    await message.answer("Пожалуйста, введите значение клипсы или нажмите 'Пропустить клипсу'.")


@dp.message(PostCreation.waiting_for_depth, F.text)
async def process_depth(message: types.Message, state: FSMContext) -> None:
    await state.update_data(depth=message.text)
    await _check_waterbody_for_temperature_or_comment_choice(message, state, next_step_number=6)


@dp.message(PostCreation.waiting_for_depth)
async def process_depth_invalid(message: types.Message):
    await message.answer("Пожалуйста, введите глубину в виде текста.")


async def _check_waterbody_for_temperature_or_comment_choice(message: types.Message, state: FSMContext, next_step_number: int):
    """Вспомогательная функция для определения следующего шага после клипсы/глубины."""
    user_data = await state.get_data()
    selected_waterbody= user_data.get('waterbody_name')

    if selected_waterbody == "оз.Медное":
        await message.answer(f"<b>{next_step_number}. Укажите температуру воды:</b>",
                             reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(PostCreation.waiting_for_temperature)
    else:
        await message.answer(f"<b>{next_step_number}. Хотите добавить комментарий к улову?</b>",
                             reply_markup=get_comment_choice_keyboard())
        await state.set_state(PostCreation.waiting_for_comment_choice)


@dp.message(PostCreation.waiting_for_temperature, F.text)
async def process_temperature(message: types.Message, state: FSMContext) -> None:
    await state.update_data(temperature=message.text)
    await message.answer("<b>7. Хотите добавить комментарий к улову?</b>",
                         reply_markup=get_comment_choice_keyboard())
    await state.set_state(PostCreation.waiting_for_comment_choice)

@dp.message(PostCreation.waiting_for_temperature)
async def process_temperature_invalid(message: types.Message):
    await message.answer("Пожалуйста, введите температуру воды в виде текста.")


@dp.message(PostCreation.waiting_for_comment_choice, F.text == "Добавить комментарий")
async def process_add_comment(message: types.Message, state: FSMContext) -> None:
    await message.answer("<b>Введите ваш комментарий:</b>",
                         reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(PostCreation.waiting_for_comment)

@dp.message(PostCreation.waiting_for_comment_choice, F.text == "Пропустить комментарий")
async def process_skip_comment(message: types.Message, state: FSMContext) -> None:
    await state.update_data(comment=None)
    await message.answer("<b>7. Укажите свой игровой ник:</b>",
                         reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(PostCreation.waiting_for_game_nickname)

@dp.message(PostCreation.waiting_for_comment_choice)
async def process_comment_choice_invalid(message: types.Message):
    await message.answer("Пожалуйста, выберите 'Добавить комментарий' или 'Пропустить комментарий'.")


@dp.message(PostCreation.waiting_for_comment, F.text)
async def process_comment(message: types.Message, state: FSMContext) -> None:
    await state.update_data(comment=message.text)
    await message.answer("<b>7. Укажите свой игровой ник:</b>",
                         reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(PostCreation.waiting_for_game_nickname)

@dp.message(PostCreation.waiting_for_comment)
async def process_comment_invalid(message: types.Message):
    await message.answer("Пожалуйста, введите ваш комментарий в виде текста.")


@dp.message(PostCreation.waiting_for_game_nickname, F.text)
async def process_game_nickname(message: types.Message, state: FSMContext) -> None:
    await state.update_data(game_nickname=message.text)
    await message.answer(
        "<b>8. Прикрепите фото вашего улова</b> (до 10 штук). "
        "Когда закончите или если фото не нужны, нажмите 'Пропустить фото'.",
        reply_markup=get_photo_keyboard(has_photos=False)
    )
    await state.set_state(PostCreation.waiting_for_photos)

@dp.message(PostCreation.waiting_for_game_nickname)
async def process_game_nickname_invalid(message: types.Message):
    await message.answer("Пожалуйста, введите свой игровой ник в виде текста.")


@dp.message(PostCreation.waiting_for_photos, F.photo)
async def process_photos(message: types.Message, state: FSMContext) -> None:
    data = await state.get_data()
    photos = data.get('photos', [])

    if len(photos) >= 10:
        await message.answer("Вы уже прикрепили максимальное количество фотографий (10). "
                             "Нажмите 'Готово', чтобы завершить.")
        return

    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)

    keyboard = get_photo_keyboard(has_photos=True)
    await message.answer(f"Фотография добавлена. Всего {len(photos)} фото.", reply_markup=keyboard)


@dp.message(PostCreation.waiting_for_photos, F.text.in_({"Пропустить фото", "Готово"}))
@dp.message(PostCreation.waiting_for_photos, F.text == "Продолжить")
async def process_skip_photos(message: types.Message, state: FSMContext) -> None:
    await _send_review_post(message, state)


@dp.message(PostCreation.waiting_for_photos)
async def process_photos_invalid(message: types.Message):
    await message.answer("Пожалуйста, присылайте фотографии или используйте кнопки 'Готово' / 'Пропустить фото'.")


async def _send_review_post(message: types.Message, state: FSMContext) -> None:
    user_data = await state.get_data()
    waterbody_name = user_data.get('waterbody_name') # Все еще извлекаем название водоема
    waterbody_hashtag = user_data.get('waterbody_hashtag')
    fish_name = user_data.get('fish_name')
    coordinates = user_data.get('coordinates')
    tackle = user_data.get('tackle')
    clip = user_data.get('clip')
    depth = user_data.get('depth')
    temperature = user_data.get('temperature')
    comment = user_data.get('comment')
    game_nickname = user_data.get('game_nickname')
    photos = user_data.get('photos', [])

    review_text_parts = [
        f"<b>Предварительный просмотр вашего улова:</b>\n",
        f"<b>Локация:</b> {waterbody_hashtag}", # ИЗМЕНЕНИЕ 1: Только хештег с префиксом "<b>Локация:</b>"
        # f"<b>Водоем:</b> {waterbody_name}", # Убрано отображение названия водоема
        f"<b>Рыба:</b> {fish_name}",
    ]
    if coordinates:
        review_text_parts.append(f"<b>Координаты:</b> {coordinates}")

    # Снасть уже убрана из превью
    # review_text_parts.append(f"<b>Снасть:</b> {tackle}")

    if clip and clip != "Нет клипсы":
        review_text_parts.append(f"<b>Клипса:</b> {clip}")
    if depth:
        review_text_parts.append(f"<b>Глубина:</b> {depth}")
    if temperature:
        review_text_parts.append(f"<b>Температура воды:</b> {temperature}")

    if comment:
        review_text_parts.append(f"<b>Комментарий:</b>\n<blockquote>{comment}</blockquote>")

    review_text_parts.append(f"<b>Игровой ник:</b> {game_nickname}")

    review_text = "\n".join(review_text_parts)

    if photos:
        review_text += f"\nПрикреплено <b>{len(photos)}</b> фото.\n\n"
    else:
        review_text += "\nФотографий нет.\n\n"

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
    waterbody_name = user_data.get('waterbody_name') # Все еще извлекаем название водоема
    waterbody_hashtag = user_data.get('waterbody_hashtag')
    # fish_name = user_data.get('fish_name') # Рыба уже не отображается, но пока сохраняется в FSM
    coordinates = user_data.get('coordinates')
    tackle = user_data.get('tackle')
    clip = user_data.get('clip')
    depth = user_data.get('depth')
    temperature = user_data.get('temperature')
    comment = user_data.get('comment')
    game_nickname = user_data.get('game_nickname')
    photos = user_data.get('photos', [])

    # Формируем текст для админа (для пересылки в канал)
    admin_post_text_parts = [
        f"<b>Локация:</b> {waterbody_hashtag}", # ИЗМЕНЕНИЕ 3:Только хештег с префиксом "<b>Локация:</b>"
        # f"<b>Водоем:</b> {waterbody_name}", # Убрано отображение названия водоема
        # Рыба уже убрана
        # f"<b>Рыба:</b> {fish_name}",
    ]
    if coordinates:
        admin_post_text_parts.append(f"<b>Координаты:</b> {coordinates}")

    # Снасть уже убрана
    # admin_post_text_parts.append(f"<b>Снасть:</b> {tackle}")

    if clip and clip != "Нет клипсы":
        admin_post_text_parts.append(f"<b>Клипса:</b> {clip}")
    if depth:
        admin_post_text_parts.append(f"<b>Глубина:</b> {depth}")
    if temperature:
        admin_post_text_parts.append(f"<b>Температура воды:</b> {temperature}")

    if comment:
        admin_post_text_parts.append(f"<b>Комментарий:</b>\n<blockquote>{comment}</blockquote>")

    admin_post_text_parts.append(f"<b>Игровой ник:</b> {game_nickname}")

    admin_post_text = "\n".join(admin_post_text_parts)
    admin_post_text += "\n\n🎁 Автору было отправлено 200 кофе"
    admin_post_text += f"\n\n<a href='{OFFER_POST_CHANNEL_URL}'>ПРЕДЛОЖИТЬ ПОСТ</a>"


    for admin_id in ADMIN_CHAT_IDS:
        try:
            if photos:
                media_group = []
                media_group.append(types.InputMediaPhoto(media=photos[0], caption=admin_post_text))
                for photo_file_id in photos[1:]:
                    media_group.append(types.InputMediaPhoto(media=photo_file_id))
                await bot.send_media_group(chat_id=admin_id, media=media_group)
            else:
                await bot.send_message(chat_id=admin_id, text=admin_post_text)

            logging.info(f"Улов от пользователя {message.from_user.id} успешно отправлен администратору {admin_id}.")

        except Exception as e:
            logging.error(f"Ошибка при отправке улова администратору {admin_id} от пользователя {message.from_user.id}: {e}")

    await message.answer("Ваш улов успешно отправлен на модерацию! Спасибо!",
                         reply_markup=types.ReplyKeyboardRemove())
    await state.clear()

@dp.message(PostCreation.confirm_post, F.text == "Редактировать")
async def process_edit_post(message: types.Message, state: FSMContext) -> None:
    await message.answer("Хорошо, давайте начнем редактирование. \n\n<b>1. Выберите водоем, где ловили:</b>",
                         reply_markup=get_waterbody_keyboard())
    await state.set_state(PostCreation.waiting_for_waterbody_selection)

@dp.message(PostCreation.confirm_post)
async def process_confirm_invalid(message: types.Message):
    await message.answer("Пожалуйста, выберите действие на клавиатуре: 'Отправить пост', 'Редактировать' или 'Отмена'.")


async def main() -> None:
    logging.info("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())