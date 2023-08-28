import html
import re
from typing import Optional, List

import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode, User, CallbackQuery
from telegram import Message, Chat, Update, Bot
from telegram.error import BadRequest
from telegram.ext import CommandHandler, run_async, DispatcherHandlerStop, MessageHandler, Filters, CallbackQueryHandler
from telegram.utils.helpers import mention_html, escape_markdown

from TPBOT import dispatcher, BAN_STICKER, spamcheck, OWNER_ID
from TPBOT.modules.disable import DisableAbleCommandHandler
from TPBOT.modules.helper_funcs.chat_status import is_user_admin, bot_admin, user_admin_no_reply, user_admin, \
    can_restrict, is_user_ban_protected
from TPBOT.modules.helper_funcs.extraction import extract_text, extract_user_and_text, extract_user
from TPBOT.modules.helper_funcs.misc import split_message
from TPBOT.modules.helper_funcs.string_handling import split_quotes
from TPBOT.modules.log_channel import loggable
from TPBOT.modules.sql import warns_sql as sql
from TPBOT.modules.connection import connected

from TPBOT.modules.helper_funcs.alternate import send_message, send_message_raw

WARN_HANDLER_GROUP = 9

__mod_name__ = "Warnings"

__help__ = """
Similar to blacklist feature, warnings will look for trigger words in the chat.  However, the offending user will be given a set number of "warnings" before the bot takes action.

*NOTE: Use the `warndelete` option to delete the original message.  Using the same words on the warning list and the blacklist can have unpredictable results.*

 - /warns <userhandle>: get a user's number, and reason, of warnings.
 - /warnlist: list of all current warning filters

*Admin only:*
 - /warn <userhandle>: warn a user. After 3 warns, the user will be banned from the group. Can also be used as a reply.
 - /resetwarn <userhandle>: reset the warnings for a user. Can also be used as a reply.
 - /addwarn <keyword> <reply message>: set a warning filter on a certain keyword. If you want your keyword to \
be a sentence, encompass it with quotes, as such: `/addwarn "very angry" This is an angry user`. 
 - /nowarn <keyword>: stop a warning filter
 - /warnlimit <num>: set the warning limit
 - /warnmode <kick/ban/mute>: Set warn mode, when user exceeding the warn limit will result in that mode.
 - /warndelete: Get current deletion setting.  i.e. Whether or not offending messages will be deleted after warnings.
 - /warndelete <on/yes/off/no>: Set message deletion mode.
"""

