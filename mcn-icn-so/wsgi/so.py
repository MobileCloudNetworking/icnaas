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
__version__ = "2.0"
__maintainer__ = "Andre Gomes"
__email__ = "gomes@inf.unibe.ch"
__status__ = "Production"

"""
Service Orchestrator for ICNaaS.
Version 2.0
"""

import os
import random
import requests
import threading
import time

import icnaas.monitor
import icnaas.template_generator

from sdk.mcn import util
from sm.so import service_orchestrator
from sm.so.service_orchestrator import LOG
from sm.so.service_orchestrator import BUNDLE_DIR

DEFAULT_REGION = 'UBern'
FMC_ENABLED = False
NUM_LAYERS = 2
NUM_ROUTERS_LAYER = 1

# DO NOT CHANGE
SCALE_NO_ACTION = 0
SCALE_IN_CPU = 1
SCALE_OUT_CPU = 2
SCALE_IN_INTERESTS = 3
SCALE_OUT_INTERESTS = 4

# Safeguards to avoid scaling because of a peak, scale only if load remains for X minutes
CPU_SCALE_IN_SAFEGUARD = 10
CPU_SCALE_OUT_SAFEGUARD = 10
INTERESTS_SCALE_IN_SAFEGUARD = 5
INTERESTS_SCALE_OUT_SAFEGUARD = 5

DEFAULT_METRICS = [icnaas.monitor.CCN_ROUTER_CPU, icnaas.monitor.CCN_NUMBER_OF_INTERESTS]
DEFAULT_THRESHOLDS = { icnaas.monitor.CCN_ROUTER_CPU: { 'scale_out': 75, 'scale_in': 0 }, \
            icnaas.monitor.CCN_NUMBER_OF_INTERESTS: { 'scale_out': 1500, 'scale_in': 30 } }

