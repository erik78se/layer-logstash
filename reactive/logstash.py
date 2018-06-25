from pathlib import Path

from charms.reactive import (
    clear_flag,
    endpoint_from_flag,
    is_flag_set,
    set_flag,
    clear_flag,
    when,
    when_any,
    when_file_changed,
    when_not,
)

from charmhelpers.core.hookenv import (
    application_version_set,
    config,
    status_set
)

from charmhelpers.core.host import service_restart
from charmhelpers.core.templating import render

from charms.layer.logstash import logstash_version


CONF_DIR = Path("/etc/logstash/conf.d")
LEGACY_CONF = CONF_DIR / "legacy.conf"
BEATS_CONF = CONF_DIR / "beats.conf"


@when('elastic.base.available')
@when_not('logstash.version.available')
def set_logstash_version():
    application_version_set(logstash_version())
    set_flag('logstash.version.available')


@when('elastic.base.available')
@when_not('logstash.legacy.conf.available')
def render_logstash_conf():
    """Create context and render legacy conf.
    """

    ctxt = {
        'es_nodes': [],
        'udp_port': config('udp_port'),
        'tcp_port': config('tcp_port'),
    }

    if is_flag_set('endpoint.elasticsearch.available'):
        endpoint = endpoint_from_flag('endpoint.elasticsearch.available')
        [ctxt['es_nodes'].append("{}:{}".format(unit['host'], unit['port']))
         for unit in endpoint.list_unit_data()]

    if LEGACY_CONF.exists():
        LEGACY_CONF.unlink()

    render('legacy.conf', str(LEGACY_CONF), ctxt)

    set_flag('logstash.legacy.conf.available')


@when('elastic.base.available')
@when_not('logstash.beats.conf.available')
def render_beat_conf():
    """Create context and render beat conf.
    """

    ctxt = {
        'es_nodes': [],
        'beats_port': config('beats_port'),
    }

    if is_flag_set('endpoint.elasticsearch.available'):
        endpoint = endpoint_from_flag('endpoint.elasticsearch.available')
        [ctxt['es_nodes'].append("{}:{}".format(unit['host'], unit['port']))
         for unit in endpoint.list_unit_data()]

    if BEATS_CONF.exists():
        BEATS_CONF.unlink()

    render('beats.conf', str(BEATS_CONF), ctxt)

    set_flag('logstash.beats.conf.available')


@when('endpoint.elasticsearch.available')
def es_available_rerender_confs():
    clear_flag('logstash.beats.conf.available')
    clear_flag('logstash.legacy.conf.available')


@when_not('endpoint.elasticsearch.available')
def es_not_available_rerender_confs():
    clear_flag('logstash.beats.conf.available')
    clear_flag('logstash.legacy.conf.available')


@when_file_changed('/etc/logstash/conf.d/legacy.conf',
                   '/etc/logstash/conf.d/beats.conf')
def recycle_logstash_service():
    service_restart('logstash')


@when('logstash.version.available',
      'elastic.base.available')
def set_logstash_version_in_unit_data():
    status_set('active',
               'Logstash running - version {}'.format(logstash_version()))


@when('client.connected')
def configure_logstash_input():
    '''Configure the legacy logstash clients.'''
    endpoint = endpoint_from_flag('client.connected')
    # Send the port data to the clients.
    endpoint.provide_data(config('tcp_port'), config('udp_port'))


@when('beat.connected')
def configure_filebeat_input():
    '''Configure the logstash beat clients.'''
    endpoint = endpoint_from_flag('beat.connected')
    endpoint.provide_data(config('beats_port'))
    clear_flag('logstash.beats.conf.available')
