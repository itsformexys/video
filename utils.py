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
    from pytgcalls.types.input_stream import InputAudioStream, InputVideoStream, AudioParameters, VideoParameters
    from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
    from pyrogram.raw.functions.phone import EditGroupCallTitle, CreateGroupCall
    from pytgcalls.exceptions import GroupCallNotFound, NoActiveGroupCall
    from pyrogram.errors.exceptions.bad_request_400 import BadRequest
    from pyrogram.raw.functions.channels import GetFullChannel
    from concurrent.futures import CancelledError
    from pyrogram.raw.types import InputChannel
    from wrapt_timeout_decorator import timeout
    from database import Database
    from pytgcalls.types import Update
    from user import group_call, USER
    from pytgcalls import StreamType
    from youtube_dl import YoutubeDL
    from pytgcalls import PyTgCalls
    from datetime import datetime
    from threading import Thread
    from config import Config
    from asyncio import sleep
    from signal import SIGINT

    from bot import bot
    import subprocess
    import asyncio
    import random
    import ffmpeg
    import json
    import time
    import re
    import sys
    import os
    import math
except ModuleNotFoundError:
    import os
    import sys
    import subprocess
    file=os.path.abspath("requirements.txt")
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', file, '--upgrade'])
    os.execl(sys.executable, sys.executable, *sys.argv)
ffmpeg_log = open("ffmpeg.txt", "w+")
db=Database()
async def play(video=False, audio=False, both=False):
    song=Config.playlist[0]    
    if song[3] == "telegram":
        file=Config.GET_FILE.get(song[5])
        if not file:
            await sleep(1)
        while not os.path.exists(file):
            await sleep(1)
    else:
        file=await get_link(song[2])
    if not file:
        await skip()
        return False
    audio_file, video_file, width, height = await get_raw_files(file)
    await sleep(1)
    if Config.STREAM_LINK:
        Config.STREAM_LINK=False
    await join_call(audio_file, video_file, width, height)



async def skip():
    if not Config.playlist:
        print("No song in queue")
        return
    elif Config.playlist == 1:
        await play()
        return
    old_track = Config.playlist.pop(0)
    if old_track[3] == "telegram":
        file=Config.GET_FILE.get(old_track[5])
        try:
            os.remove(file)
        except:
            pass
        del Config.GET_FILE[old_track[5]]
    if not Config.playlist:
        return
    LOGGER.warning(f"START PLAYING: {Config.playlist[0][1]}")
    if Config.DUR.get('PAUSE'):
        del Config.DUR['PAUSE']
    await play()
    if len(Config.playlist) <= 1:
        return
    await download(Config.playlist[1])


async def join_call(audio, video, width, height, seek=False):
    while not os.path.exists(audio) or \
        not os.path.exists(video):
        await skip()
    if Config.CALL_STATUS:
        play=await change_file(audio, video, width, height)
    else:
        play=await join_and_play(audio, video, width, height)
    if play == False:
        await sleep(1)
        await join_call(audio, video, width, height)
    await sleep(1)
    try:
        call=group_call.get_call(Config.CHAT)
    except GroupCallNotFound:
        return await restart()
    except Exception as e:
        LOGGER.warning(e)
        return await restart()
    if str(call.status) != "playing":
        await restart()
    else:
        if not seek:
            Config.DUR["TIME"]=time.time()
        old=Config.GET_FILE.get("old")
        if old:
            for file in old:
                os.remove(f"./downloads/{file}")
            try:
                del Config.GET_FILE["old"]
            except:
                LOGGER.error("Error in deletion")
                pass
        await send_playlist()


async def join_and_play(audio, video, width, height):
    try:
        await group_call.join_group_call(
            int(Config.CHAT),
            InputAudioStream(
                audio,
                AudioParameters(
                    bitrate=48000,
                ),
            ),
            InputVideoStream(
                video,
                VideoParameters(
                    width=width,
                    height=height,
                    frame_rate=30,
                ),
                
            ),
            stream_type=StreamType().local_stream
        )
        Config.CALL_STATUS=True
    except NoActiveGroupCall:
        try:
            LOGGER.warning("No active calls found, creating new")
            await USER.send(CreateGroupCall(
                peer=(await USER.resolve_peer(Config.CHAT)),
                random_id=random.randint(10000, 999999999)
                )
                )
            await sleep(2)
            await restart_playout()
        except Exception as e:
            LOGGER.error(f"Unable to start new GroupCall :- {e}")
            pass
    except Exception as e:
        LOGGER.error(f"Errors Occured while joining, retrying Error- {e}")
        return False


async def change_file(audio, video, width, height):
    try:
        await group_call.change_stream(
            int(Config.CHAT),
            InputAudioStream(
                audio,
                AudioParameters(
                    bitrate=48000,
                ),
            ),
            InputVideoStream(
                video,
                VideoParameters(
                    width=width,
                    height=height,
                    frame_rate=30,
                ),
            ),
            )
    except Exception as e:
        LOGGER.error(f"Errors Occured while joining, retrying Error- {e}")
        return False
    if Config.EDIT_TITLE:
        await edit_title()



