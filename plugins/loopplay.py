from pyrogram import Client, filters
from utils import audio_join_call, download, get_admins, is_admin, progress_bar, get_buttons, get_link, import_play_list, leave_call, play, get_playlist_str, send_playlist, shuffle_playlist, start_stream, stream_from_link, video_join_call
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from youtube_search import YoutubeSearch
from pyrogram import Client, filters
from pyrogram.types import Message
from youtube_dl import YoutubeDL
from datetime import datetime
from pyrogram import filters
from config import Config
from logger import LOGGER
import re
import time
admin_filter=filters.create(is_admin) 

@Client.on_message(filters.command(["audio", f"audio@{Config.BOT_USERNAME}"]) & (filters.chat(Config.CHAT) | filters.private))
async def loopaplay(_, message: Message):
    if Config.ADMIN_ONLY == "Y":
        admins = await get_admins(Config.CHAT)
        if message.from_user.id not in admins:
            return
    type=""
    yturl=""
    ysearch=""
    if message.reply_to_message and message.reply_to_message.audio:
        msg = await message.reply_text("⚡️ **Checking Telegram Media...**")
        type='audio'
        m_video = message.reply_to_message.audio
    else:
        if message.reply_to_message:
            link=message.reply_to_message.text
            regex = r"^(?:https?:\/\/)?(?:www\.)?youtu\.?be(?:\.com)?\/?.*(?:watch|embed)?(?:.*v=|v\/|\/)([\w\-_]+)\&?"
            match = re.match(regex,link)
            if match:
                type="youtube"
                yturl=link
        elif " " in message.text:
            text = message.text.split(" ", 1)
            query = text[1]
            regex = r"^(?:https?:\/\/)?(?:www\.)?youtu\.?be(?:\.com)?\/?.*(?:watch|embed)?(?:.*v=|v\/|\/)([\w\-_]+)\&?"
            match = re.match(regex,query)
            if match:
                type="youtube"
                yturl=query
            else:
                type="query"
                ysearch=query
        else:
            await message.reply_text("You Didn't gave me anything to play.Reply to a video or a youtube link.")
            return
    user=f"[{message.from_user.first_name}](tg://user?id={message.from_user.id})"
    if type=="audio":
        ogdo=message.reply_to_message.audio.file_id
        await message.reply("Downloading..")
        file=await message.reply_to_message.download(file_name="./tgd/", progress=progress_bar, progress_args=(message.reply_to_message.audio.file_size, time.time(), msg))
        Config.FILE['AUDIO_FILE']=file
    if type=="youtube" or type=="query":
        if type=="youtube":
            msg = await message.reply_text("⚡️ **Fetching Video From YouTube...**")
            url=yturl
        elif type=="query":
            try:
                msg = await message.reply_text("⚡️ **Fetching Video From YouTube...**")
                ytquery=ysearch
                results = YoutubeSearch(ytquery, max_results=1).to_dict()
                url = f"https://youtube.com{results[0]['url_suffix']}"
                title = results[0]["title"][:40]
            except Exception as e:
                await msg.edit(
                    "Song not found.\nTry inline mode.."
                )
                LOGGER.error(str(e))
                return
        else:
            await message.reply("I was unable to download that audio.")
        def_ydl_opts = {'quiet': True, 'prefer_insecure': False, "geo-bypass": True}
        with YoutubeDL(def_ydl_opts) as ydl:
            try:
                ydl_info = ydl.extract_info(url, download=False)
            except Exception as e:
                LOGGER.error(f"Errors occured while getting link from youtube video {e}")
                return await message.reply("I was unable to download that audio.")
            urlr=None
            ogdo=url
            for each in ydl_info['formats']:
                if each['acodec'] != 'none':
                    urlr=each['url']
                    break #prefer 640x360
                else:
                    continue
            if not urlr:
                await message.reply("I was unable to download that audio.")
        file=urlr
        k=await audio_join_call(file)
        await message.reply(k)
        Config.FILES["AUDIO_DETAILS"] = {"type":type, "link":file, 'oglink':ogdo}
        Config.LOOP=True




