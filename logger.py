import json
from logging import getLogger
from logging.config import dictConfig

from rich.logging import RichHandler

logger = getLogger('bot')
interact_logger = getLogger("interactions")

with open('conf/logging.json', 'r') as f:
    log_conf = json.load(f)

dictConfig(log_conf)

logger.addHandler(RichHandler(rich_tracebacks=True))
getLogger("discord").addHandler(RichHandler(level="INFO",rich_tracebacks=True))
getLogger("stuff").addHandler(RichHandler(level="DEBUG",rich_tracebacks=True))
