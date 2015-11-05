#   Copyright (c) 2013-2015, University of Bern, Switzerland.
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

__author__ = "Andre Gomes"
__copyright__ = "Copyright (c) 2013-2015, Mobile Cloud Networking (MCN) project"
__credits__ = ["Andre Gomes"]
__license__ = "Apache"
__version__ = "1.3"
__maintainer__ = "Andre Gomes"
__email__ = "gomes@iam.unibe.ch"
__status__ = "Production"

"""
RESTful Web Service for ICNaaS.
Version 1.3
"""

#!flask/bin/python
from flask import Flask, jsonify, abort, make_response, request, url_for
import sqlite3
import paramiko

app = Flask(__name__)

@app.route('/availability', methods=['GET'])
def availability():
    return jsonify({'result': True}), 200

@app.route('/icnaas/api/v1.0/routers', methods=['GET'])
def get_routers():
    conn = sqlite3.connect('routers.db')
    curs = conn.cursor()
    curs.execute('SELECT * FROM routers')
    res = curs.fetchall()
    conn.close()
    routers = [
    {
        'public_ip' : public_ip, 
        'hostname' : hostname,
        'coord_x' : coord_x,
        'coord_y' : coord_y,
        'layer' : layer,
        'cell_id' : cell_id
    } for public_ip, hostname, coord_x, coord_y, layer, cell_id in res
    ]
    #return jsonify({'routers': [router_to_dict(router) for router in routers]})
    return jsonify({'routers': [make_public_router(router) for router in routers]}), 200

@app.route('/icnaas/api/v1.0/routers/cell/<cell_id>', methods=['GET'])
def get_routers_cell(cell_id):
    conn = sqlite3.connect('routers.db')
    curs = conn.cursor()
    t = (cell_id,)
    curs.execute('SELECT * FROM routers WHERE cell_id = ?', t)
    res = curs.fetchall()
    conn.close()
    routers = [
    {
        'public_ip' : public_ip, 
        'hostname' : hostname,
        'coord_x' : coord_x,
        'coord_y' : coord_y,
        'layer' : layer,
        'cell_id' : cell_id
    } for public_ip, hostname, coord_x, coord_y, layer, cell_id in res
    ]
    #return jsonify({'routers': [router_to_dict(router) for router in routers]})
    return jsonify({'routers': [make_public_router(router) for router in routers]}), 200

@app.route('/icnaas/api/v1.0/routers/<router_id>', methods=['GET'])
def get_router(router_id):
    conn = sqlite3.connect('routers.db')
    curs = conn.cursor()
    t = (router_id,)
    curs.execute('SELECT * FROM routers WHERE public_ip = ?', t)
    router = curs.fetchone()
    conn.close()
    if router is None:
        abort(404)
    return jsonify({'router': router_to_dict(router)}), 200

@app.route('/icnaas/api/v1.0/routers', methods=['POST'])
def create_router():
    if not request.json or not 'public_ip' in request.json \
        or not 'hostname' in request.json \
        or not 'layer' in request.json \
        or not 'cell_id' in request.json :
        abort(400)

    if 'coord_x' in request.json and 'coord_y' in request.json:
        router = (request.json['public_ip'], request.json['hostname'],
                request.json['coord_x'], request.json['coord_y'],
                request.json['layer'], request.json['cell_id']);
    else:
        router = (request.json['public_ip'], request.json['hostname'],
                None, None, request.json['layer'], request.json['cell_id']);

    conn = sqlite3.connect('routers.db')
    curs = conn.cursor()
    curs.execute('PRAGMA foreign_keys = ON')
    curs.execute('INSERT INTO routers VALUES (?,?,?,?,?,?)', router)
    conn.commit()

    # add routes to this new router (if not content source), 
    # add routes to other routers (previous layer if exists)
    layer = int(request.json['layer'])
    if layer != 100:
        create_routes_router(request.json['public_ip'], layer)
    if layer > 0:
        t = (layer,)
        curs.execute('SELECT MAX(layer) AS layer FROM routers WHERE layer < ?;', t)
        item = curs.fetchone()
        if item is not None:
            create_routes_layer_single(item[0], request.json['public_ip'], layer)
    conn.close()

    return jsonify({'router': router_to_dict(router)}), 201

