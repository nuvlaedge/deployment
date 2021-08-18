#!/usr/bin/env python3

import os
from nuvla_api import NuvlaApi

nuvla = NuvlaApi()
nuvla.login()

nuvlabox_id = os.environ.get('NUVLABOX_ID')
services = os.environ.get('NUVLABOX_SERVICES')

supported_types = []
for pm in services:
    if pm.startswith("peripheral-manager"):
        supported_types.append(pm.split("-")[-1])

def test_peripheral_registration(request):
    nuvlabox_peripherals = nuvla.api.search('nuvlabox-peripheral', filter=f'parent="{nuvlabox_id}"')

    assert nuvlabox_peripherals.count == len(supported_types), \
        'Number of registered peripherals in Nuvla is different from deployed peripheral management services'

