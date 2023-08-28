import html
from io import BytesIO
from typing import Optional, List
import random
import uuid
import re
import json
import time
import csv
import os
from time import sleep

from future.utils import string_types
from telegram.error import BadRequest, TelegramError, Unauthorized
from telegram import ParseMode, Update, Bot, Chat, User, MessageEntity, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import run_async, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
from telegram.utils.helpers import escape_markdown, mention_html, mention_markdown

from TPBOT import dispatcher, OWNER_ID, SUDO_USERS, WHITELIST_USERS, TEMPORARY_DATA, LOGGER, spamcheck
from TPBOT.modules.helper_funcs.handlers import CMD_STARTERS
from TPBOT.modules.helper_funcs.misc import is_module_loaded, send_to_list
from TPBOT.modules.helper_funcs.chat_status import is_user_admin
from TPBOT.modules.helper_funcs.extraction import extract_user, extract_unt_fedban, extract_user_fban
from TPBOT.modules.helper_funcs.string_handling import markdown_parser
from TPBOT.modules.disable import DisableAbleCommandHandler

import TPBOT.modules.sql.feds_sql as sql

from TPBOT.modules.connection import connected
from TPBOT.modules.helper_funcs.alternate import send_message

__mod_name__ = "Federations"

__help__ = """
Ah, group management. It's all fun and games, until you start getting spammers in, and you need to ban them. Then you need to start banning more, and more, and it gets painful.
But then you have multiple groups, and you don't want these spammers in any of your groups - how can you deal? Do you have to ban them manually, in all your groups?

No more! With federations, you can make a ban in one chat overlap to all your other chats.
You can even appoint federation admins, so that your trustworthiest admins can ban across all the chats that you want to protect.

*Commands:*
 - /fedstat: List all the federations you've been banned from.
 - /fedstat <user ID>: Lists all the federations the specified user has been banned from (also works with username, mention, and replies).
 - /fedstat <user ID> <Fed ID>: Gives information on the specified user's ban reason in that federation. If no user is specified, checks the sender.
 - /joinfed <FedID>: Joins the current chat to the federation. Each chat can only be in one federation. Only chat owners can do this.
 - /leavefed <FedID>: Leaves the current federation. Only chat owners can do this.

*Only federation admin:*
 - /newfed <fedname>: Creates a new federation with the given name. Users are only allowed to own one federation. Using this method when you already have a fed will simply change the federation name. (max 64 characters)
 - /delfed: Deletes your federation, and any information relating to it. Will not unban any banned users.
 - /fedinfo <FedID>: Information about the specified federation.
 - /fbroadcast <text>: Broadcast text to all groups that join the federation.
 - /fban <user>: Bans a user from the current chat's federation.
 - /unfban <user>: Unbans a user the current chat's federation.
 - /setfrules: Set federation rules.
 - /frules: See federation regulations.
 - /chatfed: See current federation.
 - /fedadmins: Show federated admin.
 - /fednotif <on/off>: Set federation notified in PM when user is fban/unfban.
 - /fedchats: Get all chat connected in federation.
 - /myfeds: Get all your feds, only for feds owner

*Only federation owner:*
 - /fpromote <user>: Promotes the user to fed admin in your fed.
 - /fdemote <user>: Demotes the user from fed admin to normal user, in your fed.
 - /fbanlist: Get the list of currently banned users. If you want different modes, use /fbanlist <csv/json>
 - /importfbans: Reply federated backup message file to import banned list to current federation.
 - /subfed <fedid>: to subscribe federation, can subscribe multiple federations.
 - /unsubfed <fedid>: unsubscribe that federation.
 - /fedsubs: check all subscribed in current federation.

"""


# Hello bot owner, I spended for feds many hours of my life, Please don't remove this if you still respect MrYacha and peaktogoo and AyraHikari too
# Federation by MrYacha 2018-2019
# Federation rework by Mizukito Akito 2019
# Federation update v2 by Ayra Hikari 2019
# 
# Time spended on feds = 10h by #MrYacha
# Time spended on reworking on the whole feds = 22+ hours by @peaktogoo
# Time spended on updating version to v2 = 26+ hours by @AyraHikari
# 
# Total spended for making this features is 68+ hours

# LOGGER.info("Original federation module by MrYacha, reworked by Mizukito Akito (@peaktogoo) on Telegram.")

FBAN_ERRORS = {
	"User is an administrator of the chat",
	"Chat not found",
	"Not enough rights to restrict/unrestrict chat member",
	"User_not_participant",
	"Peer_id_invalid",
	"Group chat was deactivated",
	"Need to be inviter of a user to kick it from a basic group",
	"Chat_admin_required",
	"Only the creator of a basic group can kick group administrators",
	"Channel_private",
	"Not in the chat",
	"Have no rights to send a message"
}

UNFBAN_ERRORS = {
	"User is an administrator of the chat",
	"Chat not found",
	"Not enough rights to restrict/unrestrict chat member",
	"User_not_participant",
	"Method is available for supergroup and channel chats only",
	"Not in the chat",
	"Channel_private",
	"Chat_admin_required",
	"Have no rights to send a message"
}

@spamcheck
def new_fed(update, context):
	chat = update.effective_chat  # type: Optional[Chat]
	user = update.effective_user  # type: Optional[User]
	message = update.effective_message
	if chat.type != "private":
		send_message(update.effective_message, "Create your federation in my PM, not in a group.")
		return
	if len(message.text) == 1:
		send_message(update.effective_message, "Please write the federation name!")
		return
	fednam = message.text.split(None, 1)[1]
	if not fednam == '':
		fed_id = str(uuid.uuid4())
		fed_name = fednam
		LOGGER.info(fed_id)

		# Currently only for creator
		# if fednam == "Team Nusantara Disciplinary Circle":
		# 	fed_id = "TeamNusantaraDevs"
		# elif fednam == "TPBOT Official Support":
		# 	fed_id = "TPBOTSupport"

		x = sql.new_fed(user.id, fed_name, fed_id)
		if not x:
			send_message(update.effective_message, "Can't create federation! Please contact my manufacturer if the problem persists.")
			return

		send_message(update.effective_message, "*You have successfully created a new federation!*"\
											"\nName: `{}`"\
											"\nID: `{}`"
											"\n\nUse the commands below to join a federation:"
											"\n`/joinfed {}`".format(fed_name, fed_id, fed_id), parse_mode=ParseMode.MARKDOWN)
		try:
			context.bot.send_message(TEMPORARY_DATA,
				"Federation <b>{}</b> has been created with ID: <pre>{}</pre>".format(fed_name, fed_id), parse_mode=ParseMode.HTML)
		except:
			LOGGER.warning("Cannot send a message to TEMPORARY_DATA")
	else:
		send_message(update.effective_message, "Please write the federation name!")

@spamcheck
def del_fed(update, context):
	chat = update.effective_chat  # type: Optional[Chat]
	user = update.effective_user  # type: Optional[User]
	args = context.args
	if chat.type != "private":
		send_message(update.effective_message, "Remove your federation in My PM, not in a group.")
		return
	if args:
		is_fed_id = args[0]
		getinfo = sql.get_fed_info(is_fed_id)
		if getinfo == False:
			send_message(update.effective_message, "This federation was not found!")
			return
		if int(getinfo['owner']) == int(user.id) or int(user.id) == OWNER_ID:
			fed_id = is_fed_id
		else:
			send_message(update.effective_message, "Only federation owners can do this!")
			return
	else:
		send_message(update.effective_message, "What should I delete?")
		return

	if is_user_fed_owner(fed_id, user.id) == False:
		send_message(update.effective_message, "Only federation owners can do this!")
		return

	send_message(update.effective_message, "Are you sure you want to remove your federation? This action cannot be undone, you will lose your entire prohibition list, and '{}' permanently lost.".format(getinfo['fname']),
			reply_markup=InlineKeyboardMarkup(
						[[InlineKeyboardButton(text="⚠️ Remove Federation ⚠️", callback_data="rmfed_{}".format(fed_id))],
						[InlineKeyboardButton(text="Cancel", callback_data="rmfed_cancel")]]))

@spamcheck
def fed_chat(update, context):
	chat = update.effective_chat  # type: Optional[Chat]
	user = update.effective_user  # type: Optional[User]
	fed_id = sql.get_fed_id(chat.id)

	user_id = update.effective_message.from_user.id
	if not is_user_admin(update.effective_chat, user_id):
		send_message(update.effective_message, "You must be an admin to run this command")
		return

	if not fed_id:
		send_message(update.effective_message, "This group is not in any federation!")
		return

	user = update.effective_user  # type: Optional[Chat]
	chat = update.effective_chat  # type: Optional[Chat]
	info = sql.get_fed_info(fed_id)

	text = "This chat is part of the following federations:"
	text += "\n{} (ID: <code>{}</code>)".format(info['fname'], fed_id)

	send_message(update.effective_message, text, parse_mode=ParseMode.HTML)

