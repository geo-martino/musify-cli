import logging
import sys

from mytunes_cli.log.formatters import RenderableFormatter, ColourlessFormatter
from mytunes_cli.log.handlers import RenderableHandler

formatter_1 = RenderableFormatter()
formatter_2 = ColourlessFormatter()

handler_1 = RenderableHandler()
handler_1.setFormatter(formatter_1)
handler_2 = logging.StreamHandler()
handler_2.setFormatter(formatter_2)

logging.basicConfig(format="%(message)s", level=logging.INFO, handlers=[handler_1, handler_2])

logger = logging.getLogger()
logger.info("LOG MESSAGE")

