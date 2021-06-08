# -*- coding: utf8 -*-
import json
import logging
from json.decoder import JSONDecodeError

from django.db import transaction

from console.services.market_app.new_app import NewApp
from console.services.market_app.original_app import OriginalApp
from console.services.market_app.new_components import NewComponents
from console.services.market_app.update_components import UpdateComponents
# service
from console.services.group_service import group_service
from console.services.app import app_market_service
# repo
from console.repositories.app import service_source_repo
from console.repositories.market_app_repo import rainbond_app_repo
# exception
from console.exception.main import AbortRequest
# model
from www.models.main import TenantServiceGroup

logger = logging.getLogger("default")


class MarketApp(object):
    def __init__(self, enterprise_id, tenant, region_name, user, version, service_group: TenantServiceGroup,
                 component_keys):
        """
        components_keys: component keys that the user select.
        """
        self.enterprise_id = enterprise_id
        self.tenant = tenant
        self.tenant_id = tenant.tenant_id
        self.region_name = region_name
        self.user = user

        self.app_id = service_group.service_group_id
        self.upgrade_group_id = service_group.ID
        self.app_model_key = service_group.group_key
        self.version = version
        self.component_keys = component_keys

        # app template
        self.app_template_source = self._app_template_source()
        self.app_template = self._app_template()
        # original app
        self.original_app = OriginalApp(self.app_id, self.app_model_key, self.upgrade_group_id)

    @transaction.atomic
    def upgrade(self):
        # TODO(huangrh): install plugins
        # TODO(huangrh): config groups
        # components
        self._update_components()
        # TODO(huangrh): component dependencies
        # TODO(huangrh):  create update record
        # TODO(huangrh):  build, update or nothing

    def deploy(self):
        pass

    def _update_components(self):
        """
        1. create new components
        2. update existing components
        3. rollback on failure
        """
        new_app = self._new_app()
        new_app.save()
        try:
            self._sync_components(new_app.components())
        except Exception as e:
            # TODO: catch api error
            logger.exception(e)
            raise e

    def _sync_components(self, components):
        """
        synchronous components  to the application in region
        """
        # TODO(huangrh)
        pass

    def _rollback_original_app(self):
        """
        rollback the original app on failure
        """
        # TODO(huangrh): retry
        self._sync_components(self.original_app.components)

    def _app_template(self):
        if not self.app_template_source.is_install_from_cloud():
            _, app_version = rainbond_app_repo.get_rainbond_app_and_version(self.enterprise_id, self.app_model_key,
                                                                            self.version)
        else:
            _, app_version = app_market_service.cloud_app_model_to_db_model(self.app_template_source.get_market_name(),
                                                                            self.app_model_key,
                                                                            self.version)
        try:
            return json.loads(app_version.app_template)
        except JSONDecodeError:
            raise AbortRequest("invalid app template", "该版本应用模板已损坏, 无法升级")

    def _app_template_source(self):
        components = group_service.get_rainbond_services(self.app_id, self.app_model_key, self.upgrade_group_id)
        if not components:
            raise AbortRequest("components not found", "找不到组件", status_code=404, error_code=404)
        component = components[0]
        component_source = service_source_repo.get_service_source(component.tenant_id, component.service_id)
        return component_source

    def _new_app(self):
        # new components
        new_components = NewComponents(self.tenant, self.region_name, self.user, self.original_app,
                                       self.app_model_key,
                                       self.app_template,
                                       self.version,
                                       self.app_template_source.is_install_from_cloud(),
                                       self.component_keys,
                                       self.app_template_source.get_market_name()).components
        # components that need to be updated
        update_components = UpdateComponents(self.original_app, self.app_template, self.component_keys).components
        return NewApp(self.upgrade_group_id, new_components, update_components)