@spamcheck
def join_fed(update, context):
	chat = update.effective_chat  # type: Optional[Chat]
	user = update.effective_user  # type: Optional[User]

	if chat.type == 'private':
		send_message(update.effective_message, "This command is specific to the group, not to the PM!")
		return

	message = update.effective_message
	administrators = chat.get_administrators()
	fed_id = sql.get_fed_id(chat.id)
	args = context.args

	if user.id in SUDO_USERS:
		pass
	else:
		for admin in administrators:
			status = admin.status
			if status == "creator":
				if str(admin.user.id) == str(user.id):
					pass
				else:
					send_message(update.effective_message, "Only group creators can do this!")
					return
	if fed_id:
		send_message(update.effective_message, "You can't join two federations in one chat")
		return

	if len(args) >= 1:
		getfed = sql.search_fed_by_id(args[0])
		if getfed == False:
			send_message(update.effective_message, "Please enter a valid federation id.")
			return

		x = sql.chat_join_fed(args[0], chat.title, chat.id)
		if not x:
			send_message(update.effective_message, "Failed to join federation! Please contact my manufacturer if this problem persists.")
			return

		get_fedlog = sql.get_fed_log(args[0])
		if get_fedlog:
			if eval(get_fedlog):
				context.bot.send_message(get_fedlog, "Chat *{}* has joined the federation *{}*".format(chat.title, getfed['fname']), parse_mode="markdown")

		send_message(update.effective_message, "This chat has joined the federation {}!".format(getfed['fname']))

@spamcheck
def leave_fed(update, context):
	chat = update.effective_chat  # type: Optional[Chat]
	user = update.effective_user  # type: Optional[User]
	args = context.args

	if chat.type == 'private':
		send_message(update.effective_message, "This command is specific to the group, not to the PM!")
		return

	fed_id = sql.get_fed_id(chat.id)
	fed_info = sql.get_fed_info(fed_id)

	# administrators = chat.get_administrators().status
	getuser = context.bot.get_chat_member(chat.id, user.id).status
	if getuser in 'creator' or user.id in SUDO_USERS:
		if sql.chat_leave_fed(chat.id) == True:
			get_fedlog = sql.get_fed_log(fed_id)
			if get_fedlog:
				if eval(get_fedlog):
					context.bot.send_message(get_fedlog, "Chat *{}* has exited federation *{}*".format(chat.title, fed_info['fname']), parse_mode="markdown")
			send_message(update.effective_message, "This chat is not in federation {}!".format(fed_info['fname']))
		else:
			send_message(update.effective_message, "Why would you leave a federation you haven't joined?!")
	else:
		send_message(update.effective_message, "Only group creators can do this!")

@spamcheck
def user_join_fed(update, context):
	chat = update.effective_chat
	user = update.effective_user
	msg = update.effective_message
	args = context.args

	if chat.type == 'private':
		send_message(update.effective_message, "This command is specific to the group, not to the PM!")
		return

	fed_id = sql.get_fed_id(chat.id)

	if is_user_fed_owner(fed_id, user.id):
		user_id = extract_user(msg, args)
		if user_id and user_id != "error":
			user = context.bot.get_chat(user_id)
		elif not msg.reply_to_message and not args:
			user = msg.from_user
		elif not msg.reply_to_message and (not args or (
			len(args) >= 1 and not args[0].startswith("@") and not args[0].isdigit() and not msg.parse_entities(
			[MessageEntity.TEXT_MENTION]))):
			send_message(update.effective_message, "I can't extract users from this.")
			return
		else:
			LOGGER.warning('error')
		getuser = sql.search_user_in_fed(fed_id, user_id)
		fed_id = sql.get_fed_id(chat.id)
		info = sql.get_fed_info(fed_id)
		get_owner = eval(info['fusers'])['owner']
		get_owner = context.bot.get_chat(get_owner).id
		if user_id == get_owner:
			send_message(update.effective_message, "Cannot promote a user who is already a federation owner.")
			return
		if getuser:
			send_message(update.effective_message, "Cannot promote a user who is already a federation admin.")
			return
		if user_id == context.bot.id:
			send_message(update.effective_message, "Already federation admin!")
			return
		res = sql.user_join_fed(fed_id, user_id)
		if res:
			send_message(update.effective_message, "💖 Successfully promoted!")
		else:
			send_message(update.effective_message, "Failed to promote!")
	else:
		send_message(update.effective_message, "Only federation owners can do this!")


@spamcheck
def user_demote_fed(update, context):
	chat = update.effective_chat  # type: Optional[Chat]
	user = update.effective_user  # type: Optional[User]
	args = context.args

	if chat.type == 'private':
		send_message(update.effective_message, "This command is specific to the group, not to the PM!")
		return

	fed_id = sql.get_fed_id(chat.id)

	if is_user_fed_owner(fed_id, user.id):
		msg = update.effective_message
		user_id = extract_user(msg, args)
		if user_id and user_id != "error":
			user = context.bot.get_chat(user_id)

		elif not msg.reply_to_message and not args:
			user = msg.from_user

		elif not msg.reply_to_message and (not args or (
			len(args) >= 1 and not args[0].startswith("@") and not args[0].isdigit() and not msg.parse_entities(
			[MessageEntity.TEXT_MENTION]))):
			send_message(update.effective_message, "I can't extract users from this.")
			return
		else:
			LOGGER.warning('error')

		if user_id == context.bot.id:
			send_message(update.effective_message, "What are you trying to do? Demote me from your federation?")
			return

		if sql.search_user_in_fed(fed_id, user_id) == False:
			send_message(update.effective_message, "I can't demote a user who isn't a federated admin! If you want to make her cry, promote her first!")
			return

		res = sql.user_demote_fed(fed_id, user_id)
		if res == True:
			send_message(update.effective_message, "💔 Demoted from your federation!")
		else:
			send_message(update.effective_message, "I can't demote, I'm helpless!")
	else:
		send_message(update.effective_message, "Only federation owners can do this!")
		return

@spamcheck
def fed_info(update, context):
	chat = update.effective_chat  # type: Optional[Chat]
	user = update.effective_user  # type: Optional[User]
	args = context.args
	if args:
		fed_id = args[0]
		info = sql.get_fed_info(fed_id)
	else:
		fed_id = sql.get_fed_id(chat.id)
		if not fed_id:
			send_message(update.effective_message, "This group is not in any federation!")
			return
		info = sql.get_fed_info(fed_id)

	owner = context.bot.get_chat(info['owner'])
	try:
		owner_name = owner.first_name + " " + owner.last_name
	except:
		owner_name = owner.first_name
	FEDADMIN = sql.all_fed_users(fed_id)
	FEDADMIN.append(int(owner.id))
	TotalAdminFed = len(FEDADMIN)

	user = update.effective_user  # type: Optional[Chat]
	chat = update.effective_chat  # type: Optional[Chat]
	info = sql.get_fed_info(fed_id)

	text = "<b>ℹ️ Federation Info:</b>"
	text += "\nFedID: <code>{}</code>".format(fed_id)
	text += "\nName: {}".format(info['fname'])
	text += "\nCreator: {}".format(mention_html(owner.id, owner_name))
	text += "\nAdmins: <code>{}</code>".format(TotalAdminFed)
	getfban = sql.get_all_fban_users(fed_id)
	text += "\nTotal banned: <code>{}</code>".format(len(getfban))
	getfchat = sql.all_fed_chats(fed_id)
	text += "\nTotal connected groups: <code>{}</code>".format(len(getfchat))

	send_message(update.effective_message, text, parse_mode=ParseMode.HTML)

@spamcheck
def fed_admin(update, context):
	chat = update.effective_chat  # type: Optional[Chat]
	user = update.effective_user  # type: Optional[User]
	args = context.args

	if chat.type == 'private':
		send_message(update.effective_message, "This command is specific to the group, not to the PM!")
		return

	fed_id = sql.get_fed_id(chat.id)

	if not fed_id:
		send_message(update.effective_message, "This group is not in any federation!")
		return

	if is_user_fed_admin(fed_id, user.id) == False:
		send_message(update.effective_message, "Only federation admins can do this!")
		return

	user = update.effective_user  # type: Optional[Chat]
	chat = update.effective_chat  # type: Optional[Chat]
	info = sql.get_fed_info(fed_id)

	text = "<b>Federation admin {}:</b>\n\n".format(info['fname'])
	text += "👑 Owner:\n"
	owner = context.bot.get_chat(info['owner'])
	try:
		owner_name = owner.first_name + " " + owner.last_name
	except:
		owner_name = owner.first_name
	text += " • {}\n".format(mention_html(owner.id, owner_name))

	members = sql.all_fed_members(fed_id)
	if len(members) == 0:
		text += "\n🔱 There are no admins in this federation"
	else:
		text += "\n🔱 Admins:\n"
		for x in members:
			user = context.bot.get_chat(x) 
			text += " • {}\n".format(mention_html(user.id, user.first_name))

	send_message(update.effective_message, text, parse_mode=ParseMode.HTML)


