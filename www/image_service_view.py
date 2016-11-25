# -*- coding: utf8 -*-
import json
import logging

from django.http.response import JsonResponse
from django.template.response import TemplateResponse
from django.views.decorators.cache import never_cache

from www.decorator import perm_required
from www.models.main import TenantServiceInfo, ServiceInfo, ImageServiceRelation, TenantServiceEnvVar, \
    TenantServicesPort, TenantServiceVolume
from www.monitorservice.monitorhook import MonitorHook
from www.service_http import RegionServiceApi
from www.tenantservice.baseservice import TenantRegionService, TenantAccountService, TenantUsedResource, \
    BaseTenantService
from www.utils.crypt import make_uuid
from www.views.base import AuthedView
from www.views.mixin import LeftSideBarMixin
from django.conf import settings
import httplib2

logger = logging.getLogger('default')
tenantRegionService = TenantRegionService()
tenantAccountService = TenantAccountService()
tenantUsedResource = TenantUsedResource()
baseService = BaseTenantService()
monitorhook = MonitorHook()
regionClient = RegionServiceApi()


class ImageServiceDeploy(LeftSideBarMixin, AuthedView):
    def get_media(self):
        media = super(AuthedView, self).get_media() + self.vendor(
            'www/css/goodrainstyle.css', 'www/css/style.css', 'www/css/style-responsive.css', 'www/js/jquery.cookie.js',
            'www/js/common-scripts.js', 'www/js/jquery.dcjqaccordion.2.7.js', 'www/js/jquery.scrollTo.min.js',
            'www/js/respond.min.js', 'www/js/app-create.js')
        return media

    @never_cache
    @perm_required('code_deploy')
    def get(self, request, *args, **kwargs):
        choose_region = request.GET.get("region", None)
        if choose_region is not None:
            self.response_region = choose_region

        context = self.get_context()
        service_id = request.GET.get("id", "")

        try:
            if service_id != "":
                imags = ImageServiceRelation.objects.get(service_id=service_id)
                context["image_url"] = imags.image_url
                context["service_id"] = service_id
        except Exception as e:
            logger.error(e)
        return TemplateResponse(self.request, "www/app_create_step_two.html", context)

    @never_cache
    @perm_required('code_deploy')
    def post(self, request, *args, **kwargs):
        result = {}
        try:
            service_id = request.POST.get("service_id", "")
            image_url = request.POST.get("image_url", "")
            result["image_url"] = image_url
            if image_url != "":
                imagesr = None
                if service_id != "":
                    try:
                        imagesr = ImageServiceRelation.objects.get(service_id=service_id)
                    except Exception:
                        pass

                if imagesr is None:
                    imagesr = ImageServiceRelation()
                    service_id = make_uuid(self.tenant.tenant_id)

                imagesr.tenant_id = self.tenant.tenant_id
                imagesr.service_id = service_id
                imagesr.image_url = image_url
                imagesr.save()

                result["ok"] = True
                result["id"] = service_id
            else:
                result["ok"] = False
                return JsonResponse(result, status=500)
        except Exception as e:
            logger.exception(e)
        return JsonResponse(result, status=200)


