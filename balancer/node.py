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
import json
import random
import logging
from dataclasses import dataclass, field
from os.path import join
from typing import Union, List, Dict
from privex.helpers import empty, r_cache
from balancer.core import fullnode_apis, BASE_DIR, plugin_aliases, all_plugins

__STORE = {}
log = logging.getLogger(__name__)


@dataclass
class Endpoint:
    host: str
    name: str = None
    weight: int = 1
    full: bool = True
    plugins: list = field(default_factory=list)
    call_whitelist: list = field(default_factory=list)
    call_blacklist: list = field(default_factory=list)

    def has_plugin(self, plugin: str):
        """Returns True if specified plugin is in self.plugins. If self.plugins is empty, simply returns True."""
        return plugin in self.plugins if self.has_plugins else True

    def whitelisted(self, *rcall: str, check_all=True) -> bool:
        """
        Returns False if any given call in the args list isn't whitelisted.

        If ``check_all`` is set to False (must be specified as a kwarg), will instead return True if **ANY** of the
        passed ``rcall``'s are in the whitelist.

        Example:

            >>> ep = Endpoint('examplehost', call_whitelist=['get_block', 'get_accounts'])
            >>> # With the default check_all=True, this returns False because 'get_open_orders' was not whitelisted.
            >>> ep.whitelisted('get_block', 'get_open_orders')
            False
            >>> # Because check_all=False, returns True because at least one arg: 'get_block' was whitelisted
            >>> ep.whitelisted('get_block', 'get_open_orders', check_all=False)
            True

        :param str[] rcall: One or more method calls as positional args - to be tested against the whitelist
        :param bool check_all: (Default: ``True``) If True, only return True if all given rcalls are whitelisted.
        :return bool is_whitelisted: ``False`` if not whitelisted
        :return bool is_whitelisted: ``True`` if whitelisted
        """
        if not self.has_whitelist: return True
        for c in rcall:
            if check_all and c not in self.call_whitelist: return False
            if not check_all and c in self.call_whitelist: return True
        # If check_all is True, then we would've returned False if any given call wasn't whitelisted, thus we can
        # assume all are in the whitelist, and return True.
        return True if check_all else False

    def blacklisted(self, *rcall: str, check_all=True) -> bool:
        """
        Returns True if any given call in the args list is blacklisted.

        If ``check_all`` is set to False (must be specified as a kwarg), will instead return True if **ANY** of the
        passed ``rcall``'s are in the blacklist.

        Example:

            >>> ep = Endpoint('examplehost', call_blacklist=['get_block', 'get_accounts'])
            >>> # With the default check_all=True, this returns False because 'get_open_orders' was not blacklisted.
            >>> ep.blacklisted('get_block', 'get_open_orders')
            False
            >>> # Because check_all=False, returns True because at least one arg: 'get_block' was blacklisted
            >>> ep.blacklisted('get_block', 'get_open_orders', check_all=False)
            True

        :param str[] rcall: One or more method calls as positional args - to be tested against the blacklist
        :param bool check_all: (Default: ``True``) If True, only return True if all given rcalls are blacklisted.
        :return bool is_blacklisted: ``False`` if not blacklisted
        :return bool is_blacklisted: ``True`` if blacklisted
        """
        if not self.has_blacklist: return False
        for c in rcall:
            if check_all and c not in self.call_blacklist: return False
            elif not check_all and c in self.call_blacklist: return True
        # If check_all is True, then we would've returned False if any given call wasn't blacklisted, thus we can
        # assume all are in the blacklist, and return True.
        return True if check_all else False

    @property
    def has_plugins(self) -> bool:
        """Returns True if a plugin list is specified for this endpoint"""
        return not empty(self.plugins, itr=True)

    @property
    def has_whitelist(self) -> bool:
        """Returns True if a call whitelist is specified for this endpoint"""
        return not empty(self.call_whitelist, itr=True)

    @property
    def has_blacklist(self) -> bool:
        """Returns True if a call blacklist is specified for this endpoint"""
        return not empty(self.call_blacklist, itr=True)

    def can_call(self, rcall: str):
        plugin = find_plugin(rcall)
        aliases = call_aliases(rcall)
        log.debug('Original call: %s   Plugin: %s   Aliases: %s', rcall, plugin, aliases)
        # If the call (or any of it's aliases) is whitelisted, then we should just trust the call is fine.
        if self.has_whitelist and self.whitelisted(*aliases, check_all=False): return True
        # If the node doesn't have a given plugin, or the requested call is blacklisted, reject the call.
        if not self.has_plugin(plugin) or self.blacklisted(*aliases, check_all=False): return False

        # If this isn't a full node, reject this call if it's in the known full-memory only calls
        if not self.full:
            for a in aliases:
                if a in fullnode_apis:
                    return False
        return True

    @staticmethod
    def from_obj(endpoints: Union[dict, List[str]]):
        """
        Convert either a flat ``list`` of hosts, or a ``Dict[str, dict]`` of names mapped to ``dict``s with
        the same keys as this class into a dictionary of names mapped to Endpoint objects ``Dict[str, Endpoint]``

        Usage:

            **From a flat list**

            >>> ep = ['https://steemd.privex.io', 'https://api.steemit.com']
            >>> Endpoint.from_obj(ep)
            {'https://steemd.privex.io': <Endpoint 'https://steemd.privex.io' weight=1 >,
             'https://api.steemit.com': <Endpoint 'https://api.steemit.com' weight=1 >}

            **From a dictionary**

            >>> ep = {
            ...    'privex': dict(host='https://steemd.privex.io', weight=3, plugins=['condenser_api']),
            ...    'msp': dict(host="https://steemd.minnowsupportproject.org", weight=2),
            ... }
            >>>
            >>> Endpoint.from_obj(ep)
            { 'privex': <Endpoint 'https://steemd.privex.io' weight=3 >,
              'msp': <Endpoint 'https://steemd.minnowsupportproject.org' weight=2 >}

        :param list|dict endpoints:  Either a ``List[str]`` of endpoint hosts, or a ``Dict[str,dict]`` mapping names
                                     to ``dict`` endpoints with keys matching this class (host, name, weight, plugins)

        :return Dict[str, Endpoint] endpoints: A dictionary of names mapped to Endpoint objects
        """
        if type(endpoints) is list:
            return {h: Endpoint(host=h) for h in endpoints}
        else:  # noinspection PyTypeChecker
            return {h.get('name', n): Endpoint(**h) for n, h in endpoints.items() }

    def __repr__(self):
        if empty(self.name):
            return f"<Endpoint '{self.host}' weight={self.weight} >"
        else:
            return f"<Endpoint '{self.name}' weight={self.weight} >"