@app.route('/icnaas/api/v1.0/routers/<router_id>', methods=['PUT'])
def update_router(router_id):
    conn = sqlite3.connect('routers.db')
    curs = conn.cursor()
    curs.execute('PRAGMA foreign_keys = ON')
    t = (router_id,)
    curs.execute('SELECT * FROM routers WHERE public_ip=?', t)
    router = curs.fetchone()
    if router is None:
        abort(404)
    if not request.json:
        abort(400)
    if 'public_ip' in request.json and type(request.json['public_ip']) != unicode:
        abort(400)
    if 'hostname' in request.json and type(request.json['hostname']) is not unicode:
        abort(400)
    if 'layer' not in request.json:
        abort(400)
    if 'cell_id' not in request.json:
        abort(400)

    conn.commit()
    conn.close()

    # update all routes with this router (first delete)
    delete_routes_dst(router_id)

    # delete all routers from this router
    delete_routes_router(router_id)

    conn = sqlite3.connect('routers.db')
    curs = conn.cursor()
    curs.execute('PRAGMA foreign_keys = ON')

    # check if more routers exist at the layer, and otherwise add routes to reroute
    p = (router[4], router_id)
    curs.execute('SELECT * FROM routers WHERE layer = ? and public_ip NOT LIKE ?', p)
    layer_router = curs.fetchone()
    if layer_router is None:
        q = (router[4],)
        curs.execute('SELECT MAX(layer) AS layer FROM routers WHERE layer < ?;', q)
        prev = curs.fetchone()
        curs.execute('SELECT MIN(layer) AS layer FROM routers WHERE layer > ?;', q)
        next = curs.fetchone()
        if prev is not None and next is not None:
            create_routes_layer_multiple(prev[0], next[0])

    if 'coord_x' in request.json and 'coord_y' in request.json:
        data = (request.json['public_ip'], request.json['hostname'],
                request.json['coord_x'], request.json['coord_y'],  
                request.json['layer'], request.json['cell_id'], router_id);
        curs.execute('UPDATE routers SET public_ip = ?, hostname = ?, coord_x = ?, coord_y = ?, layer = ?, cell_id = ? \
                    WHERE public_ip = ?', data)
    else:    
        data = (request.json['public_ip'], request.json['hostname'], 
                request.json['layer'], request.json['cell_id'], router_id);
        curs.execute('UPDATE routers SET public_ip = ?, hostname = ?, layer = ?, cell_id = ? \
                    WHERE public_ip = ?', data)
    conn.commit()
    t = (request.json['public_ip'],)
    curs.execute('SELECT * FROM routers WHERE public_ip = ?', t)
    router_new = curs.fetchone()

    # update all routes with this router (then create)
    layer = int(request.json['layer'])
    if layer != 100:
        create_routes_router(request.json['public_ip'], layer)
    if layer > 0:
        curs.execute('SELECT MAX(layer) AS layer FROM routers WHERE layer < ?;', p)
        item = curs.fetchone()
        if item is not None:
            create_routes_layer_single(item[0], request.json['public_ip'], layer)
    conn.close()

    return jsonify({'router': router_to_dict(router_new)}), 200

