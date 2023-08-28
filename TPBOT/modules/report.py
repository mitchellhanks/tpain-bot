import html
from typing import Optional, List

from telegram import Message, Chat, Update, Bot, User, ParseMode, ChatMember
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest, Unauthorized
from telegram.ext import CommandHandler, MessageHandler, run_async, Filters, CallbackQueryHandler
from telegram.utils.helpers import mention_html, mention_markdown

from TPBOT import dispatcher, LOGGER, spamcheck, OWNER_ID, SUDO_USERS, SUPPORT_USERS, STRICT_GBAN
from TPBOT.modules.helper_funcs.chat_status import user_not_admin, user_admin
from TPBOT.modules.log_channel import loggable
from TPBOT.modules.sql import reporting_sql as sql

from TPBOT.modules.helper_funcs.alternate import send_message

__mod_name__ = "Report"

__help__ = """
 - /report <reason>: reply to a message to report it to admins.
 - @admin: reply to a message to report it to admins.
NOTE: neither of these will get triggered if used by admins

*Admin only:*
 - /reports <on/off>: change report setting, or view current status.
   - If done in pm, toggles your status.
   - If in chat, toggles that chat's status.

"""

REPORT_GROUP = 5

CURRENT_REPORT = {}


@spamcheck
@user_admin
def report_setting(update, context):
	chat = update.effective_chat  # type: Optional[Chat]
	msg = update.effective_message  # type: Optional[Message]
	args = context.args

	if chat.type == chat.PRIVATE:
		if len(args) >= 1:
			if args[0] in ("yes", "on"):
				sql.set_user_setting(chat.id, True)
				send_message(update.effective_message, "Turned on reporting! You'll be notified whenever anyone reports something.")

			elif args[0] in ("no", "off"):
				sql.set_user_setting(chat.id, False)
				send_message(update.effective_message, "Turned off reporting! You wont get any reports.")
		else:
			send_message(update.effective_message, "Your current report preference is: `{}`".format(sql.user_should_report(chat.id)),
						   parse_mode=ParseMode.MARKDOWN)

	else:
		if len(args) >= 1:
			if args[0] in ("yes", "on"):
				sql.set_chat_setting(chat.id, True)
				send_message(update.effective_message, "Turned on reporting! Admins who have turned on reports will be notified when /report or @admin are called.")

			elif args[0] in ("no", "off"):
				sql.set_chat_setting(chat.id, False)
				send_message(update.effective_message, "Turned off reporting! No admins will be notified on /report or @admin.")
		else:
			send_message(update.effective_message, "This chat's current setting is: `{}`".format(sql.chat_should_report(chat.id)),
						   parse_mode=ParseMode.MARKDOWN)