def get_nodes() -> Dict[str, Endpoint]:
    if 'nodes' not in __STORE:
        with open(join(BASE_DIR, 'configs', 'nodes.json'), mode='r') as f:
            __STORE['nodes'] = Endpoint.from_obj(json.load(f))
    return __STORE['nodes']


def find_plugin(rcall: str):
    """
    Given a method call such as 'condenser_api.get_accounts' or 'get_block', find the plugin that's
    responsible for the given call.

    Example:

        >>> find_plugin('get_accounts')
        'account_by_key'
        >>> find_plugin('condenser_api.get_block')
        'block_api'

    :param str rcall: A method call such as ``condenser_api.get_block``
    :return str plugin: The plugin we think is responsible
    """
    scall = rcall.split('.')
    bcall = scall[0]    # "Base" of the call, the first part after splitting by dots.

    # If the base call is for condenser_api, lookup the second portion of the method in the aliases
    # to find the "real" plugin.
    if bcall == 'condenser_api' and scall[1] in plugin_aliases:
        return plugin_aliases[scall[1]]

    return plugin_aliases[bcall] if bcall in plugin_aliases else (bcall if bcall in all_plugins else 'condenser_api')


def call_aliases(rcall: str) -> tuple:
    """
    Returns all potential aliases for a call in a tuple

    Example:

        >>> call_aliases('get_block')
        ('get_block', 'get_block', 'condenser_api.get_block', 'block_api.get_block',)

    """
    plugin = find_plugin(rcall)
    mcall = rcall.split('.')[-1]       # The last part of the call, generally the actual method e.g. 'get_block'
    cdcall = f'condenser_api.{mcall}'  # Bare method name prefixed with condenser_api
    pgcall = f'{plugin}.{mcall}'       # Bare method name prefixed with it's plugin, e.g. 'block_api.get_block'

    return rcall, mcall, cdcall, pgcall


def find_endpoint(rcall: str) -> Endpoint:
    """
    Randomly select an endpoint that can handle the method ``rcall`` - taking into question their weights.

    :param str rcall: A method call such as ``condenser_api.get_block``
    :return Endpoint e: A weighted random endpoint capable of serving the given method
    """
    weighted_endpoints = weight_endpoint(rcall)

    selection = random.randint(0, len(weighted_endpoints)-1)
    return weighted_endpoints[selection]


@r_cache(lambda rcall: f'stmnodes:{rcall}')
def weight_endpoint(rcall):
    endpoints = get_nodes()
    weighted_endpoints = []
    for ep_name, ep in endpoints.items():
        if not ep.can_call(rcall): continue
        for w in range(ep.weight):
            weighted_endpoints.append(ep)
    return weighted_endpoints
