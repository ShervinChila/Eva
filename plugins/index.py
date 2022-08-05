import logging
import asyncio
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.errors.exceptions.bad_request_400 import ChannelInvalid, ChatAdminRequired, UsernameInvalid, UsernameNotModified
from info import ADMINS
from info import INDEX_REQ_CHANNEL as LOG_CHANNEL
from database.ia_filterdb import save_file
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils import temp
import re
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
lock = asyncio.Lock()


@Client.on_callback_query(filters.regex(r'^index'))
async def index_files(bot, query):
    if query.data.startswith('index_cancel'):
        temp.CANCEL = True
        return await query.answer("Cancelling Indexing")
    _, raju, chat, lst_msg_id, from_user = query.data.split("#")
    if raju == 'reject':
        await query.message.delete()
        await bot.send_message(int(from_user),
                               f'درخواست شما برای ایندکس {chat} توسط مدیرها رد شد',
                               reply_to_message_id=int(lst_msg_id))
        return

    if lock.locked():
        return await query.answer('صبر کن تا فرایند قبلی تکمیل شه', show_alert=True)
    msg = query.message

    await query.answer('بصبر...⏳', show_alert=True)
    if int(from_user) not in ADMINS:
        await bot.send_message(int(from_user),
                               f'درخواست شما برای ایندکس {chat} توسط مدیرها پذیرفته شد و به زودی ادد میشه',
                               reply_to_message_id=int(lst_msg_id))
    await msg.edit(
        "Starting Indexing",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton('لغو', callback_data='index_cancel')]]
        )
    )
    try:
        chat = int(chat)
    except:
        chat = chat
    await index_files_to_db(int(lst_msg_id), chat, msg, bot)


