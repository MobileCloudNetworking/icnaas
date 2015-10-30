# Copyright 2014-2015 Zuercher Hochschule fuer Angewandte Wissenschaften
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.


from occi.backend import KindBackend

from sm.so_manager import ServiceParameters
from sm.so_manager import AsychExe
from sm.so_manager import InitSO
from sm.so_manager import ActivateSO
from sm.so_manager import DeploySO
from sm.so_manager import ProvisionSO
from sm.so_manager import RetrieveSO
from sm.so_manager import UpdateSO
from sm.so_manager import DestroySO

__author__ = 'andy'

# service state model:
#  - initialise
#  - activate
#  - deploy
#  - provision -> This is THE terminal state
#  - "active" (entered into runtime ops) This is not used
#  - update
#  - destroy
#  - fail


class ServiceBackend(KindBackend):
    """
    Provides the basic functionality required to CRUD SOs
    """
    def __init__(self, app):
        self.registry = app.registry
        # these are read from a location specified in sm,cfg, service_manager::service_params
        self.srv_prms = ServiceParameters()

    def create(self, entity, extras):
        super(ServiceBackend, self).create(entity, extras)
        extras['srv_prms'] = self.srv_prms
        # create the SO container
        InitSO(entity, extras).run()
        # run background tasks
        AsychExe([ActivateSO(entity, extras), DeploySO(entity, extras),
                  ProvisionSO(entity, extras)], self.registry).start()

    def retrieve(self, entity, extras):
        super(ServiceBackend, self).retrieve(entity, extras)
        RetrieveSO(entity, extras).run()

    def delete(self, entity, extras):
        super(ServiceBackend, self).delete(entity, extras)
        extras['srv_prms'] = self.srv_prms
        AsychExe([DestroySO(entity, extras)]).start()

    def update(self, old, new, extras):
        super(ServiceBackend, self).update(old, new, extras)
        extras['srv_prms'] = self.srv_prms
        UpdateSO(old, extras, new).run()

    def replace(self, old, new, extras):
        raise NotImplementedError()
