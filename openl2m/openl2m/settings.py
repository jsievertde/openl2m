#
# This file is part of Open Layer 2 Management (OpenL2M).
#
# OpenL2M is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License version 3 as published by
# the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
# more details.  You should have received a copy of the GNU General Public
# License along with OpenL2M. If not, see <http://www.gnu.org/licenses/>.
#
"""
Django settings for openl2m project.

Generated by 'django-admin startproject' using Django 2.2.1.

For more information on this file, see
https://docs.djangoproject.com/en/2.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.2/ref/settings/
"""

import logging
import os
import socket
import platform
import sys
import warnings
import netaddr

from django.contrib.messages import constants as messages
from django.core.exceptions import ImproperlyConfigured

# Django 2.1 requires Python 3.6+
if sys.version_info < (3, 6):
    raise RuntimeError(
        "OpenL2M requires Python 3.6 or higher (current: Python {})".format(sys.version.split()[0])
    )

# Check for configuration file
try:
    from openl2m import configuration
except ImportError:
    raise ImproperlyConfigured(
        "Configuration file is not present. Please define openl2m/openl2m/configuration.py per the documentation."
    )

# if you change this version, also change it in docs/conf.py and docs/releases/<version> !!!
VERSION = '2.1.1'
VERSION_DATE = '2021-10-12'

# Hostname
HOSTNAME = platform.node()

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Database
configuration.DATABASE.update({'ENGINE': 'django.db.backends.postgresql'})
DATABASES = {
    'default': configuration.DATABASE,
}

LOGIN_REDIRECT_URL = 'home'

# Import required configuration parameters
ALLOWED_HOSTS = DATABASE = SECRET_KEY = None
for setting in ['ALLOWED_HOSTS', 'DATABASE', 'SECRET_KEY']:
    try:
        globals()[setting] = getattr(configuration, setting)
    except AttributeError:
        raise ImproperlyConfigured(
            "Mandatory setting {} is missing from configuration.py.".format(setting)
        )

# Import optional configuration parameters
ADMINS = getattr(configuration, 'ADMINS', [])
BANNER_BOTTOM = getattr(configuration, 'BANNER_BOTTOM', '')
BANNER_LOGIN = getattr(configuration, 'BANNER_LOGIN', '')
BANNER_TOP = getattr(configuration, 'BANNER_TOP', '')
BASE_PATH = getattr(configuration, 'BASE_PATH', '')
if BASE_PATH:
    BASE_PATH = BASE_PATH.strip('/') + '/'  # Enforce trailing slash only
LOG_MAX_AGE = getattr(configuration, 'LOG_MAX_AGE', 180)
RECENT_SWITCH_LOG_COUNT = getattr(configuration, 'RECENT_SWITCH_LOG_COUNT', 25)
CORS_ORIGIN_ALLOW_ALL = getattr(configuration, 'CORS_ORIGIN_ALLOW_ALL', False)
CORS_ORIGIN_REGEX_WHITELIST = getattr(configuration, 'CORS_ORIGIN_REGEX_WHITELIST', [])
CORS_ORIGIN_WHITELIST = getattr(configuration, 'CORS_ORIGIN_WHITELIST', [])
DATE_FORMAT = getattr(configuration, 'DATE_FORMAT', 'N j, Y')
DATETIME_FORMAT = getattr(configuration, 'DATETIME_FORMAT', 'N j, Y g:i a')
DEBUG = getattr(configuration, 'DEBUG', False)
LOGGING = getattr(configuration, 'LOGGING', {})
LOGIN_TIMEOUT = getattr(configuration, 'LOGIN_TIMEOUT', 1800)
LOGOUT_ON_INACTIVITY = getattr(configuration, 'LOGOUT_ON_INACTIVITY', True)
MAINTENANCE_MODE = getattr(configuration, 'MAINTENANCE_MODE', False)
MAX_PAGE_SIZE = getattr(configuration, 'MAX_PAGE_SIZE', 1000)
PAGINATE_COUNT = getattr(configuration, 'PAGINATE_COUNT', 50)
PREFER_IPV4 = getattr(configuration, 'PREFER_IPV4', False)
SESSION_FILE_PATH = getattr(configuration, 'SESSION_FILE_PATH', None)
SHORT_DATE_FORMAT = getattr(configuration, 'SHORT_DATE_FORMAT', 'Y-m-d')
SHORT_DATETIME_FORMAT = getattr(configuration, 'SHORT_DATETIME_FORMAT', 'Y-m-d H:i')
LONG_DATETIME_FORMAT = getattr(configuration, 'LONG_DATETIME_FORMAT', '%Y-%m-%d %H:%M:%S')
SHORT_TIME_FORMAT = getattr(configuration, 'SHORT_TIME_FORMAT', 'H:i:s')
TIME_FORMAT = getattr(configuration, 'TIME_FORMAT', 'g:i a')
TIME_ZONE = getattr(configuration, 'TIME_ZONE', 'UTC')

