# News Filter Helper for Trading Bot
import requests
from datetime import datetime, timedelta

class NewsFilter:
    def __init__(self, calendar_url=None):
        self.calendar_url = calendar_url or "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"
        self.news_events = []

    def fetch_news(self):
        # Example: fetch and parse Forex Factory XML calendar
        try:
            import xml.etree.ElementTree as ET
            resp = requests.get(self.calendar_url, timeout=10)
            tree = ET.fromstring(resp.content)
            self.news_events = []
            for item in tree.findall(".//event"):
                impact = item.find("impact").text
                if impact in ["High", "Medium"]:
                    symbol = item.find("currency").text
                    time_str = item.find("date").text + " " + item.find("time").text
                    news_time = datetime.strptime(time_str, "%b %d, %Y %H:%M")
                    self.news_events.append({"symbol": symbol, "time": news_time, "impact": impact})
        except Exception as e:
            print(f"News fetch error: {e}")

    def is_news_near(self, symbol, window_minutes=30):
        now = datetime.utcnow()
        for event in self.news_events:
            if event["symbol"] == symbol:
                if abs((event["time"] - now).total_seconds()) < window_minutes * 60:
                    return True
        return False
