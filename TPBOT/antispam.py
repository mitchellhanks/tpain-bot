from . import dispatcher
from telegram import Message, Chat, Update, Bot, User, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode, ChatPermissions
from telegram.ext import Filters, MessageHandler, CommandHandler, run_async, CallbackQueryHandler

try:
	from TPBOT.config import Development as Config
except:
	import sys
	print("There is no config file.  Quitting...", file=sys.stderr)
	quit(1)

Owner = Config.OWNER_ID
NoResUser = [Config.OWNER_ID]
# AntiSpamValue = 15

# GLOBAL_USER_DATA = {}

def bad_group(chat_id, GROUP_BLACKLIST, GROUP_WHITELIST):
	if not GROUP_WHITELIST:
		if chat_id in GROUP_BLACKLIST:
			return True
	elif not chat_id in GROUP_WHITELIST:
		return True
	return False

def bad_user(user_id, SPAMMERS):
	if not SPAMMERS:
		pass
	elif user_id in SPAMMERS:
		return True
	return False