PORT_TOGGLE_DELAY = getattr(configuration, 'PORT_TOGGLE_DELAY', 5)
POE_TOGGLE_DELAY = getattr(configuration, 'POE_TOGGLE_DELAY', 5)

ALWAYS_ALLOW_POE_TOGGLE = getattr(configuration, 'ALWAYS_ALLOW_POE_TOGGLE', False)

HIDE_NONE_ETHERNET_INTERFACES = getattr(configuration, 'HIDE_NONE_ETHERNET_INTERFACES', False)

CSRF_TRUSTED_ORIGINS = ALLOWED_HOSTS

SWITCH_INFO_URLS = getattr(configuration, 'SWITCH_INFO_URLS', False)
SWITCH_INFO_URLS_STAFF = getattr(configuration, 'SWITCH_INFO_URLS_STAFF', False)
SWITCH_INFO_URLS_ADMINS = getattr(configuration, 'SWITCH_INFO_URLS_ADMINS', False)
INTERFACE_INFO_URLS = getattr(configuration, 'INTERFACE_INFO_URLS', False)
VLAN_INFO_URLS = getattr(configuration, 'VLAN_INFO_URLS', False)
IP4_INFO_URLS = getattr(configuration, 'IP4_INFO_URLS', False)
IP6_INFO_URLS = getattr(configuration, 'IP6_INFO_URLS', False)
ETHERNET_INFO_URLS = getattr(configuration, 'ETHERNET_INFO_URLS', False)

ETH_FORMAT = getattr(configuration, 'ETH_FORMAT', 0)
if ETH_FORMAT == 1:     # Hyphen 00-11-22-33-44-55
    MAC_DIALECT = None
elif ETH_FORMAT == 2:   # Cisco 0011.2233.4455
    MAC_DIALECT = netaddr.mac_cisco
else:
    # default:
    MAC_DIALECT = netaddr.mac_unix_expanded     # 00:11:22:33:44:55

IFACE_HIDE_REGEX_IFNAME = getattr(configuration, 'IFACE_HIDE_REGEX_IFNAME', '')
IFACE_HIDE_REGEX_IFDESCR = getattr(configuration, 'IFACE_HIDE_REGEX_IFDESCR', '')
IFACE_HIDE_SPEED_ABOVE = getattr(configuration, 'IFACE_HIDE_SPEED_ABOVE', 0)
IFACE_ALIAS_NOT_ALLOW_REGEX = getattr(configuration, 'IFACE_ALIAS_NOT_ALLOW_REGEX', '')
IFACE_ALIAS_KEEP_BEGINNING_REGEX = getattr(configuration, 'IFACE_ALIAS_KEEP_BEGINNING_REGEX', '')

MENU_ON_RIGHT = getattr(configuration, 'MENU_ON_RIGHT', True)
MENU_INFO_URLS = getattr(configuration, 'MENU_INFO_URLS', False)

# colors
BGCOLOR_IF_ADMIN_UP = getattr(configuration, 'BGCOLOR_IF_ADMIN_UP', "#D9FCC2")
BGCOLOR_IF_ADMIN_UP_UP = getattr(configuration, 'BGCOLOR_IF_ADMIN_UP_UP', "#ADFF2F")
BGCOLOR_IF_ADMIN_DOWN = getattr(configuration, 'BGCOLOR_IF_ADMIN_DOWN', "#FF6347")

# login view organization
TOPMENU_MAX_COLUMNS = getattr(configuration, 'TOPMENU_MAX_COLUMNS', 4)

# show the switch search form on home page
SWITCH_SEARCH_FORM = getattr(configuration, 'SWITCH_SEARCH_FORM', True)