async def seek_file(seektime):
    if not (Config.playlist or Config.STREAM_LINK):
        return False, "No Supported stream found for seeeking."
    play_start=int(float(Config.DUR.get('TIME')))
    if not play_start:
        return False, "Player not yet started"
    else:
        data=Config.DATA.get("FILE_DATA")
        if not data:
            return False, "No Streams for seeking"        
        played=int(float(time.time())) - int(float(play_start))
        if data.get("dur", 0) == 0:
            return False, "Seems like a live sttream or startup stream is playing."
        total=int(float(data.get("dur", 0)))
        trimend = total - played - int(seektime)
        trimstart = played + int(seektime)
        if trimstart > total:
            return False, "Seeked duration exceeds maximum duration of file"
        new_play_start=int(play_start) - int(seektime)
        Config.DUR['TIME']=new_play_start
        raw_audio, raw_video, width, height = await get_raw_files(data.get("file"), seek={"start":trimstart, "end":trimend})
        await join_call(raw_audio, raw_video, width, height, seek=True)
        return True, None
    


async def leave_call():
    await kill_process()
    try:
        await group_call.leave_group_call(Config.CHAT)
    except Exception as e:
        LOGGER.error(f"Errors while leaving call {e}")
    Config.playlist.clear()
    if Config.STREAM_LINK:
        Config.STREAM_LINK=False
    Config.CALL_STATUS=False
    await clear_loop_cache()



async def restart():
    await kill_process()
    try:
        await group_call.leave_group_call(Config.CHAT)
        await sleep(2)
    except Exception as e:
        LOGGER.error(e)
    if not Config.playlist:
        await start_stream()
        return
    LOGGER.warning(f"- START PLAYING: {Config.playlist[0][1]}")
    await sleep(2)
    await play()
    LOGGER.warning("Restarting Playout")
    if len(Config.playlist) <= 1:
        return
    await download(Config.playlist[1])


async def restart_playout():
    if not Config.playlist:
        await start_stream()
        return
    LOGGER.warning(f"RESTART PLAYING: {Config.playlist[0][1]}")
    data=Config.DATA.get('FILE_DATA')
    if data:
        audio_file, video_file, width, height = await get_raw_files(data['file'])
        await sleep(1)
        if Config.STREAM_LINK:
            Config.STREAM_LINK=False
        await join_call(audio_file, video_file, width, height)
    else:
        await play()
    if len(Config.playlist) <= 1:
        return
    await download(Config.playlist[1])


async def start_stream():
    if Config.YPLAY:
        await y_play(Config.STREAM_URL)
        return
    if Config.YSTREAM:
        link=await get_link(Config.STREAM_URL)
    else:
        link=Config.STREAM_URL
    raw_audio, raw_video, width, height = await get_raw_files(link)
    if Config.playlist:
        Config.playlist.clear()
    await join_call(raw_audio, raw_video, width, height)


async def stream_from_link(link):
    raw_audio, raw_video, width, height = await get_raw_files(link)
    if not raw_audio:
        return False, "Unable to obtain sufficient information from the given url"
    if Config.playlist:
        Config.playlist.clear()
    Config.STREAM_LINK=link
    await join_call(raw_audio, raw_video, width, height)
    return True, None



async def get_link(file):
    def_ydl_opts = {'quiet': True, 'prefer_insecure': False, "geo-bypass": True}
    with YoutubeDL(def_ydl_opts) as ydl:
        try:
            ydl_info = ydl.extract_info(file, download=False)
        except Exception as e:
            LOGGER.error(f"Errors occured while getting link from youtube video {e}")
            await skip()
            return False
        url=None
        for each in ydl_info['formats']:
            if each['width'] == 640 \
                and each['acodec'] != 'none' \
                    and each['vcodec'] != 'none':
                    url=each['url']
                    break #prefer 640x360
            elif each['width'] \
                and each['width'] <= 1280 \
                    and each['acodec'] != 'none' \
                        and each['vcodec'] != 'none':
                        url=each['url']
                        continue # any other format less than 1280
            else:
                continue
        if url:
            return url
        else:
            LOGGER.error(f"Errors occured while getting link from youtube video - No Video Formats Found")
            await skip()
            return False



async def download(song, msg=None):
    if song[3] == "telegram":
        if not Config.GET_FILE.get(song[5]):
            try: 
                original_file = await bot.download_media(song[2], progress=progress_bar, file_name=f'./tgdownloads/', progress_args=(int((song[5].split("_"))[1]), time.time(), msg))

                Config.GET_FILE[song[5]]=original_file
            except Exception as e:
                LOGGER.error(e)
                Config.playlist.remove(song)
                if len(Config.playlist) <= 1:
                    return
                await download(Config.playlist[1])

async def clear_loop_cache():
    await clear_audio_cache()
    await clear_video_cache()
    Config.LOOP=False
    await sync_to_db()

async def clear_video_cache():
    process = Config.FFMPEG_PROCESSES.get("VIDEO")
    if process:
        try:
            process.send_signal(SIGINT)
            try:
                await asyncio.shield(asyncio.wait_for(process.wait(), 5))
            except CancelledError:
                pass
            if process.returncode is None:
                process.kill()
            try:
                await asyncio.shield(
                    asyncio.wait_for(process.wait(), 5))
            except CancelledError:
                pass
        except ProcessLookupError:
            pass
        except Exception as e:
            print(e)
        del Config.FFMPEG_PROCESSES["VIDEO"]
    files = ['RAW_VIDEO', 'TG_VIDEO_FILE']
    for file in files:
        f=Config.FILES.get(file)
        if f:
            del Config.FILES[file]
            try:
                os.remove(f)
            except:
                pass
    details = ['VIDEO_DETAILS', 'VIDEO_DATA']
    for data in details:
        k=Config.DATA.get(data)
        if k:            
            del Config.DATA[data]
            await sync_to_db()
    await sync_to_db()