@spamcheck
def fed_ban(update, context):
	chat = update.effective_chat  # type: Optional[Chat]
	user = update.effective_user  # type: Optional[User]
	args = context.args

	if chat.type == 'private':
		send_message(update.effective_message, "This command is specific to the group, not to the PM!")
		return

	fed_id = sql.get_fed_id(chat.id)

	if not fed_id:
		send_message(update.effective_message, "This group is not in any federation!")
		return

	info = sql.get_fed_info(fed_id)
	getfednotif = sql.user_feds_report(info['owner'])

	if is_user_fed_admin(fed_id, user.id) == False:
		send_message(update.effective_message, "Only federation admins can do this!")
		return

	message = update.effective_message

	user_id, reason = extract_unt_fedban(message, args)

	fban, fbanreason, fbantime = sql.get_fban_user(fed_id, user_id)

	if not user_id:
		send_message(update.effective_message, "You don't seem to be referring to users.")
		return

	if user_id == context.bot.id:
		send_message(update.effective_message, "What's funnier than banning a group creator? Fban myself.")
		return

	if is_user_fed_owner(fed_id, user_id) == True:
		send_message(update.effective_message, "Cannot fban the federation owner!")
		return

	if is_user_fed_admin(fed_id, user_id) == True:
		send_message(update.effective_message, "Cannot fban a federation admin.")
		return

	if user_id == OWNER_ID:
		send_message(update.effective_message, "I don't want to block my master, that's a very stupid idea!")
		return

	if int(user_id) in SUDO_USERS:
		send_message(update.effective_message, "Cannot fban sudo users!")
		return

	if int(user_id) in WHITELIST_USERS:
		send_message(update.effective_message, "User is on the white list, so can't be on fban!")
		return

	try:
		user_chat = context.bot.get_chat(user_id)
		isvalid = True
		fban_user_id = user_chat.id
		fban_user_name = user_chat.first_name
		fban_user_lname = user_chat.last_name
		fban_user_uname = user_chat.username
	except BadRequest as excp:
		if not str(user_id).isdigit():
			send_message(update.effective_message, excp.message)
			return
		elif not len(str(user_id)) == 9:
			send_message(update.effective_message, "That's not a user!!")
			return
		isvalid = False
		fban_user_id = int(user_id)
		fban_user_name = "user({})".format(user_id)
		fban_user_lname = None
		fban_user_uname = None


	if isvalid and user_chat.type != 'private':
		send_message(update.effective_message, "That's not a user!!")
		return

	if isvalid:
		user_target = mention_html(fban_user_id, fban_user_name)
	else:
		user_target = fban_user_name

	if fban:
		fed_name = info['fname']
		starting = "Fban reason changed for {} in Federation <b>{}</b>.".format(user_target, fed_name)
		send_message(update.effective_message, starting, parse_mode=ParseMode.HTML)

		if reason == "":
			reason = "No excuses."

		temp = sql.un_fban_user(fed_id, fban_user_id)
		if not temp:
			send_message(update.effective_message, "Failed to update fedban reason!")
			return
		x = sql.fban_user(fed_id, fban_user_id, fban_user_name, fban_user_lname, fban_user_uname, reason, int(time.time()))
		if not x:
			send_message(update.effective_message, "Failed to fban user! If this issue continues to occur, contact my author.")
			return

		fed_chats = sql.all_fed_chats(fed_id)
		# Will send to current chat
		context.bot.send_message(chat.id, "<b>Fedban reason has been Updated</b>" \
								  "\n<b>Federation:</b> {}" \
								  "\n<b>Federation Admin:</b> {}" \
								  "\n<b>User:</b> {}" \
								  "\n<b>User ID:</b> <code>{}</code>" \
								  "\n<b>Reason:</b> {}".format(fed_name, mention_html(user.id, user.first_name), user_target, fban_user_id, reason), parse_mode="HTML")
		# Send message to owner if fednotif is enabled
		if getfednotif:
			context.bot.send_message(info['owner'], "<b>Fedban reason has been Updated</b>" \
											"\n<b>Federation:</b> {}" \
											"\n<b>Federation Admin:</b> {}" \
											"\n<b>User:</b> {}" \
											"\n<b>User ID:</b> <code>{}</code>" \
											"\n<b>Reason:</b> {}".format(fed_name, mention_html(user.id, user.first_name), user_target, fban_user_id, reason), parse_mode="HTML")
		# If fedlog is set, then send message, except fedlog is current chat
		get_fedlog = sql.get_fed_log(fed_id)
		if get_fedlog:
			if int(get_fedlog) != int(chat.id):
				context.bot.send_message(get_fedlog, "<b>Fedban reason has been Updated</b>" \
											"\n<b>Federation:</b> {}" \
											"\n<b>Federation Admin:</b> {}" \
											"\n<b>User:</b> {}" \
											"\n<b>User ID:</b> <code>{}</code>" \
											"\n<b>Reason:</b> {}".format(fed_name, mention_html(user.id, user.first_name), user_target, fban_user_id, reason), parse_mode="HTML")
		for fedschat in fed_chats:
			try:
				# Do not spamming all fed chats
				"""
				context.bot.send_message(fedschat, "<b>Fedban reason has been Updated</b>" \
							 "\n<b>Federation:</b> {}" \
							 "\n<b>Federation Admin:</b> {}" \
							 "\n<b>User:</b> {}" \
							 "\n<b>User ID:</b> <code>{}</code>" \
							 "\n<b>Reason:</b> {}".format(fed_name, mention_html(user.id, user.first_name), user_target, fban_user_id, reason), parse_mode="HTML")
				"""
				context.bot.ban_chat_member(fedschat, fban_user_id)
			except BadRequest as excp:
				if excp.message in FBAN_ERRORS:
					try:
						dispatcher.bot.getChat(fedschat)
					except Unauthorized:
						sql.chat_leave_fed(fedschat)
						LOGGER.info("Chat {} has left fed {} because bot is kicked".format(fedschat, info['fname']))
						continue
				elif excp.message == "User_id_invalid":
					break
				else:
					LOGGER.warning("Can't fban in {} because: {}".format(fedschat, excp.message))
			except TelegramError:
				pass

		# Also do not spamming all fed admins
		"""
		send_to_list(bot, FEDADMIN,
				 "<b>Fedban reason has been Updated</b>" \
				 "\n<b>Federation:</b> {}" \
				 "\n<b>Federation Admin:</b> {}" \
				 "\n<b>User:</b> {}" \
				 "\n<b>User ID:</b> <code>{}</code>" \
				 "\n<b>Reason:</b> {}".format(fed_name, mention_html(user.id, user.first_name), user_target, fban_user_id, reason), 
				html=True)
		"""

		# Fban for fed subscriber
		subscriber = list(sql.get_subscriber(fed_id))
		if len(subscriber) != 0:
			for fedsid in subscriber:
				all_fedschat = sql.all_fed_chats(fedsid)
				for fedschat in all_fedschat:
					try:
						context.bot.ban_chat_member(fedschat, fban_user_id)
					except BadRequest as excp:
						if excp.message in FBAN_ERRORS:
							try:
								dispatcher.bot.getChat(fedschat)
							except Unauthorized:
								targetfed_id = sql.get_fed_id(fedschat)
								sql.unsubs_fed(fed_id, targetfed_id)
								LOGGER.info("Chat {} has unsub fed {} because bot is kicked".format(fedschat, info['fname']))
								continue
						elif excp.message == "User_id_invalid":
							break
						else:
							LOGGER.warning("Can't fban in {} because: {}".format(fedschat, excp.message))
					except TelegramError:
						pass
		send_message(update.effective_message, "Fedban Reason has been updated.")
		return

	fed_name = info['fname']

	starting = "Start a federation ban for {} at Fed <b>{}</b>.".format(user_target, fed_name)
	send_message(update.effective_message, starting, parse_mode=ParseMode.HTML)

	if reason == "":
		reason = "No reason."

	x = sql.fban_user(fed_id, fban_user_id, fban_user_name, fban_user_lname, fban_user_uname, reason, int(time.time()))
	if not x:
		send_message(update.effective_message, "Failed to ban user! If this issue continues to occur, contact my author.")
		return

	fed_chats = sql.all_fed_chats(fed_id)
	# Will send to current chat
	context.bot.send_message(chat.id, "<b>New FedBan</b>" \
							  "\n<b>Federation:</b> {}" \
							  "\n<b>Federation Admin:</b> {}" \
							  "\n<b>User:</b> {}" \
							  "\n<b>User ID:</b> <code>{}</code>" \
							  "\n<b>Reason:</b> {}".format(fed_name, mention_html(user.id, user.first_name), user_target, fban_user_id, reason), parse_mode="HTML")
	# Send message to owner if fednotif is enabled
	if getfednotif:
		context.bot.send_message(info['owner'], "<b>New FedBan</b>" \
										"\n<b>Federation:</b> {}" \
										"\n<b>Federation Admin:</b> {}" \
										"\n<b>User:</b> {}" \
										"\n<b>User ID:</b> <code>{}</code>" \
										"\n<b>Reason:</b> {}".format(fed_name, mention_html(user.id, user.first_name), user_target, fban_user_id, reason), parse_mode="HTML")
	# If fedlog is set, then send message, except fedlog is current chat
	get_fedlog = sql.get_fed_log(fed_id)
	if get_fedlog:
		if int(get_fedlog) != int(chat.id):
			context.bot.send_message(get_fedlog, "<b>New FedBan</b>" \
										"\n<b>Federation:</b> {}" \
										"\n<b>Federation Admin:</b> {}" \
										"\n<b>User:</b> {}" \
										"\n<b>User ID:</b> <code>{}</code>" \
										"\n<b>Reason:</b> {}".format(fed_name, mention_html(user.id, user.first_name), user_target, fban_user_id, reason), parse_mode="HTML")
	for fedschat in fed_chats:
		try:
			# Do not spamming all fed chats
			"""
			context.bot.send_message(fedschat, "<b>New FedBan</b>" \
						 "\n<b>Federation:</b> {}" \
						 "\n<b>Federation Admin:</b> {}" \
						 "\n<b>User:</b> {}" \
						 "\n<b>User ID:</b> <code>{}</code>" \
						 "\n<b>Reason:</b> {}".format(fed_name, mention_html(user.id, user.first_name), user_target, fban_user_id, reason), parse_mode="HTML")
			"""
			context.bot.ban_chat_member(fedschat, fban_user_id)
		except BadRequest as excp:
			if excp.message in FBAN_ERRORS:
				pass
			elif excp.message == "User_id_invalid":
				break
			else:
				LOGGER.warning("Can't fban in {} because: {}".format(fedschat, excp.message))
		except TelegramError:
			pass

	# Also do not spamming all fed admins
	"""
	send_to_list(bot, FEDADMIN,
			 "<b>New FedBan</b>" \
			 "\n<b>Federation:</b> {}" \
			 "\n<b>Federation Admin:</b> {}" \
			 "\n<b>User:</b> {}" \
			 "\n<b>User ID:</b> <code>{}</code>" \
			 "\n<b>Reason:</b> {}".format(fed_name, mention_html(user.id, user.first_name), user_target, fban_user_id, reason), 
			html=True)
	"""

	# Fban for fed subscriber
	subscriber = list(sql.get_subscriber(fed_id))
	if len(subscriber) != 0:
		for fedsid in subscriber:
			all_fedschat = sql.all_fed_chats(fedsid)
			for fedschat in all_fedschat:
				try:
					context.bot.ban_chat_member(fedschat, fban_user_id)
				except BadRequest as excp:
					if excp.message in FBAN_ERRORS:
						try:
							dispatcher.bot.getChat(fedschat)
						except Unauthorized:
							targetfed_id = sql.get_fed_id(fedschat)
							sql.unsubs_fed(fed_id, targetfed_id)
							LOGGER.info("Chat {} has unsub fed {} because bot is kicked".format(fedschat, info['fname']))
							continue
					elif excp.message == "User_id_invalid":
						break
					else:
						LOGGER.warning("Can't fban in {} because: {}".format(fedschat, excp.message))
				except TelegramError:
					pass
	send_message(update.effective_message, "User has been fbanned.")