# snmp related constants
SNMP_TIMEOUT = getattr(configuration, 'SNMP_TIMEOUT', 4)    # seconds before retry, see EasySNMP docs
SNMP_RETRIES = getattr(configuration, 'SNMP_RETRIES', 3)    # retries before fail
SNMP_MAX_REPETITIONS = getattr(configuration, 'SNMP_MAX_REPETITIONS', 10)   # SNMP get_bulk max_repetitions

# Syslog related fields:
SYSLOG_HOST = getattr(configuration, 'SYSLOG_HOST', False)
SYSLOG_PORT = getattr(configuration, 'SYSLOG_PORT', 514)
SYSLOG_JSON = getattr(configuration, 'SYSLOG_JSON', True)
# validate host:
try:
    syslog_ip = socket.gethostbyname(SYSLOG_HOST)
except Exception as e:
    raise ImproperlyConfigured(
        "SYSLOG_HOST is not a valid host name"
    )

# Sessions
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
if LOGIN_TIMEOUT is not None:
    if type(LOGIN_TIMEOUT) is not int or LOGIN_TIMEOUT < 0:
        raise ImproperlyConfigured(
            "LOGIN_TIMEOUT must be a positive integer (value: {})".format(LOGIN_TIMEOUT)
        )
    # Django default is 1209600 seconds (14 days)
    SESSION_COOKIE_AGE = LOGIN_TIMEOUT
    # if this is set, then the login timeout is treated as inactivity timeout:
    if LOGOUT_ON_INACTIVITY:
        SESSION_SAVE_EVERY_REQUEST = True
if SESSION_FILE_PATH is not None:
    SESSION_ENGINE = 'django.contrib.sessions.backends.file'

# we use the PickleSerializer instead of JSON, so we can better cache objects:
SESSION_SERIALIZER = 'django.contrib.sessions.serializers.PickleSerializer'

# if using SSL, these should be set to True:
CSRF_COOKIE_SECURE = getattr(configuration, 'CSRF_COOKIE_SECURE', False)
SESSION_COOKIE_SECURE = getattr(configuration, 'SESSION_COOKIE_SECURE', False)

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# override the maximum GET/POST item count.
# with large numbers of switches in a group, we may exceeed the default (1000):
DATA_UPLOAD_MAX_NUMBER_FIELDS = getattr(configuration, 'DATA_UPLOAD_MAX_NUMBER_FIELDS', 10000)

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.2/howto/deployment/checklist/

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'ordered_model',
    'users.apps.UsersConfig',
    'switches.apps.SwitchesConfig',
    'counters.apps.CountersConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'openl2m.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'templates'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                # add snmp-related constants to every template, see switches/context_processors.py
                'switches.context_processors.add_variables',
            ],
        },
    },
]

WSGI_APPLICATION = 'openl2m.wsgi.application'
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True


# Authentication backend, this is the default.
# it may be changed if we use ldap, see below
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]


#
# LDAP authentication (optional)
#

try:
    from openl2m import ldap_config as LDAP_CONFIG
except ImportError:
    LDAP_CONFIG = None