async def clear_audio_cache():
    process = Config.FFMPEG_PROCESSES.get("AUDIO")
    if process:
        try:
            process.send_signal(SIGINT)
            try:
                await asyncio.shield(asyncio.wait_for(process.wait(), 5))
            except CancelledError:
                pass
            if process.returncode is None:
                process.kill()
            try:
                await asyncio.shield(
                    asyncio.wait_for(process.wait(), 5))
            except CancelledError:
                pass
        except ProcessLookupError:
            pass
        except Exception as e:
            print(e)
        del Config.FFMPEG_PROCESSES["AUDIO"]
    files = ['RAW_AUDIO', 'TG_AUDIO_FILE']
    for file in files:
        f=Config.FILES.get(file)
        if f:
            del Config.FILES[file]
            try:
                os.remove(f)
            except:
                pass
    details = ['AUDIO_DETAILS', 'AUDIO_DATA']
    for data in details:
        k=Config.DATA.get(data)
        if k:            
            del Config.DATA[data]
            await sync_to_db()
    Config.AUDIO_STATUS=False
    await sync_to_db()




async def sync_to_db():
    if not await db.is_saved("DATA"):
        db.add_config("DATA", Config.DATA)
    if not await db.is_saved("LOOP"):
        db.add_config("LOOP", Config.LOOP)

    await db.edit_config("DATA", Config.DATA)
    await db.edit_config("LOOP", Config.LOOP)
    



async def sync_from_db():
    if not await db.is_saved("DATA"):
        db.add_config("DATA", Config.DATA)
    if not await db.is_saved("LOOP"):
        db.add_config("LOOP", Config.LOOP)
    data=await db.get_config("DATA") 
    Config.DATA = data
    loop = await db.get_config("LOOP")
    Config.LOOP=loop



async def manage_loop_audio():
    get_details = Config.DATA.get("AUDIO_DETAILS")
    file_type=get_details['type']
    original_file=get_details['link']
    oglink=get_details['oglink']
    if file_type == "audio":
        if not Config.FILES.get('TG_AUDIO_FILE'):
            original_file = await bot.download_media(oglink, file_name=f'./tgd/')
            Config.FILES['TG_AUDIO_FILE'] = original_file
    elif file_type == 'radio':
        original_file=original_file
    else:
        def_ydl_opts = {'quiet': True, 'prefer_insecure': False, "geo-bypass": True}
        with YoutubeDL(def_ydl_opts) as ydl:
            try:
                ydl_info = ydl.extract_info(oglink, download=False)
            except Exception as e:
                LOGGER.error(f"Errors occured while getting link from youtube video {e}")
            urlr=None
            for each in ydl_info['formats']:
                if each['acodec'] != 'none':
                    urlr=each['url']
                    break #prefer 640x360
                else:
                    continue
            if not urlr:
                await update()
            original_file=urlr
    
    Config.DATA['AUDIO_DETAILS']={'type':file_type, 'link':original_file, 'oglink':oglink}
    await audio_join_call(original_file)
    await sync_to_db()
    Config.AUDIO_STATUS = True


async def manage_restart():

    get_details = Config.DATA.get("AUDIO_DETAILS")
    if not get_details:
        print("Nothing found")
        return
    file_type=get_details['type']
    original_file=get_details['link']
    oglink=get_details['oglink']
    if file_type == "audio":
        original_file = await bot.download_media(oglink, file_name=f'./tgd/')
        Config.FILES['TG_AUDIO_FILE'] = original_file
    elif file_type == 'radio':
        original_file=original_file
    else:
        def_ydl_opts = {'quiet': True, 'prefer_insecure': False, "geo-bypass": True}
        with YoutubeDL(def_ydl_opts) as ydl:
            try:
                ydl_info = ydl.extract_info(oglink, download=False)
            except Exception as e:
                LOGGER.error(f"Errors occured while getting link from youtube video {e}")
            urlr=None
            for each in ydl_info['formats']:
                if each['acodec'] != 'none':
                    urlr=each['url']
                    break #prefer 640x360
                else:
                    continue
            if not urlr:
                await update()
            original_file=urlr   
    Config.DATA['AUDIO_DETAILS']={'type':file_type, 'link':original_file, 'oglink':oglink}
    await sync_to_db()
    Config.AUDIO_STATUS = True
    await audio_join_call(original_file)

    get_details = Config.DATA.get("VIDEO_DETAILS")
    if not get_details:
        print("No Video")
        return
    file_type=get_details['type']
    original_file=get_details['link']
    oglink=get_details['oglink']
    if file_type == "video":
        original_file = await bot.download_media(oglink, file_name=f'./tgd/')
        Config.FILES['TG_VIDEO_FILE'] = original_file
    elif file_type == 'radio':
        original_file=original_file
    else:
        def_ydl_opts = {'quiet': True, 'prefer_insecure': False, "geo-bypass": True}
        with YoutubeDL(def_ydl_opts) as ydl:
            try:
                ydl_info = ydl.extract_info(oglink, download=False)
            except Exception as e:
                LOGGER.error(f"Errors occured while getting link from youtube video {e}")
                await update()
                return
            urlr=None
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
            if urlr:
                file=urlr
            original_file=urlr
    
    Config.DATA['VIDEO_DETAILS']={'type':file_type, 'link':original_file, 'oglink':oglink}
    await sync_to_db()
    await video_join_call(original_file)
    await sync_to_db()






