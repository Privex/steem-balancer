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
import os
import logging
from os import getenv as env
from os.path import join

from privex.helpers import env_bool
from dotenv import load_dotenv

# from balancer.app import f

cf = {}
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

DEBUG = cf['DEBUG'] = env_bool('DEBUG', False)

CONSOLE_LOG_LEVEL = env('LOG_LEVEL', None)
CONSOLE_LOG_LEVEL = logging.getLevelName(str(CONSOLE_LOG_LEVEL).upper()) if CONSOLE_LOG_LEVEL is not None else None

if CONSOLE_LOG_LEVEL is None:
    CONSOLE_LOG_LEVEL = logging.DEBUG if cf['DEBUG'] else logging.INFO

DBG_LOG, ERR_LOG = join(BASE_DIR, 'logs', 'debug.log'), join(BASE_DIR, 'logs', 'error.log')

all_plugins = [
    'condenser_api',
    'network_broadcast_api',
    'rc_api',
    'account_by_key',
    'database_api',
    'account_history_api',
    'block_api',
    'market_history_api'
]

fullnode_apis = [
    # This API is deprecated, but still available. Low memory nodes may only return a small portion of recent votes
    'get_account_votes',
    'condenser_api.get_account_votes',
    # This ONLY works on full nodes
    'condenser_api.get_active_votes',
    'condenser_api.get_blog',
    'condenser_api.get_content',
    'condenser_api.get_content_replies',
    'condenser_api.get_discussions_by_active',
    'condenser_api.get_discussions_by_author_before_date',
    'condenser_api.get_discussions_by_blog',
    'condenser_api.get_discussions_by_cashout',
    'condenser_api.get_discussions_by_children',
    'condenser_api.get_discussions_by_comments',
    'condenser_api.get_discussions_by_created',
    'condenser_api.get_discussions_by_feed',
    'condenser_api.get_discussions_by_hot',
    'condenser_api.get_discussions_by_promoted',
    'condenser_api.get_discussions_by_trending',
    'condenser_api.get_discussions_by_votes',
    'condenser_api.get_comment_discussions_by_payout',
    # These APIs are deprecated...
    'condenser_api.get_feed',
    'condenser_api.get_feed_entries',
    'condenser_api.get_follow_count',
    'condenser_api.get_followers',
    'condenser_api.get_following',
    'condenser_api.get_blog_authors',
    'condenser_api.get_blog_entries',
]

plugin_aliases = {
    'get_block': 'block_api',
    'get_account_history': 'account_history_api',
    'get_witness_by_account': 'account_by_key',
    'get_accounts': 'account_by_key',
    'get_market_history': 'market_history_api',
    'get_market_history_buckets': 'market_history_api',
    'get_open_orders': 'market_history_api',
}

MAX_BATCH = int(env('MAX_BATCH', 3000))
CHUNK_SIZE = int(env('CHUNK_SIZE', 40))