if LDAP_CONFIG is not None:

    # Check that django_auth_ldap is installed
    try:
        import ldap
        import django_auth_ldap
    except ImportError:
        raise ImproperlyConfigured(
            "LDAP authentication has been configured, but django-auth-ldap is not installed. Remove "
            "openl2m/ldap_config.py to disable LDAP."
        )

    # Required configuration parameters
    try:
        AUTH_LDAP_SERVER_URI = getattr(LDAP_CONFIG, 'AUTH_LDAP_SERVER_URI')
    except AttributeError:
        raise ImproperlyConfigured(
            "Required parameter AUTH_LDAP_SERVER_URI is missing from ldap_config.py."
        )

    # Optional configuration parameters
    AUTH_LDAP_ALWAYS_UPDATE_USER = getattr(LDAP_CONFIG, 'AUTH_LDAP_ALWAYS_UPDATE_USER', True)
    AUTH_LDAP_AUTHORIZE_ALL_USERS = getattr(LDAP_CONFIG, 'AUTH_LDAP_AUTHORIZE_ALL_USERS', False)
    AUTH_LDAP_BIND_AS_AUTHENTICATING_USER = getattr(LDAP_CONFIG, 'AUTH_LDAP_BIND_AS_AUTHENTICATING_USER', False)
    AUTH_LDAP_BIND_DN = getattr(LDAP_CONFIG, 'AUTH_LDAP_BIND_DN', '')
    AUTH_LDAP_BIND_PASSWORD = getattr(LDAP_CONFIG, 'AUTH_LDAP_BIND_PASSWORD', '')
    AUTH_LDAP_CACHE_TIMEOUT = getattr(LDAP_CONFIG, 'AUTH_LDAP_CACHE_TIMEOUT', 0)
    AUTH_LDAP_CONNECTION_OPTIONS = getattr(LDAP_CONFIG, 'AUTH_LDAP_CONNECTION_OPTIONS', {})
    AUTH_LDAP_DENY_GROUP = getattr(LDAP_CONFIG, 'AUTH_LDAP_DENY_GROUP', None)
    AUTH_LDAP_FIND_GROUP_PERMS = getattr(LDAP_CONFIG, 'AUTH_LDAP_FIND_GROUP_PERMS', False)
    AUTH_LDAP_GLOBAL_OPTIONS = getattr(LDAP_CONFIG, 'AUTH_LDAP_GLOBAL_OPTIONS', {})
    AUTH_LDAP_GROUP_SEARCH = getattr(LDAP_CONFIG, 'AUTH_LDAP_GROUP_SEARCH', None)
    AUTH_LDAP_GROUP_TYPE = getattr(LDAP_CONFIG, 'AUTH_LDAP_GROUP_TYPE', None)
    AUTH_LDAP_MIRROR_GROUPS = getattr(LDAP_CONFIG, 'AUTH_LDAP_MIRROR_GROUPS', None)
    AUTH_LDAP_MIRROR_GROUPS_EXCEPT = getattr(LDAP_CONFIG, 'AUTH_LDAP_MIRROR_GROUPS_EXCEPT', None)
    AUTH_LDAP_PERMIT_EMPTY_PASSWORD = getattr(LDAP_CONFIG, 'AUTH_LDAP_PERMIT_EMPTY_PASSWORD', False)
    AUTH_LDAP_REQUIRE_GROUP = getattr(LDAP_CONFIG, 'AUTH_LDAP_REQUIRE_GROUP', None)
    AUTH_LDAP_NO_NEW_USERS = getattr(LDAP_CONFIG, 'AUTH_LDAP_NO_NEW_USERS', False)
    AUTH_LDAP_START_TLS = getattr(LDAP_CONFIG, 'AUTH_LDAP_START_TLS', False)
    AUTH_LDAP_USER_QUERY_FIELD = getattr(LDAP_CONFIG, 'AUTH_LDAP_USER_QUERY_FIELD', None)
    AUTH_LDAP_USER_ATTRLIST = getattr(LDAP_CONFIG, 'AUTH_LDAP_USER_ATTRLIST', None)
    AUTH_LDAP_USER_ATTR_MAP = getattr(LDAP_CONFIG, 'AUTH_LDAP_USER_ATTR_MAP', {})
    AUTH_LDAP_USER_DN_TEMPLATE = getattr(LDAP_CONFIG, 'AUTH_LDAP_USER_DN_TEMPLATE', None)
    AUTH_LDAP_USER_FLAGS_BY_GROUP = getattr(LDAP_CONFIG, 'AUTH_LDAP_USER_FLAGS_BY_GROUP', {})
    AUTH_LDAP_USER_SEARCH = getattr(LDAP_CONFIG, 'AUTH_LDAP_USER_SEARCH', None)
    AUTH_LDAP_GROUP_TO_SWITCHGROUP_REGEX = getattr(LDAP_CONFIG, 'AUTH_LDAP_GROUP_TO_SWITCHGROUP_REGEX', None)

    # Optionally disable strict certificate checking
    if getattr(LDAP_CONFIG, 'LDAP_IGNORE_CERT_ERRORS', False):
        ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)

    # Prepend LDAPBackend to the authentication backends list
    AUTHENTICATION_BACKENDS.insert(0, 'django_auth_ldap.backend.LDAPBackend')

    # Enable logging for django_auth_ldap
    ldap_logger = logging.getLogger('django_auth_ldap')
    ldap_logger.addHandler(logging.StreamHandler())
    ldap_logger.setLevel(logging.DEBUG)