@spamcheck
@user_not_admin
@loggable
def report(update, context) -> str:
	message = update.effective_message  # type: Optional[Message]
	chat = update.effective_chat  # type: Optional[Chat]
	user = update.effective_user  # type: Optional[User]
	global CURRENT_REPORT

	if chat and message.reply_to_message and sql.chat_should_report(chat.id):
		reported_user = message.reply_to_message.from_user  # type: Optional[User]
		chat_name = chat.title or chat.first or chat.username

		a, b = user_protection_checker(context.bot, message.reply_to_message.from_user.id)
		if not a:
			return ""

		admin_list = chat.get_administrators()

		if chat.username and chat.type == Chat.SUPERGROUP:
			msg = f"<b>{html.escape(chat.title)}:</b>" \
				f"\n<b>User Reported:</b> {mention_html(reported_user.id, reported_user.full_name)} (<code>{reported_user.id}</code>)" \
				f"\n<b>Reported By:</b> {mention_html(user.id, user.full_name)} (<code>{user.id}</code>)"

		else:
			msg = f"{mention_html(user.id, user.full_name)} is calling for admins in \"{html.escape(chat_name)}\"!"

		if chat.username:
			chatlink = "https://t.me/{}/{}".format(chat.username, str(message.reply_to_message.message_id))
		else:
			chatlink = "https://t.me/c/{}/{}".format(str(chat.id)[4:], str(message.reply_to_message.message_id))
		keyboard = [
			  [InlineKeyboardButton("⚠️ Message reported", url=chatlink)],
			  [InlineKeyboardButton("⚠️ Kick", callback_data="rp_{}=1={}".format(chat.id, reported_user.id)),
			  InlineKeyboardButton("⛔️ Ban", callback_data="rp_{}=2={}".format(chat.id, reported_user.id))],
			  [InlineKeyboardButton("Delete message", callback_data="rp_{}=3={}".format(chat.id, message.reply_to_message.message_id))],
			  [InlineKeyboardButton("Close button", callback_data="rp_{}=4={}".format(chat.id, reported_user.id))]
			]
		reply_markup = InlineKeyboardMarkup(keyboard)

		should_forward = True
		context.bot.send_message(chat.id, "<i>⚠️ Message has been reported to all admins!</i>", parse_mode=ParseMode.HTML, reply_to_message_id=message.message_id)

		CURRENT_REPORT[str(chat.id)] = msg
		CURRENT_REPORT[str(chat.id)+"key"] = reply_markup
		CURRENT_REPORT[str(chat.id)+"user"] = {'name': reported_user.first_name, 'id': reported_user.id, 'rname': user.first_name, 'rid': user.id}
		for admin in admin_list:
			if admin.user.is_bot:  # can't message bots
				continue

			if sql.user_should_report(admin.user.id):
				try:
					#bot.send_message(admin.user.id, msg + link, parse_mode=ParseMode.HTML)
					#bot.send_message(admin.user.id, msg, parse_mode=ParseMode.HTML, reply_markup=reply_markup)

					try:
						if should_forward:
							message.reply_to_message.forward(admin.user.id)

							if len(message.text.split()) > 1:  # If user is giving a reason, send his message too
								message.forward(admin.user.id)
					except:
						pass
					context.bot.send_message(admin.user.id, msg, parse_mode=ParseMode.HTML, reply_markup=reply_markup)

				except Unauthorized:
					pass
				except BadRequest as excp:  # TODO: cleanup exceptions
					LOGGER.exception("Exception while reporting user")
		return msg

	return ""

@spamcheck
@user_not_admin
@loggable
def report_alt(update, context) -> str:
	message = update.effective_message  # type: Optional[Message]
	chat = update.effective_chat  # type: Optional[Chat]
	user = update.effective_user  # type: Optional[User]

	if chat and message.reply_to_message and sql.chat_should_report(chat.id):
		reported_user = message.reply_to_message.from_user  # type: Optional[User]
		reported_msg = message.reply_to_message
		reported_reason = message.text.split(' ', 1)[1]
		chat_name = chat.title or chat.first or chat.username
		admin_list = chat.get_administrators()

		msg = f"<b>{html.escape(chat.title)}:</b>" \
			f"\n<b>User Reported:</b> {mention_html(reported_user.id, reported_user.full_name)} (<code>{reported_user.id}</code>)" \
			f"\n<b>Reported By:</b> {mention_html(user.id, user.full_name)} (<code>{user.id}</code>)" \
			f"\n<b>Reason:</b> {reported_reason} ()" \
			f"\n\n{reported_msg.text}" \
			f"\n<b>Link:</b> <a href='{reported_msg.link}'>Go to message</a>"
		
		all_admins = []
		for admin in admin_list:
			if admin.user.is_bot:  # don't tag bot
				continue

			if sql.user_should_report(admin.user.id):
				all_admins.append("<a href='tg://user?id={}'>⁣</a>".format(admin.user.id))

		context.bot.send_message(chat.id, "⚠️ {} <b>has been reported to the admin!</b>{}".format(
					mention_html(reported_user.id, reported_user.first_name),
					"".join(all_admins)), parse_mode=ParseMode.HTML, reply_to_message_id=message.reply_to_message.message_id)
		return msg

	return ""


