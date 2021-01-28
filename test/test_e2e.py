#!/usr/bin/env python3

import cleanup
import atexit
import time
import signal
import json
import docker
import pytest
import uuid
import requests
import nuvla
from tempfile import NamedTemporaryFile
from contextlib import contextmanager
from git import Repo
from nuvla.api import Api

api = Api(endpoint="https://nuvla.io",
          reauthenticate=True)
docker_client = docker.from_env()

cleaner = cleanup.Cleanup(api, docker_client)
atexit.register(cleaner.goodbye)

repo = Repo("..")
nbe_installer_image = "nuvlabox/installer:master"


@contextmanager
def timeout(deadline):
    # Register a function to raise a TimeoutError on the signal.
    signal.signal(signal.SIGALRM, raise_timeout)
    # Schedule the signal to be sent after ``time``.
    signal.alarm(deadline)

    try:
        yield
    except TimeoutError:
        raise Exception(f'Exceeded the timeout of {deadline} sec while waiting for NuvlaBox to be COMMISSIONED')
    finally:
        # Unregister the signal so it won't be triggered
        # if the timeout is not reached.
        signal.signal(signal.SIGALRM, signal.SIG_IGN)


def raise_timeout(signum, frame):
    raise TimeoutError


# THESE ARE STATIC AND ASSUMED TO BE IN NUVLA
credential_id = "credential/78bdb494-4d8d-457a-a484-a582719ab32c"
install_module_id = "module/787510b0-9d9e-49d5-98c6-ac96cfc38301"


def test_github_repo():
    # This test is only supposed on run on releases, aka on the master branch
    assert repo.active_branch.name == "master"


def test_nuvla_login(apikey, apisecret):
    assert apikey.startswith("credential/")
    assert apisecret is not None

    api.login_apikey(apikey, apisecret)
    assert api.is_authenticated()


def test_zero_nuvlaboxes():
    existing_nuvlaboxes = api.get('nuvlabox',
                                  filter='description^="NuvlaBox for E2E testing - commit" and state="COMMISSIONED"')
    # if there are NBs then it means a previous test run left uncleaned resources. This must be fixed manually
    assert existing_nuvlaboxes.data.get('count', 0) == 0


def get_nuvlabox_version():
    major = 1
    for tag in repo.tags:
        major = int(tag.name.split(',')[0]) if int(tag.name.split(',')[0]) > major else major

    return major


def create_nuvlabox_body(vpn_server_id, local_nuvlabox, body=None):
    name = "(local) Test NuvlaBox" if local_nuvlabox else "(CI) Test NuvlaBox"

    if not body:
        body = {
            "name": name,
            "description": f"NuvlaBox for E2E testing - commit {repo.head.commit.hexsha}, by {repo.head.commit.author}",
            "version": get_nuvlabox_version()
        }

        if vpn_server_id:
            body["vpn-server-id"] = vpn_server_id

    return body


def test_create_new_nuvlaboxes(request, remote, vpnserver):
    if remote:
        new_nb = api.add('nuvlabox', data=create_nuvlabox_body(vpnserver, False))
        nuvlabox_id = new_nb.data.get('resource-id')

        assert nuvlabox_id is not None
        assert new_nb.data.get('status', -1) == 201

        request.config.cache.set('nuvlabox_id_remote', nuvlabox_id)

        atexit.register(cleaner.delete_nuvlabox, nuvlabox_id)

    new_nb = api.add('nuvlabox', data=create_nuvlabox_body(vpnserver, True))
    nuvlabox_id = new_nb.data.get('resource-id')

    assert nuvlabox_id is not None
    assert new_nb.data.get('status', -1) == 201

    request.config.cache.set('nuvlabox_id_local', nuvlabox_id)

    atexit.register(cleaner.delete_nuvlabox, nuvlabox_id)


