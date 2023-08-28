import random
import re
import time

from telegram import ParseMode, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, ChatPermissions
from telegram.ext import CommandHandler, CallbackQueryHandler, Filters, run_async
from telegram.error import BadRequest
from telegram.utils.helpers import mention_markdown

from TPBOT import dispatcher, updater, spamcheck, IS_DEBUG
import TPBOT.modules.sql.welcome_sql as sql
from TPBOT.modules.connection import connected

from TPBOT.modules.helper_funcs.alternate import send_message, send_message_raw
from TPBOT.modules.helper_funcs.chat_status import user_admin
from TPBOT.modules.helper_funcs.string_handling import make_time, extract_time_int

def welcome_timeout(context):
	for cht in sql.get_all_chat_timeout():
		user_id = cht.user_id
		chat_id = cht.chat_id
		if int(time.time()) >= int(cht.timeout_int):
			getcur, extra_verify, cur_value, timeout, timeout_mode, cust_text = sql.welcome_security(chat_id)
			if timeout_mode == 1:
				try:
					context.bot.unbanChatMember(chat_id, user_id)
				except Exception as err:
					pass
			elif timeout_mode == 2:
				try:
					context.bot.kickChatMember(chat_id, user_id)
				except Exception as err:
					pass
			sql.rm_from_timeout(chat_id, user_id)



@spamcheck
@user_admin
def set_verify_welcome(update, context):
	args = context.args
	chat = update.effective_chat
	getcur, extra_verify, cur_value, timeout, timeout_mode, cust_text = sql.welcome_security(chat.id)
	if len(args) >= 1:
		var = args[0].lower()
		if (var == "yes" or var == "ya" or var == "on"):
			check = context.bot.getChatMember(chat.id, context.bot.id)
			if check.status == 'member' or check['can_restrict_members'] == False:
				text = "I can't manage member restrictions here! Make sure I'm an admin and can mute users!"
				send_message(update.effective_message, text, parse_mode="markdown")
				return ""
			sql.set_welcome_security(chat.id, getcur, True, str(cur_value), str(timeout), int(timeout_mode), cust_text)
			send_message(update.effective_message, "Security for new members is activated! New users are required to complete verification to un-mute.")
		elif (var == "no" or var == "ga" or var == "off"):
			sql.set_welcome_security(chat.id, getcur, False, str(cur_value), str(timeout), int(timeout_mode), cust_text)
			send_message(update.effective_message, "Disabled.  New users can chat once added to the group.")
		else:
			send_message(update.effective_message, "Please choose either 'on' or 'off'.", parse_mode=ParseMode.MARKDOWN)
	else:
		getcur, extra_verify, cur_value, timeout, timeout_mode, cust_text = sql.welcome_security(chat.id)
		if cur_value[:1] == "0":
			cur_value = "Forever"
		text = "Current settings are:\nWelcome security: `{}`\nVerify security: `{}`\nMembers will be muted for: `{}`\nVerification timeout: `{}`\nUnmute custom button: `{}`".format(getcur, extra_verify, cur_value, make_time(int(timeout)), cust_text)
		send_message(update.effective_message, text, parse_mode="markdown")


@spamcheck
@user_admin
def set_welctimeout(update, context):
	args = context.args
	chat = update.effective_chat
	message = update.effective_message
	getcur, extra_verify, cur_value, timeout, timeout_mode, cust_text = sql.welcome_security(chat.id)
	if len(args) >= 1:
		var = args[0]
		if var[:1] == "0":
			mutetime = "0"
			sql.set_welcome_security(chat.id, getcur, extra_verify, cur_value, "0", timeout_mode, cust_text)
			text = "Verification timeout has been deactivated!"
		else:
			mutetime = extract_time_int(message, var)
			if mutetime == "":
				return
			sql.set_welcome_security(chat.id, getcur, extra_verify, cur_value, str(mutetime), timeout_mode, cust_text)
			text = "If the new member doesn't verify within *{}* then he/she will be *{}*".format(var, "Kicked" if timeout_mode == 1 else "Banned")
		send_message(update.effective_message, text, parse_mode="markdown")
	else:
		if timeout == "0":
			send_message(update.effective_message, "Timeout settings: *{}*".format("Disabled"), parse_mode="markdown")
		else:
			send_message(update.effective_message, "Timeout settings: *{}*".format(make_time(int(timeout))), parse_mode="markdown")

@spamcheck
@user_admin
def timeout_mode(update, context):
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

	getcur, extra_verify, cur_value, timeout, timeout_mode, cust_text = sql.welcome_security(chat.id)

	if args:
		if args[0].lower() == 'kick' or args[0].lower() == 'kicked' or args[0].lower() == 'leave':
			settypeblacklist = 'kick'
			sql.set_welcome_security(chat.id, getcur, extra_verify, cur_value, timeout, 1, cust_text)
		elif args[0].lower() == 'ban' or args[0].lower() == 'banned':
			settypeblacklist = 'banned'
			sql.set_welcome_security(chat.id, getcur, extra_verify, cur_value, timeout, 2, cust_text)
		else:
			send_message(update.effective_message, "I only understand kick/banned!")
			return
		if conn:
			text = "Timeout mode changed, User will be `{}` at *{}*!".format(settypeblacklist, chat_name)
		else:
			text = "Timeout mode changed, User will be `{}`!".format(settypeblacklist)
		send_message(update.effective_message, text, parse_mode="markdown")
	else:
		if timeout_mode == 1:
			settypeblacklist = "kick"
		elif timeout_mode == 2:
			settypeblacklist = "banned"
		if conn:
			text = "The current timeout mode is set to *{}* at *{}*.".format(settypeblacklist, chat_name)
		else:
			text = "The current timeout mode is set to *{}*.".format(settypeblacklist)
		send_message(update.effective_message, text, parse_mode=ParseMode.MARKDOWN)
	return



job = updater.job_queue

job_timeout_set = job.run_repeating(welcome_timeout, interval=10, first=1)
job_timeout_set.enabled = True


WELCVERIFY_HANDLER = CommandHandler("welcomeverify", set_verify_welcome, pass_args=True, filters=Filters.chat_type.groups)
WELTIMEOUT_HANDLER = CommandHandler("wtimeout", set_welctimeout, pass_args=True, filters=Filters.chat_type.groups)
WELMODE_HANDLER = CommandHandler("wtmode", timeout_mode, pass_args=True, filters=Filters.chat_type.groups)

dispatcher.add_handler(WELCVERIFY_HANDLER)
dispatcher.add_handler(WELTIMEOUT_HANDLER)
dispatcher.add_handler(WELMODE_HANDLER)
