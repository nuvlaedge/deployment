#!/usr/bin/env python3

import cleanup
import atexit
import time
import signal
from contextlib import contextmanager
from git import Repo
from nuvla.api import Api

api = Api(endpoint="https://nuvla.io",
          reauthenticate=True)
cleaner = cleanup.Cleanup(api)
atexit.register(cleaner.goodbye)

repo = Repo("..")

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
    existing_nuvlaboxes = api.get('nuvlabox')
    # if there are NBs then it means a previous test run left uncleaned resources. This must be fixed manually
    assert existing_nuvlaboxes.data.get('count', 0) == 0


def get_nuvlabox_version():
    major = 1
    for tag in repo.tags:
        major = int(tag.name.split(',')[0]) if int(tag.name.split(',')[0]) > major else major

    return major


def create_nuvlabox_body(vpn_server_id, body=None):
    if not body:
        body = {
            "name": "Test NuvlaBox",
            "description": f"NuvlaBox for E2E testing - commit {repo.head.commit.hexsha}, by {repo.head.commit.author}",
            "version": get_nuvlabox_version()
        }

        if vpn_server_id:
            body["vpn-server-id"] = vpn_server_id

    return body


def test_create_new_nuvlabox(request, vpnserver):
    new_nb = api.add('nuvlabox', data=create_nuvlabox_body(vpnserver))
    nuvlabox_id = new_nb.data.get('resource-id')

    assert nuvlabox_id is not None
    assert new_nb.data.get('status', -1) == 201

    request.config.cache.set('nuvlabox_id', nuvlabox_id)

    atexit.register(cleaner.delete_nuvlabox, nuvlabox_id)


def test_deploy_nuvlabox(request):
    # This app is in Nuvla.io and has been created by dev@sixsq.com, as group/sixsq-devs

    nuvlabox_id = request.config.cache.get('nuvlabox_id', '')
    assert nuvlabox_id != ''

    # find module
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
    deployment.data['module']['content']['environmental-variables'][0].update({"value": nuvlabox_id})

    deployment.data['parent'] = credential_id

    # add credential to deployment
    install_deployment_edited = api.edit(deployment_id, data=deployment.data)
    assert install_deployment_edited.data.get('parent') == credential_id
    assert install_deployment_edited.data['module']['content']['environmental-variables'][0]['value'] == nuvlabox_id

    # start deployment
    api.get(deployment_id + "/start")
    atexit.unregister(cleaner.delete_install_deployment)
    atexit.register(cleaner.stop_install_deployment, deployment_id)


def test_nuvlabox_engine_stable(request):
    deployment_id = request.config.cache.get('deployment_id', '')
    nuvlabox_id = request.config.cache.get('nuvlabox_id', '')

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

    nuvlabox_status = api.get(nuvlabox_status_id)
    assert nuvlabox_status.data.get('next-heartbeat') is not None

    # check operational status
    assert nuvlabox_status.data.get('status', 'OFF').lower() == "operational"

    # check that resource consumption is being sent
    assert isinstance(nuvlabox_status.data.get('resources'), dict)
    assert "cpu" in nuvlabox_status.data.get('resources', {}).keys()

    # check NB API endpoint
    assert isinstance(nuvlabox_status.data.get('nuvlabox-api-endpoint'), str)