def test_deploy_nuvlaboxes(request, remote):
    # This app is in Nuvla.io and has been created by dev@sixsq.com, as group/sixsq-devs

    nuvlabox_id_local = request.config.cache.get('nuvlabox_id_local', '')
    assert nuvlabox_id_local != ''

    # deploy local NB
    docker_client.images.pull(nbe_installer_image)
    local_project_name = str(uuid.uuid4())
    request.config.cache.set('local_project_name', local_project_name)
    installer = ''
    try:
        installer = docker_client.containers.run(nbe_installer_image,
                                                 environment=[f"NUVLABOX_UUID={nuvlabox_id_local}"],
                                                 command=f"install --project {local_project_name} --quiet",
                                                 name="nuvlabox-engine-installer",
                                                 remove=True)
    except docker.errors.ContainerError:
        atexit.register(cleaner.remove_local_nuvlabox, local_project_name, nbe_installer_image)

    assert "NuvlaBox Engine installed to version" in installer.decode()
    atexit.register(cleaner.decommission_nuvlabox, nuvlabox_id_local)

    if remote:
        # deploy NB via Nuvla.io
        # find module
        nuvlabox_id_remote = request.config.cache.get('nuvlabox_id_remote', '')
        assert nuvlabox_id_remote != ''
        nuvlabox_engine_app = api.get(install_module_id)

        assert nuvlabox_engine_app.id == install_module_id

        create_deployment_body = {
            "module": {
                "href": install_module_id
            }
        }

        # create app deployment
        create_deployment = api.add('deployment', data=create_deployment_body)
        assert create_deployment.data.get('status', -1) == 201

        deployment_id = create_deployment.data.get('resource-id')
        request.config.cache.set('deployment_id', deployment_id)
        atexit.register(cleaner.delete_install_deployment, deployment_id)

        deployment = api.get(deployment_id)
        deployment.data['module']['content']['environmental-variables'][0].update({"value": nuvlabox_id_remote})

        deployment.data['parent'] = credential_id

        # add credential to deployment
        install_deployment_edited = api.edit(deployment_id, data=deployment.data)
        assert install_deployment_edited.data.get('parent') == credential_id
        nb_uuid_env_var = install_deployment_edited.data['module']['content']['environmental-variables'][0]
        assert nb_uuid_env_var['value'] == nuvlabox_id_remote

        # start deployment
        api.get(deployment_id + "/start")
        atexit.unregister(cleaner.delete_install_deployment)
        atexit.register(cleaner.stop_install_deployment, deployment_id)


def test_nuvlabox_engine_local_agent_api(request):
    nuvlabox_id_local = request.config.cache.get('nuvlabox_id_local', '')

    agent_api = 'http://localhost:5080/api/'
    r = requests.get(agent_api + 'healthcheck')
    assert r.status_code == 200
    assert 'true' in r.text.lower()

    # send commissioning
    commission = {
        'tags': ['TEST_TAG']
    }
    r = requests.post(agent_api + 'commission', json=commission)
    assert r.status_code == 200

    nuvlabox = api.get(nuvlabox_id_local)
    assert 'TEST_TAG' in nuvlabox.data.get('tags', [])
    request.config.cache.set('nuvlabox_id_local_isg', nuvlabox.data['infrastructure-service-group'])

    # check peripherals api
    mock_peripheral_identifier = 'mock:usb:peripheral'
    mock_peripheral = {
        'identifier': mock_peripheral_identifier,
        'interface': 'USB',
        'version': get_nuvlabox_version(),
        'name': '(local NB) Mock USB Peripheral',
        'available': True,
        'classes': ['video']
    }
    r = requests.post(agent_api + 'peripheral', json=mock_peripheral)
    assert r.status_code == 201

    mock_peripheral_id = r.json()['resource-id']

    r = requests.get(agent_api + 'peripheral')
    assert r.status_code == 200
    assert mock_peripheral_identifier in r.json()

    r = requests.get(agent_api + 'peripheral/' + mock_peripheral_identifier)
    assert r.status_code == 200
    assert isinstance(r.json(), dict)
    assert mock_peripheral_id == r.json()['id']

    new_description = 'new test description'
    r = requests.put(agent_api + 'peripheral/' + mock_peripheral_identifier, json={'description': new_description})
    assert r.status_code == 200
    assert r.json().get('description', '') == new_description

    r = requests.get(agent_api + 'peripheral?identifier_pattern=mock*')
    assert r.status_code == 200
    assert isinstance(r.json(), dict)
    assert mock_peripheral_id == r.json()[mock_peripheral_identifier]['id']

    r = requests.get(agent_api + 'peripheral?identifier_pattern=bad-peripheral')
    assert r.status_code == 200
    assert not r.json()

    # 2nd peripheral
    mock_peripheral_identifier_two = 'mock:usb:peripheral:2'
    mock_peripheral.update({
        'identifier': mock_peripheral_identifier_two,
        'name': '(local NB) Mock USB Peripheral 2'
    })
    r = requests.post(agent_api + 'peripheral', json=mock_peripheral)
    assert r.status_code == 201

    request.config.cache.set('peripheral_id', r.json()['resource-id'])

    r = requests.get(agent_api + 'peripheral?identifier_pattern=mock*')
    assert r.status_code == 200
    assert isinstance(r.json(), dict)
    assert len(r.json().keys()) == 2

    r = requests.get(agent_api + 'peripheral?parameter=description&value=' + new_description)
    assert r.status_code == 200
    assert isinstance(r.json(), dict)
    assert len(r.json().keys()) == 1

    r = requests.delete(agent_api + 'peripheral/' + mock_peripheral_identifier)
    assert r.status_code == r.json()['status'] == 200
    assert r.json()['resource-id'] == mock_peripheral_id

    with pytest.raises(nuvla.api.api.NuvlaError):
        api.get(mock_peripheral_id)


