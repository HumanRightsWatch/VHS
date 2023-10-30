import glob
import json
import os.path
import re
import time
import random

import cv2
from telethon import TelegramClient
from telethon.tl.types import Message
from telethon.sessions.sqlite import SQLiteSession


class TelegramSessionPool:
    __sessions: list[str]
    __session_states: dict

    def __init__(self):
        self.refresh_session_list()

    def session_exists(self, session_name):
        self.refresh_session_list()
        return os.path.isfile(f'{session_name}.session') and session_name in self.__sessions
        
    def lock_session(self, session_name):
        with open(f'{session_name}.lock', mode='w') as lock:
            lock.write(str(time.time()))

    def release_session(self, session_name):
        self.refresh_session_list()
        if self.session_exists(session_name) and os.path.isfile(f'{session_name}.lock'):
            os.unlink(f'{session_name}.lock')
        self.refresh_session_list()
    
    def is_locked(self, session_name):
        return os.path.isfile(f'{session_name}.lock')
    
    def print_sessions(self):
        print(self.__session_states)

    def free_old_sessions(self):
        for session, locked in self.__session_states.items():
            if not locked:
                continue
            current_time = time.time()
            with open(f'{session}.lock') as lock:
                raw = lock.read().strip()
            lock_time = float(raw)
            delta = current_time - lock_time
            if delta > 12*3600:  # 12 hours
                os.unlink(f'{session}.lock')

    def get_session(self):
        self.refresh_session_list()
        self.free_old_sessions()
        self.refresh_session_list()
        try:
            for session, locked in self.__session_states.items():
                if not locked:
                    self.lock_session(session)
                    return session
            
            session = f'annon_bot-{time.time_ns()}'
            self.lock_session(session)
            return session
        finally:
            self.refresh_session_list()

    def refresh_session_list(self):
        self.__session_states = {}
        self.__sessions = SQLiteSession.list_sessions()
        for s in self.__sessions:
            self.__session_states[s] = self.is_locked(s)



class TelegramPostDownloader:
    url: str
    output_dir: str
    user_id: str
    post_id: int
    api_id: int
    api_hash: str
    bot_token: str
    __session_id: str = 'anon_bot'
    __client: TelegramClient
    __session_pool: TelegramSessionPool
    url_regex = r"^https:\/\/t\.me\/(?P<user_id>.*?)\/(?P<post_id>[0-9]+)"

    def __init__(self, api_id: int, api_hash: str, bot_token: str):
        self.api_id = api_id
        self.api_hash = api_hash
        self.bot_token = bot_token

    def login(self):
        time.sleep(random.uniform(0.2, 2.1))
        self.__session_pool = TelegramSessionPool()
        self.__session_id = self.__session_pool.get_session()
        self.__session_pool.lock_session(self.__session_id)
        print(f'TG log in with session [{self.__session_id}]')
        try:
            self.__client = TelegramClient(self.__session_id, self.api_id, self.api_hash).start(bot_token=self.bot_token)
        except Exception as e:
            self.__session_pool.release_session(self.__session_id)
            raise e

    def prepare(self, url: str) -> bool:
        self.url = url
        match = re.match(self.url_regex, self.url, re.IGNORECASE)
        if match:
            self.user_id = match.groupdict().get('user_id')
            self.post_id = int(match.groupdict().get('post_id'))
            return True
        return False

    async def get_message(self):
        messages = []
        message: Message = await self.__client.get_messages(self.user_id, ids=self.post_id)
        with open(f'{self.output_dir}/post.json', mode='w') as doc:
            message.to_json(doc, indent=2, ensure_ascii=False)
        with open(f'{self.output_dir}/post.json', mode='r') as doc:
            obj = json.load(doc)
            obj['uploader'] = self.user_id
            obj['platform'] = 'Telegram'
            obj['webpage_url'] = self.url
        with open(f'{self.output_dir}/post.json', mode='w') as doc:
            json.dump(obj, doc, indent=2, ensure_ascii=False)

        if message.grouped_id:  # this post contains multiple medio
            for _id in range(max(0, self.post_id-10), self.post_id+10):  # based on Telegram limits of 10 media per post
                try:
                    m: Message = await self.__client.get_messages(self.user_id, ids=_id)
                    if m.grouped_id == message.grouped_id:
                        messages.append(m)
                except:
                    pass
        else:
            messages.append(message)
        return messages

    def __create_thumbnails(self):
        for filename in glob.glob(f'{self.output_dir}/*.mp4')+glob.glob(f'{self.output_dir}/*.MP4'):
            root, ext = os.path.splitext(filename)
            print(f'Creating thumbnail for {filename}: {root}|{ext}')
            cap = None
            try:
                cap = cv2.VideoCapture(filename)
                frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                frame_index = int(frame_count/2)
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
                success, frame = cap.read()
                if success:
                    cv2.imwrite(f'{root}.thumbnail.jpg', frame)
            except Exception as e:
                print(e)
            finally:
                try:
                    cap.release()
                    cv2.destroyAllWindows()
                except:
                    pass

    async def __download_message(self, message: Message):
        await self.__client.download_media(message, self.output_dir)

    def download(self, output_dir: str):
        self.output_dir = output_dir
        try:
            with self.__client:
                messages: list[Message] = self.__client.loop.run_until_complete(self.get_message())
                for message in messages:
                    self.__client.loop.run_until_complete(self.__download_message(message))
        finally:
            print(f'Release TG session [{self.__session_id}]')
            self.__session_pool.release_session(self.__session_id)
        self.__create_thumbnails()