@spamcheck
def unfban(update, context):
	chat = update.effective_chat  # type: Optional[Chat]
	user = update.effective_user  # type: Optional[User]
	message = update.effective_message
	args = context.args

	if chat.type == 'private':
		send_message(update.effective_message, "This command is specific to the group, not to the PM!")
		return

	fed_id = sql.get_fed_id(chat.id)

	if not fed_id:
		send_message(update.effective_message, "This group is not in any federation!")
		return

	info = sql.get_fed_info(fed_id)
	getfednotif = sql.user_feds_report(info['owner'])

	if is_user_fed_admin(fed_id, user.id) == False:
		send_message(update.effective_message, "Only federation admins can do this!")
		return

	user_id = extract_user_fban(message, args)
	if not user_id:
		send_message(update.effective_message, "You don't seem to be referring to users.")
		return

	try:
		user_chat = context.bot.get_chat(user_id)
		isvalid = True
		fban_user_id = user_chat.id
		fban_user_name = user_chat.first_name
		fban_user_lname = user_chat.last_name
		fban_user_uname = user_chat.username
	except BadRequest as excp:
		if not str(user_id).isdigit():
			send_message(update.effective_message, excp.message)
			return
		elif not len(str(user_id)) == 9:
			send_message(update.effective_message, "That's not a user!!")
			return
		isvalid = False
		fban_user_id = int(user_id)
		fban_user_name = "user({})".format(user_id)
		fban_user_lname = None
		fban_user_uname = None

	if isvalid and user_chat.type != 'private':
		send_message(update.effective_message, "That's not a user!!")
		return

	if isvalid:
		user_target = mention_html(fban_user_id, fban_user_name)
	else:
		user_target = fban_user_name

	fban, fbanreason, fbantime = sql.get_fban_user(fed_id, fban_user_id)
	if fban == False:
		send_message(update.effective_message, "This user is not currently fbanned!")
		return

	banner = update.effective_user  # type: Optional[User]

	send_message(update.effective_message, "I'll give {} a second chance in this federation.".format(user_target), parse_mode="HTML")

	chat_list = sql.all_fed_chats(fed_id)
	# Will send to current chat
	context.bot.send_message(chat.id, "<b>Un-FedBan</b>" \
						 "\n<b>Federation:</b> {}" \
						 "\n<b>Federation Admin:</b> {}" \
						 "\n<b>User:</b> {}" \
						 "\n<b>User ID:</b> <code>{}</code>".format(info['fname'], mention_html(user.id, user.first_name), user_target, fban_user_id), parse_mode="HTML")
	# Send message to owner if fednotif is enabled
	if getfednotif:
		context.bot.send_message(info['owner'], "<b>Un-FedBan</b>" \
						 "\n<b>Federation:</b> {}" \
						 "\n<b>Federation Admin:</b> {}" \
						 "\n<b>User:</b> {}" \
						 "\n<b>User ID:</b> <code>{}</code>".format(info['fname'], mention_html(user.id, user.first_name), user_target, fban_user_id), parse_mode="HTML")
	# If fedlog is set, then send message, except fedlog is current chat
	get_fedlog = sql.get_fed_log(fed_id)
	if get_fedlog:
		if int(get_fedlog) != int(chat.id):
			context.bot.send_message(get_fedlog, "<b>Un-FedBan</b>" \
						 "\n<b>Federation:</b> {}" \
						 "\n<b>Federation Admin:</b> {}" \
						 "\n<b>User:</b> {}" \
						 "\n<b>User ID:</b> <code>{}</code>".format(info['fname'], mention_html(user.id, user.first_name), user_target, fban_user_id), parse_mode="HTML")
	for fedchats in chat_list:
		try:
			member = context.bot.get_chat_member(fedchats, user_id)
			if member.status == 'kicked':
				context.bot.unban_chat_member(fedchats, user_id)
				# Do not spamming all fed chats
				"""
				context.bot.send_message(fedchats, "<b>Un-FedBan</b>" \
						 "\n<b>Federation:</b> {}" \
						 "\n<b>Federation Admin:</b> {}" \
						 "\n<b>User:</b> {}" \
						 "\n<b>User ID:</b> <code>{}</code>".format(info['fname'], mention_html(user.id, user.first_name), user_target, fban_user_id), parse_mode="HTML")
				"""
		except BadRequest as excp:
			if excp.message in UNFBAN_ERRORS:
				pass
			elif excp.message == "User_id_invalid":
				break
			else:
				LOGGER.warning("Can't fban in {} because: {}".format(fedchats, excp.message))
		except TelegramError:
			pass

	try:
		x = sql.un_fban_user(fed_id, user_id)
		if not x:
			send_message(update.effective_message, "Failed fban, This user may have been un-fedbanned!")
			return
	except:
		pass

	# UnFban for fed subscriber
	subscriber = list(sql.get_subscriber(fed_id))
	if len(subscriber) != 0:
		for fedsid in subscriber:
			all_fedschat = sql.all_fed_chats(fedsid)
			for fedschat in all_fedschat:
				try:
					context.bot.unban_chat_member(fedchats, user_id)
				except BadRequest as excp:
					if excp.message in FBAN_ERRORS:
						try:
							dispatcher.bot.getChat(fedschat)
						except Unauthorized:
							targetfed_id = sql.get_fed_id(fedschat)
							sql.unsubs_fed(fed_id, targetfed_id)
							LOGGER.info("Chat {} has unsub fed {} because bot is kicked".format(fedschat, info['fname']))
							continue
					elif excp.message == "User_id_invalid":
						break
					else:
						LOGGER.warning("Can't fban in {} because: {}".format(fedschat, excp.message))
				except TelegramError:
					pass

	send_message(update.effective_message, "This user has been un-fbanned.")
	# Also do not spamming all fed admins
	"""
	FEDADMIN = sql.all_fed_users(fed_id)
	for x in FEDADMIN:
		getreport = sql.user_feds_report(x)
		if getreport == False:
			FEDADMIN.remove(x)
	send_to_list(bot, FEDADMIN,
			 "<b>Un-FedBan</b>" \
			 "\n<b>Federation:</b> {}" \
			 "\n<b>Federation Admin:</b> {}" \
			 "\n<b>User:</b> {}" \
			 "\n<b>User ID:</b> <code>{}</code>".format(info['fname'], mention_html(user.id, user.first_name), user_target, fban_user_id),
			html=True)
	"""