@app.route('/icnaas/api/v1.0/routers/<router_id>', methods=['DELETE'])
def delete_router(router_id):
    conn = sqlite3.connect('routers.db')
    curs = conn.cursor()
    t = (router_id,)
    curs.execute('SELECT * FROM routers WHERE public_ip = ?', t)
    router = curs.fetchone()
    if router is None:
        abort(404)

    # check if more routers exist at the layer, and otherwise add routes to reroute
    p = (router[4], router_id)
    curs.execute('SELECT * FROM routers WHERE layer = ? and public_ip NOT LIKE ?', p)
    layer_router = curs.fetchone()
    if layer_router is None:
        q = (router[4],)
        curs.execute('SELECT MAX(layer) AS layer FROM routers WHERE layer < ?;', q)
        prev = curs.fetchone()
        curs.execute('SELECT MIN(layer) AS layer FROM routers WHERE layer > ?;', q)
        next = curs.fetchone()
        if prev is not None and next is not None:
            create_routes_layer_multiple(prev[0], next[0])

    # delete all routes to this router, add new routes to higher layer if needed
    curs.execute('SELECT * FROM routes WHERE next_hop = ?', t)
    if curs.fetchone() is not None:
        conn.commit()
        conn.close()
        delete_routes_dst(router_id)

    # delete all routers from this router
    delete_routes_router(router_id)

    conn = sqlite3.connect('routers.db')
    curs = conn.cursor()
    curs.execute('DELETE FROM routers WHERE public_ip = ?', t)
    conn.commit()
    conn.close()

    return jsonify({'result': True}), 200

@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'error': 'Not found'}), 404)

def make_public_router(router):
    new_router= {}
    for field in router:
        if field == 'public_ip':
            new_router['uri'] = url_for('get_router', router_id=router['public_ip'], _external=True)
            new_router['public_ip'] = router[field]
        else:
            new_router[field] = router[field]
    return new_router

def router_to_dict(router):
    out = {
        'public_ip' : router[0], 
        'hostname' : router[1],
        'coord_x' : router[2],
        'coord_y' : router[3],
        'layer' : router[4],
        'cell_id' : router[5]
    }
    return out

@app.route('/icnaas/api/v1.0/prefixes', methods=['GET'])
def get_prefixes():
    conn = sqlite3.connect('routers.db')
    curs = conn.cursor()
    curs.execute('SELECT * FROM prefixes')
    res = curs.fetchall()
    conn.close()
    prefixes = [
    {
        'id' : prefix_id,
        'url' : url,
        'balancing' : balancing
    } for prefix_id, url, balancing in res
    ]
    #return jsonify({'prefixes': [prefix_to_dict(prefix) for prefix in prefixes]})
    return jsonify({'prefixes': [make_public_prefix(prefix) for prefix in prefixes]}), 200

@app.route('/icnaas/api/v1.0/prefixes/<prefix_id>', methods=['GET'])
def get_prefix(prefix_id):
    conn = sqlite3.connect('routers.db')
    curs = conn.cursor()
    t = (prefix_id,)
    curs.execute('SELECT * FROM prefixes WHERE id = ?', t)
    prefix = curs.fetchone()
    conn.close()
    if prefix is None:
        abort(404)
    return jsonify({'prefix': prefix_to_dict(prefix)}), 200

@app.route('/icnaas/api/v1.0/prefixes', methods=['POST'])
def create_prefix():
    if not request.json or not 'url' in request.json \
        or not 'balancing' in request.json :
        abort(400)

    data = (request.json['url'], request.json['balancing']);

    conn = sqlite3.connect('routers.db')
    curs = conn.cursor()
    curs.execute('PRAGMA foreign_keys = ON')
    curs.execute('INSERT INTO prefixes (url, balancing) VALUES (?,?)', data)
    conn.commit()
    rowid = curs.lastrowid
    t = (rowid,)
    curs.execute('SELECT * FROM prefixes WHERE id = ?', t)
    prefix = curs.fetchone()
    conn.close()

    # add new routes to all routers
    create_routes_prefix(rowid, request.json['url'], request.json['balancing'])

    return jsonify({'prefix': prefix_to_dict(prefix)}), 201