class ImageParamsViews(LeftSideBarMixin, AuthedView):
    def get_media(self):
        media = super(AuthedView, self).get_media() + self.vendor(
            'www/css/goodrainstyle.css', 'www/css/style.css', 'www/css/style-responsive.css', 'www/js/jquery.cookie.js',
            'www/js/common-scripts.js', 'www/js/jquery.dcjqaccordion.2.7.js', 'www/js/jquery.scrollTo.min.js',
            'www/js/respond.min.js')
        return media

    @never_cache
    @perm_required('code_deploy')
    def get(self, request, *args, **kwargs):
        choose_region = request.GET.get("region", None)
        if choose_region is not None:
            self.response_region = choose_region

        context = self.get_context()
        try:
            service_id = request.GET.get("id", "")
            context["service_id"] = service_id
            return TemplateResponse(self.request, "www/app_create_step_four.html", context)
        except Exception as e:
            logger.exception(e)

    @never_cache
    @perm_required('code_deploy')
    def post(self, request, *args, **kwargs):
        service_id = request.POST.get("service_id", "")
        result = {}
        try:
            imsr = ImageServiceRelation.objects.get(service_id=service_id)
            tenant_id = imsr.tenant_id
            image_url = imsr.image_url
        except Exception as e:
            logger.exception(e)
            result["status"] = "notfound"
            return JsonResponse(result, status=200)

        service_alias = "gr" + service_id[-6:]
        try:
            success = tenantRegionService.init_for_region(self.response_region, self.tenantName, tenant_id, self.user)

            # 从url中分析出来service_cname 和 version
            version = ""
            if ":" in image_url:
                index = image_url.index(":")
                service_cname = image_url[:index]
                version = image_url[index + 1:]
            else:
                service_cname = image_url
                version = "lastest"

            # 端口信息
            port_list = json.loads(request.POST.get("port_list", "[]"))
            # 环境变量信息
            env_list = json.loads(request.POST.get("env_list", "[]"))
            # 持久化目录信息
            volume_list = json.loads(request.POST.get("volume_list", "[]"))
            # 资源内存
            image_service_memory = request.POST.get("image_service_memory", 128)
            # 启动命令
            start_cmd = request.POST.get("start_cmd", "")

            if not success:
                result["status"] = "failure"
                return JsonResponse(result, status=200)
            if tenantAccountService.isOwnedMoney(self.tenant, self.response_region):
                result["status"] = "owed"
                return JsonResponse(result, status=200)
            if tenantAccountService.isExpired(self.tenant):
                result["status"] = "expired"
                return JsonResponse(result, status=200)

            service = ServiceInfo()
            service.service_key = "0000"
            service.desc = ""
            service.category = "app_publish"
            service.image = image_url
            service.cmd = start_cmd
            service.setting = ""
            service.extend_method = "stateless"
            service.env = ","
            service.min_node = 1
            cm = 128
            ccpu = 20
            if image_service_memory != "":
                cm = int(image_service_memory)
                ccpu = int(cm / 128) * 20
            service.min_memory = cm
            service.min_cpu = ccpu
            service.inner_port = 0
            # version version需要从image_url中分析出来
            service.version = version
            service.namespace = "goodrain"
            service.update_version = 1
            service.volume_mount_path = ""
            service.service_type = "application"
            # calculate resource
            tempService = TenantServiceInfo()
            tempService.min_memory = cm
            tempService.service_region = self.response_region
            tempService.min_node = int(service.min_node)

            diffMemory = cm
            # 判断是否超出资源
            rt_type, flag = tenantUsedResource.predict_next_memory(self.tenant, tempService, diffMemory, False)
            if not flag:
                if rt_type == "memory":
                    result["status"] = "over_memory"
                else:
                    result["status"] = "over_money"
                return JsonResponse(result, status=200)

            newTenantService = baseService.create_service(service_id, tenant_id, service_alias, service_cname, service,
                                                          self.user.pk,
                                                          region=self.response_region)
            newTenantService.code_from = "image_manual"
            newTenantService.language = "docker-image"
            newTenantService.save()
            monitorhook.serviceMonitor(self.user.nick_name, newTenantService, 'create_service', True)
            self.save_ports_envs_and_volumes(port_list, env_list, volume_list, newTenantService)
            baseService.create_region_service(newTenantService, self.tenantName, self.response_region,
                                              self.user.nick_name, dep_sids=json.dumps([]))
            # self.send_task("aws-jp-1", "image_manual", newTenantService)
            monitorhook.serviceMonitor(self.user.nick_name, newTenantService, 'init_region_service', True)
            result["status"] = "success"
            result["service_id"] = service_id
            result["service_alias"] = service_alias
        except Exception as e:
            TenantServiceInfo.objects.filter(service_id=service_id).delete()
            TenantServiceEnvVar.objects.filter(service_id=service_id).delete()
            TenantServicesPort.objects.filter(service_id=service_id).delete()
            TenantServiceVolume.objects.filter(service_id=service_id).delete()
            logger.exception(e)

        return JsonResponse(result, status=200)

    def save_ports_envs_and_volumes(self, ports, envs, volumes, tenant_serivce):
        """保存端口,环境变量和持久化目录"""
        for port in ports:
            baseService.addServicePort(tenant_serivce, False, container_port=int(port["container_port"]),
                                       protocol=port["protocol"], port_alias=port["port_alias"],
                                       is_inner_service=port["is_inner_service"],
                                       is_outer_service=port["is_outer_service"])
            logger.info(port["container_port"], "*", port["protocol"], "*", port["port_alias"], "*",
                        port["is_inner_service"], "*", port["is_outer_service"])

        for env in envs:
            baseService.saveServiceEnvVar(tenant_serivce.tenant_id, tenant_serivce.service_id, 0,
                                          env["name"], env["attr_name"], env["attr_value"], True, "inner")

        for volume in volumes:
            baseService.add_volume_list(tenant_serivce, volume["volume_path"])

    def send_task(self, region, topic, tenant_service):
        body = {"image": tenant_service.image_name,
                "deploy_version": tenant_service.deploy_version,
                "service_id": tenant_service.service_id,
                "service_alias": tenant_service.service_alias,
                "app_version": tenant_service.service_version,
                "namespace": tenant_service.namespace,
                "operator": tenant_service.operator,
                "action": "download_and_deploy",
                "dep_sids": json.dumps([])}
        regionClient.send_task(region, topic, body)