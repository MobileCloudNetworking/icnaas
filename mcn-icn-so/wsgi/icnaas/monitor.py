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
__credits__ = ["Andre Gomes", "Bruno Sousa", "Claudio Marques"]
__license__ = "Apache"
__version__ = "1.2"
__maintainer__ = "Andre Gomes"
__email__ = "gomes@iam.unibe.ch"
__status__ = "Production"

"""
Monitor for ICNaaS.
Version 1.2
"""

from zabbix_api import ZabbixAPI
import time
import traceback
import sys

MAAS_UID = 'admin'
MAAS_PWD = 'zabbix'

CCN_ROUTER_CPU = 0
CCN_CACHE_SIZE = 1
CCN_CCND_STATUS = 2
CCN_CCNR_STATUS = 3
CCN_NETWORK_DAEMON_STATUS = 4
CCN_NUMBER_OF_INTERESTS = 5
CCN_REPOSITORY_SIZE = 6
CCN_TOTAL_NETWORK_TRAFFIC = 7

class ICNaaSMonitor(object):

    def __init__(self, maas_endpoint):
        """
        Initialize the ICNaaS Monitor object
        """
        # Connect to MaaS
        if maas_endpoint is None:
            self.maas_endpoint = '130.92.70.142'
        else:
            self.maas_endpoint = maas_endpoint
        self.server = 'http://' + self.maas_endpoint + '/zabbix'
        self.username = MAAS_UID
        self.password = MAAS_PWD
        self.connFailed = False

        # Zabbix API
        self.zapi = ZabbixAPI(server=self.server)
        for i in range(1,4):
            try:
                print('*** Connecting to MaaS at ' + self.server)
                self.zapi.login(self.username, self.password)
                print('*** Connected to MaaS')
                self.connFailed = False
                break
            except Exception as e:
                print('*** Caught exception: %s: %s' % (e.__class__, e))
                traceback.print_exc()
                print('*** Connection to MaaS has failed! Retrying ('+str(i)+').')
                self.connFailed = True
            time.sleep(3)
        if self.connFailed:
            print('*** Connection to MaaS has failed! Waiting for an update to try again.')
        self.__metrics = []

    @property
    def metrics(self):
        return self.__metrics

    @metrics.setter
    def metrics(self, value):
        self.__metrics = value
        pass

    def get(self, public_ip):
        measured_values = {}
        for metric in self.metrics:
            measured_values[metric] = self.get_value(metric, public_ip)
            if measured_values[metric] is None:
                return
        return measured_values

    def get_value(self, metric, public_ip):
        raise NotImplementedError

class ICNaaSMonitorCCNRouter(ICNaaSMonitor):

    def __init__(self, maas_endpoint):
        ICNaaSMonitor.__init__(self, maas_endpoint)
        self.metrics = [CCN_ROUTER_CPU, CCN_NUMBER_OF_INTERESTS]

    def get_value(self, metric, public_ip):
        item=""

        if metric == CCN_ROUTER_CPU:
            item = "system.cpu.util[,idle]"

        if metric == CCN_CACHE_SIZE:
            item = "ccnx.cache"

        if metric == CCN_CCND_STATUS:
            item = "proc.num[ccnd]"

        if metric == CCN_CCNR_STATUS:
            item = "proc.num[ccnr]"

        if metric == CCN_NETWORK_DAEMON_STATUS:
            item = "net.udp.listen[9695]"

        if metric == CCN_NUMBER_OF_INTERESTS:
            item = "ccnx.interests"

        if metric == CCN_REPOSITORY_SIZE:
            item = "ccnx.repository"

        if metric == CCN_TOTAL_NETWORK_TRAFFIC:
            item = "net.if.total[eth0]"

        try:
            hostid = self.zapi.host.get({"filter":{'ip':public_ip}})[0]["hostid"]
        except:
            print "WARNING: Public IP " + public_ip + " not found"
            return

        try:
            value = self.zapi.item.get({"output":"extend","hostids":hostid,"filter":{"key_":item}})[0]["lastvalue"]
            return value
        except Exception as e:
            print "ERROR: User metric not found"
            traceback.print_exc()
            
