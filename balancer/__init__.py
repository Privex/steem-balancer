"""

Copyright::
    +===================================================+
    |                 © 2019 Privex Inc.                |
    |               https://www.privex.io               |
    +===================================================+
    |                                                   |
    |        Steem RPC Load Balancer                    |
    |                                                   |
    |        Core Developer(s):                         |
    |                                                   |
    |          (+)  Chris (@someguy123) [Privex]        |
    |                                                   |
    +===================================================+

"""
import logging
from privex.loghelper import LogHelper
from balancer.core import cf, CONSOLE_LOG_LEVEL, DBG_LOG, ERR_LOG
from balancer.app import flask

lh = LogHelper(__name__)

lh.add_console_handler(level=CONSOLE_LOG_LEVEL)

lh.add_timed_file_handler(DBG_LOG, when='D', interval=1, backups=14, level=logging.INFO)
lh.add_timed_file_handler(ERR_LOG, when='D', interval=1, backups=14, level=logging.WARNING)


