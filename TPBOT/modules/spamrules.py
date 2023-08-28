from TPBOT.modules.log_channel import loggable,send_log
import html
from telegram.ext import CommandHandler
from telegram import Message, Chat, Update, Bot, User, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode, ChatPermissions
from telegram.error import BadRequest
from telegram.ext import Filters, MessageHandler, CommandHandler, run_async, CallbackQueryHandler
from telegram.utils.helpers import mention_html, escape_markdown

from TPBOT import dispatcher, spamcheck, LOGGER, BAN_STICKER, SUDO_USERS, WHITELIST_USERS, SUPPORT_USERS, OWNER_ID, DUMP_CHAT
from TPBOT.modules.helper_funcs.chat_status import is_user_admin, user_admin, can_restrict
from TPBOT.modules.helper_funcs.alternate import send_message

SPAMRULES_HANDLER_GROUP = 12

__mod_name__ = "Spam Rules"

__help__ = ""  # No help info for this (yet)

def bad_charset(msgtxt):
    # msgtxt = f"{message}"
    if msgtxt is None or msgtxt == "":
        return False
    if max(msgtxt) <= u'\u036F':
        return False
    for ch in msgtxt:
        num = ord(ch)
        # (880 to 8191) Western non-English languages (can contain Latin-like characters)
        # (8304 to 8351) Superscripts and subscripts (contain entire Latin alphabet)
        # (11360 to 11519) Western non-English languages
        # (42192 to 42239) Lisu - (Latin-like characters)
        # (65280 to 65519) Halfwidth and Fullwidth forms (Latin but in fixed-width)
        # (66304 - 66382) Old Italic and other Latin-like sets
        # (119808 - 120831) Mathematical Alphanumeric Symbols (most used by spammers; contains entire Latin in different styles)
        if (880 <= num <= 8191) or (8304 <= num <= 8351) or (9312 <= num <= 9471) or (11360 <= num <= 11519) or (42192 <= num <= 42239) \
                or (65280 <= num <= 65519) or (66304 <= num <= 66382) or (119808 <= num <= 120831):
            return True

    return False

# @loggable
def check_rules(update, context):
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message
    log_reason = ''

    if (not user) or (chat.type == chat.PRIVATE):
        return ""
    if is_user_admin(chat, user.id) or user.id == OWNER_ID:
        return ""
    if user and (user.id in SUDO_USERS or user.id in WHITELIST_USERS or user.id in SUPPORT_USERS):
        return ""
    if bad_charset(message.text):
        log_reason = 'Forbidden character set used in message'

    if not (log_reason == ''):
        log_reason = f"<b>{chat.title}:</b>\n" \
                "#SPAM_RULE_TRIGGERED\n" \
                f"<b>Reason:</b> {log_reason}\n" \
                f"<b>Action Taken:</b> Automatically Banned\n" \
                f"<b>From:</b> {user.full_name} @{user.username}  <b>ID:</b>  <code>{user.id}</code>\n\n" \
                f"{message.text}\n"
        message.delete()
        context.bot.ban_chat_member(chat.id, user.id)
    return log_reason

dispatcher.add_handler(MessageHandler(Filters.all & ~Filters.status_update & ~Filters.command & Filters.chat_type.groups, check_rules), SPAMRULES_HANDLER_GROUP)

