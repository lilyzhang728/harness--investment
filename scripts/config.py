"""全局配置：路径、时区、密钥。所有敏感值只从环境变量读取。"""
import os
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
NOTE_DIR = ROOT / "投资学习"
IMG_DIR = NOTE_DIR / "images"
BUILD_DIR = NOTE_DIR / "build"
DATA_DIR = ROOT / "data"
HISTORY_FILE = DATA_DIR / "history.json"

CN = ZoneInfo("Asia/Shanghai")
WEEKDAY_CN = ["一", "二", "三", "四", "五", "六", "日"]

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36")

# ---------- 坚果云 WebDAV ----------
JGY_BASE = os.getenv("JGY_BASE", "https://dav.jianguoyun.com/dav").rstrip("/")
JGY_DIR = os.getenv("JGY_DIR", "投资学习")          # 网盘里的根目录
JGY_USER = os.getenv("JGY_USER", "")
JGY_PASS = os.getenv("JGY_PASS", "")

# ---------- DeepSeek ----------
DS_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DS_URL = os.getenv("DEEPSEEK_URL", "https://api.deepseek.com/chat/completions")
DS_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# ---------- 抓取参数 ----------
HTTP_TIMEOUT = 15
HISTORY_KEEP = 400          # 每只标的最多保留多少个交易日的收盘价
