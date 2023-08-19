import textwrap
from datetime import datetime, timedelta, tzinfo
import os
from time import sleep
from typing import Dict, List, Optional

import csv
import dateutil.parser
import pytz
import requests
from requests.auth import HTTPBasicAuth


WEEKDAY_NAMES = ['月', '火', '水', '木', '金', '土', '日']
TIME_ZONE = "Asia/Tokyo"

# カレンダー
CAL_USER = os.environ["CAL_USER"]
CAL_PASSWORD = os.environ["CAL_PASSWORD"]
CAL_LINK = "https://cal.camph.net/private/schedule.json"

# Slack_API
SLACK_TOKEN = os.environ["SLACK_TOKEN"]
SLACK_CHANNEL = os.environ["SLACK_CHANNEL"]
SLACK_LINK = "https://slack.com/api/chat.postMessage"

class Event:
    start: datetime
    end: datetime
    title: str
    opener: str
    url: Optional[str]

    def __init__(self, *, start: datetime, end: datetime, title: str, opener: str,
                 url: Optional[str]) -> None:
        self.start = start
        self.end = end
        self.title = title
        self.opener = opener
        self.url = url

    @classmethod
    def from_json(cls, data: Dict[str, Optional[str]]) -> "Event":
        # print(type(data["title"]))
        if data["start"] is not None:
            start = dateutil.parser.parse(data["start"])
        else:
            raise KeyError
        if data["end"] is not None:
            end = dateutil.parser.parse(data["end"])
        else:
            raise KeyError
        if data["title"] != "Closed":
            title = "open"
            opener = list(data["title"].split())
        elif data["title"] == "Closed":
            title = "closed"
            opener = []
        else:
            raise KeyError
        return cls(start=start, end=end, title=title, opener=opener, url=data["url"])

    def get_start(self, tz: tzinfo) -> str:
        start = self.start.astimezone(tz).time().strftime("%H:%M")
        return start

    def get_end(self, tz: tzinfo) -> str:
        end = self.end.astimezone(tz).time().strftime("%H:%M")
        return end

    def get_day_and_time(self, tz: tzinfo) -> str:
        date = self.start.astimezone(tz).date().strftime("%m/%d")
        day = get_japanese_weekday(self.start.astimezone(tz).weekday())
        return f"{date} ({day}) {self.get_start(tz)}〜{self.get_end(tz)}"

    def get_day_and_time_with_title(self, tz: tzinfo) -> str:
        return f"{self.title} {self.get_day_and_time(tz)}"


def divide_events_by_title(events: List[Event]) -> Dict[str, List[Event]]:
    events_by_title: Dict[str, List[Event]] = {}
    for title in ["open", "make", "online open"]:
        events_by_title[title] = [
            e for e in events if e.title.lower() == title]
        events = [e for e in events if e.title.lower() != title]
    events_by_title["other"] = [e for e in events if e.title.strip() != ""]
    return events_by_title


def get_japanese_weekday(day: int) -> str:
    return WEEKDAY_NAMES[day]


def download_events(url: str) -> Optional[List[Event]]:
    # BASIC認証
    auth = HTTPBasicAuth(CAL_USER, CAL_PASSWORD)
    response = requests.get(url, auth=auth)
    if response.status_code != requests.codes.ok:
        return None
    return [Event.from_json(e) for e in response.json()]


def post_alert_to_slack(message: str) -> None:
    url = SLACK_LINK
    headers = {"Authorization": "Bearer " + SLACK_TOKEN}
    data = {
        "channel": SLACK_CHANNEL, 
        "text": message,
    }

    r = requests.post(url=url, headers=headers, data=data)
    print('return', r.json())


def check_open(door_isopen: bool):
    tz = pytz.timezone(TIME_ZONE)
    now = datetime.now(tz=tz)
    # if now is None:
    #     now = datetime.now(tz=tz)
    # elif now.tzinfo is None:
    #     now = now.replace(tzinfo=tz)
    
    # イベントの取得
    events = download_events(CAL_LINK)
    events = list(filter(
                    lambda e: e.start.astimezone(tz).date()
                    == now.astimezone(tz).date(), events))
    events_by_title = divide_events_by_title(events)

    # 時間の取得
    open_events = events_by_title["open"]
    if len(open_events) == 1:
        open_event = open_events[0]
        open_start = open_event.get_start(tz)
        # CAMPHOR- Make あり
        make_events = events_by_title["make"]
        if len(make_events) == 1:
            make_event = make_events[0]
            make_start = make_event.get_start(tz)
        elif len(make_events) > 1:
            raise ValueError("The maximum number of Make events per day"
                                " is one, but found several.")
    elif len(open_events) > 1:
        raise ValueError("The maximum number of Open events per day is"
                            " one, but found several.")
    elif len(open_events) == 0:
        open_start = None
        make_start = None
    
    # テスト
    open_start = "15:00"
    opener = "@Tomo"
    
    if open_start is None:
        pass
    else:
        # 開館の20分前から3時間後までの間にドアが開いていない場合はSlackに通知
        # try:
        #     opener = ''.join(events_by_title["open"][0].opener)
        # except:
        #     raise ValueError("Member is not found.")
        
        # user_IDの取得
        # with open('members_ID.csv') as f:
        #     reader = csv.reader(f)
        #     members = [row for row in reader]
        # 
        # for user, id_ in members:
        #     if user == opener:
        #         id = id_

        # message通知の時間設定
        alert_interval_minutes = 10 * 60
        before_alert_minutes = 10
        before_delta = timedelta(minutes=before_alert_minutes)
        after_alert_hour = 3
        after_delta = timedelta(hours=after_alert_hour)

        # テスト
        before_delta = timedelta(hours=24)
        after_delta = timedelta(hours=24)

        open_start = datetime.strptime(open_start, '%H:%M')
        dt_open_start = datetime.now().replace(hour=open_start.hour, minute=open_start.minute, second=0, microsecond=0).astimezone(tz) 

        # messageの通知
        message = "@channel 開館されていません"
        # テスト
        # message = "<@channel>" + " 開館されていません" 
        # if (dt_open_start - before_delta <= now <= dt_open_start + after_delta) and (not door_isopen):
        post_alert_to_slack(message=message)


def open_slack():
    post_alert_to_slack("解錠されました")
def close_slack()
    post_alert_to_slack("施錠されました")
