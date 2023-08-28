import logging
import os
import sys
import time
from datetime import datetime
from functools import wraps

import telegram.ext as tg
from telegram import ParseMode
from telegram.ext import Updater, Defaults

# enable logging
logging.basicConfig(
	format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
	level=logging.INFO)

LOGGER = logging.getLogger(__name__)

# if version < 3.6, stop bot.
if sys.version_info[0] < 3 or sys.version_info[1] < 6:
	LOGGER.error("You MUST have a python version of at least 3.6! Multiple features depend on this. Bot quitting.")
	quit(1)

# Check if system is reboot or not
# try:
# 	os.remove("reboot")
# except:
# 	pass

from TPBOT.config import Development as Config
TOKEN = Config.API_KEY
try:
	OWNER_ID = int(Config.OWNER_ID)
except ValueError:
	raise Exception("Your OWNER_ID variable is not a valid integer.")

MESSAGE_DUMP = Config.MESSAGE_DUMP
OWNER_USERNAME = Config.OWNER_USERNAME


try:
	IS_DEBUG = Config.IS_DEBUG
except AttributeError:
	IS_DEBUG = False

try:
	SUDO_USERS = set(int(x) for x in Config.SUDO_USERS or [])
except ValueError:
	raise Exception("Your sudo users list does not contain valid integers.")

try:
	SUPPORT_USERS = set(int(x) for x in Config.SUPPORT_USERS or [])
except ValueError:
	raise Exception("Your support users list does not contain valid integers.")

try:
	SPAMMERS = set(int(x) for x in Config.SPAMMERS or [])
except ValueError:
	raise Exception("Your spammers users list does not contain valid integers.")

try:
	GROUP_BLACKLIST = set(int(x) for x in Config.GROUP_BLACKLIST or [])
except ValueError:
	raise Exception("Your GROUP_BLACKLIST users list does not contain valid integers.")
except AttributeError:
	GROUP_BLACKLIST = []

try:
	GROUP_WHITELIST = set(int(x) for x in Config.GROUP_WHITELIST or [])
except ValueError:
	raise Exception("Your GROUP_WHITELIST users list does not contain valid integers.")
except AttributeError:
	GROUP_WHITELIST = []

try:
	WHITELIST_USERS = set(int(x) for x in Config.WHITELIST_USERS or [])
except ValueError:
	raise Exception("Your whitelisted users list does not contain valid integers.")

WEBHOOK = Config.WEBHOOK
URL = Config.URL
PORT = Config.PORT
CERT_PATH = Config.CERT_PATH

USE_DUMP_CHAT = Config.USE_DUMP_CHAT
DUMP_CHAT = int(Config.DUMP_CHAT)

DB_URI = Config.SQLALCHEMY_DATABASE_URI
# DONATION_LINK = Config.DONATION_LINK
LOAD = Config.LOAD
NO_LOAD = Config.NO_LOAD
DEL_CMDS = Config.DEL_CMDS
STRICT_GBAN = Config.STRICT_GBAN
WORKERS = Config.WORKERS
BAN_STICKER = Config.BAN_STICKER
# ALLOW_EXCL = Config.ALLOW_EXCL
CUSTOM_CMD = Config.CUSTOM_CMD
# API_WEATHER = Config.API_OPENWEATHER
# API_ACCUWEATHER = Config.API_ACCUWEATHER
# MAPS_API = Config.MAPS_API
TEMPORARY_DATA = Config.TEMPORARY_DATA
try:
	SPAMWATCH_TOKEN = Config.SPAMWATCH_TOKEN
except:
	pass


SUDO_USERS.add(OWNER_ID)

defaults = Defaults(parse_mode=ParseMode.MARKDOWN, run_async=True)

updater = Updater(TOKEN, workers=WORKERS, use_context=True, defaults=defaults)

dispatcher = updater.dispatcher


SUDO_USERS = list(SUDO_USERS)
WHITELIST_USERS = list(WHITELIST_USERS)
SUPPORT_USERS = list(SUPPORT_USERS)
SPAMMERS = list(SPAMMERS)
GROUP_BLACKLIST = list(GROUP_BLACKLIST)
GROUP_WHITELIST = list(GROUP_WHITELIST)

# Load at end to ensure all prev variables have been set
from TPBOT.modules.helper_funcs.handlers import CustomCommandHandler
from TPBOT.modules.helper_funcs.alternate import send_message
from TPBOT.modules.helper_funcs.chat_status import is_user_admin

if CUSTOM_CMD and len(CUSTOM_CMD) >= 1:
	tg.CommandHandler = CustomCommandHandler

try:
	from TPBOT.antispam import bad_user, bad_group
	LOGGER.info("Note: AntiSpam loaded!")
	antispam_module = True
except ModuleNotFoundError:
	antispam_module = False

def spamcheck(func):
	@wraps(func)
	def check_spam(update, context, *args, **kwargs):
		if antispam_module:
			chat = update.effective_chat
			user = update.effective_user
			message = update.effective_message
			reason = ''

			if IS_DEBUG:
				print(f"{message.text or message.caption} | {user.id} | {message.chat.title} | {chat.id}")
			if (not user) or (chat.type == chat.PRIVATE):
				pass
			elif user and (user.id in SUDO_USERS or user.id in WHITELIST_USERS or user.id in SUPPORT_USERS):
				pass
			elif is_user_admin(chat, user.id) or user.id == OWNER_ID:
				pass
			elif user and user.id == context.bot.id:
				return False
			elif bad_group(int(chat.id), GROUP_BLACKLIST, GROUP_WHITELIST):
				LOGGER.info(f"Blacklisted group removed: {chat}")
				dispatcher.bot.sendMessage(chat.id, "I'm not allowed in this group!  I'm leaving...")
				dispatcher.bot.leaveChat(chat.id)
				reason = f"Unauthorized group attempting to use bot\n" \
						f"*Action Taken:* Self-kicked bot from group\n" \
						f"*Group Title:* {chat.title}" \
						f"*Group ID:* {chat.id}"
			elif bad_user(int(user.id), SPAMMERS):
				LOGGER.info(f"Blacklisted user removed: {user}")
				reason = "Known spammer was blocked" \
						f"*Reason:* Blacklisted" \
						f"*User:* {user.first_name} {user.last_name} @{user.username}  *ID:*  `{user.id}`\n\n"
			if not (reason==''):
				# msg.delete()
				# chat.ban_member(user.id)
				reason = f"Detected spam in *{chat.title}*\n" \
						f"*Reason:* {reason}\n" \
						f"*Action Taken:* Log only\n" \
						f"*From:* {user.first_name} {user.last_name} @{user.username}  *ID:*  `{user.id}`\n\n" \
						f"{message.text}"
				dispatcher.bot.sendMessage(DUMP_CHAT, reason)
				return False

		return func(update, context, *args, **kwargs)
	
	return check_spam
