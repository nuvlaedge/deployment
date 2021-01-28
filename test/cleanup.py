import docker

class Cleanup(object):
    def __init__(self, api, docker_client):
        self.api = api
        self.docker_client = docker_client

    @staticmethod
    def goodbye():
        print("End of NBE E2E tests, bye")

    def delete_nuvlabox(self, nuvlabox_id):
        print(f"Deleting NuvlaBox with UUID: {nuvlabox_id}")
        self.api.delete(nuvlabox_id)

    def delete_install_deployment(self, deployment_id):
        print(f'Deleting NuvlaBox installation deployment with UUID: {deployment_id}')
        self.api.delete(deployment_id)

    def stop_install_deployment(self, deployment_id):
        print(f'Stopping NuvlaBox installation deployment with UUID: {deployment_id}')
        self.api.get(deployment_id + "/stop")

    def decommission_nuvlabox(self, nuvlabox_id):
        print(f'Decommissioning NuvlaBox with UUID: {nuvlabox_id}')
        self.api.get(nuvlabox_id + "/decommission")

    def remove_local_nuvlabox(self, project, image):
        print(f'Removing local NuvlaBox Engine installation with project: {project}')
        self.docker_client.containers.run(image,
                                          command=f"uninstall --project {project}",
                                          remove=True,
                                          detach=True)

    def delete_zombie_mjpg_streamer(self, container_name):
        print(f'Removing local zombie MJPG streamer with name: {container_name}')
        try:
            container = self.docker_client.containers.get(container_name)
            container.remove(force=True)
        except docker.errors.NotFound:
            pass



