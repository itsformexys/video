#!/usr/bin/env python3
# Copyright (C) @subinps
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import asyncio
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaDocument
from utils import edit_title_custom, is_admin
from pyrogram import Client, filters
from utils import update, is_admin
from config import Config
from logger import LOGGER
import os
from database import Database
db=Database()
HOME_TEXT = "@Ayrr4d is my master 💕"
admin_filter=filters.create(is_admin) 

@Client.on_message(filters.command(['start', f"start@{Config.BOT_USERNAME}"]))
async def start(client, message):
    await message.reply(HOME_TEXT)



@Client.on_message(filters.command(['restart', 'update', f"restart@{Config.BOT_USERNAME}", f"update@{Config.BOT_USERNAME}"]) & admin_filter)
async def update_handler(client, message):
    if Config.HEROKU_APP:
        k=await message.reply("Heroku APP found, Restarting app to update.")
        dicts={"chat":k.chat.id, "msg_id":k.message_id}
        if not await db.is_saved("RESTART"):
            db.add_config('RESTART', dicts)
        else:
            await db.edit_config("RESTART", dicts)
    else:
        await message.reply("No Heroku APP found, Trying to restart.")
    await update()

@Client.on_message(filters.command(['logs', f"logs@{Config.BOT_USERNAME}"]) & admin_filter)
async def get_logs(client, message):
    logs=[]
    if os.path.exists("ffmpeg.txt"):
        logs.append(InputMediaDocument("ffmpeg.txt", caption="FFMPEG Logs"))
    if os.path.exists("ffmpeg.txt"):
        logs.append(InputMediaDocument("botlog.txt", caption="Bot Logs"))
    if logs:
        try:
            await message.reply_media_group(logs)
        except:
            await message.reply("Errors occured while uploading log file.")
            pass
        logs.clear()
    else:
        await message.reply("No log files found.")

@Client.on_message(filters.command(['env', f"env@{Config.BOT_USERNAME}"]) & filters.user(Config.SUDO))
async def set_heroku_var(client, message):
    if not Config.HEROKU_APP:
        buttons = [[InlineKeyboardButton('Heroku API_KEY', url='https://dashboard.heroku.com/account/applications/authorizations/new')]]
        await message.reply(
            text="No heroku app found, this command needs the following heroku vars to be set.\n\n1. <code>HEROKU_API_KEY</code>: Your heroku account api key.\n2. <code>HEROKU_APP_NAME</code>: Your heroku app name.", 
            reply_markup=InlineKeyboardMarkup(buttons)) 
        return     
    if " " in message.text:
        cmd, env = message.text.split(" ", 1)
        if  not "=" in env:
            return await message.reply("You should specify the value for env.\nExample: /env CHAT=-100213658211")
        var, value = env.split("=", 2)
        config = Config.HEROKU_APP.config()
        if not value:
            m=await message.reply(f"No value for env specified. Trying to delete env {var}.")
            await asyncio.sleep(2)
            if var in config:
                del config[var]
                k=await m.edit(f"Sucessfully deleted {var}, Now restarting..")
                dicts={"chat":k.chat.id, "msg_id":k.message_id}
                if not await db.is_saved("RESTART"):
                    db.add_config('RESTART', dicts)
                else:
                    await db.edit_config("RESTART", dicts)
                config[var] = None               
            else:
                await m.edit(f"No env named {var} found. Nothing was changed.")
            return
        if var in config:
            m=await message.reply(f"Variable already found. Now edited to {value}")
        else:
            m=await message.reply(f"Variable not found, Now setting as new var.")
        await asyncio.sleep(2)
        k=await m.edit(f"Succesfully set {var} with value {value}, Now Restarting to take effect of changes...")
        dicts={"chat":k.chat.id, "msg_id":k.message_id}
        if not await db.is_saved("RESTART"):
            db.add_config('RESTART', dicts)
        else:
            await db.edit_config("RESTART", dicts)
        config[var] = str(value)
    else:
        await message.reply("You haven't provided any value for env, you should follow the correct format.\nExample: <code>/env CHAT=-1020202020202</code> to change or set CHAT var.\n<code>/env REPLY_MESSAGE= <code>To delete REPLY_MESSAGE.")



@Client.on_message(filters.command(['title', f"title@{Config.BOT_USERNAME}"]) & admin_filter)
async def edit_to_cusrom(client, message):
    if ' ' in message.text:
        c, t = message.text.split(" ", 1)
        k, re = await edit_title_custom(t)
        if not k:
            await message.reply(f"Errors occured while editing title, may be iam not an admin here or there may be no active voicechats.\n\nError message: {re}")
            return
        await message.reply(f"Succesfully edited title to {t}")
    else:
        await message.reply("Give me a title.")
    