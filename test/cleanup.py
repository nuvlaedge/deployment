class Cleanup(object):
    def __init__(self, api):
        self.api = api

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