def button(context, update):
	query = update.callback_query
	splitter = query.data.replace("rp_", "").split("=")
	chat = update.effective_chat
	report_chat = splitter[0]
	report_method = splitter[1]
	report_target = splitter[2]
	msg = CURRENT_REPORT.get(str(report_chat))
	userinfo = CURRENT_REPORT.get(str(report_chat)+"user")
	key = CURRENT_REPORT.get(str(report_chat)+"key")
	if msg == None or userinfo == None or key == None:
		query.message.edit_text("Session timed out!")
		return

	if splitter[1] == "1":
		keyboard = [
			[InlineKeyboardButton("Yes", callback_data="ak_1+y|{}={}".format(report_chat, report_target)),
			InlineKeyboardButton("No", callback_data="ak_1+n|{}={}".format(report_chat, report_target))]
		]
		reply_markup = InlineKeyboardMarkup(keyboard)
		context.bot.edit_message_text(text=msg + "\n\nAre you sure you wish to kick {}?".format(userinfo.get('name')),
						  chat_id=query.message.chat_id,
						  message_id=query.message.message_id, parse_mode=ParseMode.HTML,
						  reply_markup=reply_markup)
	elif splitter[1] == "2":
		keyboard = [
			[InlineKeyboardButton("Yes", callback_data="ak_2+y|{}={}".format(report_chat, report_target)),
			InlineKeyboardButton("No", callback_data="ak_2+n|{}={}".format(report_chat, report_target))]
		]
		reply_markup = InlineKeyboardMarkup(keyboard)
		context.bot.edit_message_text(text=msg + "\n\nAre you sure you wish to ban {}?".format(userinfo.get('name')),
						  chat_id=query.message.chat_id,
						  message_id=query.message.message_id, parse_mode=ParseMode.HTML,
						  reply_markup=reply_markup)
	elif splitter[1] == "3":
		keyboard = [
			[InlineKeyboardButton("Yes", callback_data="ak_3+y|{}={}".format(report_chat, report_target)),
			InlineKeyboardButton("No", callback_data="ak_3+n|{}={}".format(report_chat, report_target))]
		]
		reply_markup = InlineKeyboardMarkup(keyboard)
		context.bot.edit_message_text(text=msg + "\n\nDelete message?",
						  chat_id=query.message.chat_id,
						  message_id=query.message.message_id, parse_mode=ParseMode.HTML,
						  reply_markup=reply_markup)
	elif splitter[1] == "4":
		try:
			context.bot.edit_message_text(text=msg + "\n\nButton closed!",
						  chat_id=query.message.chat_id,
						  message_id=query.message.message_id, parse_mode=ParseMode.HTML)
		except Exception as err:
			context.bot.edit_message_text(text=msg + "\n\nError: {}".format(err),
						  chat_id=query.message.chat_id,
						  message_id=query.message.message_id, parse_mode=ParseMode.HTML)

