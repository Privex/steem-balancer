#!/usr/bin/env python3
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
import asyncio
import json
from datetime import datetime
from typing import Union
from urllib.parse import urlparse
from quart import Quart, request, jsonify
from privex.helpers import empty
from privex.jsonrpc import JsonRPC
from werkzeug.exceptions import BadRequest
import logging
from balancer.node import find_endpoint, Endpoint

log = logging.getLogger(__name__)

flask = Quart(__name__)
loop = asyncio.get_event_loop()

MAX_BATCH = 200


class EndpointException(BaseException):
    def __init__(self, message, endpoint: Endpoint = None):
        super().__init__(message)
        self.endpoint = endpoint


async def extract_json(rq: request):
    try:
        data = await rq.get_json(force=True)
        return data
    except (json.decoder.JSONDecodeError, BadRequest) as e:
        log.debug('get_json failed, falling back to extracting from form keys')
        data = list(rq.form.keys())
        if len(data) >= 1:
            return json.loads(data[0])
        raise e


async def make_call(method, params):
    endpoint = find_endpoint(method)  # type: Endpoint
    uri = urlparse(endpoint.host)
    port = uri.port if uri.port is not None else 443 if uri.scheme == 'https' else 80

    j = JsonRPC(uri.hostname, port=port, ssl=(uri.scheme == 'https'))
    try:
        if type(params) is dict:
            return j.call(method, **params), endpoint
        elif type(params) is list:
            return j.call(method, *params), endpoint
        else:
            raise AttributeError('JSON Params was neither dict nor list...')
    except AttributeError as e:
        raise e
    except Exception as e:
        raise EndpointException(
            f'Error while calling {method} on {endpoint.host} - reason: {type(e)} {str(e)}', endpoint=endpoint
        )


@flask.route('/', methods=['GET', 'POST'])
async def index():
    if request.method == 'GET':
        if not request.form or len(request.form) == 0:
            return jsonify(
                status='OK',
                datetime=str(datetime.utcnow()),
                source_commit="000000",
                jussi_num=0,
                message='This is a Privex steem-balancer node. Fake Jussi data returned for compatibility reasons.'
            )
    try:
        data = await extract_json(request)
        log.debug('JSON Request: %s', data)

        if type(data) is dict:
            method = data['method']  # type: str
            params = data.get('params', [])  # type: Union[dict, list]
            call_list = [make_call(method=method, params=params)]
        elif type(data) is list:
            if len(data) > MAX_BATCH:
                return jsonify(error=True, message=f"Too many batch calls. Max batch calls is: {MAX_BATCH}")
            call_list = [make_call(method=d['method'], params=d.get('params', [])) for d in data]
        else:
            raise Exception("JSON data was not dict or list.")
    except Exception as e:
        log.warning('Could not parse request. Returning error. Reason: %s %s', type(e), str(e))
        return jsonify(error=True, message="An error occurred while attempting to parse JSON request body..."), 400

    # endpoint = find_endpoint(method)  # type: Endpoint
    # uri = urlparse(endpoint.host)
    # port = uri.port if uri.port is not None else 443 if uri.scheme == 'https' else 80

    # j = JsonRPC(uri.hostname, port=port, ssl=(uri.scheme == 'https'))

    try:
        call_res = await asyncio.gather(*call_list)
        if len(call_res) == 1:
            res, endpoint = call_res[0]
            resp = jsonify(jsonrpc='2.0', result=res, id=res.get('id', 1))
            resp.headers['X-Upstream'] = endpoint.host if empty(endpoint.name) else endpoint.name
        else:
            res = [dict(jsonrpc='2.0', result=r[0], id=i+1) for i, r in enumerate(call_res)]
            resp = jsonify(res)
            resp.headers['X-Upstream'] = 'Unknown due to batch call.'
        # resp = jsonify(jsonrpc='2.0', result=res, id=data.get('id', 1))
        # resp.headers['X-Upstream'] = endpoint.host if empty(endpoint.name) else endpoint.name
        return resp
    except AttributeError:
        return jsonify(error=True, message="Incorrectly formatted 'params'. Must be list or dict"), 400
    except EndpointException as e:
        log.warning('Exception while calling JsonRPC server %s - reason: %s %s', e.endpoint, type(e), str(e))
        return jsonify(error=True, message=f"Unknown error from upstream {e.endpoint.host}"), 502


if __name__ == "__main__":
    flask.run()