@spamcheck
def set_frules(update, context):
	chat = update.effective_chat  # type: Optional[Chat]
	user = update.effective_user  # type: Optional[User]
	args = context.args

	if chat.type == 'private':
		send_message(update.effective_message, "This command is specific to the group, not to the PM!")
		return

	fed_id = sql.get_fed_id(chat.id)

	if not fed_id:
		send_message(update.effective_message, "This chat is not in any federation!")
		return

	if is_user_fed_admin(fed_id, user.id) == False:
		send_message(update.effective_message, "Only federation admins can do this!")
		return

	if len(args) >= 1:
		msg = update.effective_message
		raw_text = msg.text
		args = raw_text.split(None, 1)  # use python's maxsplit to separate cmd and args
		if len(args) == 2:
			txt = args[1]
			offset = len(txt) - len(raw_text)  # set correct offset relative to command
			markdown_rules = markdown_parser(txt, entities=msg.parse_entities(), offset=offset)
		x = sql.set_frules(fed_id, markdown_rules)
		if not x:
			send_message(update.effective_message, "There is an error while setting federation rules! If you wondered why please ask it in support group!")
			return

		rules = sql.get_fed_info(fed_id)['frules']
		getfed = sql.get_fed_info(fed_id)
		get_fedlog = sql.get_fed_log(fed_id)
		if get_fedlog:
			if eval(get_fedlog):
				context.bot.send_message(get_fedlog, "*{}* has changed the federation rules *{}*".format(user.first_name, getfed['fname']), parse_mode="markdown")
		send_message(update.effective_message, "The rule has been changed to:\n{}!".format(rules))
	else:
		send_message(update.effective_message, "Please write a rule to set it!")


@spamcheck
def get_frules(update, context):
	chat = update.effective_chat  # type: Optional[Chat]
	args = context.args

	if chat.type == 'private':
		send_message(update.effective_message, "This command is specific to the group, not to the PM!")
		return

	fed_id = sql.get_fed_id(chat.id)
	if not fed_id:
		send_message(update.effective_message, "This group is not in any federation!")
		return

	rules = sql.get_frules(fed_id)
	text = "*The fed's rules:*\n"
	text += rules
	send_message(update.effective_message, text, parse_mode=ParseMode.MARKDOWN)


@spamcheck
def fed_broadcast(update, context):
	msg = update.effective_message
	user = update.effective_user  # type: Optional[User]
	chat = update.effective_chat  # type: Optional[Chat]
	args = context.args

	if chat.type == 'private':
		send_message(update.effective_message, "This command is specific to the group, not to the PM!")
		return

	if args:
		chat = update.effective_chat  # type: Optional[Chat]
		fed_id = sql.get_fed_id(chat.id)
		fedinfo = sql.get_fed_info(fed_id)
		# Parsing md
		raw_text = msg.text
		args = raw_text.split(None, 1)  # use python's maxsplit to separate cmd and args
		txt = args[1]
		offset = len(txt) - len(raw_text)  # set correct offset relative to command
		text_parser = markdown_parser(txt, entities=msg.parse_entities(), offset=offset)
		text = text_parser
		try:
			broadcaster = user.first_name
		except:
			broadcaster = user.first_name + " " + user.last_name
		text += "\n\n- {}".format(mention_markdown(user.id, broadcaster))
		chat_list = sql.all_fed_chats(fed_id)
		failed = 0
		for chat in chat_list:
			title = "*New broadcasts from the Federation {}*\n".format(fedinfo['fname'])
			try:
				context.bot.sendMessage(chat, title + text, parse_mode="markdown")
			except TelegramError:
				try:
					dispatcher.bot.getChat(chat)
				except Unauthorized:
					failed += 1
					sql.chat_leave_fed(chat)
					LOGGER.info("Chat {} has leave fed {} because bot is kicked".format(chat, fedinfo['fname']))
					continue
				failed += 1
				LOGGER.warning("Couldn't send broadcast to {}".format(str(chat)))

		send_text = "Siaran Federasi selesai."
		if failed >= 1:
			send_text += "{} group failed to receive message, possibly due to federation leave.".format(failed)
		send_message(update.effective_message, send_text)

@spamcheck
def fed_ban_list(update, context):
	chat = update.effective_chat  # type: Optional[Chat]
	user = update.effective_user  # type: Optional[User]
	args = context.args
	chat_data = context.chat_data

	if chat.type == 'private':
		send_message(update.effective_message, "This command is specific to the group, not to the PM!")
		return

	fed_id = sql.get_fed_id(chat.id)
	info = sql.get_fed_info(fed_id)

	if not fed_id:
		send_message(update.effective_message, "This group is not in any federation!")
		return

	if is_user_fed_owner(fed_id, user.id) == False:
		send_message(update.effective_message, "Only federation owners can do this!")
		return

	user = update.effective_user  # type: Optional[Chat]
	chat = update.effective_chat  # type: Optional[Chat]
	getfban = sql.get_all_fban_users(fed_id)
	if len(getfban) == 0:
		send_message(update.effective_message, "No users on fban in federation {}".format(info['fname']), parse_mode=ParseMode.HTML)
		return

	if args:
		if args[0] == 'json':
			jam = time.time()
			new_jam = jam + 1800
			cek = get_chat(chat.id, chat_data)
			if cek.get('status'):
				if jam <= int(cek.get('value')):
					waktu = time.strftime("%H:%M:%S %d/%m/%Y", time.localtime(cek.get('value')))
					send_message(update.effective_message, "You can get data once every 30 minutes!\nYou can get this data again on `{}`".format(waktu), parse_mode=ParseMode.MARKDOWN)
					return
				else:
					if user.id not in SUDO_USERS:
						put_chat(chat.id, new_jam, chat_data)
			else:
				if user.id not in SUDO_USERS:
					put_chat(chat.id, new_jam, chat_data)
			backups = ""
			for users in getfban:
				getuserinfo = sql.get_all_fban_users_target(fed_id, users)
				json_parser = {"user_id": users, "first_name": getuserinfo['first_name'], "last_name": getuserinfo['last_name'], "user_name": getuserinfo['user_name'], "reason": getuserinfo['reason']}
				backups += json.dumps(json_parser)
				backups += "\n"
			with BytesIO(str.encode(backups)) as output:
				output.name = "TPBOT_fbanned_users.json"
				update.effective_message.reply_document(document=output, filename="TPBOT_fbanned_users.json",
													caption="Total {} users blocked from federation {}.".format(len(getfban), info['fname']))
			return
		elif args[0] == 'csv':
			jam = time.time()
			new_jam = jam + 1800
			cek = get_chat(chat.id, chat_data)
			if cek.get('status'):
				if jam <= int(cek.get('value')):
					waktu = time.strftime("%H:%M:%S %d/%m/%Y", time.localtime(cek.get('value')))
					send_message(update.effective_message, "You can get data once every 30 minutes!\nYou can get this data again on `{}`".format(waktu), parse_mode=ParseMode.MARKDOWN)
					return
				else:
					if user.id not in SUDO_USERS:
						put_chat(chat.id, new_jam, chat_data)
			else:
				if user.id not in SUDO_USERS:
					put_chat(chat.id, new_jam, chat_data)
			backups = "id,firstname,lastname,username,reason\n"
			for users in getfban:
				getuserinfo = sql.get_all_fban_users_target(fed_id, users)
				backups += "{user_id},{first_name},{last_name},{user_name},{reason}".format(user_id=users, first_name=getuserinfo['first_name'], last_name=getuserinfo['last_name'], user_name=getuserinfo['user_name'], reason=getuserinfo['reason'])
				backups += "\n"
			with BytesIO(str.encode(backups)) as output:
				output.name = "TPBOT_fbanned_users.csv"
				update.effective_message.reply_document(document=output, filename="TPBOT_fbanned_users.csv",
													caption="Total {} users blocked from federation {}.".format(len(getfban), info['fname']))
			return

	text = "<b>Total {} users on fban in federation {}:</b>\n".format(len(getfban), info['fname'])
	for users in getfban:
		getuserinfo = sql.get_all_fban_users_target(fed_id, users)
		if getuserinfo == False:
			text = "No users on fban in federation {}".format(info['fname'])
			break
		user_name = getuserinfo['first_name']
		if getuserinfo['last_name']:
			user_name += " " + getuserinfo['last_name']
		text += " • {} (<code>{}</code>)\n".format(mention_html(users, user_name), users)

	try:
		send_message(update.effective_message, text, parse_mode=ParseMode.HTML)
	except:
		jam = time.time()
		new_jam = jam + 1800
		cek = get_chat(chat.id, chat_data)
		if cek.get('status'):
			if jam <= int(cek.get('value')):
				waktu = time.strftime("%H:%M:%S %d/%m/%Y", time.localtime(cek.get('value')))
				send_message(update.effective_message, "You can get data once every 30 minutes!\nYou can get this data again on `{}`".format(waktu), parse_mode=ParseMode.MARKDOWN)
				return
			else:
				if user.id not in SUDO_USERS:
					put_chat(chat.id, new_jam, chat_data)
		else:
			if user.id not in SUDO_USERS:
				put_chat(chat.id, new_jam, chat_data)
		cleanr = re.compile('<.*?>')
		cleantext = re.sub(cleanr, '', text)
		with BytesIO(str.encode(cleantext)) as output:
			output.name = "fbanlist.txt"
			update.effective_message.reply_document(document=output, filename="fbanlist.txt",
													caption="Here is a list of users currently banned on federation {}.".format(info['fname']))

