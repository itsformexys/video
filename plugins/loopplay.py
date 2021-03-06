from pyrogram import Client, filters
from utils import audio_join_call, clear_audio_cache, clear_video_cache, download, get_admins, get_audio_raw, get_duration, get_height_and_width, is_admin, is_audio_codec, is_radio, progress_bar, get_buttons, get_link, import_play_list, leave_call, play, get_playlist_str, send_playlist, shuffle_playlist, start_stream, stream_from_link, sync_to_db, video_join_call
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from youtube_search import YoutubeSearch
from pyrogram import Client, filters
from pyrogram.types import Message
from youtube_dl import YoutubeDL
from datetime import datetime
from pyrogram import filters
from config import Config
from logger import LOGGER
from asyncio import sleep
import re
import os
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
    msg = await message.reply_text("⚡️ **Checking Recived input...**")
    if message.reply_to_message and message.reply_to_message.audio:        
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
            elif "http" in link:
                type='radio'
                file=link
                try:
                    k=is_radio(file)
                except:
                    k=False
                if not k:
                    return await msg.edit("This is an unsupported url, give me an m3u8 link.")
        elif " " in message.text:
            text = message.text.split(" ", 1)
            query = text[1]
            regex = r"^(?:https?:\/\/)?(?:www\.)?youtu\.?be(?:\.com)?\/?.*(?:watch|embed)?(?:.*v=|v\/|\/)([\w\-_]+)\&?"
            match = re.match(regex,query)
            if match:
                type="youtube"
                yturl=query
            elif "http" in query:
                type='radio'
                file=query
                msg=await msg.edit("Checking radio link..")
                try:
                    k=is_radio(file)
                except:
                    k=False
                if not k:
                    return await msg.edit("This is an unsupported url, give me an m3u8 link.")
            else:
                type="query"
                ysearch=query
        else:
            await msg.edit("You Didn't gave me anything to play.Reply to a video or a youtube link.")
            return
    user=f"[{message.from_user.first_name}](tg://user?id={message.from_user.id})"
    if type=="audio":
        ogdo=message.reply_to_message.audio.file_id
        await msg.edit("Downloading..")
        file=await message.reply_to_message.download(file_name="./tgd/", progress=progress_bar, progress_args=(message.reply_to_message.audio.file_size, time.time(), msg))
        await msg.edit("Coverting to raw file.")

    elif type=="youtube" or type=="query":
        if type=="youtube":
            msg = await msg.edit("⚡️ **Fetching Audio From YouTube...**")
            url=yturl
        elif type=="query":
            try:
                await msg.edit("⚡️ **Searching Audio From YouTube...**")
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
            await msg.edit("I was unable to download that audio.")
            return
        def_ydl_opts = {'quiet': True, 'prefer_insecure': False, "geo-bypass": True}
        with YoutubeDL(def_ydl_opts) as ydl:
            try:
                ydl_info = ydl.extract_info(url, download=False)
            except Exception as e:
                LOGGER.error(f"Errors occured while getting link from youtube video {e}")
                return await msg.edit("I was unable to download that audio.")
            urlr=None
            ogdo=url
            try:
                urlr=is_audio_codec(ydl_info)
            except:
                urlr=None
            if not urlr:
                return await msg.edit("I was unable to download that audio.")
        file=urlr
    elif type == 'radio':
        file=file
        ogdo = file
    else:
        await msg.edit("Unsupported URL")
        return
    await clear_audio_cache(delete=False)
    existing=Config.FILES.get("TG_AUDIO_FILE")
    if existing:
        try:
            os.remove(existing)
        except:
            pass
    if type=='audio':
        Config.FILES['TG_AUDIO_FILE']=file
    Config.DATA["AUDIO_DETAILS"] = {"type":type, "link":file, 'oglink':ogdo}
    try:
        dur=get_duration(file)
    except:
        dur=0
    print("Trigger")
    Config.DATA['AUDIO_DATA']={'dur':dur}
    raw_audio=await get_audio_raw(file)
    if not raw_audio:
        await msg.edit("Audio Unsupported.")
        return
    data=Config.DATA.get('VIDEO_DETAILS')
    if data:
        vlink=data['link']
        await video_join_call(vlink)
    else:
        await audio_join_call(raw_audio, is_raw=True)
    await msg.edit("Started Playing.")
    Config.LOOP=True
    await sync_to_db()