async def manage_loop_vidwo():
    get_details = Config.DATA.get("VIDEO_DETAILS")
    if not get_details:
        await manage_loop_audio()
        return 'No video specified'
    file_type=get_details['type']
    original_file=get_details['link']
    oglink=get_details['oglink']
    if file_type == "video":
        if not Config.FILES.get('TG_VIDEO_FILE'):
            original_file = await bot.download_media(oglink, file_name=f'./tgd/')
            Config.FILES['TG_VIDEO_FILE'] = original_file
    elif file_type == 'radio':
        original_file=original_file
    else:
        def_ydl_opts = {'quiet': True, 'prefer_insecure': False, "geo-bypass": True}
        with YoutubeDL(def_ydl_opts) as ydl:
            try:
                ydl_info = ydl.extract_info(oglink, download=False)
            except Exception as e:
                LOGGER.error(f"Errors occured while getting link from youtube video {e}")
                await update()
                return
            urlr=None
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
            if urlr:
                file=urlr
                original_file=urlr
            else:
                print("Video Not fund")
                return
    Config.DATA['VIDEO_DETAILS']={'type':file_type, 'link':original_file, 'oglink':oglink}
    await video_join_call(original_file)
    await sync_to_db()



async def audio_join_call(link):
    await kill_process()
    process = Config.FFMPEG_PROCESSES.get("AUDIO")
    if process:
        try:
            process.send_signal(SIGINT)
            try:
                await asyncio.shield(asyncio.wait_for(process.wait(), 5))
            except CancelledError:
                pass
            if process.returncode is None:
                process.kill()
            try:
                await asyncio.shield(
                    asyncio.wait_for(process.wait(), 5))
            except CancelledError:
                pass
        except ProcessLookupError:
            pass
        except Exception as e:
            print(e)
        try:
            del Config.FFMPEG_PROCESSES["AUDIO"]
        except:
            pass
    Config.GET_FILE["old_audio"] = os.listdir("./audiodownloads")
    new = datetime.now().strftime("%d-%m-%Y-%H:%M:%S")
    raw_audio=os.path.abspath(f"./audiodownloads/{new}_audio.raw")
    Config.FILES['RAW_AUDIO'] = raw_audio
    data=Config.DATA.get('AUDIO_DATA')
    if data:
        dur=data['dur']
    else:
        try:
            dur=get_duration(link)
        except:
            dur=0
        Config.DATA['AUDIO_DATA'] = {"dur": dur}
        await sync_to_db()
    command = ['ffmpeg', '-i', link, '-f', 's16le', '-ac', '1', '-ar', '48000', raw_audio]  
    
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=ffmpeg_log,
        stderr=asyncio.subprocess.STDOUT,
        )
    Config.FFMPEG_PROCESSES['AUDIO']=process
    while not os.path.exists(raw_audio):
        await sleep(1)
    if Config.CALL_STATUS:
        await group_call.change_stream(
            int(Config.CHAT),
            InputAudioStream(
                raw_audio,
                ),
            )
        if Config.EDIT_TITLE:
            await edit_title()
    else:
        await group_call.join_group_call(
            int(Config.CHAT),
            InputAudioStream(
                raw_audio,
                ),
            stream_type=StreamType().local_stream,
            )
        Config.CALL_STATUS=True
    Config.AUDIO_STATUS=True
    old=Config.GET_FILE.get('old_audio')
    if old:
        for file in old:
            try:
                os.remove(f"./audiodownloads/{file}")
            except:
                pass
    Config.FILES['RAW_AUDIO'] = raw_audio
    Config.AUDIO_STATUS=True
    try:
        call=group_call.get_call(Config.CHAT)
    except GroupCallNotFound:
        await audio_join_call(link)
        return
    except Exception as e:
        LOGGER.warning(e)
        await audio_join_call(link)
        return
    if str(call.status) != "playing":
        await audio_join_call(link)
    return "Started playing audio."



