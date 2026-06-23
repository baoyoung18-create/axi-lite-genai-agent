import os
from dotenv import load_dotenv

# 加载 .env 配置文件
load_dotenv()

# DeepSeek / OpenAI 兼容接口配置
API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# 最大重试修复次数
MAX_RETRY_ATTEMPTS = 4

