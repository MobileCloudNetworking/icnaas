#!/bin/sh
IP=
/usr/bin/curl -i -H "Content-Type: application/json" -XPOST -d '{"hostname":"'$HOSTNAME'","public_ip":"'$IP'","layer":"'$1'","cell_id":"'$2'"}' http://[url]/icnaas/api/v1.0/routers