def test_nuvlabox_engine_local_management_api(request, remote):
    isg_id = request.config.cache.get('nuvlabox_id_local_isg')

    infra_service_group = api.get(isg_id)
    local_nb_credential = None
    for infra in infra_service_group.data['infrastructure-services']:
        infra_service = api.get(infra['href'])
        if infra_service.data['subtype'] == "swarm":
            cred_subtype = "infrastructure-service-swarm"
            local_nb_credential = api.get('credential',
                                          filter=f'parent="{infra_service.id}" and subtype="{cred_subtype}"')
            assert local_nb_credential.data['count'] == 1
            break

    assert local_nb_credential is not None
    cert = NamedTemporaryFile(delete=True)
    cert.write(local_nb_credential.data['resources'][0]['cert'].encode())
    cert.flush()

    key = NamedTemporaryFile(delete=True)
    key.write(local_nb_credential.data['resources'][0]['key'].encode())
    key.flush()

    request.config.cache.set('local_api_cert', cert.name)
    request.config.cache.set('local_api_key', key.name)

    management_api = 'https://localhost:5001/api/'
    r = requests.get(management_api, verify=False, cert=(cert.name, key.name))

    assert r.status_code == 200
    assert 'nuvlabox-api-endpoints' in r.json()

    # won't do the test on add/revoke-ssh-key because it is a sensitive action
    # let's not compromise the test environment

    peripheral_id = request.config.cache.get('peripheral_id', '')
    assert peripheral_id != ''

    r = requests.post(management_api + 'data-source-mjpg/enable',
                      verify=False,
                      cert=(cert.name, key.name),
                      json={'id': peripheral_id, 'video-device': '/dev/null'})
    assert r.status_code == 200

    r = requests.post(management_api + 'data-source-mjpg/disable',
                      verify=False,
                      cert=(cert.name, key.name),
                      json={'id': peripheral_id})
    atexit.register(cleaner.delete_zombie_mjpg_streamer, peripheral_id)
    assert r.status_code == 200
    atexit.unregister(cleaner.delete_zombie_mjpg_streamer)

    if remote:
        nuvlabox_id = request.config.cache.get('nuvlabox_id_remote', '')

        # check-api
        check_api = api.get(nuvlabox_id + "/check-api")
        assert check_api.data.get('status') == 202

        job_id = check_api.data['location']

        with timeout(60):
            while True:
                job = api.get(job_id)
                assert job.data.get('state', '').lower() != "failed"
                if job.data.get('state', '') == 'SUCCESS':
                    break

                time.sleep(5)


def test_nuvlabox_engine_local_compute_api(request):
    cert_name = request.config.cache.get('local_api_cert', '')
    key_name = request.config.cache.get('local_api_key', '')

    compute_api = 'https://localhost:5000/'

    r = requests.get(compute_api + 'containers/json', verify=False, cert=(cert_name, key_name))
    assert r.status_code == 200
    assert len(r.json()) > 0


