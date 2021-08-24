import docker
import nuvla
import time
import os
from common.nuvla_api import NuvlaApi

class Cleanup(object):
    def __init__(self, api, docker_client):
        self.api = api
        self.docker_client = docker_client

    @staticmethod
    def goodbye():
        print("End of NBE E2E tests, bye")

    def delete_nuvlabox(self, nuvlabox_id):
        print(f"Deleting NuvlaBox with UUID: {nuvlabox_id}")
        try:
            self.api.delete(nuvlabox_id)
        except nuvla.api.api.NuvlaResourceOperationNotAvailable:
            self.decommission_nuvlabox(nuvlabox_id)
            self.delete_nuvlabox(nuvlabox_id)

    def delete_deployment(self, deployment_id):
        print(f'Deleting deployment with UUID: {deployment_id}')
        depl = self.api.get(deployment_id)
        self.api.operation(depl, 'force-delete')

    def stop_deployment(self, deployment_id):
        print(f'Stopping deployment with UUID: {deployment_id}')
        r = self.api.get(deployment_id + "/stop")
        while True:
            j_status = self.api.get(r.data.get('location'))
            if j_status.data['progress'] < 100:
                time.sleep(1)
                continue

            break

    def decommission_nuvlabox(self, nuvlabox_id):
        print(f'Decommissioning NuvlaBox with UUID: {nuvlabox_id}')
        self.api.get(nuvlabox_id + "/decommission")
        time.sleep(5)

    def remove_local_nuvlabox(self, project, image):
        print(f'Removing local NuvlaBox Engine installation with project: {project}')
        try:
            self.docker_client.api.remove_container("nuvlabox-engine-installer")
        except docker.errors.NotFound:
            pass
        except Exception as e:
            print(f'Cannot remove local NuvlaBox installer container. Reason: {str(e)}. Moving on')

        self.docker_client.containers.run(image,
                                          command=f"uninstall --project={project}",
                                          remove=True,
                                          volumes={
                                              '/var/run/docker.sock': {'bind': '/var/run/docker.sock',
                                                                       'mode': 'ro'}
                                          },
                                          detach=True)



if __name__ == '__main__':
    nuvla_client = NuvlaApi()
    nuvla_client.login()

    c = Cleanup(nuvla_client.api, docker.from_env())

    nuvlabox_ids = os.environ.get('NUVLABOX_IDS', '')
    nuvla_depls = os.environ.get('DEPLOYMENT_IDS', '')

    for nbid in nuvlabox_ids.split(','):
        if len(nbid) > 0:
            try:
                c.decommission_nuvlabox(nbid)
                c.delete_nuvlabox(nbid)
            except Exception as e:
                print(f'Error: {str(e)}')
                continue

    for deplid in nuvla_depls.split(','):
        if len(deplid) > 0:
            try:
                c.stop_deployment(deplid)
                c.delete_deployment(deplid)
            except Exception as e:
                print(f'Error: {str(e)}')
                continue