class SOE(service_orchestrator.Execution):
    """
    SO execution part.
    """
    def __init__(self, token, tenant, ready_event):
        super(SOE, self).__init__(token, tenant)
        self.token = token
        self.tenant = tenant
        self.event = ready_event
        self.updated = False
        self.endpoint = None
        self.maas_endpoint = None
        self.mobaas_endpoint = None
        # Default topology
        self.layers = {}
        self.routers = {}
        self.stack_id = None
        self.deployer = util.get_deployer(self.token,
                                          url_type='public',
                                          tenant_name=self.tenant,
                                          region=DEFAULT_REGION)

    def design(self):
        """
        Do initial design steps here.
        """
        LOG.debug('Executing design logic')
        self.resolver.design()
        # Create topology
        routers_count = 0
        init_cell_id = 200
        for layer in range(NUM_LAYERS):
            self.layers[layer] = { 'cpu_scale_in_count': 0, 'cpu_scale_out_count': 0, \
                'int_scale_in_count': 0, 'int_scale_out_count': 0 }
            for i in range(1,NUM_ROUTERS_LAYER + 1):
                routers_count += 1
                cell_id = 0
                if layer == 0:
                    cell_id = init_cell_id
                    init_cell_id += 1
                self.routers[routers_count] = { 'public_ip': 'unassigned', 'layer': layer, \
                            'cell_id': cell_id, 'provisioned': False }

    def deploy(self, attributes):
        """
        deploy SICs.
        """
        LOG.debug('Deploy service dependencies')
        self.resolver.deploy()
        LOG.debug('Executing deployment logic')
        # Get template
        generator = icnaas.template_generator.ICNaaSTemplateGenerator(self.routers)
        template = generator.generate(fmc = FMC_ENABLED)
        # Deploy template
        if self.stack_id is None:
            self.stack_id = self.deployer.deploy(template, self.token, \
                name='icnaas_' + str(random.randint(1000, 9999)))

    def provision(self, attributes=None):
        """
        (Optional) if not done during deployment - provision.
        """
        self.resolver.provision()
        LOG.debug('ICN SO provision - Getting EPs')
        for ep_entity in self.resolver.service_inst_endpoints:
            for item in ep_entity:
                if 'mcn.endpoint.mobaas' in item['attributes']:
                    self.mobaas_endpoint = item['attributes']['mcn.endpoint.mobaas']

        # EP is only the IP
        if self.mobaas_endpoint is not None and self.mobaas_endpoint.startswith('http'):
            self.mobaas_endpoint = self.mobaas_endpoint.split('/')[2].split(':')[0]
            
        LOG.info('Now I can provision my resources once my resources are created. Service info:')
        LOG.info(self.resolver.service_inst_endpoints)

        # Wait for create/update to be completed
        while (True):
            if self.stack_id is not None:
                tmp = self.deployer.details(self.stack_id, self.token)
                if tmp['state'] == 'CREATE_COMPLETE' or tmp['state'] == 'UPDATE_COMPLETE':
                    break
                else:
                    time.sleep(10)

        LOG.debug('Executing resource provisioning logic')
        # XXX note that provisioning of external services must happen before resource provisioning
        # Get endpoint of MaaS
        if attributes:
            #print attributes
            if 'mcn.endpoint.maas' in attributes:
                self.maas_endpoint = str(attributes['mcn.endpoint.maas'])
            if 'mcn.endpoint.mobaas' in attributes:
                self.mobaas_endpoint = str(attributes['mcn.endpoint.mobaas'])

        # Update stack
        self.update(True)

        # Mark all routers as provisioned
        for r in self.routers:
            self.routers[r]['provisioned'] = True

        # once logic executes, deploy phase is done
        self.event.set()

    def dispose(self):
        """
        Dispose SICs.
        """
        LOG.info('Disposing of 3rd party service instances...')
        self.resolver.dispose()

        if self.stack_id is not None:
            LOG.info('Disposing of resource instances...')
            self.deployer.dispose(self.stack_id, self.token)
            self.endpoint = None
            self.maas_endpoint = None
            self.routers = { 1: { 'public_ip': 'unassigned', 'layer': 0, 'cell_id': 200, \
            'provisioned': False, 'scale_in_count': 0, 'scale_out_count': 0 }, \
            2: { 'public_ip': 'unassigned', 'layer': 1, 'cell_id': 0, \
            'provisioned': False, 'scale_in_count': 0, 'scale_out_count': 0 } }
            self.stack_id = None

    def state(self):
        """
        Report on state.
        """

        # TODO ideally here you compose what attributes should be returned to the SM
        # In this case only the state attributes are returned.
        resolver_state = self.resolver.state()
        LOG.info('Resolver state:')
        LOG.info(resolver_state.__repr__())

        if self.stack_id is not None:
            tmp = self.deployer.details(self.stack_id, self.token)
            # Update routers dictionary and service endpoint
            if tmp.get('output', None) is not None:
                for i in tmp['output']:
                    # CCNx Router IP
                    if i['output_key'].startswith('mcn.ccnx'):
                        router_id = i['output_key'].split('.')[2][6:]
                        self.routers[int(router_id)]['public_ip'] = str(i['output_value'])
                    # ICNaaS Service Endpoint
                    elif i['output_key'] == 'mcn.endpoint.icnaas':
                        self.endpoint = 'http://' + str(i['output_value']) + ':5000'
                        i['output_value'] = self.endpoint
                return tmp['state'], self.stack_id, tmp['output']
            else:
                return tmp['state'], self.stack_id, None
        else:
            return 'Unknown', 'N/A'

    def update(self, provisioning = False, attributes = None):
        """
        deploy updated SICs.
        """
        LOG.debug('Executing update deployment logic')
        # Check if attributes are being updated
        if attributes:
            if 'mcn.endpoint.maas' in attributes:
                self.maas_endpoint = str(attributes['mcn.endpoint.maas'])
            if 'mcn.endpoint.mobaas' in attributes:
                self.mobaas_endpoint = str(attributes['mcn.endpoint.mobaas'])
        # Get new template
        generator = icnaas.template_generator.ICNaaSTemplateGenerator(self.routers, self.maas_endpoint, \
            self.mobaas_endpoint)
        template = generator.generate(provisioning, FMC_ENABLED)
        # Wait for any pending operation to complete
        while (True):
            if self.stack_id is not None:
                tmp = self.deployer.details(self.stack_id, self.token)
                if tmp['state'] == 'CREATE_COMPLETE' or tmp['state'] == 'UPDATE_COMPLETE':
                    break
                else:
                    time.sleep(10)
        # Deploy new template
        if self.stack_id is not None:
            self.deployer.update(self.stack_id, template, self.token)
        # Mark as updated for SOD
        self.updated = True

    def notify(self, entity, attributes, extras):
        super(SOE, self).notify(entity, attributes, extras)
        # TODO here you can add logic to handle a notification event sent by the CC
        # XXX this is optional