@Client.on_message(filters.command(["video", f"video@{Config.BOT_USERNAME}"]) & (filters.chat(Config.CHAT) | filters.private))
async def addideoloop_to_playlist(_, message: Message):
    if not Config.AUDIO_STATUS:
        return await message.reply("You need to start an audio first.")
    if Config.ADMIN_ONLY == "Y":
        admins = await get_admins(Config.CHAT)
        if message.from_user.id not in admins:
            await message.reply_sticker("CAADBQADsQIAAtILIVYld1n74e3JuQI")
            return
    type=""
    yturl=""
    ysearch=""
    if message.reply_to_message and message.reply_to_message.video:
        msg = await message.reply_text("⚡️ **Checking Telegram Media...**")
        type='video'
        m_video = message.reply_to_message.video       
    elif message.reply_to_message and message.reply_to_message.document:
        msg = await message.reply_text("⚡️ **Checking Telegram Media...**")
        m_video = message.reply_to_message.document
        type='video'
        if not "video" in m_video.mime_type:
            return await msg.edit("The given file is invalid")
    else:
        if message.reply_to_message:
            link=message.reply_to_message.text
            regex = r"^(?:https?:\/\/)?(?:www\.)?youtu\.?be(?:\.com)?\/?.*(?:watch|embed)?(?:.*v=|v\/|\/)([\w\-_]+)\&?"
            match = re.match(regex,link)
            if match:
                type="youtube"
                yturl=link
        elif " " in message.text:
            text = message.text.split(" ", 1)
            query = text[1]
            regex = r"^(?:https?:\/\/)?(?:www\.)?youtu\.?be(?:\.com)?\/?.*(?:watch|embed)?(?:.*v=|v\/|\/)([\w\-_]+)\&?"
            match = re.match(regex,query)
            if match:
                type="youtube"
                yturl=query
            else:
                type="query"
                ysearch=query
        else:
            await message.reply_text("You Didn't gave me anything to play.Reply to a video or a youtube link.")
            return
    user=f"[{message.from_user.first_name}](tg://user?id={message.from_user.id})"
    if type=="video":
        ogdo=m_video.file_id
        await message.reply("Downloading..")
        file=await message.reply_to_message.download(file_name="tgd/", progress=progress_bar, progress_args=(m_video.file_size, time.time(), msg))
    elif type=="youtube" or type=="query":
        if type=="youtube":
            msg = await message.reply_text("⚡️ **Fetching Video From YouTube...**")
            url=yturl
        elif type=="query":
            try:
                msg = await message.reply_text("⚡️ **Fetching Video From YouTube...**")
                ytquery=ysearch
                results = YoutubeSearch(ytquery, max_results=1).to_dict()
                url = f"https://youtube.com{results[0]['url_suffix']}"
                title = results[0]["title"][:40]
            except Exception as e:
                await msg.edit(
                    "Song not found.\nTry inline mode.."
                )
                LOGGER.error(str(e))
                return
        else:
            return
        def_ydl_opts = {'quiet': True, 'prefer_insecure': False, "geo-bypass": True}
        with YoutubeDL(def_ydl_opts) as ydl:
            try:
                ydl_info = ydl.extract_info(url, download=False)
            except Exception as e:
                LOGGER.error(f"Errors occured while getting link from youtube video {e}")
                return await message.reply("Unable to download video")
            urlr=None
            ogdo=url
            for each in ydl_info['formats']:
                if each['width'] == 640 \
                    and each['acodec'] != 'none' \
                        and each['vcodec'] != 'none':
                        urlr=each['url']
                        break #prefer 640x360
                elif each['width'] \
                    and each['width'] <= 1280 \
                        and each['acodec'] != 'none' \
                            and each['vcodec'] != 'none':
                            urlr=each['url']
                            continue # any other format less than 1280
                else:
                    continue
            if url:
                file=urlr
            else:
                return await message.reply("Unable to download video")
       
        file=urlr
    k=await video_join_call(file)
    await message.reply(k)
    Config.FILES["VIDEO_DETAILS"] = {"type":type, "link":file, "oglink":ogdo}
    Config.LOOP=True

        