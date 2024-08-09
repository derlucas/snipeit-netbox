import argparse
import configparser
import logging
import snipe
import pynetbox
import syncer
import sys

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--allow-update', action='store_true')
    parser.add_argument('--allow-linking', action='store_true')
    parser.add_argument('--update-unique-existing', action='store_true')
    parser.add_argument('--no-append-assettag', action='store_true')
    args = parser.parse_args()

    config = configparser.ConfigParser()
    config.read('config.ini')

    logging.basicConfig(level=logging.INFO)

    snipe = snipe.Snipe(config['config']['snipe_url'], config['config']['snipe_token'])
    netbox = pynetbox.api(config['config']['netbox_url'], config['config']['netbox_token'])

    logging.info("Checking Netbox Custom Fields")
    syncer = syncer.Syncer(netbox, snipe, args.allow_update, args.allow_linking)
    syncer.ensure_netbox_custom_field(False)

    logging.info("Syncing Companies")
    snipe_companies = snipe.get_companies()
    syncer.sync_companies_to_tenants(snipe_companies)

    logging.info("Syncing Manufacturers and Models with MACs")
    snipe_manufacturers, snipe_models = snipe.get_models_and_manufacturers_with_mac()
    syncer.sync_manufacturers(snipe_manufacturers)
    syncer.sync_models_to_device_types(snipe_models)

    logging.info("Syncing Locations")
    locations = snipe.get_locations()
    syncer.sync_top_locations_to_sites(locations)
    syncer.sync_locations(locations)
    
    logging.info("Syncing Assets with MACs")
    assets = snipe.get_assets_with_mac()
    syncer.sync_assets_to_devices(assets, args.update_unique_existing, args.no_append_assettag)
    # for asset in assets:
    #     print("{} {}".format(asset['asset_tag'], asset['name']))

    sys.exit()