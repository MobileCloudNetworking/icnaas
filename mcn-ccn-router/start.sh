#!/bin/bash
export CCND_CAP=262144
export CCNR_DIRECTORY=/home/centos/repo
export FMC_MONITORING=
/usr/bin/setsid /home/centos/ccnx-0.8.2/bin/ccnd >/dev/null 2>&1 &
sleep 10
/usr/bin/setsid /home/centos/ccnx-0.8.2/bin/ccnr >/dev/null 2>&1 &
