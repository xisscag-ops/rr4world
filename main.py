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
OFFER_POST_CHANNEL_URL = os.getenv("OFFER_POST_CHANNEL_URL", "https://t.me/your_channel_link")

if not BOT_TOKEN:
    raise ValueError("Токен бота не найден.")
if not ADMIN_CHAT_IDS_STR:
    raise ValueError("ID чатов администраторов не найдены.")

try:
    ADMIN_CHAT_IDS = [int(id_str.strip()) for id_str in ADMIN_CHAT_IDS_STR.split(',')]
except ValueError:
    raise ValueError("Некорректный формат ADMIN_CHAT_IDS.")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- Определение состояний для FSM ---
class PostCreation(StatesGroup):
    waiting_for_waterbody_selection = State() # 1. Выбор водоема
    # Шаг с рыбой удален
    waiting_for_coordinates = State()         # 2. Координаты
    waiting_for_tackle_choice = State()       # 3. Выбор снасти
    waiting_for_clip = State()                # 4a. Клипса
    waiting_for_depth = State()               # 4b. Глубина
    waiting_for_comment_choice = State()      # 5. Выбор комментария
    waiting_for_comment = State()             # 5a. Ввод комментария
    waiting_for_game_nickname = State()       # 6. Игровой ник
    waiting_for_temperature = State()         # 7. Температура (для Медного)
    waiting_for_photos = State()              # 8. Фото (ОБЯЗАТЕЛЬНО)
    confirm_post = State()                    # 9. Подтверждение

# --- Вспомогательные данные ---
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

# --- Клавиатуры ---
def get_waterbody_keyboard():
    buttons = []
    waterbodies = list(WATERBODY_MAPPING.keys())
    for i in range(0, len(waterbodies), 2):
        row = [types.KeyboardButton(text=waterbodies[i])]
        if i + 1 < len(waterbodies):
            row.append(types.KeyboardButton(text=waterbodies[i+1]))
        buttons.append(row)
    return types.ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_tackle_keyboard():
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Мах"), types.KeyboardButton(text="Спиннинг"), types.KeyboardButton(text="Донка")],
            [types.KeyboardButton(text="Матч"), types.KeyboardButton(text="Морская ловля")]
        ], resize_keyboard=True
    )

def get_clip_skip_keyboard():
    return types.ReplyKeyboardMarkup(keyboard=[[types.KeyboardButton(text="Пропустить клипсу")]], resize_keyboard=True)

def get_comment_choice_keyboard():
    return types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="Добавить комментарий")], [types.KeyboardButton(text="Пропустить комментарий")]],
        resize_keyboard=True
    )

def get_photo_keyboard(has_photos: bool):buttons = []
    if has_photos:
        buttons.append([types.KeyboardButton(text="Готово")])
    return types.ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# --- Обработчики ---

