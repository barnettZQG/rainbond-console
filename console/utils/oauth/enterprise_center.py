# -*- coding: utf8 -*-

from console.utils.oauth.base.oauth import OAuth2User
from console.utils.oauth.base.communication_oauth import CommunicationOAuth2Interface
from console.utils.restful_client import get_enterprise_server_auth_client
from console.utils.restful_client import get_enterprise_server_ent_client
from console.utils.restful_client import ENTERPRISE_SERVER_API
from console.exception.main import ServiceHandleException

from console.utils.oauth.base.exception import NoAccessKeyErr, NoOAuthServiceErr
from console.utils.urlutil import set_get_url


class EnterpriseCenterV1MiXin(object):
    def set_api(self, oauth_token):
        self.auth_api = get_enterprise_server_auth_client(token=oauth_token)
        self.ent_api = get_enterprise_server_ent_client(token=oauth_token)


class EnterpriseCenterV1(EnterpriseCenterV1MiXin, CommunicationOAuth2Interface):
    def __init__(self):
        super(EnterpriseCenterV1, self).set_session()
        self.request_params = {
            "response_type": "code",
        }

    def get_auth_url(self, home_url=""):
        return ENTERPRISE_SERVER_API + "/enterprise-server/oauth/authorize"

    def get_access_token_url(self, home_url=None):
        return ENTERPRISE_SERVER_API + "/enterprise-server/oauth/token"

    def get_user_url(self, home_url=""):
        return ENTERPRISE_SERVER_API + "/enterprise-server/api/v1/oauth/user"

    def _get_access_token(self, code=None):
        '''
        private function, get access_token
        :return: access_token, refresh_token
        '''
        if not self.oauth_service:
            raise NoOAuthServiceErr("no found oauth service")
        if code:
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "Connection": "close"
            }
            params = {
                "client_id": self.oauth_service.client_id,
                "client_secret": self.oauth_service.client_secret,
                "code": code,
                "redirect_uri": self.oauth_service.redirect_uri + '?service_id=' + str(self.oauth_service.ID),
                "grant_type": "authorization_code"
            }
            url = self.get_access_token_url(self.oauth_service.home_url)
            try:
                rst = self._session.request(method='POST', url=url,
                                            headers=headers, params=params)
            except Exception:
                raise NoAccessKeyErr("can not get access key")
            if rst.status_code == 200:
                try:
                    data = rst.json()
                except ValueError:
                    raise ServiceHandleException(msg="return value error", msg_show="enterprise center 服务不正常")
                self.access_token = data.get("access_token")
                self.refresh_token = data.get("refresh_token")
                if self.access_token is None:
                    return None, None
                self.set_api(self.access_token)
                self.update_access_token(self.access_token, self.refresh_token)
                return self.access_token, self.refresh_token
            else:
                raise NoAccessKeyErr("can not get access key")
        else:
            if self.oauth_user:
                self.set_api(self.oauth_user.access_token)
                try:
                    user = self.auth_api.oauth_user()
                    if user.real_name:
                        return self.oauth_user.access_token, self.oauth_user.refresh_token
                except Exception:
                    if self.oauth_user.refresh_token:
                        try:
                            self.refresh_access_token()
                            return self.access_token, self.refresh_token
                        except Exception:
                            self.oauth_user.delete()
                            raise NoAccessKeyErr("access key is expired, please reauthorize")
                    else:
                        self.oauth_user.delete()
                        raise NoAccessKeyErr("access key is expired, please reauthorize")
            raise NoAccessKeyErr("can not get access key")

    def refresh_access_token(self):
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded"
        }

        params = {
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token",
            "scope": "api"
        }
        rst = self._session.request(method='POST', url=self.oauth_service.access_token_url,
                                    headers=headers, params=params)
        data = rst.json()
        if rst.status_code == 200:
            self.oauth_user.refresh_token = data.get("refresh_token")
            self.oauth_user.access_token = data.get("access_token")
            self.access_token = data.get("access_token")
            self.refresh_token = data.get("refresh_token")
            self.set_api(self.oauth_user.access_token)
            self.oauth_user = self.oauth_user.save()

    def get_user_info(self, code=None):
        access_token, refresh_token = self._get_access_token(code=code)
        user = self.auth_api.oauth_user()
        communication_user = OAuth2User(user.username, user.user_id, user.email)
        communication_user.phone = user.phone
        communication_user.phone = user.real_name
        communication_user.enterprise_id = user.enterprise.id
        communication_user.enterprise_name = user.enterprise.name
        communication_user.enterprise_domain = user.enterprise.domain
        return communication_user, access_token, refresh_token

    def get_authorize_url(self):
        if self.oauth_service:
            params = {
                "client_id": self.oauth_service.client_id,
                "redirect_uri": self.oauth_service.redirect_uri+"?service_id="+str(self.oauth_service.ID),
            }
            params.update(self.request_params)
            return set_get_url(self.oauth_service.auth_url, params)
        else:
            raise NoOAuthServiceErr("no found oauth service")

    def create_user(self, eid, body):
        self._get_access_token()
        return self.ent_api.create_user(eid, body=body)

    def list_user(self, eid):
        self._get_access_token()
        self.ent_api.list_user(eid)

    def delete_user(self, eid, uid):
        self._get_access_token()
        self.ent_api.delete_user(eid, uid)

    def update_user(self, eid, uid, body):
        self._get_access_token()
        self.ent_api.update_user(eid, uid, body=body)