def test_nuvlabox_engine_local_datagateway():
    nuvlabox_network = 'nuvlabox-shared-network'

    check_dg = docker_client.containers.run('alpine',
                                            command='sh -c "ping -c 1 data-gateway 2>&1 >/dev/null && echo OK"',
                                            network=nuvlabox_network,
                                            remove=True)

    assert 'OK' in check_dg.decode()

    cmd = 'sh -c "apk add mosquitto-clients >/dev/null && mosquitto_sub -h datagateway -t nuvlabox-status -C 1"'
    check_mqtt = docker_client.containers.run('alpine',
                                              command=cmd,
                                              network=nuvlabox_network,
                                              remove=True)

    nb_status = json.loads(check_mqtt.decode())
    assert nb_status['status'] == 'OPERATIONAL'


def test_nuvlabox_engine_local_system_manager():
    system_manager_dashboard = 'http://127.0.0.1:3636/dashboard'

    r = requests.get(system_manager_dashboard)
    assert r.status_code == 200
    assert 'NuvlaBox Local Dashboard' in r.text

    r = requests.get(system_manager_dashboard + '/logs')
    assert r.status_code == 200
    assert 'NuvlaBox Local Dashboard - Logs' in r.text

    r = requests.get(system_manager_dashboard + '/peripherals')
    assert r.status_code == 200
    assert 'NuvlaBox Local Dashboard - Peripherals' in r.text


def test_nuvlabox_engine_remote_system_manager(remote):
    if not remote:
        print('Nothing to do')
    else:
        system_manager_dashboard = 'http://swarm.nuvla.io:3636/dashboard'

        with pytest.raises(requests.exceptions.ConnectionError):
            requests.get(system_manager_dashboard)


def test_nuvlabox_engine_containers_stability(request, remote, vpnserver):
    nb_containers = docker_client.containers.list(filters={'label': 'nuvlabox.component=True'}, all=True)

    for container in nb_containers:
        if container.name == 'vpn-client' and not vpnserver:
            continue

        assert container.attrs['RestartCount'] == 0
        assert container.status.lower() in ['running', 'paused']

    if remote:
        deployment_id = request.config.cache.get('deployment_id', '')
        nuvlabox_id = request.config.cache.get('nuvlabox_id_remote', '')

        wait_for_start_job = 0
        while True:
            # deployment is not moving away from created...might be stuck. Gave it 2 attempts already. Aborting
            assert wait_for_start_job < 2

            deployment = api.get(deployment_id)
            current_state = deployment.data['state'].lower()
            if current_state == "starting":
                time.sleep(5)
                continue
            elif current_state == "created":
                wait_for_start_job += 1
                time.sleep(2)
                continue
            elif current_state == "started":
                break
            else:
                assert current_state in ['starting', 'created', 'started']

        # wait 60 seconds for activation
        decommission_registered = 0
        with timeout(60):
            while True:
                # now check for the NuvlaBox
                nuvlabox = api.get(nuvlabox_id)

                nb_state = nuvlabox.data['state'].lower()
                if nb_state == "commissioned":
                    break
                elif nb_state == "activated" and decommission_registered == 0:
                    # in case the commissioning never comes
                    atexit.register(cleaner.decommission_nuvlabox, nuvlabox_id)
                    decommission_registered = 1
                else:
                    time.sleep(3)

        # In case the activation went too fast
        if decommission_registered == 0:
            atexit.register(cleaner.decommission_nuvlabox, nuvlabox_id)

        atexit.unregister(cleaner.delete_nuvlabox)

        assert nb_state == "commissioned"

        # check for an hearbeat
        nuvlabox = api.get(nuvlabox_id)
        nuvlabox_status_id = nuvlabox.data.get('nuvlabox-status')
        assert nuvlabox_status_id is not None
        request.config.cache.set('nuvlabox_status_id_remote', nuvlabox_status_id)

        nuvlabox_status = api.get(nuvlabox_status_id)
        assert nuvlabox_status.data.get('next-heartbeat') is not None

        # check operational status
        assert nuvlabox_status.data.get('status', 'OFF').lower() == "operational"

        # check that resource consumption is being sent
        assert isinstance(nuvlabox_status.data.get('resources'), dict)
        assert "cpu" in nuvlabox_status.data.get('resources', {}).keys()

        # check NB API endpoint
        assert isinstance(nuvlabox_status.data.get('nuvlabox-api-endpoint'), str)
