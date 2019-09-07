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
import math
from datetime import datetime
from json import JSONDecodeError
from typing import Union

import httpx
from quart_cors import cors
from quart import Quart, request, jsonify
from privex.helpers import empty, retry_on_err
from werkzeug.exceptions import BadRequest
import logging

from balancer.core import MAX_BATCH, CHUNK_SIZE
from balancer.node import find_endpoint, Endpoint

log = logging.getLogger(__name__)

flask = Quart(__name__)
cors(flask, allow_origin="*")
loop = asyncio.get_event_loop()


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

rs = httpx.AsyncClient()


@retry_on_err()
async def json_call(url, method, params, jid=1, timeout=120):
    headers = {'content-type': 'application/json'}

    payload = {
        "method": method,
        "params": params,
        "jsonrpc": "2.0",
        "id": jid,
    }
    r = None
    try:
        log.debug('Sending JsonRPC request to %s with payload: %s', url, payload)
        r = await rs.post(url, data=json.dumps(payload), headers=headers, timeout=timeout)
        r.raise_for_status()
        response = r.json()
    except JSONDecodeError as e:
        log.warning('JSONDecodeError while querying %s', url)
        log.warning('Params: %s', params)
        t = r.text.decode('utf-8') if type(r.text) is bytes else str(r.text)
        log.warning('Raw response data was: %s', t)
        raise e

    return response


@retry_on_err()
async def json_list_call(url, data: list, timeout=120):
    headers = {'content-type': 'application/json'}
    r = await rs.post(url, data=json.dumps(data), headers=headers, timeout=timeout)
    r.raise_for_status()
    response = r.json()
    for rl in response:
        if 'error' in rl and type(rl['errpr']) is dict:
            raise Exception('Result contains error')
    return response


@retry_on_err()
async def make_batch_call(method, data):
    if method == 'call':
        endpoint = find_endpoint('.'.join(data[0]['params'][:-1]))
    else:
        endpoint = find_endpoint(method)  # type: Endpoint
    try:
        return await json_list_call(endpoint.host, data), endpoint
    except Exception as e:
        raise EndpointException(
            f'Error while calling {method} on {endpoint.host} - reason: {type(e)} {str(e)}', endpoint=endpoint
        )


async def make_call(method, params, jid=1):
    _method = method
    if method == 'call':
        _method = '.'.join(params[:-1])
    endpoint = find_endpoint(_method)  # type: Endpoint
    # uri = urlparse(endpoint.host)
    # port = uri.port if uri.port is not None else 443 if uri.scheme == 'https' else 80

    # j = JsonRPC(uri.hostname, port=port, ssl=(uri.scheme == 'https'))
    try:
        return await json_call(endpoint.host, method=method, params=params, jid=jid), endpoint
    except Exception as e:
        raise EndpointException(
            f'Error while calling {method} on {endpoint.host} - reason: {type(e)} {str(e)}', endpoint=endpoint
        )


async def filter_methods(data: list):
    methods = {}
    for d in data:
        m = d['method']
        if m not in methods:
            methods[m] = []
        methods[m].append(d)
    return methods


def chunked(iterable, n):
    """ Split iterable into ``n`` iterables of similar size

    Examples::
        >>> l = [1, 2, 3, 4]
        >>> list(chunked(l, 4))
        [[1], [2], [3], [4]]

        >>> l = [1, 2, 3]
        >>> list(chunked(l, 4))
        [[1], [2], [3], []]

        >>> l = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        >>> list(chunked(l, 4))
        [[1, 2, 3], [4, 5, 6], [7, 8, 9], [10]]

    """
    chunksize = int(math.ceil(len(iterable) / n))
    return (iterable[i * chunksize:i * chunksize + chunksize] for i in range(n))


@flask.route('/', methods=['GET', 'POST'])
async def index():
    if request.method == 'GET':
        frm = await request.form
        if not frm or len(frm) == 0:
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
            # data = [data]
            method = data['method']  # type: str
            params = data.get('params', [])  # type: Union[dict, list]

            log.debug('Method: %s Params: %s', method, params)
            call_list = [make_call(method=method, params=params, jid=data.get('id', 1))]
        elif type(data) is list:
            if len(data) > MAX_BATCH:
                return jsonify(error=True, message=f"Too many batch calls. Max batch calls is: {MAX_BATCH}")
            call_dict = await filter_methods(data)
            call_chunks = []
            for meth, rq in call_dict.items():
                mcl = call_dict[meth]

                chunk_size = math.ceil(len(mcl) / CHUNK_SIZE) if len(mcl) > CHUNK_SIZE else 1
                call_chunks += list(chunked(call_dict[meth], chunk_size))

            log.info(call_chunks)

            call_list = []
            for c in call_chunks:
                call_list.append(make_batch_call(c[0]['method'], c))

        # else:
        #     raise Exception("JSON data was not dict or list.")
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
            log.debug('Returning response: %s', res)
            resp = jsonify(res)
            resp.headers['X-Upstream'] = endpoint.host if empty(endpoint.name) else endpoint.name
        else:
            res = [r[0] for i, r in enumerate(call_res)]
            log.debug('Returning response: %s', res)
            resp = jsonify(res)
            resp.headers['X-Upstream'] = 'Unknown due to batch call.'
        # resp = jsonify(jsonrpc='2.0', result=res, id=data.get('id', 1))
        # resp.headers['X-Upstream'] = endpoint.host if empty(endpoint.name) else endpoint.name
        return resp
    except AttributeError as e:
        log.exception('attribute error')
        return jsonify(error=True, message="Incorrectly formatted 'params'. Must be list or dict"), 400
    except EndpointException as e:
        log.warning('Exception while calling JsonRPC server %s - reason: %s %s', e.endpoint, type(e), str(e))
        return jsonify(error=True, message=f"Unknown error from upstream {e.endpoint.host}"), 502


if __name__ == "__main__":
    flask.run()
