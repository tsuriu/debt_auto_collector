import requests
import re
import json
import html
from datetime import datetime
from loguru import logger
from database import Database
from utils.time_utils import is_within_operational_window

class ReportService:
    CDR_FIELDS = [
        "calldate", "src", "dst", "dcontext", "channel", 
        "dstchannel", "lastapp", "disposition", "duration", "uniqueid"
    ]

    EVENT_FIELDS = [
        "eventtime", "eventtype", "cid_name", "cid_num", 
        "cid_dnid", "exten", "appname", "uniqueid"
    ]

    def __init__(self, instance):
        self.instance = instance
        asterisk_config = instance.get('asterisk', {})
        
        host = asterisk_config.get('cdr_host')
        port = asterisk_config.get('cdr_port', '80')
        self.username = asterisk_config.get('cdr_username')
        self.password = asterisk_config.get('cdr_password')
        
        if not all([host, self.username, self.password]):
            logger.warning(f"Missing CDR configuration for instance {instance.get('instance_name')}. Check cdr_host, cdr_username, cdr_password.")
            
        self.base_url = f"http://{host}:{port}".rstrip('/')
        
        # Determine channel pattern (field_pattern)
        # Requirement: "field_pattern is in instannce_document.asterisk.channel"
        # Fallback to try.py default "sqd3718-trunk" if not found
        self.channel_pattern = asterisk_config.get('channel', 'sqd3718-trunk')

        self.login_url = f"{self.base_url}/index.php"
        self.cdr_url = f"{self.base_url}/index.php?menu=cdrreport"
        
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "text/html"
        })

    def clean_html(self, text):
        if not text:
            return None
        text = str(text) # Ensure string
        # Remove all HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        # Convert HTML entities
        text = html.unescape(text)
        text = text.strip()
        if text in ("", "&nbsp;"):
            return None
        return text

    def login(self):
        payload = {
            "input_user": self.username,
            "input_pass": self.password,
            "submit_login": ""
        }
        try:
            r = self.session.post(self.login_url, data=payload, allow_redirects=True, timeout=30)
            if not any(c.name == "issabelSession" for c in self.session.cookies):
                raise Exception("Session cookie not found after login")
            logger.info(f"Logged in to Asterisk/Issabel at {self.base_url}")
        except Exception as e:
            logger.error(f"Login failed: {e}")
            raise

    def fetch_cdr_list(self):
        # Requirement: date_* must be today date
        today_str = datetime.now().strftime("%d %b %Y") # e.g., "10 Dec 2025"
        
        payload = {
            "date_start": today_str,
            "date_end": today_str,
            "field_name": "channel",
            "field_pattern": self.channel_pattern,
            "status": "ALL",
            "limit": "100000",
            "ringgroup": "",
            "timeInSecs": "on",
            "filter": "Filter"
        }
        
        logger.debug(f"Fetching CDRs with payload: {payload}")
        
        try:
            r = self.session.post(self.cdr_url, data=payload, timeout=60)
            if r.status_code != 200:
                raise Exception(f"Failed to fetch CDR list. HTTP {r.status_code}")

            match = re.search(r"var cdrs\s*=\s*(\[\[.*?\]\]);", r.text, re.S)
            if not match:
                # If no CDRs found, sometimes the array is just empty or not present?
                # The page structure changes when no results are found.
                # Since we verified login success, we assume this means no data.
                logger.warning("CDR JS array not found. Assuming no records for today.")
                return []

            rows = json.loads(match.group(1))
            cdrs = []
            for row in rows:
                cdr = {field: self.clean_html(row[i]) if i < len(row) else None for i, field in enumerate(self.CDR_FIELDS)}
                cdrs.append(cdr)
            
            return cdrs
            
        except Exception as e:
            logger.error(f"Error fetching CDR list: {e}")
            raise

    def fetch_events(self, uniqueid):
        if not uniqueid:
            return []
            
        url = f"{self.cdr_url}&rawmode=yes&uniqueid={uniqueid}"
        try:
            r = self.session.get(url, timeout=30)
            if r.status_code != 200:
                return []

            table_match = re.search(r'<table[^>]*class="issabel-standard-table"[^>]*>(.*?)</table>', r.text, re.S)
            if not table_match:
                return []

            table_html = table_match.group(1)
            rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, re.S)
            events = []

            for row in rows[1:]:  # skip header
                cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.S)
                clean_cells = [self.clean_html(c) for c in cells]
                
                # Basic check to avoid empty rows
                if any(clean_cells): 
                    # Zip with expected fields
                    # Note: If cells count differs from EVENT_FIELDS, zip truncates. 
                    events.append(dict(zip(self.EVENT_FIELDS, clean_cells)))

            return events
        except Exception as e:
            logger.warning(f"Error fetching events for uniqueid {uniqueid}: {e}")
            return []

    def check_window(self):
        """Returns True if current time is within allowed call window (same as Dialer)"""
        # Check instance debug flag (mirrored from Dialer logic, though 'debug_calls' is specific)
        return is_within_operational_window(self.instance.get('debug_calls', False))

    def process(self):
        """
        Orchestrates the entire report fetching process and saves to DB.
        """
        try:
            if not self.check_window():
                logger.info(f"Skipping report fetch for {self.instance.get('instance_name')} (Outside Window)")
                return

            self.login()
            cdrs = self.fetch_cdr_list()
            logger.info(f"Fetched {len(cdrs)} CDR records")
            
            if not cdrs:
                return

            # Enrich with events
            # This might be slow for 1000s of records. try.py did it sequentially.
            # We will keep it sequential for now as per try.py logic.
            for cdr in cdrs:
                uid = cdr.get("uniqueid")
                cdr["events"] = self.fetch_events(uid) if uid else []

            # Insert into 'last_reports' collection
            # Requirement: "fetch_cdr_list return must be inserted in last_reports collection and add a key with last run timestamp"
            
            db = Database().get_db()
            
            report_doc = {
                "instance_full_id": f"{self.instance.get('instance_name')}-{self.instance.get('_id')}", # Best effort ID
                "last_run_timestamp": datetime.now(),
                "date_collected": datetime.now().strftime("%Y-%m-%d"),
                "total_records": len(cdrs),
                "data": cdrs
            }
            
            db.last_reports.insert_one(report_doc)
            logger.info("Saved report to 'last_reports' collection")
            
            return len(cdrs)

        except Exception as e:
            logger.error(f"Report Service process failed: {e}")
            return 0
