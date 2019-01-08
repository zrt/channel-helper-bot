#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Channel Helper Bot """
""" private_msg.py """
""" Copyright 2018, Jogle Lew """
import helper_const
import helper_global
import helper_database
import telegram
import threading
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import MessageHandler, Filters

def add_record(channel_id, msg_id, message, anonymous):
    user = message.from_user
    username = user.username
    name = user.first_name
    if user.last_name:
        name += " " + user.last_name
    if anonymous:
        name = ''
    date = message.date.strftime("%Y-%m-%d %H:%M:%S")

    msg_type = "text"
    msg_content = ""
    media_id = ""
    if message.text:
        msg_type = "text"
        msg_content = message.text
    elif message.sticker:
        msg_type = 'sticker'
        media_id = message.sticker.file_id
        if message.sticker.emoji:
            msg_content = message.sticker.emoji
    elif message.photo:
        msg_type = 'photo'
        media_id = message.photo[-1].file_id
        if message.caption:
            msg_content = message.caption
    elif message.video:
        msg_type = 'video'
        media_id = message.video.file_id
        if message.caption:
            msg_content = message.caption
    elif message.document:
        msg_type = 'document'
        media_id = message.document.file_id
        if message.document.file_name:
            msg_content = message.document.file_name
    elif message.audio:
        msg_type = 'audio'
        media_id = message.audio.file_id
        if message.audio.title:
            msg_content = message.audio.title
    elif message.voice:
        msg_type = 'voice'
        media_id = message.voice.file_id

    helper_database.add_record(channel_id, msg_id, username, name, msg_type, msg_content, media_id, date)


def update_comments(bot, channel_id, msg_id):
    # update comments in channel
    comment_id = helper_database.get_comment_id(channel_id, msg_id)
    config = helper_database.get_channel_config(channel_id)
    if config is None:
        return
    recent = config[3]
    records = helper_database.get_recent_records(channel_id, msg_id, recent)

    # Prepare Keyboard
    motd_keyboard = [[
        InlineKeyboardButton(
            helper_global.value("add_comment", "Add Comment"),
            url="http://telegram.me/%s?start=add_%d_%d" % (helper_global.value('bot_username', ''), channel_id, msg_id)
        ),
        InlineKeyboardButton(
            helper_global.value("add_anonymous_comment", "Add Anonymous Comment"),
            url="http://telegram.me/%s?start=addanonymous_%d_%d" % (helper_global.value('bot_username', ''), channel_id, msg_id)
        ),
        InlineKeyboardButton(
            helper_global.value("show_all_comments", "Show All"),
            url="http://telegram.me/%s?start=show_%s_%d" % (helper_global.value('bot_username', ''), channel_id, msg_id)
        )
    ]]
    motd_markup = InlineKeyboardMarkup(motd_keyboard)

    bot.edit_message_text(
        text=helper_global.records_to_str(records), 
        chat_id=channel_id, 
        message_id=comment_id, 
        parse_mode=telegram.ParseMode.HTML,
        reply_markup=motd_markup
    )


def update_dirty_list():
    lock.acquire()
    dirty_list = helper_global.value("dirty_list", [])
    bot = helper_global.value("bot", None)
    for item in dirty_list:
        channel_id, msg_id = item
        threading.Thread(
            target=update_comments,
            args=(bot, channel_id, msg_id)
        ).start()
    helper_global.assign("dirty_list", [])
    lock.release()


def check_channel_message(bot, message):
    chat_id = message.chat_id
    if not message.forward_from_chat:
        bot.send_message(chat_id=chat_id, text=helper_global.value("register_cmd_invalid", ""))
        return
    chat_type = message.forward_from_chat.type
    if not chat_type == "channel":
        bot.send_message(chat_id=chat_id, text=helper_global.value("register_cmd_invalid", ""))
        return
    channel_username = message.forward_from_chat.username
    channel_id = message.forward_from_chat.id
    try:
        helper_database.add_channel_config(channel_id, 'zh-CN', 1, 10, channel_username, chat_id)
    except:
        helper_global.assign(str(chat_id) + "_status", "0,0")
        bot.send_message(chat_id=chat_id, text=helper_global.value("register_cmd_failed", ""))
        return

    helper_global.assign(str(chat_id) + "_status", "0,0")
    bot.send_message(chat_id=chat_id, text=helper_global.value("register_cmd_success", ""))


def private_msg(bot, update):
    message = update.message
    # print(message)
    chat_id = message.chat_id

    args = helper_global.value(str(chat_id) + "_status", "0,0")
    params = args.split(",")
    channel_id = int(params[0])
    msg_id = int(params[1])
    anonymous = False
    if len(params) >= 3 and params[2] == '3':
        anonymous = True
    if channel_id == 0:
        if msg_id == 1:
            check_channel_message(bot, message)
        return

    add_record(channel_id, msg_id, message, anonymous)

    # Update Dirty List
    lock.acquire()
    dirty_list = helper_global.value("dirty_list", [])
    if not (channel_id, msg_id) in dirty_list:
        dirty_list.append((channel_id, msg_id))
    helper_global.assign("dirty_list", dirty_list)
    lock.release()

    bot.send_message(chat_id=chat_id, text=helper_global.value("comment_success", "Success!"))


def set_interval(func, sec):
    def func_wrapper():
        set_interval(func, sec)
        func()
    t = threading.Timer(sec, func_wrapper)
    t.start()
    return t


refresh_status = helper_global.value("refresh_status", False)
if not refresh_status:
    set_interval(update_dirty_list, helper_const.MIN_REFRESH_INTERVAL)
    helper_global.assign("refresh_status", True)
lock = threading.Lock()
_handler = MessageHandler(Filters.private, private_msg)