@app.route('/icnaas/api/v1.0/prefixes/<prefix_id>', methods=['PUT'])
def update_prefix(prefix_id):
    conn = sqlite3.connect('routers.db')
    curs = conn.cursor()
    curs.execute('PRAGMA foreign_keys = ON')
    t = (prefix_id,)
    curs.execute('SELECT * FROM prefixes WHERE id=?', t)
    prefix = curs.fetchone()
    if prefix is None:
        abort(404)
    if not request.json:
        abort(400)
    if 'url' in request.json and type(request.json['url']) != unicode:
        abort(400)
    if 'balancing' not in request.json:
        abort(400)

    data = (request.json['url'], request.json['balancing'], prefix_id);
    curs.execute('UPDATE prefixes SET url = ?, balancing = ? \
                WHERE id = ?', data)
    conn.commit()
    curs.execute('SELECT * FROM prefixes WHERE id = ?', t)
    prefix = curs.fetchone()
    conn.close()

    # change routes in all routers
    delete_routes_prefix(prefix_id, prefix[1])
    create_routes_prefix(prefix_id, request.json['url'])

    return jsonify({'prefix': prefix_to_dict(prefix)}), 200

@app.route('/icnaas/api/v1.0/prefixes/<prefix_id>', methods=['DELETE'])
def delete_prefix(prefix_id):
    conn = sqlite3.connect('routers.db')
    curs = conn.cursor()
    curs.execute('PRAGMA foreign_keys = ON')
    t = (prefix_id,)
    curs.execute('SELECT * FROM prefixes WHERE id = ?', t)
    prefix = curs.fetchone()
    if prefix is None:
        abort(404)

    conn.commit()
    conn.close()

    # delete routes in all routers
    delete_routes_prefix(prefix_id, prefix[1])

    conn = sqlite3.connect('routers.db')
    curs = conn.cursor()
    curs.execute('PRAGMA foreign_keys = ON')
    curs.execute('DELETE FROM prefixes WHERE id = ?', t)
    conn.commit()
    conn.close()

    return jsonify({'result': True}), 200

def make_public_prefix(prefix):
    new_prefix= {}
    for field in prefix:
        if field == 'id':
            new_prefix['uri'] = url_for('get_prefix', prefix_id=prefix['id'], _external=True)
        else:
            new_prefix[field] = prefix[field]
    return new_prefix

def prefix_to_dict(prefix):
    out = {
        'id' : prefix[0], 
        'url' : prefix[1],
        'balancing' : prefix[2]
    }
    return out

@app.route('/icnaas/api/v1.0/routes', methods=['GET'])
def get_routes():
    conn = sqlite3.connect('routers.db')
    curs = conn.cursor()
    curs.execute('SELECT * FROM routes')
    res = curs.fetchall()
    conn.close()
    routes = [
    {
        'id' : route_id,
        'router_ip' : router_ip,
        'prefix_id' : prefix_id,
        'next_hop' : next_hop,
        'balancing' : balancing
    } for route_id, router_ip, prefix_id, next_hop, balancing in res
    ]
    #return jsonify({'routes': [route_to_dict(route) for route in routes]})
    return jsonify({'routes': [make_public_route(route) for route in routes]}), 200

@app.route('/icnaas/api/v1.0/routes/<route_id>', methods=['GET'])
def get_route(route_id):
    conn = sqlite3.connect('routers.db')
    curs = conn.cursor()
    t = (route_id,)
    curs.execute('SELECT * FROM routes WHERE id = ?', t)
    route = curs.fetchone()
    conn.close()
    if route is None:
        abort(404)
    return jsonify({'route': route_to_dict(route)}), 200

def make_public_route(route):
    new_route= {}
    for field in route:
        if field == 'id':
            new_route['uri'] = url_for('get_route', route_id=route['id'], _external=True)
        else:
            new_route[field] = route[field]
    return new_route

def route_to_dict(route):
    out = {
        'id' : route[0],
        'router_ip' : route[1],
        'prefix_id' : route[2],
        'next_hop' : route[3],
        'balancing' : route[4]
    }
    return out