@Client.on_message(filters.command(["video", f"video@{Config.BOT_USERNAME}"]) & (filters.chat(Config.CHAT) | filters.private))
async def addideoloop_to_playlist(_, message: Message):
    data=Config.DATA.get('AUDIO_DATA')
    if not data:
        return await message.reply("You need to start an audio first.")
    if Config.ADMIN_ONLY == "Y":
        admins = await get_admins(Config.CHAT)
        if message.from_user.id not in admins:
            await message.reply_sticker("CAADBQADsQIAAtILIVYld1n74e3JuQI")
            return
    type=""
    yturl=""
    ysearch=""
    msg = await message.reply_text("⚡️ **Checking Telegram Media...**")
    if message.reply_to_message and message.reply_to_message.video:     
        type='video'
        m_video = message.reply_to_message.video       
    elif message.reply_to_message and message.reply_to_message.document:
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
            elif "http" in link:
                type='radio'
                file=link
                try:
                    k, l=get_height_and_width(file)
                except:
                    k=False
                if not k:
                    return await msg.edit("This is an unsupported url, give me an m3u8 link.")
        elif " " in message.text:
            text = message.text.split(" ", 1)
            query = text[1]
            regex = r"^(?:https?:\/\/)?(?:www\.)?youtu\.?be(?:\.com)?\/?.*(?:watch|embed)?(?:.*v=|v\/|\/)([\w\-_]+)\&?"
            match = re.match(regex,query)
            if match:
                type="youtube"
                yturl=query
            elif "http" in query:
                type='radio'
                file=query
                try:
                    k, l=get_height_and_width(file)
                except:
                    k=False
                if not k:
                    return await msg.edit("This is an unsupported url, give me an m3u8 link.")
            else:
                type="query"
                ysearch=query
            
        else:
            await msg.edit("You Didn't gave me anything to play.Reply to a video or a youtube link.")
            return
    user=f"[{message.from_user.first_name}](tg://user?id={message.from_user.id})"
    if type=="video":
        ogdo=m_video.file_id
        await msg.edit("Downloading..")
        file=await message.reply_to_message.download(file_name="tgd/", progress=progress_bar, progress_args=(m_video.file_size, time.time(), msg))
        await msg.edit("Converting raw files.")
    elif type=="youtube" or type=="query":
        if type=="youtube":
            await msg.edit("⚡️ **Fetching Video From YouTube...**")
            url=yturl
        elif type=="query":
            try:
                await msg.edit("⚡️ **Fetching Video From YouTube...**")
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
                return await msg.edit("Unable to download video")
        file=urlr
    elif type == 'radio':
        file=file
        ogdo=file
    await clear_video_cache(delete=False)
    existing=Config.FILES.get("TG_VIDEO_FILE")
    if existing:
        try:
            os.remove(existing)
        except:
            pass
    if type == "video":
        Config.FILES['TG_VIDEO_FILE']=file
    Config.DATA["VIDEO_DETAILS"] = {"type":type, "link":file, "oglink":ogdo}
    await video_join_call(file)
    await msg.edit("Started Video")    
    Config.LOOP=True
    await sync_to_db()



@Client.on_message(filters.command(["loop", f"loop@{Config.BOT_USERNAME}"]) & (filters.chat(Config.CHAT) | filters.private))
async def toggle_looping(_, message: Message):
    if ' ' in message.text:
        c, d = message.text.split(' ')
        if d == 'on':
            data=Config.DATA.get('AUDIO_DATA')
            if not data:
                Config.LOOP=False
                await sync_to_db()
                return await message.reply("No files are found for looping")
            Config.LOOP=True
            await sync_to_db()
            await message.reply("Looping turned on")
        elif d == 'off':
            Config.LOOP=False
            await sync_to_db()
            await message.reply("Looping toggled off.")
    else:
        await message.reply("What should I Do?\n Pass 'on' or 'off' along command.")