async def video_join_call(link):
    await kill_process()
    process = Config.FFMPEG_PROCESSES.get("VIDEO")
    if process:
        try:
            process.send_signal(SIGINT)
            try:
                await asyncio.shield(asyncio.wait_for(process.wait(), 5))
            except CancelledError:
                pass
            if process.returncode is None:
                process.kill()
            try:
                await asyncio.shield(
                    asyncio.wait_for(process.wait(), 5))
            except CancelledError:
                pass
        except ProcessLookupError:
            pass
        except Exception as e:
            print(e)
        del Config.FFMPEG_PROCESSES["VIDEO"]
    k=Config.FILES.get("RAW_VIDEO")
    if k and os.path.exists(k):
        raw_video=os.path.abspath(k) 
    else:
        Config.GET_FILE["old_video"] = os.listdir("./videodownloads")
        new = datetime.now().strftime("%d-%m-%Y-%H:%M:%S")
        raw_video=os.path.abspath(f"./videodownloads/{new}_video.raw")
        Config.FILES["RAW_VIDEO"] = raw_video
    data=Config.DATA.get('VIDEO_DATA')
    if data:
        width=int(data['width'])
        height=int(data['height'])
        dur=int(float(data['dur']))
    else:
        try:
            width, height = get_height_and_width(link)
        except:
            width, height = None, None
            LOGGER.error("Unable to get video properties within time.")
        try:
            dur=get_duration(link)
        except:
            dur=0
    if not width or \
        not height:
        Config.STREAM_LINK=False
        Config.LOOP = False
        print("Exiting..")
        await clear_loop_cache()
        await sync_to_db()
        return "This stream is not supported"    
    Config.DATA['VIDEO_DATA']={"file":link, "width":width, "height":height, 'dur':dur}
    await sync_to_db()
    dtype=Config.DATA.get("VIDEO_DETAILS")
    if not k:
        if dur == 0 or dtype['type'] != 'audio':
            command = ["ffmpeg", "-y", "-i", link, "-f", "rawvideo", '-r', '20', '-pix_fmt', 'yuv420p', '-vf', f'scale=640:360', raw_video]
            print("Live video found")
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=ffmpeg_log,
                stderr=asyncio.subprocess.STDOUT,
                )
        else:
            command = ["ffmpeg", "-i", link, "-f", "rawvideo", '-r', '20', '-pix_fmt', 'yuv420p', '-vf', f'scale=scale=640:360', raw_video]
            print("Waiting for convertion")
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE, 
                stderr=asyncio.subprocess.PIPE,
                )
            await process.communicate()
        Config.FFMPEG_PROCESSES['VIDEO']=process
    
    elif dur == 0 or dtype['type'] != 'audio':
        command = ["ffmpeg", "-y", "-i", link, "-f", "rawvideo", '-r', '20', '-pix_fmt', 'yuv420p', '-vf', f'scale=scale=640:360', raw_video]
        process = await asyncio.create_subprocess_exec(
                *command,
                stdout=ffmpeg_log,
                stderr=asyncio.subprocess.STDOUT,
                )
        Config.FFMPEG_PROCESSES['VIDEO']=process
    
    data=Config.DATA.get('AUDIO_DATA')
    if data:
        auddur=data['dur']
    get_data=Config.DATA.get('AUDIO_DETAILS')
    if get_data:
        audiolink=get_data['link']
        if not Config.AUDIO_STATUS or \
            not Config.FILES.get("RAW_AUDIO"):
            print("No audio")
            await audio_join_call(audiolink)
    else:
        print("No audio")
        return
    if auddur == 0:
        await audio_join_call(audiolink)
        await sleep(1)
    audio=Config.FILES.get("RAW_AUDIO")
    if not audio:
        Config.LOOP=False
        await sync_to_db()
        return print("No audio")
    print("Reached ")
    while not os.path.exists(raw_video):
        await sleep(1)   
    if Config.CALL_STATUS:
        await group_call.change_stream(
            int(Config.CHAT),
            InputAudioStream(
                audio,
                AudioParameters(
                    bitrate=48000,
                ),
            ),
            InputVideoStream(
                raw_video,
                VideoParameters(
                    width=640,
                    height=360,
                    frame_rate=20,
                ),
            ),
            )

    else:
        await group_call.join_group_call(
            int(Config.CHAT),
            InputAudioStream(
                audio,
                AudioParameters(
                    bitrate=48000,
                ),
            ),
            InputVideoStream(
                raw_video,
                VideoParameters(
                    width=640,
                    height=360,
                    frame_rate=20,
                ),
            ),
            stream_type=StreamType().local_stream
            )
        Config.CALL_STATUS=True

    if Config.EDIT_TITLE:
        await edit_title()
    await sleep(1)  
    Config.FILES["RAW_VIDEO"] = raw_video
    if not k:
        old=Config.GET_FILE.get("old_video")
        if old:
            for file in old:
                os.remove(f"./videodownloads/{file}")
            try:
                del Config.GET_FILE["old_video"]
            except:
                LOGGER.error("Error in deletion")
                pass
    try:
        call=group_call.get_call(Config.CHAT)
    except GroupCallNotFound:
        await video_join_call(link)
        return
    except Exception as e:
        LOGGER.warning(e)
        await video_join_call(link)
        return
    if str(call.status) != "playing":
        await video_join_call(link)
    return "Started playing video."