@spamcheck
def fed_notif(update, context):
	chat = update.effective_chat  # type: Optional[Chat]
	user = update.effective_user  # type: Optional[User]
	msg = update.effective_message
	args = context.args
	fed_id = sql.get_fed_id(chat.id)

	if not fed_id:
		send_message(update.effective_message, "This group is not in any federation!")
		return

	if args:
		if args[0] in ("yes", "on", "ya"):
			sql.set_feds_setting(user.id, True)
			send_message(update.effective_message, "Federation reporting live! Every user in fban / unfban you will be notified via PM.")
		elif args[0] in ("no", "off", "ga"):
			sql.set_feds_setting(user.id, False)
			send_message(update.effective_message, "Federation reporting is dead! Any user in fban / unfban you will not be notified via PM.")
		else:
			send_message(update.effective_message, "Please input `yes`/`on`/`no`/`off`", parse_mode="markdown")
	else:
		getreport = sql.user_feds_report(user.id)
		send_message(update.effective_message, "Your federation report preferences: `{}`".format(getreport), parse_mode="markdown")

@spamcheck
def fed_chats(update, context):
	chat = update.effective_chat  # type: Optional[Chat]
	user = update.effective_user  # type: Optional[User]
	args = context.args

	if chat.type == 'private':
		send_message(update.effective_message, "This command is specific to the group, not to the PM!")
		return

	fed_id = sql.get_fed_id(chat.id)
	info = sql.get_fed_info(fed_id)

	if not fed_id:
		send_message(update.effective_message, "This group is not in any federation!")
		return

	if is_user_fed_admin(fed_id, user.id) == False:
		send_message(update.effective_message, "Only federation admins can do this!")
		return

	getlist = sql.all_fed_chats(fed_id)
	if len(getlist) == 0:
		send_message(update.effective_message, "No chats joined the federation {}".format(info['fname']), parse_mode=ParseMode.HTML)
		return

	text = "<b>Chats that join a federation {}:</b>\n".format(info['fname'])
	for chats in getlist:
		chat_name = sql.get_fed_name(chats)
		text += " • {} (<code>{}</code>)\n".format(chat_name, chats)

	try:
		send_message(update.effective_message, text, parse_mode=ParseMode.HTML)
	except:
		cleanr = re.compile('<.*?>')
		cleantext = re.sub(cleanr, '', text)
		with BytesIO(str.encode(cleantext)) as output:
			output.name = "fedchats.txt"
			update.effective_message.reply_document(document=output, filename="fedchats.txt",
													caption="Here's a list of chats that federated {}.".format(info['fname']))

@spamcheck
def fed_import_bans(update, context, chat_data):
	chat = update.effective_chat  # type: Optional[Chat]
	user = update.effective_user  # type: Optional[User]
	msg = update.effective_message

	if chat.type == 'private':
		send_message(update.effective_message, "This command is specific to the group, not to the PM!")
		return

	fed_id = sql.get_fed_id(chat.id)
	info = sql.get_fed_info(fed_id)
	getfed = sql.get_fed_info(fed_id)

	if not fed_id:
		send_message(update.effective_message, "This group is not in any federation!")
		return

	if is_user_fed_owner(fed_id, user.id) == False:
		send_message(update.effective_message, "Only federation owners can do this!")
		return

	if msg.reply_to_message and msg.reply_to_message.document:
		jam = time.time()
		new_jam = jam + 1800
		cek = get_chat(chat.id, chat_data)
		if cek.get('status'):
			if jam <= int(cek.get('value')):
				waktu = time.strftime("%H:%M:%S %d/%m/%Y", time.localtime(cek.get('value')))
				send_message(update.effective_message, "You can get data once every 30 minutes!\nYou can get this data again on `{}`".format(waktu), parse_mode=ParseMode.MARKDOWN)
				return
			else:
				if user.id not in SUDO_USERS:
					put_chat(chat.id, new_jam, chat_data)
		else:
			if user.id not in SUDO_USERS:
				put_chat(chat.id, new_jam, chat_data)
		# if int(int(msg.reply_to_message.document.file_size)/1024) >= 200:
		# 	send_message(update.effective_message, "File ini terlalu besar!")
		# 	return
		success = 0
		failed = 0
		try:
			file_info = context.bot.get_file(msg.reply_to_message.document.file_id)
		except BadRequest:
			send_message(update.effective_message, "Try downloading and re-uploading the file, this one looks like it's broken!")
			return
		fileformat = msg.reply_to_message.document.file_name.split('.')[-1]
		if fileformat == 'json':
			multi_fed_id = []
			multi_import_userid = []
			multi_import_firstname = []
			multi_import_lastname = []
			multi_import_username = []
			multi_import_reason = []
			with BytesIO() as file:
				file_info.download(out=file)
				file.seek(0)
				reading = file.read().decode('UTF-8')
				splitting = reading.split('\n')
				for x in splitting:
					if x == '':
						continue
					try:
						data = json.loads(x)
					except json.decoder.JSONDecodeError as err:
						failed += 1
						continue
					try:
						import_userid = int(data['user_id']) # Make sure it int
						import_firstname = str(data['first_name'])
						import_lastname = str(data['last_name'])
						import_username = str(data['user_name'])
						import_reason = str(data['reason'])
					except ValueError:
						failed += 1
						continue
					# Checking user
					if int(import_userid) == context.bot.id:
						failed += 1
						continue
					if is_user_fed_owner(fed_id, import_userid) == True:
						failed += 1
						continue
					if is_user_fed_admin(fed_id, import_userid) == True:
						failed += 1
						continue
					if str(import_userid) == str(OWNER_ID):
						failed += 1
						continue
					if int(import_userid) in SUDO_USERS:
						failed += 1
						continue
					if int(import_userid) in WHITELIST_USERS:
						failed += 1
						continue
					multi_fed_id.append(fed_id)
					multi_import_userid.append(str(import_userid))
					multi_import_firstname.append(import_firstname)
					multi_import_lastname.append(import_lastname)
					multi_import_username.append(import_username)
					multi_import_reason.append(import_reason)
					success += 1
				sql.multi_fban_user(multi_fed_id, multi_import_userid, multi_import_firstname, multi_import_lastname, multi_import_username, multi_import_reason)
			text = "The block file was imported successfully. {} people blocked.".format(success)
			if failed >= 1:
				text += " {} failed in import.".format(failed)
			get_fedlog = sql.get_fed_log(fed_id)
			if get_fedlog:
				if eval(get_fedlog):
					teks = "Federation *{}* has successfully imported data. {} blocked".format(getfed['fname'], success)
					if failed >= 1:
						teks += " {} failed in import.".format(failed)
					context.bot.send_message(get_fedlog, teks, parse_mode="markdown")
		elif fileformat == 'csv':
			multi_fed_id = []
			multi_import_userid = []
			multi_import_firstname = []
			multi_import_lastname = []
			multi_import_username = []
			multi_import_reason = []
			file_info.download("fban_{}.csv".format(msg.reply_to_message.document.file_id))
			with open("fban_{}.csv".format(msg.reply_to_message.document.file_id), 'r', encoding="utf8") as csvFile:
				reader = csv.reader(csvFile)
				for data in reader:
					try:
						import_userid = int(data[0]) # Make sure it int
						import_firstname = str(data[1])
						import_lastname = str(data[2])
						import_username = str(data[3])
						import_reason = str(data[4])
					except ValueError:
						failed += 1
						continue
					# Checking user
					if int(import_userid) == context.bot.id:
						failed += 1
						continue
					if is_user_fed_owner(fed_id, import_userid) == True:
						failed += 1
						continue
					if is_user_fed_admin(fed_id, import_userid) == True:
						failed += 1
						continue
					if str(import_userid) == str(OWNER_ID):
						failed += 1
						continue
					if int(import_userid) in SUDO_USERS:
						failed += 1
						continue
					if int(import_userid) in WHITELIST_USERS:
						failed += 1
						continue
					multi_fed_id.append(fed_id)
					multi_import_userid.append(str(import_userid))
					multi_import_firstname.append(import_firstname)
					multi_import_lastname.append(import_lastname)
					multi_import_username.append(import_username)
					multi_import_reason.append(import_reason)
					success += 1
					# t = ThreadWithReturnValue(target=sql.fban_user, args=(fed_id, str(import_userid), import_firstname, import_lastname, import_username, import_reason,))
					# t.start()
				sql.multi_fban_user(multi_fed_id, multi_import_userid, multi_import_firstname, multi_import_lastname, multi_import_username, multi_import_reason)
			csvFile.close()
			os.remove("fban_{}.csv".format(msg.reply_to_message.document.file_id))
			text = "The block file was imported successfully. {} people blocked.".format(success)
			if failed >= 1:
				text += " {} failed in import.".format(failed)
			get_fedlog = sql.get_fed_log(fed_id)
			if get_fedlog:
				if eval(get_fedlog):
					teks = "Federation *{}* has successfully imported data. {} blocked".format(getfed['fname'], success)
					if failed >= 1:
						teks += " {} failed in import.".format(failed)
					context.bot.send_message(get_fedlog, teks, parse_mode="markdown")
		else:
			send_message(update.effective_message, "Files not supported.")
			return
		send_message(update.effective_message, text)