# Not async
def warn(user: User, chat: Chat, reason: str, message: Message, warner: User = None, conn=False) -> str:
    if is_user_admin(chat, user.id):
        return ""

    if warner:
        warner_tag = mention_html(warner.id, warner.first_name)
    else:
        warner_tag = "Automated warn filter"

    limit, soft_warn, warn_mode = sql.get_warn_setting(chat.id)
    num_warns, reasons = sql.warn_user(user.id, chat.id, reason)
    if num_warns >= limit:
        sql.reset_warns(user.id, chat.id)
        if not warn_mode:
            chat.unban_member(user.id)
            reply = "{} warnings, {} has been kicked!".format(limit, mention_html(user.id, user.full_name))
        elif warn_mode == 1:
            chat.unban_member(user.id)
            reply = "{} warnings, {} has been kicked!".format(limit, mention_html(user.id, user.full_name))
        elif warn_mode == 2:
            chat.ban_member(user.id)
            reply = "{} warnings, {} has been banned!".format(limit, mention_html(user.id, user.full_name))
        else:
            message.bot.restrict_chat_member(chat.id, user.id, can_send_messages=False)
            reply = "{} warnings, {} has been muted!".format(limit, mention_html(user.id, user.full_name))

        for warn_reason in reasons:
            reply += "\n - {}".format(html.escape(warn_reason))

        # message.bot.send_sticker(chat.id, BAN_STICKER)  # banhammer marie sticker
        keyboard = None
        log_reason = "<b>{}:</b>" \
                     "\n#WARN_BAN" \
                     "\n<b>Admin:</b> {}" \
                     "\n<b>User:</b> {} (<code>{}</code>)" \
                     "\n<b>Reason:</b> {}"\
                     "\n<b>Counts:</b> <code>{}/{}</code>".format(html.escape(chat.title),
                                                                  warner_tag,
                                                                  mention_html(user.id, user.full_name),
                                                                  user.id, reason, num_warns, limit)

    else:
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Remove warning", callback_data="rm_warn({})".format(user.id)), InlineKeyboardButton("Rules", url="t.me/{}?start={}".format(dispatcher.bot.username, chat.id))]])

        if num_warns+1 == limit:
            if not warn_mode:
                action_mode = "kicked"
            elif warn_mode == 1:
                action_mode = "kicked"
            elif warn_mode == 2:
                action_mode = "banned"
            elif warn_mode == 3:
                action_mode = "muted"
            reply = "{} has {}/{} warnings... If you are warned again, you will be {}!".format(mention_html(user.id, user.full_name), num_warns, limit, action_mode)
        else:
            reply = "{} has {}/{} warnings... watch out!".format(mention_html(user.id, user.full_name), num_warns, limit)
        if reason:
            reply += "\nReason for last warning:\n{}".format(html.escape(reason))

        log_reason = f"<b>{html.escape(chat.title)}:</b>" \
                     "\n#WARN" \
                     f"\n<b>Admin:</b> {warner_tag}" \
                     f"\n<b>User:</b> {mention_html(user.id, user.full_name)} (<code>{user.id}</code>)" \
                     f"\n<b>Reason:</b> {reason}"\
                     f"\n<b>Counts:</b> <code>{num_warns}/{limit}</code>" \
                     f"\n\n{message.text}"

    try:
        if conn:
            send_message_raw(chat.id, reply, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        else:
            send_message_raw(chat.id, reply, reply_to_message_id=message.message_id, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        if not soft_warn:
            message.delete()
    except BadRequest as excp:
        if excp.message == "Reply message not found":
            # Do not reply
            if conn:
                message.bot.sendMessage(chat.id, reply, reply_markup=keyboard, parse_mode=ParseMode.HTML)
            else:
                try:
                    message.bot.sendMessage(chat.id, reply, reply_to_message_id=message.message_id, reply_markup=keyboard, parse_mode=ParseMode.HTML, quote=False)
                except BadRequest:
                    message.bot.sendMessage(chat.id, reply, reply_markup=keyboard, parse_mode=ParseMode.HTML, quote=False)
        else:
            raise
    return log_reason


@user_admin_no_reply
@bot_admin
@loggable
def button(update, context):
    query = update.callback_query
    user = update.effective_user
    match = re.match(r"rm_warn\((.+?)\)", query.data)
    if match:
        user_id = match.group(1)
        chat = update.effective_chat
        res = sql.remove_warn(user_id, chat.id)
        if res:
            update.effective_message.edit_text(
                "Warnings removed by {}.".format(mention_html(user.id, user.first_name)),
                parse_mode=ParseMode.HTML)
            user_member = chat.get_member(user_id)
            return "<b>{}:</b>" \
                   "\n#UNWARN" \
                   "\n<b>Admin:</b> {}" \
                   "\n<b>User:</b> {} (<code>{}</code>)".format(html.escape(chat.title),
                                                                mention_html(user.id, user.first_name),
                                                                mention_html(user_member.user.id, user_member.user.full_name),
                                                                user_member.user.id)
        else:
            update.effective_message.edit_text(
            "User already has no warnings.".format(mention_html(user.id, user.full_name)),
            parse_mode=ParseMode.HTML)
            
    return ""


@spamcheck
@user_admin
#@can_restrict
@loggable
def warn_user(update, context):
    message = update.effective_message
    chat = update.effective_chat
    warner = update.effective_user
    user = update.effective_user
    args = context.args

    user_id, reason = extract_user_and_text(message, args)
    if user_id == "error":
        send_message(update.effective_message, reason)
        return ""

    conn = connected(context.bot, update, chat, user.id, need_admin=True)
    if conn:
        chat = dispatcher.bot.getChat(conn)
        chat_id = conn
        chat_name = dispatcher.bot.getChat(conn).title
    else:
        if update.effective_message.chat.type == "private":
            send_message(update.effective_message, "You can do this command in groups, not PM")
            return ""
        chat = update.effective_chat
        chat_id = update.effective_chat.id
        chat_name = update.effective_message.chat.title

    check = context.bot.getChatMember(chat_id, context.bot.id)
    if check.status == 'member' or check['can_restrict_members'] == False:
        if conn:
            text = "I can't restrect people on {}! Make sure I'm already an admin.".format(chat_name)
        else:
            text = "I can't restrect people in here! Make sure I'm already an admin."
        send_message(update.effective_message, text, parse_mode="markdown")
        return ""

    if user_id:
        if conn:
            warning = warn(chat.get_member(user_id).user, chat, reason, message, warner, conn=True)
            send_message(update.effective_message, "That user has been warned in *{}*".format(chat_name), parse_mode="markdown")
            return warning
        else:
            if message.reply_to_message and message.reply_to_message.from_user.id == user_id:
                return warn(message.reply_to_message.from_user, chat, reason, message.reply_to_message, warner)
            else:
                return warn(chat.get_member(user_id).user, chat, reason, message, warner)
    else:
        send_message(update.effective_message, "No user was designated!")
    return ""


@spamcheck
@user_admin
#@bot_admin
@loggable
def reset_warns(update, context):
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    args = context.args

    user_id = extract_user(message, args)

    conn = connected(context.bot, update, chat, user.id, need_admin=True)
    if conn:
        chat = dispatcher.bot.getChat(conn)
        chat_id = conn
        chat_name = dispatcher.bot.getChat(conn).title
    else:
        if update.effective_message.chat.type == "private":
            send_message(update.effective_message, "You can do this command in groups, not PM")
            return ""
        chat = update.effective_chat
        chat_id = update.effective_chat.id
        chat_name = update.effective_message.chat.title

    check = context.bot.getChatMember(chat_id, context.bot.id)
    if check.status == 'member' or check['can_restrict_members'] == False:
        if conn:
            text = "I can't restrect people on {}! Make sure I'm already an admin.".format(chat_name)
        else:
            text = "I can't restrect people in here! Make sure I'm already an admin."
        send_message(update.effective_message, text, parse_mode="markdown")
        return ""
    
    if user_id and user_id != "error":
        sql.reset_warns(user_id, chat.id)
        if conn:
            send_message(update.effective_message, "Warnings have been reset in *{}*!".format(chat_name), parse_mode="markdown")
        else:
            send_message(update.effective_message, "Warnings have been reset!")
        warned = chat.get_member(user_id).user
        return "<b>{}:</b>" \
               "\n#RESETWARNS" \
               "\n<b>Admin:</b> {}" \
               "\n<b>User:</b> {} (<code>{}</code>)".format(html.escape(chat.title),
                                                            mention_html(user.id, user.first_name),
                                                            mention_html(warned.id, warned.full_name),
                                                            warned.id)
    else:
        send_message(update.effective_message, "No user was designated!")
    return ""


@spamcheck
def warns(update, context):
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    args = context.args

    conn = connected(context.bot, update, chat, user.id, need_admin=False)
    if conn:
        chat = dispatcher.bot.getChat(conn)
        chat_id = conn
        chat_name = dispatcher.bot.getChat(conn).title
    else:
        if update.effective_message.chat.type == "private":
            send_message(update.effective_message, "You can do this command in groups, not PM")
            return ""
        chat = update.effective_chat
        chat_id = update.effective_chat.id
        chat_name = update.effective_message.chat.title

    user_id = extract_user(message, args) or update.effective_user.id
    result = sql.get_warns(user_id, chat.id)

    if result and result[0] != 0:
        num_warns, reasons = result
        limit, soft_warn, warn_mode = sql.get_warn_setting(chat.id)

        if reasons:
            if conn:
                text = "This user has {}/{} warnings at *{}*, for the following reasons:".format(num_warns, limit, chat_name)
            else:
                text = "This user has {}/{} warnings, for the following reasons:".format(num_warns, limit)
            for reason in reasons:
                text += "\n - {}".format(reason)

            msgs = split_message(text)
            for msg in msgs:
                send_message(update.effective_message, msg, parse_mode="markdown")
        else:
            if conn:
                send_message(update.effective_message, 
                    "User has {}/{} warnings at *{}*, but no reasons for any of them.".format(num_warns, limit, chat_name), parse_mode="markdown")
            else:
                send_message(update.effective_message, 
                    "User has {}/{} warnings, but no reasons for any of them.".format(num_warns, limit))
    else:
        if conn:
            send_message(update.effective_message, "This user doesn't have any warnings in *{}*!".format(chat_name), parse_mode="markdown")
        else:
            send_message(update.effective_message, "This user doesn't have any warnings!")


@spamcheck
@user_admin
def add_warn_filter(update, context):
    chat = update.effective_chat
    msg = update.effective_message
    user = update.effective_user

    conn = connected(context.bot, update, chat, user.id, need_admin=True)
    if conn:
        chat = dispatcher.bot.getChat(conn)
        chat_id = conn
        chat_name = dispatcher.bot.getChat(conn).title
    else:
        if update.effective_message.chat.type == "private":
            send_message(update.effective_message, "You can do this command in groups, not PM")
            return ""
        chat = update.effective_chat
        chat_id = update.effective_chat.id
        chat_name = update.effective_message.chat.title

    args = msg.text.split(None, 1)  # use python's maxsplit to separate Cmd, keyword, and reply_text

    if len(args) < 2:
        return

    extracted = split_quotes(args[1])

    if len(extracted) >= 2:
        # set trigger -> lower, so as to avoid adding duplicate filters with different cases
        keyword = extracted[0].lower()
        content = extracted[1]

    else:
        return

    # Note: perhaps handlers can be removed somehow using sql.get_chat_filters
    for handler in dispatcher.handlers.get(WARN_HANDLER_GROUP, []):
        if handler.filters == (keyword, chat.id):
            dispatcher.remove_handler(handler, WARN_HANDLER_GROUP)

    sql.add_warn_filter(chat.id, keyword, content)

    if conn:
        text = "Warn handler added for '{}' at *{}*!".format(keyword, chat_name)
    else:
        text = "Warn handler added for '{}'!".format(keyword)
    send_message(update.effective_message, text, parse_mode="markdown")
    raise DispatcherHandlerStop


@spamcheck
@user_admin
def remove_warn_filter(update, context):
    chat = update.effective_chat
    msg = update.effective_message
    user = update.effective_user

    conn = connected(context.bot, update, chat, user.id, need_admin=True)
    if conn:
        chat = dispatcher.bot.getChat(conn)
        chat_id = conn
        chat_name = dispatcher.bot.getChat(conn).title
    else:
        if update.effective_message.chat.type == "private":
            send_message(update.effective_message, "You can do this command in groups, not PM")
            return ""
        chat = update.effective_chat
        chat_id = update.effective_chat.id
        chat_name = update.effective_message.chat.title

    args = msg.text.split(None, 1)  # use python's maxsplit to separate Cmd, keyword, and reply_text

    if len(args) < 2:
        return

    extracted = split_quotes(args[1])

    if len(extracted) < 1:
        return

    chat_filters = sql.get_chat_warn_triggers(chat.id)
    if not chat_filters:
        if conn:
            text = "No warning filters are active in *{}*!".format(chat_name)
        else:
            text = "No warning filters are active here!"
        send_message(update.effective_message, text)
        return

    nowarn = 0
    inwarn = 0
    success = ""
    fail = ""
    teks = args[1].split(" ")
    for x in range(len(teks)):
        to_remove = teks[x]
        if to_remove not in chat_filters:
            fail += "`{}` ".format(to_remove)
            nowarn += 1
        for filt in chat_filters:
            if filt == to_remove:
                sql.remove_warn_filter(chat.id, to_remove)
                success += "`{}` ".format(to_remove)
                inwarn += 1
    if nowarn == 0:
        if conn:
            text = "Yep, I'll stop warning people for {} in *{}*.".format(success, chat_name)
        else:
            text = "Yep, I'll stop warning people for {}.".format(success)
        send_message(update.effective_message, text, parse_mode=ParseMode.MARKDOWN)
        raise DispatcherHandlerStop
    elif inwarn == 0:
        if conn:
            text = "Failed to delete warn filter for {} in *{}*.".format(fail, chat_name)
        else:
            text = "Failed to delete warn filter for {}.".format(fail)
        send_message(update.effective_message, text, parse_mode=ParseMode.MARKDOWN)
        raise DispatcherHandlerStop
    else:
        if conn:
            text = "Yep, I'll stop warning people for {}.\nAnd failed to delete warn filter for {} in *{}*".format(success, fail, chat_name)
        else:
            text = "Yep, I'll stop warning people for {}.\nAnd failed to delete warn filter for {}.".format(success, fail)
        send_message(update.effective_message, text, parse_mode=ParseMode.MARKDOWN)
        raise DispatcherHandlerStop

    # """
    # if not chat_filters:
    #     send_message(update.effective_message, "Tidak ada filter peringatan aktif di sini!")
    #     return

    # for filt in chat_filters:
    #     if filt == to_remove:
    #         sql.remove_warn_filter(chat.id, to_remove)
    #             send_message(update.effective_message, "Ya, saya akan berhenti memperingatkan orang-orang untuk {}.".format(to_remove))
    #             raise DispatcherHandlerStop
    # """

    if conn:
        text = "That's not a current warning filter - run /warnlist for all active warning filters in *{}*."
    else:
        text = "That's not a current warning filter - run /warnlist for all active warning filters."
    send_message(update.effective_message, text, parse_mode="markdown")


@spamcheck
def list_warn_filters(update, context):
    chat = update.effective_chat
    user = update.effective_user

    conn = connected(context.bot, update, chat, user.id, need_admin=False)
    if conn:
        chat = dispatcher.bot.getChat(conn)
        chat_id = conn
        chat_name = dispatcher.bot.getChat(conn).title
    else:
        if update.effective_message.chat.type == "private":
            send_message(update.effective_message, "You can do this command in groups, not PM")
            return ""
        chat = update.effective_chat
        chat_id = update.effective_chat.id
        chat_name = update.effective_message.chat.title

    all_handlers = sql.get_chat_warn_triggers(chat.id)

    if not all_handlers:
        if conn:
            text = "No alert filter is active in *{}*!".format(chat_name)
        else:
            text = "No alert filter is active!"
        send_message(update.effective_message, text, parse_mode="markdown")
        return

    filter_list = "CURRENT_WARNING_FILTER_STRING"
    if conn:
        filter_list = filter_list.replace('this chat', 'chat *{}*'.format(chat_name))
    for keyword in all_handlers:
        entry = " - {}\n".format(html.escape(keyword))
        if len(entry) + len(filter_list) > telegram.MAX_MESSAGE_LENGTH:
            send_message(update.effective_message, filter_list, parse_mode=ParseMode.HTML)
            filter_list = entry
        else:
            filter_list += entry

    if not filter_list == "CURRENT_WARNING_FILTER_STRING":
        send_message(update.effective_message, filter_list, parse_mode=ParseMode.HTML)


@loggable
def reply_filter(update, context) -> str:
    chat = update.effective_chat
    message = update.effective_message

    chat_warn_filters = sql.get_chat_warn_triggers(chat.id)
    to_match = extract_text(message)
    if not to_match:
        return ""

    for keyword in chat_warn_filters:
        pattern = r"( |^|[^\w])" + re.escape(keyword) + r"( |$|[^\w])"
        if re.search(pattern, to_match, flags=re.IGNORECASE):
            user = update.effective_user
            warn_filter = sql.get_warn_filter(chat.id, keyword)
            return warn(user, chat, warn_filter.reply, message)
    return ""


@spamcheck
@user_admin
@loggable
def set_warn_limit(update, context) -> str:
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message
    args = context.args

    conn = connected(context.bot, update, chat, user.id, need_admin=True)
    if conn:
        chat = dispatcher.bot.getChat(conn)
        chat_id = conn
        chat_name = dispatcher.bot.getChat(conn).title
    else:
        if update.effective_message.chat.type == "private":
            send_message(update.effective_message, "You can do this command in groups, not PM")
            return ""
        chat = update.effective_chat
        chat_id = update.effective_chat.id
        chat_name = update.effective_message.chat.title

    if args:
        if args[0].isdigit():
            if int(args[0]) < 3:
                send_message(update.effective_message, "The minimum for a warning limit is 3!")
            else:
                sql.set_warn_limit(chat.id, int(args[0]))
                if conn:
                    text = "Updated the warning limit to {} in *{}*".format(args[0], chat_name)
                else:
                    text = "Updated the warning limit to {}".format(args[0])
                send_message(update.effective_message, text, parse_mode="markdown")
                return "<b>{}:</b>" \
                       "\n#SET_WARN_LIMIT" \
                       "\n<b>Admin:</b> {}" \
                       "\nSet the warning limit to <code>{}</code>".format(html.escape(chat.title),
                                                                        mention_html(user.id, user.first_name), args[0])
        else:
            send_message(update.effective_message, "Give me a number to set the limit!")
    else:
        limit, soft_warn, warn_mode = sql.get_warn_setting(chat.id)
        if conn:
            text = "The current warning limit is {} in *{}*".format(limit, chat_name)
        else:
            text = "The current warning limit is {}".format(limit)
        send_message(update.effective_message, text, parse_mode="markdown")
    return ""

@spamcheck
@user_admin
def set_warn_delete(update, context):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message
    args = context.args
    conn = connected(context.bot, update, chat, user.id, need_admin=True)
    if conn:
        chat = dispatcher.bot.getChat(conn)
        chat_id = conn
        chat_name = dispatcher.bot.getChat(conn).title
    else:
        if update.effective_message.chat.type == "private":
            send_message(update.effective_message, "You can do this command in groups, not PM")
            return ""
        chat = update.effective_chat
        chat_id = update.effective_chat.id
        chat_name = update.effective_message.chat.title

    if args:
        if args[0].lower() in ("on", "yes"):
            sql.set_warn_strength(chat.id, False)
            if conn:
                text = "Offending messages will be deleted after warnings in *{}*!".format(chat_name)
            else:
                text = "Offending messages will be deleted after warnings!"
            send_message(update.effective_message, text, parse_mode="markdown")
            return "<b>{}:</b>\n" \
                   "<b>Admin:</b> {}\n" \
                   "...has enabled deletion of offending messages after warnings.".format(html.escape(chat.title),
                                                                            mention_html(user.id, user.first_name))

        elif args[0].lower() in ("off", "no"):
            sql.set_warn_strength(chat.id, True)
            if conn:
                text = "Offending messages will NOT be deleted after warnings in *{}*! Replied-to message will remain.".format(chat_name)
            else:
                text = "Offending messages will NOT be deleted after warnings.  Replied-to message will remain."
            send_message(update.effective_message, text, parse_mode="markdown")
            return "<b>{}:</b>\n" \
                   "<b>Admin:</b> {}\n" \
                   "...has disabled deletion of offending messages after warnings.".format(html.escape(chat.title),
                                                                                  mention_html(user.id,
                                                                                               user.first_name))

        else:
            send_message(update.effective_message, "I only understand on/yes/no/off!")
    else:
        limit, soft_warn, warn_mode = sql.get_warn_setting(chat.id)
        if soft_warn:
            if conn:
                text = "Warnings are currently set to *leave* the offending message after a warning within *{}*.".format(chat_name)
            else:
                text = "Warnings are currently set to *leave* the offending message after a warning."
            send_message(update.effective_message, text,
                           parse_mode=ParseMode.MARKDOWN)
        else:
            if conn:
                text = "Warnings are currently set to *delete* the offending message after a warning within *{}*.".format(chat_name)
            else:
                text = "Warnings are currently set to *delete* the offending message after a warning."
            send_message(update.effective_message, text,
                           parse_mode=ParseMode.MARKDOWN)
    return ""


@spamcheck
@user_admin
def set_warn_strength(update, context):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message
    args = context.args

    conn = connected(context.bot, update, chat, user.id, need_admin=True)
    if conn:
        chat = dispatcher.bot.getChat(conn)
        chat_id = conn
        chat_name = dispatcher.bot.getChat(conn).title
    else:
        if update.effective_message.chat.type == "private":
            send_message(update.effective_message, "You can do this command in groups, not PM")
            return ""
        chat = update.effective_chat
        chat_id = update.effective_chat.id
        chat_name = update.effective_message.chat.title

    if args:
        if args[0].lower() in ("on", "yes"):
            sql.set_warn_strength(chat.id, False)
            if conn:
                text = "Too many warnings will now result in a ban within *{}*!".format(chat_name)
            else:
                text = "Too many warnings will now result in a ban!"
            send_message(update.effective_message, text, parse_mode="markdown")
            return "<b>{}:</b>\n" \
                   "<b>Admin:</b> {}\n" \
                   "...has enabled strong warning mode.  Violators will banned!".format(html.escape(chat.title),
                                                                            mention_html(user.id, user.first_name))

        elif args[0].lower() in ("off", "no"):
            sql.set_warn_strength(chat.id, True)
            if conn:
                text = "Too many warnings will result in being kicked from *{}*! Users will be able to rejoin.".format(chat_name)
            else:
                text = "Too many warnings will result in being kicked!  Users will be able to rejoin."
            send_message(update.effective_message, text, parse_mode="markdown")
            return "<b>{}:</b>\n" \
                   "<b>Admin:</b> {}\n" \
                   "...has disabled strong warning mode.  Violators will only be kicked.".format(html.escape(chat.title),
                                                                                  mention_html(user.id,
                                                                                               user.first_name))

        else:
            send_message(update.effective_message, "I only understand on/yes/no/off!")
    else:
        limit, soft_warn, warn_mode = sql.get_warn_setting(chat.id)
        if soft_warn:
            if conn:
                text = "Warnings are currently set to *kick* the user when exceeding the limit within *{}*.".format(chat_name)
            else:
                text = "Warnings are currently set to *kick* the user when exceeding the limit."
            send_message(update.effective_message, text,
                           parse_mode=ParseMode.MARKDOWN)
        else:
            if conn:
                text = "Warnings are currently set to *ban* the user when exceeding the limit within *{}*.".format(chat_name)
            else:
                text = "Warnings are currently set to *ban* the user when exceeding the limit."
            send_message(update.effective_message, text,
                           parse_mode=ParseMode.MARKDOWN)
    return ""


@spamcheck
@user_admin
def set_warn_mode(update, context):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message
    args = context.args

    conn = connected(context.bot, update, chat, user.id, need_admin=True)
    if conn:
        chat = dispatcher.bot.getChat(conn)
        chat_id = conn
        chat_name = dispatcher.bot.getChat(conn).title
    else:
        if update.effective_message.chat.type == "private":
            send_message(update.effective_message, "You can do this command in groups, not PM")
            return ""
        chat = update.effective_chat
        chat_id = update.effective_chat.id
        chat_name = update.effective_message.chat.title

    if args:
        if args[0].lower() in ("kick", "soft"):
            sql.set_warn_mode(chat.id, 1)
            if conn:
                text = "Too many warns will now result in a kick in *{}*! Users will be able to join again after.".format(chat_name)
            else:
                text = "Too many warns will now result in a kick! Users will be able to join again after."
            send_message(update.effective_message, text, parse_mode="markdown")
            return "<b>{}:</b>\n" \
                   "<b>Admin:</b> {}\n" \
                   "Has changed the final warning to kick.".format(html.escape(chat.title),
                                                                            mention_html(user.id, user.first_name))

        elif args[0].lower() in ("ban", "banned", "hard"):
            sql.set_warn_mode(chat.id, 2)
            if conn:
                text = "Too many warns will now result in a ban from *{}*!".format(chat_name)
            else:
                text = "Too many warns will now result in a ban!"
            send_message(update.effective_message, text, parse_mode="markdown")
            return "<b>{}:</b>\n" \
                   "<b>Admin:</b> {}\n" \
                   "Has changed the final warning to banned.".format(html.escape(chat.title),
                                                                                  mention_html(user.id,
                                                                                               user.first_name))

        elif args[0].lower() in ("mute"):
            sql.set_warn_mode(chat.id, 3)
            if conn:
                text = "Too many warnings will now result in a mute within *{}*!".format(chat_name)
            else:
                text = "Too many warnings will now result in a mute!"
            send_message(update.effective_message, text, parse_mode="markdown")
            return "<b>{}:</b>\n" \
                   "<b>Admin:</b> {}\n" \
                   "Has changed the final warning to mute.".format(html.escape(chat.title),
                                                                                  mention_html(user.id,
                                                                                               user.first_name))

        else:
            send_message(update.effective_message, "I only understand kick/ban/mute!")
    else:
        limit, soft_warn, warn_mode = sql.get_warn_setting(chat.id)
        if not soft_warn:
            if not warn_mode:
                if conn:
                    text = "Warnings currently set to *kick* users when they exceed the limits within *{}*.".format(chat_name)
                else:
                    text = "Warnings currently set to *kick* users when they exceed the limits."
            elif warn_mode == 1:
                if conn:
                    text = "Warnings currently set to *kick* users when they exceed the limits within *{}*.".format(chat_name)
                else:
                    text = "Warnings currently set to *kick* users when they exceed the limits."
            elif warn_mode == 2:
                if conn:
                    text = "Warnings currently set to *ban* users when they exceed the limits within *{}*.".format(chat_name)
                else:
                    text = "Warnings currently set to *ban* users when they exceed the limits."
            elif warn_mode == 3:
                if conn:
                    text = "Warnings currently set to *mute* users when they exceed the limits within *{}*.".format(chat_name)
                else:
                    text = "Warnings currently set to *mute* users when they exceed the limits."
            send_message(update.effective_message, text,
                           parse_mode=ParseMode.MARKDOWN)
        else:
            if conn:
                text = "Alerts are currently set to *ban* users when they exceed the limits within *{}*.".format(chat_name)
            else:
                text = "Alerts are currently set to *ban* users when they exceed the limits."
            send_message(update.effective_message, text,
                           parse_mode=ParseMode.MARKDOWN)
    return ""


def __stats__():
    return "{} overall warnings, across {} chats.\n" \
           "{} warn filters, across {} chats.".format(sql.num_warns(), sql.num_warn_chats(),
                                                      sql.num_warn_filters(), sql.num_warn_filter_chats())


def __import_data__(chat_id, data):
    for user_id, count in data.get('warns', {}).items():
        for x in range(int(count)):
            sql.warn_user(user_id, chat_id)


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(chat_id, user_id):
    num_warn_filters = sql.num_warn_chat_filters(chat_id)
    limit, soft_warn, warn_mode = sql.get_warn_setting(chat_id)
    return "This chat has `{}` warn filters. It takes `{}` warnings " \
           "before the user gets *{}*.".format(num_warn_filters, limit, "kicked" if soft_warn else "banned")


dispatcher.add_handler(CommandHandler("warn", warn_user, pass_args=True))
dispatcher.add_handler(CallbackQueryHandler(button, pattern=r"rm_warn"))
dispatcher.add_handler(CommandHandler(["resetwarn", "resetwarns", "rmwarn"], reset_warns, pass_args=True))
dispatcher.add_handler(DisableAbleCommandHandler("warns", warns, pass_args=True))
dispatcher.add_handler(CommandHandler("addwarn", add_warn_filter, run_async=False))
dispatcher.add_handler(CommandHandler(["nowarn", "stopwarn"], remove_warn_filter, run_async=False))
dispatcher.add_handler(DisableAbleCommandHandler(["warnlist", "warnfilters"], list_warn_filters))
dispatcher.add_handler(CommandHandler("warnlimit", set_warn_limit, pass_args=True))
dispatcher.add_handler(CommandHandler("warnmode", set_warn_mode, pass_args=True))
dispatcher.add_handler(MessageHandler(Filters.text & Filters.chat_type.groups, reply_filter), WARN_HANDLER_GROUP)
dispatcher.add_handler(CommandHandler("warndelete", set_warn_delete, pass_args=True))