# Password validation
# https://docs.djangoproject.com/en/2.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/2.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.2/howto/static-files/

# Static files (CSS, JavaScript, Images)
STATIC_ROOT = BASE_DIR + '/static'
STATIC_URL = '/{}static/'.format(BASE_PATH)
STATICFILES_DIRS = (
    os.path.join(BASE_DIR, 'project-static'),
)

# task scheduling via Celery:
TASKS_ENABLED = getattr(configuration, 'TASKS_ENABLED', False)
TASKS_BCC_ADMINS = getattr(configuration, 'TASKS_BCC_ADMINS', False)
CELERY_BROKER_URL = getattr(configuration, 'CELERY_BROKER_URL', 'redis://localhost:6379')
CELERY_RESULT_BACKEND = getattr(configuration, 'CELERY_RESULT_BACKEND', 'redis://localhost:6379')
CELERY_ACCEPT_CONTENT = getattr(configuration, 'CELERY_ACCEPT_CONTENT', ['application/json'])
CELERY_RESULT_SERIALIZER = getattr(configuration, 'CELERY_RESULT_SERIALIZER', 'json')
CELERY_TASK_SERIALIZER = getattr(configuration, 'CELERY_TASK_SERIALIZER', 'json')

# customizing Flatpickr time/date settings:
#
# this defines the date/time format used in the Flatpickr JS library:
# Flatpickr option 'time_24hr: true'
TASK_USE_24HR_TIME = getattr(configuration, 'TASK_USE_24HR_TIME', False)
if TASK_USE_24HR_TIME:
    FLATPICKR_24HR_OPTION = 'true'
else:
    FLATPICKR_24HR_OPTION = 'false'
TASK_SUBMIT_MINUTE_INCREMENT = getattr(configuration, 'TASK_SUBMIT_MINUTE_INCREMENT', 5)    # the library default
TASK_SUBMIT_MAX_DAYS_IN_FUTURE = getattr(configuration, 'TASK_SUBMIT_MAX_DAYS_IN_FUTURE', 28)

# pay attention to these two, they need to match format!
# Flatpickr option 'dateFormat: "Y-m-d H:i"''
FLATPICKR_DATE_FORMAT = getattr(configuration, 'FLATPICKR_DATE_FORMAT', 'Y-m-d H:i')
# this next one needs to match the Flatpickr 'dateFormat' option above,
# minus the ending %z which add timezone offset:
TASK_SUBMIT_DATE_FORMAT = getattr(configuration, 'TASK_SUBMIT_DATE_FORMAT', '%Y-%m-%d %H:%M %z')
#
# Email settings for sending results of Bulk-Edit jobs
#
EMAIL_HOST = getattr(configuration, 'EMAIL_SERVER', 'localhost')
EMAIL_HOST_USER = getattr(configuration, 'EMAIL_USERNAME', '')
EMAIL_HOST_PASSWORD = getattr(configuration, 'EMAIL_PASSWORD', '')
EMAIL_PORT = getattr(configuration, 'EMAIL_PORT', 25)
EMAIL_USE_TLS = getattr(configuration, 'EMAIL_USE_TLS', False)
EMAIL_USE_SSL = getattr(configuration, 'EMAIL_USE_SSL', False)
EMAIL_SSL_CERTFILE = getattr(configuration, 'EMAIL_SSL_CERTFILE', None)
EMAIL_SSL_KEYFILE = getattr(configuration, 'EMAIL_SSL_KEYFILE', None)
EMAIL_TIMEOUT = getattr(configuration, 'EMAIL_TIMEOUT', 10)
EMAIL_SUBJECT_PREFIX = getattr(configuration, 'EMAIL_SUBJECT_PREFIX', '[OpenL2M-Admin] ')
EMAIL_SUBJECT_PREFIX_USER = getattr(configuration, 'EMAIL_SUBJECT_PREFIX_USER', '[OpenL2M] ')
EMAIL_FROM_ADDRESS = getattr(configuration, 'EMAIL_FROM_ADDRESS', '<openl2m@localhost>')


# Vendor specific settings:
CISCO_WRITE_MEM_MAX_WAIT = getattr(configuration, 'CISCO_WRITE_MEM_MAX_WAIT', 5)