def del_fed_button(update, context):
	query = update.callback_query
	userid = query.message.chat.id
	fed_id = query.data.split("_")[1]

	if fed_id == 'cancel':
		query.message.edit_text("Federation deletion cancelled")
		return

	getfed = sql.get_fed_info(fed_id)
	if getfed:
		delete = sql.del_fed(fed_id)
		if delete:
			query.message.edit_text("You have removed your federation! Now all Groups connected to the `{}` now has no federation.".format(getfed['fname']), parse_mode='markdown')

@spamcheck
def fed_stat_user(update, context):
	chat = update.effective_chat  # type: Optional[Chat]
	user = update.effective_user  # type: Optional[User]
	msg = update.effective_message
	args = context.args

	if args:
		if args[0].isdigit():
			user_id = args[0]
		else:
			user_id = extract_user(msg, args)
	else:
		user_id = extract_user(msg, args)

	if user_id and user_id != "error":
		if len(args) == 2 and args[0].isdigit():
			fed_id = args[1]
			user_name, reason, fbantime = sql.get_user_fban(fed_id, str(user_id))
			if fbantime:
				fbantime = time.strftime("%d/%m/%Y", time.localtime(fbantime))
			else:
				fbantime = "Unavaiable"
			if user_name == False:
				send_message(update.effective_message, "Federation {} not found!".format(fed_id), parse_mode="markdown")
				return
			if user_name == "" or user_name == None:
				user_name = "Dia"
			if not reason:
				send_message(update.effective_message, "{} has not been banned in this federation!".format(user_name))
			else:
				teks = "{} banned in this federation because:\n`{}`\n*Banned on:* `{}`".format(user_name, reason, fbantime)
				send_message(update.effective_message, teks, parse_mode="markdown")
			return
		user_name, fbanlist = sql.get_user_fbanlist(str(user_id))
		if user_name == "":
			try:
				user_name = context.bot.get_chat(user_id).first_name
			except BadRequest:
				user_name = "Dia"
			if user_name == "" or user_name == None:
				user_name = "Dia"
		if len(fbanlist) == 0:
			send_message(update.effective_message, "{} has not been banned in any federation!".format(user_name))
			return
		else:
			teks = "{} already banned in this federation:\n".format(user_name)
			for x in fbanlist:
				teks += "- `{}`: {}\n".format(x[0], x[1][:20])
			teks += "\nIf you want to find out more about the specific reasons for fedban, use /fbanstat <FedID>"
			send_message(update.effective_message, teks, parse_mode="markdown")

	elif not msg.reply_to_message and not args:
		user_id = msg.from_user.id
		user_name, fbanlist = sql.get_user_fbanlist(user_id)
		if user_name == "":
			user_name = msg.from_user.first_name
		if len(fbanlist) == 0:
			send_message(update.effective_message, "{} has not been banned in any federation!".format(user_name))
		else:
			teks = "{} already banned in this federation:\n".format(user_name)
			for x in fbanlist:
				teks += "- `{}`: {}\n".format(x[0], x[1][:20])
			teks += "\nIf you want to find out more about the specific reasons for fedban, use /fbanstat <FedID>"
			send_message(update.effective_message, teks, parse_mode="markdown")

	else:
		fed_id = args[0]
		fedinfo = sql.get_fed_info(fed_id)
		if not fedinfo:
			send_message(update.effective_message, "Federation {} not found!".format(fed_id))
			return
		name, reason, fbantime = sql.get_user_fban(fed_id, msg.from_user.id)
		if fbantime:
			fbantime = time.strftime("%d/%m/%Y", time.localtime(fbantime))
		else:
			fbantime = "Unavaiable"
		if not name:
			name = msg.from_user.first_name
		if not reason:
			send_message(update.effective_message, "{} not banned in this federation".format(name))
			return
		send_message(update.effective_message, "{} banned in this federation because:\n`{}`\n*Banned on:* `{}`".format(name, reason, fbantime), parse_mode="markdown")


@spamcheck
def set_fed_log(update, context):
	chat = update.effective_chat  # type: Optional[Chat]
	user = update.effective_user  # type: Optional[User]
	msg = update.effective_message
	args = context.args

	if chat.type == 'private':
		send_message(update.effective_message, "This command is specific to the group, not to the PM!")
		return

	if args:
		fedinfo = sql.get_fed_info(args[0])
		if not fedinfo:
			send_message(update.effective_message, "This federation does not exist!")
			return
		isowner = is_user_fed_owner(args[0], user.id)
		if not isowner:
			send_message(update.effective_message, "Only the federation creator can assign federation logs.")
			return
		setlog = sql.set_fed_log(args[0], chat.id)
		if setlog:
			send_message(update.effective_message, "Federation logs `{}` has been set on the {}".format(fedinfo['fname'], chat.title), parse_mode="markdown")
	else:
		send_message(update.effective_message, "You haven't provided their federation ID!")

@spamcheck
def unset_fed_log(update, context):
	chat = update.effective_chat  # type: Optional[Chat]
	user = update.effective_user  # type: Optional[User]
	msg = update.effective_message
	args = context.args

	if chat.type == 'private':
		send_message(update.effective_message, "This command is specific to the group, not to the PM!")
		return

	if args:
		fedinfo = sql.get_fed_info(args[0])
		if not fedinfo:
			send_message(update.effective_message, "This federation does not exist!")
			return
		isowner = is_user_fed_owner(args[0], user.id)
		if not isowner:
			send_message(update.effective_message, "Only the federation creator can assign federation logs.")
			return
		setlog = sql.set_fed_log(args[0], None)
		if setlog:
			send_message(update.effective_message, "Federation logs `{}` has been revoked on {}".format(fedinfo['fname'], chat.title), parse_mode="markdown")
	else:
		send_message(update.effective_message, "You haven't provided their federation ID!")


@spamcheck
def subs_feds(update, context):
	chat = update.effective_chat  # type: Optional[Chat]
	user = update.effective_user  # type: Optional[User]
	msg = update.effective_message
	args = context.args

	if chat.type == 'private':
		send_message(update.effective_message, "This command is specific to the group, not to the PM!")
		return

	fed_id = sql.get_fed_id(chat.id)
	fedinfo = sql.get_fed_info(fed_id)

	if not fed_id:
		send_message(update.effective_message, "This group is not in any federation!")
		return

	if is_user_fed_owner(fed_id, user.id) == False:
		send_message(update.effective_message, "Only federation owners can do this!")
		return

	if args:
		getfed = sql.search_fed_by_id(args[0])
		if getfed == False:
			send_message(update.effective_message, "Please enter a valid federation id.")
			return
		subfed = sql.subs_fed(args[0], fed_id)
		if subfed:
			send_message(update.effective_message, "Federation `{}` have followed the federation `{}`. Any fedban of the federation, this federation will also be banned users tsb.".format(fedinfo['fname'], getfed['fname']), parse_mode="markdown")
			get_fedlog = sql.get_fed_log(args[0])
			if get_fedlog:
				if int(get_fedlog) != int(chat.id):
					context.bot.send_message(get_fedlog, "Federation `{}` have followed the federation `{}`".format(fedinfo['fname'], getfed['fname']), parse_mode="markdown")
		else:
			send_message(update.effective_message, "Federation `{}` already following the federation `{}`.".format(fedinfo['fname'], getfed['fname']), parse_mode="markdown")
	else:
		send_message(update.effective_message, "You haven't provided their federation ID!")