def buttonask(context, update):
	query = update.callback_query
	splitter = query.data.replace("ak_", "").split("+")
	isyes = splitter[1].split('|')[0]
	report_chat = splitter[1].split('|')[1].split('=')[0]
	report_target = splitter[1].split('|')[1].split('=')[1]
	chat = update.effective_chat
	msg = CURRENT_REPORT.get(str(report_chat))
	userinfo = CURRENT_REPORT.get(str(report_chat)+"user")
	key = CURRENT_REPORT.get(str(report_chat)+"key")

	if isyes == "y":
		a, b = user_protection_checker(context.bot, report_target)
		if not a:
			context.bot.edit_message_text(text=msg + b,
							  chat_id=query.message.chat_id,
							  message_id=query.message.message_id, parse_mode=ParseMode.HTML)
			return
		if splitter[0] == "1":
			try:
				context.bot.unbanChatMember(report_chat, report_target)
				context.bot.sendMessage(report_chat, text="{} has been kicked!\nBy: {}".format(\
					mention_markdown(userinfo['id'], userinfo['name']), mention_markdown(chat.id, chat.first_name)), \
					parse_mode=ParseMode.MARKDOWN)
				context.bot.edit_message_text(text=msg + "\n\n{} has been kicked!".format(mention_html(userinfo['id'], userinfo['name'])),
							  chat_id=query.message.chat_id,
							  message_id=query.message.message_id, parse_mode=ParseMode.HTML)
			except Exception as err:
				context.bot.edit_message_text(text=msg + "\n\nError: {}".format(err),
							  chat_id=query.message.chat_id,
							  message_id=query.message.message_id, parse_mode=ParseMode.HTML)
		elif splitter[0] == "2":
			try:
				context.bot.kickChatMember(report_chat, report_target)
				context.bot.sendMessage(report_chat, text="{} has been banned!\nBy: {}".format(\
					mention_markdown(userinfo['id'], userinfo['name']), mention_markdown(chat.id, chat.first_name)), \
					parse_mode=ParseMode.MARKDOWN)
				context.bot.edit_message_text(text=msg + "\n\n{} has been banned!".format(mention_html(userinfo['id'], userinfo['name'])),
							  chat_id=query.message.chat_id,
							  message_id=query.message.message_id, parse_mode=ParseMode.HTML)
			except Exception as err:
				context.bot.edit_message_text(text=msg + "\n\nError: {}".format(err),
							  chat_id=query.message.chat_id,
							  message_id=query.message.message_id, parse_mode=ParseMode.HTML)
		elif splitter[0] == "3":
			try:
				context.bot.deleteMessage(report_chat, report_target)
				context.bot.edit_message_text(text=msg + "\n\nMessage was deleted!",
							  chat_id=query.message.chat_id,
							  message_id=query.message.message_id, parse_mode=ParseMode.HTML)
			except Exception as err:
				context.bot.edit_message_text(text=msg + "\n\nError: {}".format(err),
							  chat_id=query.message.chat_id,
							  message_id=query.message.message_id, parse_mode=ParseMode.HTML)
	elif isyes == "n":
		context.bot.edit_message_text(text=msg,
							  chat_id=query.message.chat_id,
							  message_id=query.message.message_id, parse_mode=ParseMode.HTML,
							  reply_markup=key)


def user_protection_checker(bot, user_id):
	if not user_id:
		return False, "You don't seem to be referring to a user."

	if int(user_id) == OWNER_ID:
		return False, "\n\nError: This one is my owner!"

	if int(user_id) in SUDO_USERS:
		return False, "\n\nError: User is under my protection"

	# if int(user_id) in SUPPORT_USERS:
	# 	return False, "Error: User is under protection"

	if int(user_id) == bot.id:
		return False, "\n\nError: This is myself!"

	return True, ""


def __migrate__(old_chat_id, new_chat_id):
	sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(chat_id, user_id):
	return "This chat is setup to send user reports to admins, via /report and @admin: `{}`".format(
		sql.chat_should_report(chat_id))


def __user_settings__(user_id):
	return "You receive reports from chats you're admin in: `{}`.\nToggle this with /reports in PM.".format(
		sql.user_should_report(user_id))


dispatcher.add_handler(CommandHandler("report", report_alt, filters=Filters.chat_type.groups), REPORT_GROUP)
dispatcher.add_handler(MessageHandler(Filters.regex("(?i)@admin(s)?"), report_alt), REPORT_GROUP)
dispatcher.add_handler(CommandHandler("reports", report_setting, pass_args=True))
dispatcher.add_handler(CallbackQueryHandler(button, pattern=r"rp_"))
dispatcher.add_handler(CallbackQueryHandler(buttonask, pattern=r"ak_"))
