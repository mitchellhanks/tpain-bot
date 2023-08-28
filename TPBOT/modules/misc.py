import html
from datetime import datetime
from typing import Optional, List

from telegram.error import BadRequest
from telegram import Message, Chat, Update, Bot, MessageEntity, InlineKeyboardMarkup
from telegram import ParseMode
from telegram.ext import CommandHandler, Filters
from telegram.utils.helpers import escape_markdown, mention_html, mention_markdown

from TPBOT import dispatcher, OWNER_ID, SUDO_USERS, SUPPORT_USERS, WHITELIST_USERS, BAN_STICKER, spamcheck
from TPBOT.__main__ import STATS, USER_INFO
from TPBOT.modules.disable import DisableAbleCommandHandler
from TPBOT.modules.helper_funcs.extraction import extract_user
from TPBOT.modules.helper_funcs.msg_types import get_message_type
from TPBOT.modules.helper_funcs.misc import build_keyboard_alternate

import TPBOT.modules.sql.feds_sql as feds_sql
from TPBOT.modules.helper_funcs.alternate import send_message

__mod_name__ = "Misc"

__help__ = """
 - /id: get the current group id. If used by replying to a message, gets that user's id.
 - /info: get information about a user.
 - /markdownhelp: quick summary of how markdown works in telegram - can only be called in private chats.
"""

MARKDOWN_HELP = f"""
Markdown is a very powerful formatting tool supported by telegram. {dispatcher.bot.first_name} has some enhancements, to make sure that \
saved messages are correctly parsed, and to allow you to create buttons.
- <code>_italic_</code>: wrapping text with '_' will produce italic text
- <code>*bold*</code>: wrapping text with '*' will produce bold text
- <code>`code`</code>: wrapping text with '`' will produce monospaced text, also known as 'code'
- <code>[sometext](someURL)</code>: this will create a link - the message will just show <code>sometext</code>, \
and tapping on it will open the page at <code>someURL</code>.
EG: <code>[test](example.com)</code>
- <code>[buttontext](buttonurl:someURL)</code>: this is a special enhancement to allow users to have telegram \
buttons in their markdown. <code>buttontext</code> will be what is displayed on the button, and <code>someurl</code> \
will be the url which is opened.
EG: <code>[This is a button](buttonurl:example.com)</code>
If you want multiple buttons on the same line, use :same, as such:
<code>[one](buttonurl:example.com)
[two](buttonurl:google.com:same)</code>
This will create two buttons on a single line, instead of one button per line.
Keep in mind that your message <b>MUST</b> contain some text other than just a button!

"""

@spamcheck
def get_id(update, context):
    args = context.args
    user_id = extract_user(update.effective_message, args)
    if user_id and user_id != "error":
        if update.effective_message.reply_to_message and update.effective_message.reply_to_message.forward_from:
            user1 = update.effective_message.reply_to_message.from_user
            user2 = update.effective_message.reply_to_message.forward_from
            text = f"The original sender, {escape_markdown(user2.first_name)}, has an ID of `{user2.id}`.\n" \
                   f"The forwarder, {escape_markdown(user1.first_name)}, has an ID of `{user1.id}`."
            if update.effective_message.chat.type != "private":
                text += "\n" + f"This group's id is `{update.effective_message.chat.id}`."
            send_message(update.effective_message, text)
        else:
            user = context.bot.get_chat(user_id)
            text = f"{escape_markdown(user.first_name)}'s id is `{user.id}`."
            if update.effective_message.chat.type != "private":
                text += "\n" + f"This group's id is `{update.effective_message.chat.id}`."
            send_message(update.effective_message, text)
    elif user_id == "error":
        try:
            user = context.bot.get_chat(args[0])
        except BadRequest:
            send_message(update.effective_message, "Error: Unknown User/Chat!")
            return
        text = f"Your id is `{update.effective_message.from_user.id}`."
        text += "\n" + f"That group's id is `{user.id}`."
        if update.effective_message.chat.type != "private":
            text += "\n" + f"This group's id is `{update.effective_message.chat.id}`."
        send_message(update.effective_message, text, parse_mode=ParseMode.MARKDOWN)
    else:
        chat = update.effective_chat  # type: Optional[Chat]
        if chat.type == "private":
            send_message(update.effective_message, f"Your id is `{update.effective_message.from_user.id}`.")

        else:
            send_message(update.effective_message, f"Your id is `{update.effective_message.from_user.id}`." + "\n" + \
                    f"This group's id is `{chat.id}`.")

