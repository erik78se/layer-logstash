from charms.reactive import set_flag
from charms.reactive import clear_flag
from charms.reactive import when
from charms.reactive import when_any
from charms.reactive import context
from charms.reactive import when_not
from charms.reactive import when_file_changed
from charmhelpers.core.hookenv import (
    application_version_set,
    config,
    status_set
)
from charmhelpers.core import host
from charmhelpers.core.templating import render
from charmhelpers.core.unitdata import kv

from charms.layer.logstash import logstash_version


CONF_DIR = "/etc/logstash/conf.d"


@when('endpoint.elasticsearch.host-port')
def trigger_logstash_service_recycle():
    clear_flag('logstash.elasticsearch.configured')


@when_any('apt.installed.logstash',
          'deb.installed.logstash')
@when_not('logstash.elasticsearch.configured')
def get_all_elasticsearch_nodes_or_all_master_nodes():
    cache = kv()
    if cache.get('logstash.elasticsearch', ''):
        hosts = cache.get('logstash.elasticsearch')
    else:
        hosts = []

    nodes = context.endpoints.elasticsearch.relation_data()
    for unit in nodes:
        host_string = "{0}:{1}".format(unit['host'], unit['port'])
        if host_string not in hosts:
            hosts.append(host_string)

    cache.set('logstash.elasticsearch', hosts)
    set_flag('logstash.render')
    set_flag('logstash.elasticsearch.configured')


@when_file_changed('/etc/logstash/conf.d/legacy.conf',
                   '/etc/logstash/conf.d/beats.conf')
def recycle_logstash_service():
    host.service_restart('logstash')


@when_any('apt.installed.logstash',
          'deb.installed.logstash')
@when_not('logstash.version.available')
def set_logstash_version_in_unit_data():
    ls_version = logstash_version()
    application_version_set(ls_version)
    status_set('active',
               'Logstash running - version {}'.format(ls_version))
    set_flag('logstash.version.available')


@when('logstash.render')
def config_changed():
    render_without_context('beats.conf', '{}/beats.conf'.format(CONF_DIR))
    render_without_context('legacy.conf', '{}/legacy.conf'.format(CONF_DIR))
    clear_flag('logstash.render')


@when('client.connected')
def configure_logstash_input(client):
    '''Configure the legacy logstash clients.'''
    # Send the port data to the clients.
    client.provide_data(config('tcp_port'), config('udp_port'))
    set_flag('logstash.render')


@when('beat.connected')
def configure_filebeat_input(filebeat):
    '''Configure the logstash beat clients.'''
    filebeat.provide_data(config('beats_port'))
    set_flag('logstash.render')


def render_without_context(source, target):
    ''' Convenience method to re-render a target template with cached data.
        Useful during config-changed cycles without needing to re-iterate The
        relationship interfaces. '''
    context = config()
    cache = kv()
    esearch = cache.get('logstash.elasticsearch')
    if esearch:
        context.update({'elasticsearch': ', '.join(esearch)})
    render(source, target, context)