@app.route('/icnaas/api/v1.0/endpoints/client', methods=['GET'])
def get_client_endpoints():
    conn = sqlite3.connect('routers.db')
    curs = conn.cursor()
    curs.execute('SELECT * FROM routers WHERE layer = 0')
    res = curs.fetchall()
    conn.close()
    routers = [
    {
        'public_ip' : public_ip, 
        'hostname' : hostname,
        'coord_x' : coord_x,
        'coord_y' : coord_y,
        'layer' : layer,
        'cell_id' : cell_id
    } for public_ip, hostname, coord_x, coord_y, layer, cell_id in res
    ]
    #return jsonify({'routers': [router_to_dict(router) for router in routers]})
    return jsonify({'routers': [make_public_router(router) for router in routers]}), 200

@app.route('/icnaas/api/v1.0/endpoints/server', methods=['GET'])
def get_server_endpoints():
    conn = sqlite3.connect('routers.db')
    curs = conn.cursor()
    curs.execute('SELECT * FROM routers WHERE layer >= 1 AND layer != 100')
    res = curs.fetchall()
    conn.close()
    routers = [
    {
        'public_ip' : public_ip, 
        'hostname' : hostname,
        'coord_x' : coord_x,
        'coord_y' : coord_y,
        'layer' : layer,
        'cell_id' : cell_id
    } for public_ip, hostname, coord_x, coord_y, layer, cell_id in res
    ]
    #return jsonify({'routers': [router_to_dict(router) for router in routers]})
    return jsonify({'routers': [make_public_router(router) for router in routers]}), 200

def create_routes_router(public_ip, layer):
    # SPECIAL CASE: no higher layer, exit
    conn = sqlite3.connect('routers.db')
    curs = conn.cursor()
    t = (layer,)
    curs.execute('SELECT * FROM routers WHERE layer > ?', t);
    router = curs.fetchone()
    if router is None:
        return 0

    # if one exists at the same layer, copy from routes table
    t = (layer, public_ip)
    curs.execute('SELECT * FROM routers WHERE layer = ? AND public_ip NOT LIKE ?', t);
    router = curs.fetchone()
    if router is not None:
        # copy from routes
        t = (router[0],)
        curs.execute('SELECT * FROM routes WHERE router_ip LIKE ?', t)
        routes = curs.fetchall() 
        for route in routes:
            # add route to DB with router_ip as public_ip
            new_route = (public_ip, route[2], route[3], route[4]);
            curs.execute('PRAGMA foreign_keys = ON')
            curs.execute('INSERT INTO routes (router_ip, prefix_id, \
                next_hop, balancing) VALUES (?,?,?,?)', new_route)
            conn.commit()
            # add route to router via SSH
            p = (route[2],)
            curs.execute('SELECT url, balancing FROM prefixes WHERE id = ?', p)
            prefix = curs.fetchone()
            add_route_ssh(new_route, prefix[0], prefix[1])
    else:
        # otherwise, get list of next layer public_ips and iterate through all prefixes to create routes
        t = (int(layer),)
        curs.execute('SELECT DISTINCT(layer) FROM routers WHERE layer > ? ORDER BY layer ASC', t)
        next_layer = curs.fetchone()[0]
        t = (next_layer,)
        curs.execute('SELECT public_ip FROM routers WHERE layer = ?', t)
        ips = curs.fetchall()
        for ip in ips:
            curs.execute('SELECT * FROM prefixes')
            prefixes = curs.fetchall()
            for prefix in prefixes:
                route = (public_ip, prefix[0], ip[0], 0)
                curs.execute('PRAGMA foreign_keys = ON')
                curs.execute('INSERT INTO routes (router_ip, prefix_id, \
                    next_hop, balancing) VALUES (?,?,?,?)', route)
                conn.commit()
                # add route to router via SSH
                add_route_ssh(route, prefix[1], prefix[2])
    conn.close()
    return 0