class SOD(service_orchestrator.Decision, threading.Thread):
    """
    Decision part of SO.
    """

    def __init__(self, so_e, token, ready_event):
        super(service_orchestrator.Decision, self).__init__()
        self.so_e = so_e
        self.token = token
        self.event = ready_event
        self.monitor = None
        self.rules_engine = RulesEngine()

    def run(self):
        """
        Decision part implementation goes here.
        """
        while True:
            # It is unlikely that logic executed will be of any use until the provisioning phase has completed
            LOG.debug('Waiting for deploy and provisioning to finish')
            self.event.wait()
            LOG.debug('Starting runtime logic...')
            # Decision logic
            # Until service instance is destroyed
            while self.so_e.stack_id is not None:
                # Check if update is complete
                while True:
                    tmp = self.so_e.deployer.details(self.so_e.stack_id, self.so_e.token)
                    if tmp['state'] == 'UPDATE_COMPLETE':
                        break
                    else:
                        time.sleep(10)
                # Set updated back to False
                self.so_e.updated = False
                # Update the information about CCNx routers
                self.so_e.state()
                # Then, attempt to connect to MaaS
                self.monitor = icnaas.monitor.ICNaaSMonitorCCNRouter(self.so_e.maas_endpoint)
                # Afterwards, keep checking the metrics until service is updated
                while not self.so_e.updated:
                    self.check_metrics()
                    for i in range(0, 6):
                        if self.so_e.updated:
                            break
                        time.sleep(10)
            self.event = ready_event
            
    def check_metrics(self):
        # If monitoring is not connected, ignore
        if self.monitor.connFailed:
            return
        # Check metrics for all active routers in each layer
        for layer in self.so_e.layers:
            layer_values = { 'routers_count': 0, 'sum_cpu': 0.0, 'sum_interests': 0 }
            for r in self.so_e.routers:
                if self.so_e.routers[r]['layer'] != layer:
                    continue
                if self.so_e.routers[r]['public_ip'] != 'unassigned':
                    values = self.monitor.get(self.so_e.routers[r]['public_ip'])
                if values is not None:
                    layer_values['routers_count'] += 1
                    layer_values['sum_cpu'] += float(values[icnaas.monitor.CCN_ROUTER_CPU])
                    layer_values['sum_interests'] += int(values[icnaas.monitor.CCN_NUMBER_OF_INTERESTS])
            if layer_values['routers_count'] > 0:
                layer_avg = { icnaas.monitor.CCN_ROUTER_CPU: (layer_values['sum_cpu'] / layer_values['routers_count']), \
                    icnaas.monitor.CCN_NUMBER_OF_INTERESTS: (layer_values['sum_interests'] / float(layer_values['routers_count'])) }
                actions = self.rules_engine.process(layer_avg)
                if not actions:
                    self.scale_actions(SCALE_NO_ACTION, layer)
                else:
                    for a in actions:
                        self.scale_actions(a, layer)

    def scale_actions(self, action, layer):
        if action == SCALE_NO_ACTION:
            self.so_e.layers[layer]['cpu_scale_in_count'] = 0
            self.so_e.layers[layer]['cpu_scale_out_count'] = 0
            self.so_e.layers[layer]['int_scale_in_count'] = 0
            self.so_e.layers[layer]['int_scale_out_count'] = 0
        elif action == SCALE_IN_CPU or action == SCALE_IN_INTERESTS:
            safeguard = CPU_SCALE_IN_SAFEGUARD
            count = self.so_e.layers[layer]['cpu_scale_in_count']
            if action == SCALE_IN_INTERESTS:
                safeguard = INTERESTS_SCALE_IN_SAFEGUARD
                count = self.so_e.layers[layer]['int_scale_in_count']
                self.so_e.layers[layer]['int_scale_out_count'] = 0
            else:
                self.so_e.layers[layer]['cpu_scale_out_count'] = 0
            if count >= (safeguard - 1):
                if action == SCALE_IN_INTERESTS:
                    self.so_e.layers[layer]['int_scale_in_count'] = 0
                else:
                    self.so_e.layers[layer]['cpu_scale_in_count'] = 0
                # Do not scale in if minimum amount of components are running
                minimum = 1
                #if layer == 1:
                #    minimum = 2
                if sum(1 for x in self.so_e.routers.values() if x['layer'] == layer) > minimum:
                    # SCALE IN
                    for k in reversed(sorted(self.so_e.routers.keys())):
                        if self.so_e.routers[k]['layer'] == layer:
                            # Remove from ICN Manager
                            out = requests.delete(self.so_e.endpoint + '/icnaas/api/v1.0/routers/' \
                                + self.so_e.routers[k]['public_ip'])
                            # Update service instance
                            del self.so_e.routers[k]
                            self.so_e.update()
                            self.so_e.provision()
                            self.so_e.state()
                            return
            else:
                if action == SCALE_IN_INTERESTS:
                    self.so_e.layers[layer]['int_scale_in_count'] += 1
                else:
                    self.so_e.layers[layer]['cpu_scale_in_count'] += 1
        elif action == SCALE_OUT_CPU or action == SCALE_OUT_INTERESTS:
            safeguard = CPU_SCALE_OUT_SAFEGUARD
            count = self.so_e.layers[layer]['cpu_scale_out_count']
            if action == SCALE_OUT_INTERESTS:
                safeguard = INTERESTS_SCALE_OUT_SAFEGUARD
                count = self.so_e.layers[layer]['int_scale_out_count']
                self.so_e.layers[layer]['int_scale_in_count'] = 0
            else:
                self.so_e.layers[layer]['cpu_scale_in_count'] = 0
            # SCALE OUT
            if count >= (safeguard - 1):
                if action == SCALE_OUT_INTERESTS:
                    self.so_e.layers[layer]['int_scale_out_count'] = 0
                else:
                    self.so_e.layers[layer]['cpu_scale_out_count'] = 0
                cell_id = 0
                if layer == 0:
                    for x in self.so_e.routers.values():
                        if x['cell_id'] > cell_id:
                            cell_id = x['cell_id']
                    cell_id += 1
                key = max(self.so_e.routers.keys()) + 1
                self.so_e.routers[key] = { 'public_ip': 'unassigned', 'layer': layer, \
                    'cell_id': cell_id, 'provisioned': False }
                self.so_e.update()
                self.so_e.provision()
                self.so_e.state()
                return
            else:
                if action == SCALE_OUT_INTERESTS:
                    self.so_e.layers[layer]['int_scale_out_count'] += 1
                else:
                    self.so_e.layers[layer]['cpu_scale_out_count'] += 1