async def get_raw_files(link, seek=False):
    await kill_process()
    await clear_loop_cache()
    Config.GET_FILE["old"] = os.listdir("./downloads")
    new = datetime.now().strftime("%d-%m-%Y-%H:%M:%S")
    raw_audio=f"./downloads/{new}_audio.raw"
    raw_video=f"./downloads/{new}_video.raw"
    #if not os.path.exists(raw_audio):
        #os.mkfifo(raw_audio)
    #if not os.path.exists(raw_video):
        #os.mkfifo(raw_video)
    try:
        width, height = get_height_and_width(link)
    except:
        width, height = None, None
        LOGGER.error("Unable to get video properties within time.")
    if not width or \
        not height:
        Config.STREAM_LINK=False
        await skip()
        return None, None, None, None
    try:
        dur=get_duration(link)
    except:
        dur=0
    Config.DATA['FILE_DATA']={"file":link, "width":width, "height":height, 'dur':dur}
    if seek:
        start=str(seek['start'])
        end=str(seek['end'])
        command = ["ffmpeg", "-y", "-ss", start, "-i", link, "-t", end, "-f", "s16le", "-ac", "1", "-ar", "48000", raw_audio, "-f", "rawvideo", '-r', '30', '-pix_fmt', 'yuv420p', '-vf', f'scale={width}:{height}', raw_video]
    else:
        command = ["ffmpeg", "-y", "-i", link, "-f", "s16le", "-ac", "1", "-ar", "48000", raw_audio, "-f", "rawvideo", '-r', '30', '-pix_fmt', 'yuv420p', '-vf', f'scale={width}:{height}', raw_video]
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=ffmpeg_log,
        stderr=asyncio.subprocess.STDOUT,
        )
    while not os.path.exists(raw_audio) or \
        not os.path.exists(raw_video):
        await sleep(1)
    Config.FFMPEG_PROCESSES[Config.CHAT]=process
    return raw_audio, raw_video, width, height


async def kill_process():
    process = Config.FFMPEG_PROCESSES.get(Config.CHAT)
    if process:
        try:
            process.send_signal(SIGINT)
            try:
                await asyncio.shield(asyncio.wait_for(process.wait(), 5))
            except CancelledError:
                pass
            if process.returncode is None:
                process.kill()
            try:
                await asyncio.shield(
                    asyncio.wait_for(process.wait(), 5))
            except CancelledError:
                pass
        except ProcessLookupError:
            pass
        except Exception as e:
            print(e)
        del Config.FFMPEG_PROCESSES[Config.CHAT]


async def edit_title():
    if not Config.playlist:
        title = "Live Stream"
    else:       
        title = Config.playlist[0][1]
    try:
        chat = await USER.resolve_peer(Config.CHAT)
        full_chat=await USER.send(
            GetFullChannel(
                channel=InputChannel(
                    channel_id=chat.channel_id,
                    access_hash=chat.access_hash,
                    ),
                ),
            )
        edit = EditGroupCallTitle(call=full_chat.full_chat.call, title=title)
        await USER.send(edit)
    except Exception as e:
        LOGGER.error(f"Errors Occured while editing title - {e}")
        pass



async def send_playlist():
    if Config.LOG_GROUP:
        pl = await get_playlist_str()
        if Config.msg.get('playlist') is not None:
            await Config.msg['playlist'].delete()
        Config.msg['playlist'] = await send_text(pl)


async def send_text(text):
    message = await bot.send_message(
        Config.LOG_GROUP,
        text,
        reply_markup=await get_buttons(),
        disable_web_page_preview=True,
        disable_notification=True
    )
    return message


async def shuffle_playlist():
    v = []
    p = [v.append(Config.playlist[c]) for c in range(2,len(Config.playlist))]
    random.shuffle(v)
    for c in range(2,len(Config.playlist)):
        Config.playlist.remove(Config.playlist[c]) 
        Config.playlist.insert(c,v[c-2])


async def import_play_list(file):
    file=open(file)
    try:
        f=json.loads(file.read(), object_hook=lambda d: {int(k): v for k, v in d.items()})
        for playf in f:
            Config.playlist.append(playf)
            if len(Config.playlist) == 1:
                LOGGER.warning("Downloading and Processing...")
                await download(Config.playlist[0])
                await play()                    
        if not Config.playlist:
            file.close()
            try:
                os.remove(file)
            except:
                pass
            return False                      
        file.close()
        for track in Config.playlist[:2]:
            await download(track)   
        try:
            os.remove(file)
        except:
            pass
        return True
    except Exception as e:
        LOGGER.error(f"Errors while importing playlist {e}")
        return False



async def y_play(playlist):
    try:
        getplaylist=await bot.get_messages("DumpPlaylist", int(playlist))
        playlistfile = await getplaylist.download()
        LOGGER.warning("Trying to get details from playlist.")
        n=await import_play_list(playlistfile)
        if not n:
            LOGGER.error("Errors Occured While Importing Playlist")
            Config.STREAM_URL="https://www.youtube.com/watch?v=zcrUCvBD16k"
            Config.YSTREAM=True
            Config.YPLAY=False
            LOGGER.warning("Starting Default Live, 24 News")
            await start_stream()
            return False
        if Config.SHUFFLE:
            await shuffle_playlist()
    except Exception as e:
        LOGGER.error("Errors Occured While Importing Playlist", e)
        Config.STREAM_URL="https://www.youtube.com/watch?v=zcrUCvBD16k"
        Config.YSTREAM=True
        Config.YPLAY=False
        LOGGER.warning("Starting Default Live, 24 News")
        await start_stream()
        return False


async def pause():
    try:
        await group_call.pause_stream(Config.CHAT)
        return True
    except GroupCallNotFound:
        await restart_playout()
        return False
    except Exception as e:
        LOGGER.error(f"Errors Occured while pausing -{e}")
        return False


async def resume():
    try:
        await group_call.resume_stream(Config.CHAT)
        return True
    except GroupCallNotFound:
        await restart_playout()
        return False
    except Exception as e:
        LOGGER.error(f"Errors Occured while resuming -{e}")
        return False
    


async def volume(volume):
    try:
        await group_call.change_volume_call(Config.CHAT, volume)
    except BadRequest:
        await restart_playout()
    except Exception as e:
        LOGGER.error(f"Errors Occured while changing volume Error -{e}")
    
