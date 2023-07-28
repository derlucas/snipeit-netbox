import argparse
import configparser
import logging
import snipe
import pynetbox
import syncer


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--allow-update', action='store_true')
    parser.add_argument('--allow-linking', action='store_true')
    args = parser.parse_args()

    config = configparser.ConfigParser()
    config.read('config.ini')

    logging.basicConfig(level=logging.INFO)

    snipe = snipe.Snipe(config['config']['snipe_url'], config['config']['snipe_token'])
    netbox = pynetbox.api(config['config']['netbox_url'], config['config']['netbox_token'])

    syncer = syncer.Syncer(netbox, snipe, args.allow_update, args.allow_linking)
    syncer.ensure_netbox_custom_field()


    snipe_manufacturers, snipe_models = snipe.get_via_models()
    syncer.sync_manufacturers(snipe_manufacturers)

    syncer.sync_device_types(snipe_models)

    # netbox_manufacturers2 = list(netbox.dcim.manufacturers.all())
    # print(netbox_manufacturers2)

