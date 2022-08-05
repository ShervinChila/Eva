from pyrogram import filters, Client
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from database.connections_mdb import add_connection, all_connections, if_active, delete_connection
from info import ADMINS
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)


@Client.on_message((filters.private | filters.group) & filters.command('connect'))
async def addconnection(client, message):
    userid = message.from_user.id if message.from_user else None
    if not userid:
        return await message.reply(f"شما ادمین نیستی،دستور /connect {message.chat.id} رو بفرست تو پی وی")
    chat_type = message.chat.type

    if chat_type == "private":
        try:
            cmd, group_id = message.text.split(" ", 1)
        except:
            await message.reply_text(
                "<b>بافرمت صحیح وارد کنید</b>\n\n"
                "<code>/connect آیدی گپ</code>\n\n"
                "<i>ربات رو به گروه خودت ادد کن و آیدی رو با این دستور دریافت کن  <code>/id</code></i>",
                quote=True
            )
            return

    elif chat_type in ["group", "supergroup"]:
        group_id = message.chat.id

    try:
        st = await client.get_chat_member(group_id, userid)
        if (
                st.status != "administrator"
                and st.status != "creator"
                and userid not in ADMINS
        ):
            await message.reply_text("باید در گروه ادمین باشی", quote=True)
            return
    except Exception as e:
        logger.exception(e)
        await message.reply_text(
            "آیدی گروه اشتباهه\n\nیا اگر درسته،چک کن ببین من تو گروه هستم یا نه",
            quote=True,
        )

        return
    try:
        st = await client.get_chat_member(group_id, "me")
        if st.status == "administrator":
            ttl = await client.get_chat(group_id)
            title = ttl.title

            addcon = await add_connection(str(group_id), str(userid))
            if addcon:
                await message.reply_text(
                    f"با موفقیت متصل شد **{title}**\nحالا میتونی گروه خودت رو از پیوی من مدیریت کنی",
                    quote=True,
                    parse_mode="md"
                )
                if chat_type in ["group", "supergroup"]:
                    await client.send_message(
                        userid,
                        f"متصل شد به **{title}** !",
                        parse_mode="md"
                    )
            else:
                await message.reply_text(
                    "من قبلا به این گپ متصل شدم",
                    quote=True
                )
        else:
            await message.reply_text("من رو ادمین کن", quote=True)
    except Exception as e:
        logger.exception(e)
        await message.reply_text('انگار قیمه ها ریخته شدن تو ماستا🤔دوباره امتحان کن', quote=True)
        return


@Client.on_message((filters.private | filters.group) & filters.command('disconnect'))
async def deleteconnection(client, message):
    userid = message.from_user.id if message.from_user else None
    if not userid:
        return await message.reply(f"شما ادمین نیستی،دستور /connect {message.chat.id} رو بفرست تو پی وی")
    chat_type = message.chat.type

    if chat_type == "private":
        await message.reply_text("دستور /connections رو برای دیدن یا قطع ارتباط گروه ها اجرا کن", quote=True)

    elif chat_type in ["group", "supergroup"]:
        group_id = message.chat.id

        st = await client.get_chat_member(group_id, userid)
        if (
                st.status != "administrator"
                and st.status != "creator"
                and str(userid) not in ADMINS
        ):
            return

        delcon = await delete_connection(str(userid), str(group_id))
        if delcon:
            await message.reply_text("ارتباط با این گپ با موفقیت قطع شد", quote=True)
        else:
            await message.reply_text("این گپ به من متصل نیست\nدستور /connect رو برای اتصال وارد کن", quote=True)


@Client.on_message(filters.private & filters.command(["connections"]))
async def connections(client, message):
    userid = message.from_user.id

    groupids = await all_connections(str(userid))
    if groupids is None:
        await message.reply_text(
            "من به هیچ جا وصل نیستم،اول به ی گپی وصللم کن باو😕",
            quote=True
        )
        return
    buttons = []
    for groupid in groupids:
        try:
            ttl = await client.get_chat(int(groupid))
            title = ttl.title
            active = await if_active(str(userid), str(groupid))
            act = " - ACTIVE" if active else ""
            buttons.append(
                [
                    InlineKeyboardButton(
                        text=f"{title}{act}", callback_data=f"groupcb:{groupid}:{act}"
                    )
                ]
            )
        except:
            pass
    if buttons:
        await message.reply_text(
            "جزئیات گروه متصل\n\n",
            reply_markup=InlineKeyboardMarkup(buttons),
            quote=True
        )
    else:
        await message.reply_text(
            "من به هیچ جا وصل نیستم،اول به ی گپی وصللم کن باو😕",
            quote=True
        )