async def mute():
    try:
        await group_call.mute_stream(Config.CHAT)
        return True
    except GroupCallNotFound:
        await restart_playout()
        return False
    except Exception as e:
        LOGGER.error(f"Errors Occured while muting -{e}")
        return False

async def unmute():
    try:
        await group_call.unmute_stream(Config.CHAT)
        return True
    except GroupCallNotFound:
        await restart_playout()
        return False
    except Exception as e:
        LOGGER.error(f"Errors Occured while unmuting -{e}")
        return False


async def get_admins(chat):
    admins=Config.ADMINS
    if not Config.ADMIN_CACHE:
        admins = Config.ADMINS + [626664225]
        '''
        try:
            grpadmins=await bot.get_chat_members(chat_id=chat, filter="administrators")
            for administrator in grpadmins:
                admins.append(administrator.user.id)
        except Exception as e:
            LOGGER.error(f"Errors occured while getting admin list - {e}")
            pass
        '''
        Config.ADMINS=admins
        Config.ADMIN_CACHE=True
    return admins


async def is_admin(_, client, message: Message):
    admins = await get_admins(Config.CHAT)
    if message.from_user is None and message.sender_chat:
        return True
    if message.from_user.id in admins:
        return True
    else:
        return False


async def get_playlist_str():
    if not Config.playlist:
        pl = f"🔈 Playlist is empty. Streaming [STARTUP_STREAM]({Config.STREAM_URL})"
    else:
        if len(Config.playlist)>=25:
            tplaylist=Config.playlist[:25]
            pl=f"Listing first 25 songs of total {len(Config.playlist)} songs.\n"
            pl += f"▶️ **Playlist**:\n" + "\n".join([
                f"**{i}**. **🎸{x[1]}**\n   👤**Requested by:** {x[4]}"
                for i, x in enumerate(tplaylist)
                ])
            tplaylist.clear()
        else:
            pl = f"▶️ **Playlist**:\n" + "\n".join([
                f"**{i}**. **🎸{x[1]}**\n   👤**Requested by:** {x[4]}\n"
                for i, x in enumerate(Config.playlist)
            ])
    return pl


async def get_buttons():
    data=Config.DATA.get("FILE_DATA")
    if data.get('dur', 0) == 0:
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(f"{get_player_string()}", callback_data="player"),
                ],
                [
                    InlineKeyboardButton(f"⏯ {get_pause(Config.PAUSE)}", callback_data=f"{get_pause(Config.PAUSE)}"),
                    InlineKeyboardButton(f"{'🔇 Unmute' if Config.MUTED else '🔊 Mute'}", callback_data='mute'),
                ],
            ]
            )
    else:
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(f"{get_player_string()}", callback_data='player'),
                ],
                [
                    InlineKeyboardButton("⏮ Rewind", callback_data='rewind'),
                    InlineKeyboardButton(f"⏯ {get_pause(Config.PAUSE)}", callback_data=f"{get_pause(Config.PAUSE)}"),
                    InlineKeyboardButton(f"⏭ Seek", callback_data='seek'),
                ],
                [
                    InlineKeyboardButton(f"{'🔇 Unmute' if Config.MUTED else '🔊 Mute'}", callback_data='mute'),
                    InlineKeyboardButton("🔄 Shuffle", callback_data="shuffle"),
                    InlineKeyboardButton("⏩ Skip", callback_data="skip"),
                    InlineKeyboardButton("⏮ Replay", callback_data="replay"),
                ],
            ]
            )
    return reply_markup


async def progress_bar(current, zero, total, start, msg):
    now = time.time()
    if total == 0:
        return
    if round((now - start) % 3) == 0 or current == total:
        speed = current / (now - start)
        percentage = current * 100 / total
        time_to_complete = round(((total - current) / speed)) * 1000
        time_to_complete = TimeFormatter(time_to_complete)
        progressbar = "[{0}{1}]".format(\
            ''.join(["▰" for i in range(math.floor(percentage / 5))]),
            ''.join(["▱" for i in range(20 - math.floor(percentage / 5))])
            )
        current_message = f"**Downloading** {round(percentage, 2)}% \n{progressbar}\n⚡️ **Speed**: {humanbytes(speed)}/s\n⬇️ **Downloaded**: {humanbytes(current)} / {humanbytes(total)}\n🕰 **Time Left**: {time_to_complete}"
        if msg:
            try:
                await msg.edit(text=current_message)
            except:
                pass
        LOGGER.warning(current_message)


@timeout(10)#wait for maximum 10 sec, temp fix for ffprobe
def get_height_and_width(file):
    try:
        k=ffmpeg.probe(file)['streams']
        width=None
        height=None
        for f in k:
            try:
                width=int(f["width"])
                height=int(f["height"])
                if height >= 256:
                    break
            except KeyError:
                continue
    except:
        LOGGER.error("Error, This stream is not supported.")
        width, height = False, False
    return width, height
@timeout(10)
def is_radio(file):
    try:
        k=ffmpeg.probe(file)['streams']
        if k:
            return True
        else:
            return False
    except KeyError:
        return False
    except Exception as e:
        print("Strem Unsupported ", e)
        return False
    