@dp.message(CommandStart())
async def command_start_handler(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Привет! <b>1. Выберите водоем:</b>", reply_markup=get_waterbody_keyboard())
    await state.set_state(PostCreation.waiting_for_waterbody_selection)

@dp.message(Command("cancel"))
@dp.message(F.text.lower() == "отмена")
async def cmd_cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Отменено. Начните заново с /start.", reply_markup=types.ReplyKeyboardRemove())

@dp.message(PostCreation.waiting_for_waterbody_selection, F.text)
async def process_waterbody_selection(message: types.Message, state: FSMContext):
    if message.text not in WATERBODY_MAPPING:
        await message.answer("Выберите водоем кнопкой.")
        return
    
    hashtag = f"#{WATERBODY_MAPPING[message.text]}@rr4world"
    await state.update_data(waterbody_name=message.text, waterbody_hashtag=hashtag)
    
    await message.answer("<b>2. Введите координаты:</b>", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(PostCreation.waiting_for_coordinates)

@dp.message(PostCreation.waiting_for_coordinates, F.text)
async def process_coordinates(message: types.Message, state: FSMContext):
    await state.update_data(coordinates=message.text)
    await message.answer("<b>3. Выберите снасть:</b>", reply_markup=get_tackle_keyboard())
    await state.set_state(PostCreation.waiting_for_tackle_choice)

@dp.message(PostCreation.waiting_for_tackle_choice, F.text.in_({"Мах", "Спиннинг", "Донка", "Матч", "Морская ловля"}))
async def process_tackle_choice(message: types.Message, state: FSMContext):
    tackle = message.text
    await state.update_data(tackle=tackle)
    if tackle == "Мах":
        await message.answer("<b>4. Укажите глубину:</b>", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(PostCreation.waiting_for_depth)
    else:
        await message.answer("<b>4. Укажите клипсу:</b>", reply_markup=get_clip_skip_keyboard())
        await state.set_state(PostCreation.waiting_for_clip)

@dp.message(PostCreation.waiting_for_clip, F.text)
async def process_clip(message: types.Message, state: FSMContext):
    clip = "Нет клипсы" if message.text == "Пропустить клипсу" else message.text
    await state.update_data(clip=clip)
    data = await state.get_data()
    if data.get('tackle') == "Матч":
        await message.answer("<b>Теперь укажите глубину:</b>", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(PostCreation.waiting_for_depth)
    else:
        await _check_temp_or_comment(message, state)

@dp.message(PostCreation.waiting_for_depth, F.text)
async def process_depth(message: types.Message, state: FSMContext):
    await state.update_data(depth=message.text)
    await _check_temp_or_comment(message, state)

async def _check_temp_or_comment(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if data.get('waterbody_name') == "оз.Медное":
        await message.answer("<b>5. Укажите температуру воды:</b>", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(PostCreation.waiting_for_temperature)
    else:
        await message.answer("<b>5. Добавить комментарий?</b>", reply_markup=get_comment_choice_keyboard())
        await state.set_state(PostCreation.waiting_for_comment_choice)

@dp.message(PostCreation.waiting_for_temperature, F.text)
async def process_temperature(message: types.Message, state: FSMContext):
    await state.update_data(temperature=message.text)
    await message.answer("<b>6. Добавить комментарий?</b>", reply_markup=get_comment_choice_keyboard())
    await state.set_state(PostCreation.waiting_for_comment_choice)

@dp.message(PostCreation.waiting_for_comment_choice, F.text == "Добавить комментарий")
async def add_com(message: types.Message,state: FSMContext):
    await message.answer("Введите комментарий:", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(PostCreation.waiting_for_comment)

@dp.message(PostCreation.waiting_for_comment_choice, F.text == "Пропустить комментарий")
@dp.message(PostCreation.waiting_for_comment, F.text)
async def skip_or_fill_com(message: types.Message, state: FSMContext):
    if message.text != "Пропустить комментарий":
        await state.update_data(comment=message.text)
    await message.answer("<b>7. Ваш игровой ник:</b>", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(PostCreation.waiting_for_game_nickname)

@dp.message(PostCreation.waiting_for_game_nickname, F.text)
async def process_nick(message: types.Message, state: FSMContext):
    await state.update_data(game_nickname=message.text)
    await message.answer("<b>8. Прикрепите фото улова</b> (Обязательно):\nЗагрузите фото и нажмите 'Готово'.", reply_markup=get_photo_keyboard(False))
    await state.set_state(PostCreation.waiting_for_photos)

@dp.message(PostCreation.waiting_for_photos, F.photo)
async def process_photos(message: types.Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get('photos', [])
    if len(photos) < 10:
        photos.append(message.photo[-1].file_id)
        await state.update_data(photos=photos)
    await message.answer(f"Фото добавлено ({len(photos)}/10).", reply_markup=get_photo_keyboard(True))

@dp.message(PostCreation.waiting_for_photos, F.text == "Готово")
async def photo_done(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if not data.get('photos'):
        await message.answer("Нужно хотя бы одно фото!")
        return
    await _send_review(message, state)

async def _send_review(message: types.Message, state: FSMContext):
    d = await state.get_data()
    text = f"<b>Предпросмотр:</b>\n\n<b>Локация:</b> {d['waterbody_hashtag']}\n<b>Координаты:</b> {d['coordinates']}\n"
    if d.get('clip') and d['clip'] != "Нет клипсы": text += f"<b>Клипса:</b> {d['clip']}\n"
    if d.get('depth'): text += f"<b>Глубина:</b> {d['depth']}\n"
    if d.get('temperature'): text += f"<b>Температура:</b> {d['temperature']}\n"
    if d.get('comment'): text += f"<b>Комментарий:</b>\n<blockquote>{d['comment']}</blockquote>\n"
    text += f"<b>Ник:</b> {d['game_nickname']}"

    kb = types.ReplyKeyboardMarkup(keyboard=[[types.KeyboardButton(text="Отправить пост")], [types.KeyboardButton(text="Редактировать")], [types.KeyboardButton(text="Отмена")]], resize_keyboard=True)
    
    media = [types.InputMediaPhoto(media=d['photos'][0], caption=text)]
    for p in d['photos'][1:]: media.append(types.InputMediaPhoto(media=p))
    await message.answer_media_group(media=media)
    await message.answer("Все верно?", reply_markup=kb)
    await state.set_state(PostCreation.confirm_post)

@dp.message(PostCreation.confirm_post, F.text == "Отправить пост")
async def final_send(message: types.Message, state: FSMContext):
    d = await state.get_data()
    post_text = f"<b>Локация:</b> {d['waterbody_hashtag']}\n<b>Координаты:</b> {d['coordinates']}\n"
    if d.get('clip') and d['clip'] != "Нет клипсы": post_text += f"<b>Клипса:</b> {d['clip']}\n"
    if d.get('depth'): post_text += f"<b>Глубина:</b> {d['depth']}\n"
    if d.get('temperature'): post_text += f"<b>Температура:</b> {d['temperature']}\n"
    if d.get('comment'): post_text += f"<b>Комментарий:</b>\n<blockquote>{d['comment']}</blockquote>\n"
    post_text += f"<b>Игровой ник:</b> {d['game_nickname']}\n\n🎁 Автору отправлено 200 кофе\n<a href='{OFFER_POST_CHANNEL_URL}'>ПРЕДЛОЖИТЬ ПОСТ</a>"

    user_link = f"<a href='tg://user?id={message.from_user.id}'>{message.from_user.full_name}</a>"
    username = f"@{message.from_user.username}" if message.from_user.username else f"ID: {message.from_user.id}"
    service_info = f"<b>👤 Отправитель:</b> {user_link} ({username})"

    for admin_id in ADMIN_CHAT_IDS:
        try:
            media = [types.InputMediaPhoto(media=d['photos'][0], caption=post_text)]
            for p in d['photos'][1:]: media.append(types.InputMediaPhoto(media=p))
            await bot.send_media_group(chat_id=admin_id, media=media)
            await bot.send_message(chat_id=admin_id, text=service_info)
        except Exception as e: logging.error(f"Error sending to admin {admin_id}: {e}")

    await message.answer("Отправлено на модерацию!", reply_markup=types.ReplyKeyboardRemove())
    await state.clear()

@dp.message(PostCreation.confirm_post, F.text == "Редактировать")
async def edit_back(message: types.Message, state: FSMContext):
    await command_start_handler(message, state)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())