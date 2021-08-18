#!/usr/bin/env python3

import os
import time
from nuvla_api import NuvlaApi
from timeout import timeout

nuvla = NuvlaApi()
nuvla.login()


def test_nuvlabox_is_commissioned(request):
    nuvlabox_id = os.environ.get('NUVLABOX_ID')
    error_msg = f'Waiting for NB {nuvlabox_id} to get COMMISSIONED'

    with timeout(180, error_msg):
        while True:
            nuvlabox = nuvla.api.get(nuvlabox_id)
            if nuvlabox.data.get('state', 'UNKNOWN') == 'COMMISSIONED':
                break

            time.sleep(3)

    assert nuvlabox.data['state'] == 'COMMISSIONED', \
        f'NuvlaBox {nuvlabox_id} did not commission'