@Client.on_message((filters.forwarded | (filters.regex("(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")) & filters.text ) & filters.private & filters.incoming)
async def send_for_index(bot, message):
    if message.text:
        regex = re.compile("(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")
        match = regex.match(message.text)
        if not match:
            return await message.reply('لینک نامعتبر')
        chat_id = match.group(4)
        last_msg_id = int(match.group(5))
        if chat_id.isnumeric():
            chat_id  = int(("-100" + chat_id))
    elif message.forward_from_chat.type == 'channel':
        last_msg_id = message.forward_from_message_id
        chat_id = message.forward_from_chat.username or message.forward_from_chat.id
    else:
        return
    try:
        await bot.get_chat(chat_id)
    except ChannelInvalid:
        return await message.reply('این ممکنه یک کانال یا گپ خصوصی باشه باید اول من رو اونجا ادمین کنی تا بتونم فایل ها رو ایندکس کنم')
    except (UsernameInvalid, UsernameNotModified):
        return await message.reply('لینک نامعتبر')
    except Exception as e:
        logger.exception(e)
        return await message.reply(f'Errors - {e}')
    try:
        k = await bot.get_messages(chat_id, last_msg_id)
    except:
        return await message.reply('فکر کنم کانال خصوصیه و منم ادمینش نیستم،اول مطمئن شو ادمین باشم')
    if k.empty:
        return await message.reply('ممکنه اینجا گروهی باشه که من ادمینش نیستم')

    if message.from_user.id in ADMINS:
        buttons = [
            [
                InlineKeyboardButton('بله',
                                     callback_data=f'index#accept#{chat_id}#{last_msg_id}#{message.from_user.id}')
            ],
            [
                InlineKeyboardButton('خیر', callback_data='close_data'),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        return await message.reply(
            f' میخوای این کانال یا گروه رو ایندکس کنی؟\n\nChat ID/ Username: <code>{chat_id}</code>\nLast Message ID: <code>{last_msg_id}</code>',
            reply_markup=reply_markup)

    if type(chat_id) is int:
        try:
            link = (await bot.create_chat_invite_link(chat_id)).invite_link
        except ChatAdminRequired:
            return await message.reply('مطمئن شو که در گپ مدیر باشم و اجازه دعوت از کاربران رو داشته باشی')
    else:
        link = f"@{message.forward_from_chat.username}"
    buttons = [
        [
            InlineKeyboardButton('موافقت با ایندکس',
                                 callback_data=f'index#accept#{chat_id}#{last_msg_id}#{message.from_user.id}')
        ],
        [
            InlineKeyboardButton('لغو ایندکس',
                                 callback_data=f'index#reject#{chat_id}#{message.message_id}#{message.from_user.id}'),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    await bot.send_message(LOG_CHANNEL,
                           f'#درخواست فهرست\n\nتوسط : {message.from_user.mention} (<code>{message.from_user.id}</code>)\nChat ID/ Username - <code> {chat_id}</code>\nLast Message ID - <code>{last_msg_id}</code>\nInviteLink - {link}',
                           reply_markup=reply_markup)
    await message.reply('با تشکر از مشارکت شما،منتظر باش تا ادمین های من فایل ها رو تایید کنن')


@Client.on_message(filters.command('setskip') & filters.user(ADMINS))
async def set_skip_number(bot, message):
    if ' ' in message.text:
        _, skip = message.text.split(" ")
        try:
            skip = int(skip)
        except:
            return await message.reply("عدد اسکیپ،باید یک عدد صحیح باشد")
        await message.reply(f"عدد اسکیپ،با موفقیت تنظیم شد {skip}")
        temp.CURRENT = int(skip)
    else:
        await message.reply("یک عدد اسکیپ وارد کن")


async def index_files_to_db(lst_msg_id, chat, msg, bot):
    total_files = 0
    duplicate = 0
    errors = 0
    deleted = 0
    no_media = 0
    unsupported = 0
    async with lock:
        try:
            current = temp.CURRENT
            temp.CANCEL = False
            async for message in bot.iter_messages(chat, lst_msg_id, temp.CURRENT):
                if temp.CANCEL:
                    await msg.edit(f"با موفقیت لغو شد\n\nذخیره شده <code>{total_files}</code> فایل ها به دیتابیس\nفایل های تکراری اسکیپ شده: <code>{duplicate}</code>\nپیامهای تکراری حذف شده رد شده: <code>{deleted}</code>\nپیامهای غیر رسانه های رد شده: <code>{no_media + unsupported}</code>(Unsupported Media - `{unsupported}` )\nقیمه های تو ماست ریخته شده: <code>{errors}</code>")
                    break
                current += 1
                if current % 20 == 0:
                    can = [[InlineKeyboardButton('لغو', callback_data='index_cancel')]]
                    reply = InlineKeyboardMarkup(can)
                    await msg.edit_text(
                        text=f"کل پیامها: <code>{current}</code>\nپیامهای ذخیره شده: <code>{total_files}</code>\nفایل های تکراری اسکیپ شده: <code>{duplicate}</code>\nپیامهای تکراری حذف شده رد شده: <code>{deleted}</code>\nپیامهای غیر رسانه های رد شده: <code>{no_media + unsupported}</code>(Unsupported Media - `{unsupported}` )\nقیمه های تو ماست ریخته شده: <code>{errors}</code>",
                        reply_markup=reply)
                if message.empty:
                    deleted += 1
                    continue
                elif not message.media:
                    no_media += 1
                    continue
                elif message.media not in ['audio', 'video', 'document']:
                    unsupported += 1
                    continue
                media = getattr(message, message.media, None)
                if not media:
                    unsupported += 1
                    continue
                media.file_type = message.media
                media.caption = message.caption
                aynav, vnay = await save_file(media)
                if aynav:
                    total_files += 1
                elif vnay == 0:
                    duplicate += 1
                elif vnay == 2:
                    errors += 1
        except Exception as e:
            logger.exception(e)
            await msg.edit(f'Error: {e}')
        else:
            await msg.edit(f'با موفقیت ذخیره شد <code>{total_files}</code> در دیتابیس\nفایل های تکراری اسکیپ شده: <code>{duplicate}</code>\nپیامهای تکراری حذف شده رد شده: <code>{deleted}</code>\nپیامهای غیر رسانه های رد شده: <code>{no_media + unsupported}</code>(Unsupported Media - `{unsupported}` )\nقیمه های تو ماست ریخته شده: <code>{errors}</code>')