@spamcheck
def info(update, context):
    args = context.args
    msg = update.effective_message  # type: Optional[Message]
    chat = update.effective_chat  # type: Optional[Chat]
    user_id = extract_user(update.effective_message, args)

    if user_id and user_id != "error":
        user = context.bot.get_chat(user_id)

    elif not msg.reply_to_message and not args:
        user = msg.from_user

    elif not msg.reply_to_message and (not args or (
            len(args) >= 1 and not args[0].startswith("@") and not args[0].isdigit() and not msg.parse_entities(
        [MessageEntity.TEXT_MENTION]))):
        send_message(update.effective_message, "I can't extract a user from this.")
        return

    else:
        return

    text = "<b>User Info</b>:\n" \
           + f"ID: <code>{user.id}</code>\n" \
           + f"First Name: {html.escape(user.first_name)}"

    if user.last_name:
        text += f"\nLast Name: {html.escape(user.last_name)}"

    if user.username:
        text += f"\nUsername: @{html.escape(user.username)}"

    text += "\nPermanent user link: {}".format(mention_html(user.id, "link"))

    if user.id == OWNER_ID:
        text += "\n\nThis person is my owner - I would never do anything against them!"
    else:
        if user.id in SUDO_USERS:
            text += "\nThis person is one of my sudo users! Nearly as powerful as my owner - so watch it."
        else:
            if user.id in SUPPORT_USERS:
                text += "\nThis person is one of my support users! Not quite a sudo user, but can still gban you off the map."

            if user.id in WHITELIST_USERS:
                text += "\n\nThis person has been whitelisted! That means I'm not allowed to ban/kick them."

    fedowner = feds_sql.get_user_owner_fed_name(user.id)
    if fedowner:
        text += "\n\n<b>This user is the owner of this federation:</b>\n<code>"
        text += "</code>, <code>".join(fedowner)
        text += "</code>"
    # fedadmin = feds_sql.get_user_admin_fed_name(user.id)
    # if fedadmin:
    #     text += "\n\nThis user is a fed admin in the current federation:\n"
    #     text += ", ".join(fedadmin)

    for mod in USER_INFO:
        mod_info = mod.__user_info__(user.id, chat.id).strip()
        if mod_info:
            text += "\n\n" + mod_info

    send_message(update.effective_message, text, parse_mode=ParseMode.HTML)


def echo(update, context):
    message = update.effective_message
    chat_id = update.effective_chat.id
    try:
        message.delete()
    except BadRequest:
        pass
    # Advanced
    text, data_type, content, buttons = get_message_type(message)
    knob = build_keyboard_alternate(buttons)
    if str(data_type) in ('Types.BUTTON_TEXT', 'Types.TEXT'):
        try:
            if message.reply_to_message:
                context.bot.send_message(chat_id, text, reply_to_message_id=message.reply_to_message.message_id, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(knob))
            else:
                context.bot.send_message(chat_id, text, quote=False, disable_web_page_preview=True, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(knob))
        except BadRequest:
            context.bot.send_message(chat_id, "Wrong markdown text!\nIf you don't know what markdown is, please type `/markdownhelp` in PM.")
            return


@spamcheck
def markdown_help(update, context):
    send_message(update.effective_message, MARKDOWN_HELP, parse_mode=ParseMode.HTML)
    send_message(update.effective_message, "Try forwarding the following message to me, and you'll see!")
    send_message(update.effective_message, "/save test This is a markdown test. _italics_, *bold*, `code`, "
                                        "[URL](example.com) [button](buttonurl:github.com) [button2](buttonurl:google.com:same)")


def stats(update, context):
    send_message(update.effective_message, "Current stats:\n" + "\n".join([mod.__stats__() for mod in STATS]))


dispatcher.add_handler(DisableAbleCommandHandler("id", get_id, pass_args=True))
dispatcher.add_handler(DisableAbleCommandHandler("info", info, pass_args=True))
dispatcher.add_handler(CommandHandler("echo", echo, filters=Filters.user(OWNER_ID)))
dispatcher.add_handler(CommandHandler("markdownhelp", markdown_help, filters=Filters.chat_type.private))
dispatcher.add_handler(CommandHandler("stats", stats, filters=Filters.user(SUDO_USERS)))

