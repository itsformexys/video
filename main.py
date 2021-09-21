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
from logger import LOGGER
try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from utils import manage_restart, sync_from_db, refresh_links
    from user import group_call
    from config import Config
    from pyrogram import idle
    from bot import bot
    import asyncio
    from database import Database
    import os
except ModuleNotFoundError:
    import os
    import sys
    import subprocess
    file=os.path.abspath("requirements.txt")
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', file, '--upgrade'])
    os.execl(sys.executable, sys.executable, *sys.argv)

db=Database()
scheduler = AsyncIOScheduler()

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
    if await db.is_saved("RESTART"):
        msg=await db.get_config("RESTART")
        try:
            await bot.edit_message_text(msg['chat'], msg['msg_id'], text="Succesfully restarted.")
            await db.del_config("RESTART")
        except:
            pass
    if Config.LOOP:
        await manage_restart()
    #await start_stream()
    scheduler.add_job(refresh_links, "interval", minutes=180, max_instances=50, misfire_grace_time=2)
    LOGGER.warning("Scheduler started.")
    scheduler.start()
    LOGGER.warning(f"{Config.BOT_USERNAME} Started.")
    await idle()
    LOGGER.warning("Stoping")
    await group_call.start()
    await bot.stop()

if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(main())