@timeout(10)
def get_duration(file):
    try:
        total=ffmpeg.probe(file)['format']['duration']
        if total is None:
            total=0
        return total
    except:
        return 0
@timeout(10)
def is_audio_codec(ydl_info):
    urlr=None
    for each in ydl_info['formats']:
        if each['acodec'] != 'none':
            urlr=each['url']
            break #prefer 640x360
        else:
            continue
    if urlr:
        return urlr
    else:
        return False



def humanbytes(size):
    if not size:
        return ""
    power = 2**10
    n = 0
    Dic_powerN = {0: ' ', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return str(round(size, 2)) + " " + Dic_powerN[n] + 'B'


def get_player_string():
    now = time.time()
    data=Config.DATA.get('FILE_DATA')
    dur=int(float(data.get('dur', 0)))
    start = int(Config.DUR.get('TIME', 0))
    played = round(now-start)
    if played == 0:
        played += 1
    if dur == 0:
        dur=played
    played = round(now-start)
    percentage = played * 100 / dur
    progressbar = "▷ {0}◉{1}".format(\
            ''.join(["━" for i in range(math.floor(percentage / 5))]),
            ''.join(["─" for i in range(20 - math.floor(percentage / 5))])
            )
    finaal=f"{convert(played)}   {progressbar}    {convert(dur)}"
    return finaal


def TimeFormatter(milliseconds: int) -> str:
    seconds, milliseconds = divmod(int(milliseconds), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    tmp = ((str(days) + " days, ") if days else "") + \
        ((str(hours) + " hours, ") if hours else "") + \
        ((str(minutes) + " min, ") if minutes else "") + \
        ((str(seconds) + " sec, ") if seconds else "") + \
        ((str(milliseconds) + " millisec, ") if milliseconds else "")
    return tmp[:-2]


def convert(seconds):
    seconds = seconds % (24 * 3600)
    hour = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60      
    return "%d:%02d:%02d" % (hour, minutes, seconds)

def get_pause(status):
    if status == True:
        return "Resume"
    else:
        return "Pause"


def stop_and_restart():
    os.system("git pull")
    time.sleep(10)
    os.execl(sys.executable, sys.executable, *sys.argv)


async def update():
    if Config.HEROKU_APP:
        Config.HEROKU_APP.restart()
    else:
        await kill_process()
        Thread(
            target=stop_and_restart()
            ).start()



@group_call.on_raw_update()
async def handler(client: PyTgCalls, update: Update):
    print(update, "raw")
    if str(update) == "JOINED_VOICE_CHAT":
        Config.CALL_STATUS = True
        if Config.EDIT_TITLE:
            await edit_title()
    elif str(update) == "LEFT_VOICE_CHAT":
        Config.CALL_STATUS = False
    elif str(update) == "PAUSED_STREAM":
        Config.DUR['PAUSE'] = time.time()
        Config.PAUSE=True
    elif str(update) == "RESUMED_STREAM":
        pause=Config.DUR.get('PAUSE')
        if pause:
            diff = time.time() - pause
            start=Config.DUR.get('TIME')
            if start:
                Config.DUR['TIME']=start+diff
        Config.PAUSE=False
    elif str(update) == 'MUTED_STREAM':
        Config.MUTED = True
    elif str(update) == 'UNMUTED_STREAM':
        Config.MUTED = False
    elif str(update)== 'CHANGED_STREAM':
        await sleep(2)
        try:
            call=group_call.get_call(Config.CHAT)
        except GroupCallNotFound:
            await manage_loop_vidwo()
            return
        except Exception as e:
            LOGGER.warning(e)
            await manage_loop_vidwo()
            return
        if str(call.status) != "playing":
            await manage_loop_vidwo()  



@group_call.on_stream_end()
async def handler(client: PyTgCalls, update: Update):
    print(update, "stream end")  
    if Config.LOOP:
        if str(update) == 'STREAM_AUDIO_ENDED':
            #await manage_loop_audio()
            await manage_loop_vidwo()
            await sleep(1)
            try:
                call=group_call.get_call(Config.CHAT)
            except GroupCallNotFound:
                await manage_loop_vidwo()
                return
            except Exception as e:
                LOGGER.warning(e)
                await manage_loop_vidwo()
                return
            print(str(call.status), "Update call")
            if str(call.status) != "playing":
                await manage_loop_vidwo()  
        if str(update) == 'STREAM_VIDEO_ENDED':
            await manage_loop_vidwo()
            await sleep(1)
            try:
                call=group_call.get_call(Config.CHAT)
            except GroupCallNotFound:
                await manage_loop_vidwo()
                return
            except Exception as e:
                LOGGER.warning(e)
                await manage_loop_vidwo()
                return
            if str(call.status) != "playing":
                await manage_loop_vidwo()
                return      
        return
    if str(update) == "STREAM_AUDIO_ENDED" or str(update) == "STREAM_VIDEO_ENDED":
        if not Config.STREAM_END.get("STATUS"):
            Config.STREAM_END["STATUS"]=str(update)
            if Config.STREAM_LINK and len(Config.playlist) == 0:
                await stream_from_link(Config.STREAM_LINK)
            else:
                await skip()          
            await sleep(15) #wait for max 15 sec
            try:
                del Config.STREAM_END["STATUS"]
            except:
                pass
        else:
            try:
                del Config.STREAM_END["STATUS"]
            except:
                pass