class RulesEngine(object):
    """
    Rules Engine for Scaling Decisions
    """

    def __init__(self, metrics = None, thresholds = None):
        if metrics is None:
            self.metrics = DEFAULT_METRICS
        else:
            self.metrics = metrics
        if thresholds is None:
            self.thresholds = DEFAULT_THRESHOLDS
        else:
            self.thresholds = thresholds

    def process(self, values):
        actions = []
        for metric in self.metrics:
            if metric == icnaas.monitor.CCN_ROUTER_CPU:
                if (100 - float(values[icnaas.monitor.CCN_ROUTER_CPU])) >= \
                    self.thresholds[icnaas.monitor.CCN_ROUTER_CPU]['scale_out']:
                    actions.append(SCALE_OUT_CPU)
                elif (100 - float(values[icnaas.monitor.CCN_ROUTER_CPU])) <= \
                    self.thresholds[icnaas.monitor.CCN_ROUTER_CPU]['scale_in']:
                    actions.append(SCALE_IN_CPU)
            elif metric == icnaas.monitor.CCN_NUMBER_OF_INTERESTS:
                if int(values[icnaas.monitor.CCN_NUMBER_OF_INTERESTS]) >= \
                    self.thresholds[icnaas.monitor.CCN_NUMBER_OF_INTERESTS]['scale_out']:
                    actions.append(SCALE_OUT_INTERESTS)
                elif int(values[icnaas.monitor.CCN_NUMBER_OF_INTERESTS]) <= \
                    self.thresholds[icnaas.monitor.CCN_NUMBER_OF_INTERESTS]['scale_in']:
                    actions.append(SCALE_IN_INTERESTS)
            else:
                pass
        return actions

class ServiceOrchestrator(object):
    """
    ICNaaS SO.
    """

    def __init__(self, token, tenant):
        # this python thread event is used to notify the SOD that the runtime phase can execute its logic
        self.event = threading.Event()
        self.so_e = SOE(token=token, tenant=tenant, ready_event=self.event)
        self.so_d = SOD(so_e=self.so_e, token=token, ready_event=self.event)
        LOG.debug('Starting SOD thread...')
        self.so_d.start()