def delete_routes_router(public_ip):
    # iterate over all routes where router_ip = public_ip
    conn = sqlite3.connect('routers.db')
    curs = conn.cursor()   

    t = (public_ip,)
    curs.execute('SELECT * FROM routes WHERE router_ip LIKE ?', t)
    routes = curs.fetchall()
    for route in routes:
        p = (route[2],)
        curs.execute('SELECT url FROM prefixes WHERE id = ?', p)
        # delete route from router via SSH
        delete_route_ssh(route, curs.fetchone()[0])
    curs.execute('PRAGMA foreign_keys = ON')
    curs.execute('DELETE FROM routes WHERE router_ip LIKE ?', t)
    conn.commit()
    conn.close()
    return 0

def create_routes_prefix(prefix_id, prefix_url, prefix_balancing):
    # iterate over all routes (by next_hop), add another with prefix_id
    conn = sqlite3.connect('routers.db')
    curs = conn.cursor()

    curs.execute('SELECT * FROM routes')
    route = curs.fetchone()
    # if routes already exist (not first prefix)
    if route is not None:
        curs.execute('SELECT public_ip FROM routers')
        ips = curs.fetchall()
        for ip in ips:
            t = (ip[0],)
            curs.execute('SELECT prefix_id FROM routes WHERE router_ip LIKE ?', t)
            base = curs.fetchone()
            if base is not None:
                t = (ip[0], base[0])
                curs.execute('SELECT * FROM routes WHERE router_ip LIKE ? AND prefix_id = ?', t)
                routes = curs.fetchall()
                for route in routes:
                    new_route = (ip[0], prefix_id, route[3], route[4])
                    curs.execute('PRAGMA foreign_keys = ON')
                    curs.execute('INSERT INTO routes (router_ip, prefix_id, \
                        next_hop, balancing) VALUES (?,?,?,?)', new_route)
                    conn.commit()
                    # add route to router via SSH
                    add_route_ssh(new_route, prefix_url, prefix_balancing)
    else:
        # Get layers
        curs.execute('SELECT DISTINCT(layer) FROM routers ORDER BY layer ASC')
        layers = curs.fetchall()
        for element in range(0, len(layers) - 1):
            create_routes_layer_multiple(layers[element][0], layers[element + 1][0]);
    conn.close()
    return 0

def create_routes_layer_single(layer, public_ip, dst_layer):
    # iterate through all prefixes, add routes to routers of layer with next_hop public_ip
    conn = sqlite3.connect('routers.db')
    curs = conn.cursor()

    curs.execute('SELECT id, url, balancing FROM prefixes')
    prefixes = curs.fetchall()
    for prefix in prefixes:
        t = (layer,)
        curs.execute('SELECT public_ip FROM routers WHERE layer = ?', t)
        ips = curs.fetchall()
        for ip in ips:
            route = (ip[0], prefix[0], public_ip, 0)
            curs.execute('PRAGMA foreign_keys = ON')
            curs.execute('INSERT INTO routes (router_ip, prefix_id, \
                next_hop, balancing) VALUES (?,?,?,?)', route)
            conn.commit()
            # add route to router via SSH
            add_route_ssh(route, prefix[1], prefix[2])


    # if routes exist to layer above the layer of router with public_ip, remove
    t = (layer,)
    curs.execute('SELECT public_ip FROM routers WHERE layer = ?', t)
    ips_layer = curs.fetchall()
    for ip_layer in ips_layer:
        t = (dst_layer,)
        curs.execute('SELECT public_ip FROM routers WHERE layer > ?', t)
        ips_layer2 = curs.fetchall()
        for ip_layer2 in ips_layer2:
            t = (ip_layer[0], ip_layer2[0])
            curs.execute('SELECT * FROM routes WHERE router_ip LIKE ? AND next_hop LIKE ?', t)
            routes = curs.fetchall()
            for route in routes:
                p = (route[2],)
                curs.execute('SELECT url FROM prefixes WHERE id = ?', p)
                # delete route from router via SSH
                delete_route_ssh(route, curs.fetchone()[0])
            curs.execute('PRAGMA foreign_keys = ON')
            curs.execute('DELETE FROM routes WHERE router_ip LIKE ? AND next_hop LIKE ?', t)
            conn.commit()
    conn.close()
    return 0

