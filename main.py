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
    syncer.ensure_netbox_custom_field(False)

    # snipe_companies = snipe.get_companies()
    # syncer.sync_companies_to_tenants(snipe_companies)

    # snipe_manufacturers, snipe_models = snipe.get_models_and_manufacturers_with_mac()
    # syncer.sync_manufacturers(snipe_manufacturers)
    # syncer.sync_device_types(snipe_models)

    locations = snipe.get_locations()
    # the top locations without a parent will be the Sites in NetBox
    top_locations = list(filter(lambda s: s['parent'] is None, locations))
    syncer.sync_sites(top_locations)

    locations = list(filter(lambda s: s['parent'] is not None, locations))
    syncer.sync_locations(locations)





    # assets = snipe.get_assets_with_mac()
    # for asset in assets:
    #     print("{} {}".format(asset['asset_tag'], asset['name']))

