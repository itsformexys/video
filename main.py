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

from utils import manage_loop_vidwo, manage_restart, start_stream, sync_from_db
from user import group_call
from logger import LOGGER
from config import Config
from pyrogram import idle
from bot import bot
import asyncio
import os

if not os.path.isdir("./downloads"):
    os.makedirs("./downloads")
else:
    for f in os.listdir("./downloads"):
        os.remove(f"./downloads/{f}")
       
if not os.path.isdir("./videodownloads"):
    os.makedirs("./videodownloads")
else:
    for f in os.listdir("./videodownloads"):
        os.remove(f"./videodownloads/{f}")

if not os.path.isdir("./audiodownloads"):
    os.makedirs("./audiodownloads")
else:
    for f in os.listdir("./audiodownloads"):
        os.remove(f"./audiodownloads/{f}")
async def main():
    await sync_from_db()
    await bot.start()
    Config.BOT_USERNAME = (await bot.get_me()).username
    await group_call.start()
    if Config.LOOP:
        await manage_restart()
    #await start_stream()
    LOGGER.warning(f"{Config.BOT_USERNAME} Started.")
    await idle()
    LOGGER.warning("Stoping")
    await group_call.start()
    await bot.stop()

if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(main())