def create_routes_layer_multiple(layer_src, layer_dst):
    # get list of layer_src/layer_dst public_ips and iterate through all prefixes to create routes at layer_src routers
    conn = sqlite3.connect('routers.db')
    curs = conn.cursor()

    t = (layer_src,)
    curs.execute('SELECT public_ip FROM routers WHERE layer = ?', t)
    ips_src = curs.fetchall()

    t = (layer_dst,)
    curs.execute('SELECT public_ip FROM routers WHERE layer = ?', t)
    ips_dst = curs.fetchall()

    curs.execute('SELECT id, url, balancing FROM prefixes')
    prefixes = curs.fetchall()
    for prefix in prefixes:
        for ip_src in ips_src:
            for ip_dst in ips_dst:
                route = (ip_src[0], prefix[0], ip_dst[0], 0)
                curs.execute('PRAGMA foreign_keys = ON')
                curs.execute('INSERT INTO routes (router_ip, prefix_id, \
                    next_hop, balancing) VALUES (?,?,?,?)', route)
                conn.commit()
                # add route to router via SSH
                add_route_ssh(route, prefix[1], prefix[2])
    conn.close()
    return 0

def delete_routes_dst(public_ip):
    # delete all routes with public_ip = next_hop.
    conn = sqlite3.connect('routers.db')
    curs = conn.cursor()

    t = (public_ip,)
    curs.execute('SELECT * FROM routes WHERE next_hop LIKE ?', t)
    routes = curs.fetchall()
    for route in routes:
        p = (route[2],)
        curs.execute('SELECT url FROM prefixes WHERE id = ?', p)
        # delete route from router via SSH
        delete_route_ssh(route, curs.fetchone()[0])
    curs.execute('PRAGMA foreign_keys = ON')
    curs.execute('DELETE FROM routes WHERE next_hop LIKE ?', t)
    conn.commit()
    conn.close()
    return 0

def delete_routes_prefix(prefix_id, prefix_url):
    # delete all routes with prefix_id = prefix_id.
    conn = sqlite3.connect('routers.db')
    curs = conn.cursor()

    t = (prefix_id,)
    curs.execute('SELECT * FROM routes WHERE prefix_id LIKE ?', t)
    routes = curs.fetchall()
    for route in routes:
        # delete route from router via SSH
        delete_route_ssh(route, prefix_url)
    curs.execute('PRAGMA foreign_keys = ON')
    curs.execute('DELETE FROM routes WHERE prefix_id LIKE ?', t)
    conn.commit()
    conn.close()
    return 0

def add_route_ssh(route, prefix_url, balancing):
    host = route[0]
    cmd = '/home/centos/ccnx-0.8.2/bin/ccndc add ' + prefix_url \
        + ' tcp ' + route[2] + ' 9695'
    execute_ssh_command(host, cmd)
    if int(balancing) > 0:
        cmd2 = '/home/centos/ccnx-0.8.2/bin/ccndc setstrategy ' + prefix_url \
        + ' loadsharing'
        execute_ssh_command(host, cmd2)
    return 0

def delete_route_ssh(route, prefix_url):
    host = route[1]
    cmd = '/home/centos/ccnx-0.8.2/bin/ccndc del ' + prefix_url \
        + ' tcp ' + route[3] + ' 9695'
    execute_ssh_command(host, cmd)
    return 0

def execute_ssh_command(host, command):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(host, username='centos', key_filename='id_rsa', timeout=5)
        stdin, stdout, stderr = ssh.exec_command(command)
        #print stdout.readlines()
        ssh.close()
    except Exception as e:
        print('SSH Connection Exception: %s: %s' % (e.__class__, e))

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0')
