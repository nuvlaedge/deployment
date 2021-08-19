#!/usr/bin/env python3

import os
import time
from nuvla_api import NuvlaApi
from timeout import timeout

nuvla = NuvlaApi()
nuvla.login()

nuvlabox_id = os.environ.get('NUVLABOX_ID')

def test_nuvlabox_has_pull_capability(request):
    nuvlabox = nuvla.api.get(nuvlabox_id)
    request.config.cache.set('nuvlabox', nuvlabox.data)
    request.config.cache.set('nuvlabox_status_id', nuvlabox.data['nuvlabox-status'])
    request.config.cache.set('nuvlabox_isg_id', nuvlabox.data['infrastructure-service-group'])

    assert 'NUVLA_JOB_PULL' in nuvlabox.data.get('capabilities', []), \
        f'NuvlaBox {nuvlabox_id} is missing the  NUVLA_JOB_PULL capability'

    request.config.cache.set('nuvlabox_has_pull', True)

def test_nuvlabox_is_stable(request):
    nuvlabox_status_id = request.config.cache.get('nuvlabox_status_id', '')
    with timeout(120, f'Waited too long for container-stats'):
        while True:
            nuvlabox_status = nuvla.api.get(nuvlabox_status_id)
            if nuvlabox_status.data.get('resources', {}).get('container-stats'):
                break

    request.config.cache.set('nuvlabox_status', nuvlabox_status.data)
    print(f'')
    for container in nuvlabox_status.data['resources']['container-stats']:
        assert container['container-status'].lower() in ['running', 'paused'], \
            f'NuvlaBox container {container["name"]} is not running'

        assert container['restart-count'] == 0, \
            f'NuvlaBox container {container["name"]} is unstable and restarting'

def test_nuvlabox_infra(request):
    isg_id = request.config.cache.get('nuvlabox_isg_id', '')
    infra_service_group = nuvla.api.get(isg_id)
    request.config.cache.set('nuvlabox_isg', infra_service_group.data)

    # check IS
    for infra in infra_service_group.data['infrastructure-services']:
        infra_service = nuvla.api.get(infra['href'])
        if infra_service.data['subtype'] == "swarm":
            cred_subtype = "infrastructure-service-swarm"
            query = f'parent="{infra_service.id}" and subtype="{cred_subtype}"'
            nb_credential = nuvla.api.search('credential', filter=query)
            assert nb_credential.count == 1, \
                f'Cannot find credential for NuvlaBox in {nuvla.api.endpoint}, with query: {query}'

            request.config.cache.set('infra_service', infra_service.data)
            request.config.cache.set('nuvlabox_credential', nb_credential.resources[0].data)
            print(f'::set-output name=nuvlabox_credential_id::{nb_credential.resources[0].id}')
            break

    credential = nb_credential.resources[0].data
    if credential.get('status', '') != "VALID":
        r = nuvla.api.get(credential['id'] + "/check")
        assert r.data.get('status') == 202, \
            f'Failed to create job to check credential {credential['id']}'

        with timeout(30, f"Unable to check NuvlaBox's credential for the compute infrastructure"):
            while True:
                j_status = nuvla.api.get(r.data.get('location'))
                if j_status.data['progress'] < 100:
                    time.sleep(1)
                    continue

                assert j_status.data['state'] == 'SUCCESS', \
                    f'Failed to perform credential check'

                break

        credential = nuvla.api.get(credential['id'])
        assert credential.data['status'] == 'VALID', \
            f'The NuvlaBox compute credential is invalid'

    request.config.cache.set('swarm_enabled', infra_service.data['swarm-enabled'])

def test_expected_attributes(request):
    swarm_enabled = request.config.cache.get('swarm_enabled', '')
    nuvlabox_status = request.config.cache.get('nuvlabox_status', {})

    default_err_log_suffix = ': attribute missing from NuvlaBox status'
    assert nuvlabox_status.get('operating-system'), \
        f'Operating System{default_err_log_suffix}'

    assert nuvlabox_status.get('architecture'), \
        f'Architecture{default_err_log_suffix}'

    assert nuvlabox_status.get('hostname'), \
        f'Hostname{default_err_log_suffix}'

    assert nuvlabox_status.get('hostname'), \
        f'Hostname{default_err_log_suffix}'

    assert nuvlabox_status.get('ip'), \
        f'IP{default_err_log_suffix}'

    request.config.cache.set('nuvlabox_ip', nuvlabox_status['ip'])

    assert nuvlabox_status.get('last-boot'), \
        f'Last Boot{default_err_log_suffix}'

    assert nuvlabox_status.get('nuvlabox-engine-version'), \
        f'NuvlaBox Engine Version{default_err_log_suffix}'

    assert nuvlabox_status.get('installation-parameters'), \
        f'Installation Parameters{default_err_log_suffix}'

    assert nuvlabox_status.get('orchestrator'), \
        f'Orchestrator{default_err_log_suffix}'

    if swarm_enabled.lower() == "true":
        assert nuvlabox_status.get('node-id'), \
            f'Node ID{default_err_log_suffix}'

        assert nuvlabox_status.get('cluster-id'), \
            f'Cluster ID{default_err_log_suffix}'

        assert nuvlabox_status.get('cluster-node-role'), \
            f'Cluster Node Role{default_err_log_suffix}'

        assert nuvlabox_status.get('cluster-nodes'), \
            f'Cluster Nodes{default_err_log_suffix}'

        assert nuvlabox_status.get('cluster-managers'), \
            f'Cluster managers{default_err_log_suffix}'

        assert nuvlabox_status.get('cluster-join-address'), \
            f'Cluster Join Address{default_err_log_suffix}'

def test_vpn(request):
    ip = request.config.cache.get('nuvlabox_ip', '')

    assert ip.startswith('10.'), \
        'VPN IP is not set'

