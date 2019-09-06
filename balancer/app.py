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
from os.path import join
from typing import Union
from urllib.parse import urlparse

from flask import Flask, request, jsonify
from privex.helpers import empty
from privex.jsonrpc import JsonRPC
from werkzeug.exceptions import BadRequest

from balancer.core import BASE_DIR
import logging

from balancer.node import find_endpoint, Endpoint

log = logging.getLogger(__name__)

flask = Flask(__name__)


def extract_json(rq: request):
    try:
        data = rq.get_json(force=True)
        return data
    except (json.decoder.JSONDecodeError, BadRequest) as e:
        log.debug('get_json failed, falling back to extracting from form keys')
        data = list(rq.form.keys())
        if len(data) >= 1:
            return json.loads(data[0])
        raise e


@flask.route('/', methods=['GET', 'POST'])
def index():
    try:
        data = extract_json(request)
        log.info('JSON Request: %s', data)
        method = data['method']   # type: str
        params = data['params']   # type: Union[dict, list]
    except Exception as e:
        log.warning('Could not parse request. Returning error. Reason: %s %s', type(e), str(e))
        return jsonify(error=True, message="An error occurred while attempting to parse JSON request body..."), 400

    endpoint = find_endpoint(method)  # type: Endpoint
    uri = urlparse(endpoint.host)
    port = uri.port if uri.port is not None else 443 if uri.scheme == 'https' else 80

    j = JsonRPC(uri.hostname, port=port, ssl=(uri.scheme == 'https'))
    try:
        if type(params) is dict:
            res = j.call(method, **params)
        elif type(params) is list:
            res = j.call(method, *params)
        else:
            raise BadRequest('JSON Params was neither dict nor list...')

        resp = jsonify(res)
        resp.headers['X-Upstream'] = endpoint.host if empty(endpoint.name) else endpoint.name
        return resp
    except BadRequest:
        return jsonify(error=True, message="Incorrectly formatted 'params'. Must be list or dict"), 400
    except Exception as e:
        log.warning('Exception while calling JsonRPC server %s - reason: %s %s', endpoint, type(e), str(e))
        return jsonify(error=True, message=f"Unknown error from upstream {endpoint.host}"), 502