@spamcheck
def unsubs_feds(update, context):
	chat = update.effective_chat  # type: Optional[Chat]
	user = update.effective_user  # type: Optional[User]
	msg = update.effective_message
	args = context.args

	if chat.type == 'private':
		send_message(update.effective_message, "This command is specific to the group, not to the PM!")
		return

	fed_id = sql.get_fed_id(chat.id)
	fedinfo = sql.get_fed_info(fed_id)

	if not fed_id:
		send_message(update.effective_message, "This group is not in any federation!")
		return

	if is_user_fed_owner(fed_id, user.id) == False:
		send_message(update.effective_message, "Only federation owners can do this!")
		return

	if args:
		getfed = sql.search_fed_by_id(args[0])
		if getfed == False:
			send_message(update.effective_message, "Please enter a valid federation id.")
			return
		subfed = sql.unsubs_fed(args[0], fed_id)
		if subfed:
			send_message(update.effective_message, "Federation `{}` no longer follow `{}` again.".format(fedinfo['fname'], getfed['fname']), parse_mode="markdown")
			get_fedlog = sql.get_fed_log(args[0])
			if get_fedlog:
				if int(get_fedlog) != int(chat.id):
					context.bot.send_message(get_fedlog, "Federation `{}` no longer follow `{}`".format(fedinfo['fname'], getfed['fname']), parse_mode="markdown")
		else:
			send_message(update.effective_message, "Federation `{}` not following federation `{}`.".format(fedinfo['fname'], getfed['fname']), parse_mode="markdown")
	else:
		send_message(update.effective_message, "You haven't provided their federation ID!")

@spamcheck
def get_myfedsubs(update, context):
	chat = update.effective_chat  # type: Optional[Chat]
	user = update.effective_user  # type: Optional[User]
	msg = update.effective_message
	args = context.args

	if chat.type == 'private':
		send_message(update.effective_message, "This command is specific to the group, not to the PM!")
		return

	fed_id = sql.get_fed_id(chat.id)
	fedinfo = sql.get_fed_info(fed_id)

	if not fed_id:
		send_message(update.effective_message, "This group is not in any federation!")
		return

	if is_user_fed_owner(fed_id, user.id) == False:
		send_message(update.effective_message, "Only federation owners can do this!")
		return

	getmy = sql.get_mysubs(fed_id)

	if len(getmy) == 0:
		send_message(update.effective_message, "Federation `{}` not following any federation.".format(fedinfo['fname']), parse_mode="markdown")
		return
	else:
		listfed = "Federation `{}` following these federations:\n".format(fedinfo['fname'])
		for x in getmy:
			listfed += "- `{}`\n".format(x)
		listfed += "\nFor federation info, type`/fedinfo <fedid>`. To unsubscribe type `/unsubfed <fedid>`."
		send_message(update.effective_message, listfed, parse_mode="markdown")

@spamcheck
def get_myfeds_list(update, context):
	chat = update.effective_chat  # type: Optional[Chat]
	user = update.effective_user  # type: Optional[User]
	msg = update.effective_message
	args = context.args

	fedowner = sql.get_user_owner_fed_full(user.id)
	if fedowner:
		text = "*This is your federation:\n*"
		for f in fedowner:
			text += "- `{}`: *{}*\n".format(f['fed_id'], f['fed']['fname'])
	else:
		text = "*You don't have federation!*"
	send_message(update.effective_message, text, parse_mode="markdown")


def is_user_fed_admin(fed_id, user_id):
	fed_admins = sql.all_fed_users(fed_id)
	if fed_admins == False:
		return False
	if int(user_id) in fed_admins or int(user_id) == OWNER_ID:
		return True
	else:
		return False


def is_user_fed_owner(fed_id, user_id):
	getsql = sql.get_fed_info(fed_id)
	if getsql == False:
		return False
	getfedowner = eval(getsql['fusers'])
	if getfedowner == None or getfedowner == False:
		return False
	getfedowner = getfedowner['owner']
	if str(user_id) == getfedowner or int(user_id) == OWNER_ID:
		return True
	else:
		return False


def welcome_fed(update, context):
	chat = update.effective_chat  # type: Optional[Chat]
	user = update.effective_user  # type: Optional[User]

	fed_id = sql.get_fed_id(chat.id)
	fban, fbanreason, fbantime = sql.get_fban_user(fed_id, user.id)
	if fban:
		send_message(update.effective_message, "This user is banned in current federation! I will remove him.")
		context.bot.ban_chat_member(chat.id, user.id)
		return True
	else:
		return False


def __stats__():
	all_fbanned = sql.get_all_fban_users_global()
	all_feds = sql.get_all_feds_users_global()
	return "{} user on fbanned, on {} federation".format(len(all_fbanned), len(all_feds))


def __user_info__(user_id, chat_id):
	fed_id = sql.get_fed_id(chat_id)
	if fed_id:
		fban, fbanreason, fbantime = sql.get_fban_user(fed_id, user_id)
		info = sql.get_fed_info(fed_id)
		infoname = info['fname']

		if int(info['owner']) == user_id:
			text = "This user is the current owner of federation: <b>{}</b>.".format(infoname)
		elif is_user_fed_admin(fed_id, user_id):
			text = "This user is a current admin of federation: <b>{}</b>.".format(infoname)

		elif fban:
			text = "Banned in federations today: <b>Yes</b>"
			text += "\n<b>Reason:</b> {}".format(fbanreason)
		else:
			text = "Banned in federations today: <b>No</b>"
	else:
		text = ""
	return text


# Temporary data
def put_chat(chat_id, value, chat_data):
	# print(chat_data)
	if value == False:
		status = False
	else:
		status = True
	chat_data[chat_id] = {'federation': {"status": status, "value": value}}

def get_chat(chat_id, chat_data):
	# print(chat_data)
	try:
		value = chat_data[chat_id]['federation']
		return value
	except KeyError:
		return {"status": False, "value": False}


dispatcher.add_handler(CommandHandler("newfed", new_fed))
dispatcher.add_handler(CommandHandler("delfed", del_fed, pass_args=True))
dispatcher.add_handler(CommandHandler("joinfed", join_fed, pass_args=True))
dispatcher.add_handler(CommandHandler("leavefed", leave_fed, pass_args=True))
dispatcher.add_handler(CommandHandler("fpromote", user_join_fed, pass_args=True))
dispatcher.add_handler(CommandHandler("fdemote", user_demote_fed, pass_args=True))
dispatcher.add_handler(CommandHandler("fedinfo", fed_info, pass_args=True))
dispatcher.add_handler(DisableAbleCommandHandler(["fban", "fedban"], fed_ban, pass_args=True))
dispatcher.add_handler(CommandHandler("unfban", unfban, pass_args=True))
dispatcher.add_handler(CommandHandler("fbroadcast", fed_broadcast, pass_args=True))
dispatcher.add_handler(CommandHandler("setfrules", set_frules, pass_args=True))
dispatcher.add_handler(CommandHandler("frules", get_frules, pass_args=True))
dispatcher.add_handler(CommandHandler("chatfed", fed_chat, pass_args=True))
dispatcher.add_handler(CommandHandler("fedadmins", fed_admin, pass_args=True))
dispatcher.add_handler(CommandHandler("fbanlist", fed_ban_list, pass_args=True, pass_chat_data=True))
dispatcher.add_handler(CommandHandler("fednotif", fed_notif, pass_args=True))
dispatcher.add_handler(CommandHandler("fedchats", fed_chats, pass_args=True))
dispatcher.add_handler(CommandHandler("importfbans", fed_import_bans, pass_chat_data=True, filters=Filters.user(OWNER_ID)))
dispatcher.add_handler(DisableAbleCommandHandler(["fedstat", "fbanstat"], fed_stat_user, pass_args=True))
dispatcher.add_handler(CommandHandler("setfedlog", set_fed_log, pass_args=True))
dispatcher.add_handler(CommandHandler("unsetfedlog", unset_fed_log, pass_args=True))
dispatcher.add_handler(CommandHandler("subfed", subs_feds, pass_args=True))
dispatcher.add_handler(CommandHandler("unsubfed", unsubs_feds, pass_args=True))
dispatcher.add_handler(CommandHandler("fedsubs", get_myfedsubs, pass_args=True))
dispatcher.add_handler(CommandHandler("myfeds", get_myfeds_list))
dispatcher.add_handler(CallbackQueryHandler(del_fed_button, pattern=r"rmfed_"))

