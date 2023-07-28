import datetime
import logging
import unicodedata
import re
from datetime import datetime, timezone

import pynetbox

KEY_CUSTOM_FIELD = "snipe_object_id"


class Syncer:
    def __init__(self, netbox, snipe, allow_updates: bool = False, allow_linking: bool = False):
        self.netbox = netbox
        self.snipe = snipe
        self.allow_updates = allow_updates
        self.allow_linking = allow_linking
        self.desc = "Imported from SnipeIT {}".format(datetime.now(timezone.utc).strftime("%y-%m-%d %H:%M:%S (UTC)"))


    @staticmethod
    def slugify(value):
        value = (unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii"))
        value = re.sub(r"[^\w\s-]", "", value.lower())
        return re.sub(r"[-\s]+", "-", value).strip("-_")


    def ensure_netbox_custom_field(self, lock: bool = False):
        content_types = ['dcim.device', 'dcim.devicerole', 'dcim.devicetype', 'dcim.interface', 'dcim.manufacturer', 'dcim.site', 'tenancy.tenant']
        cufi = {"name": KEY_CUSTOM_FIELD, "display": "Snipe object id", "content_types": content_types,
                "description": "The ID of the original SnipeIT Object used for Sync",
                "type": "integer", "ui_visibility": "read-only" if lock else "read-write"}

        field = self.netbox.extras.custom_fields.get(name=KEY_CUSTOM_FIELD)
        if field is None:
            logging.info("netbox custom field is missing -> creating one")
            self.netbox.extras.custom_fields.create(cufi)
        else:
            logging.info("netbox custom field is present -> updating")
            cufi = cufi | {"id": field['id']}
            self.netbox.extras.custom_fields.update([cufi])


    def sync_companies_to_tenants(self, snipe_companies):
        netbox_tenants = list(self.netbox.tenancy.tenants.all())
        desc = "Imported from SnipeIT {}".format(datetime.now(timezone.utc).strftime("%y-%m-%d %H:%M:%S (UTC)"))

        for snipe_company in snipe_companies:
            logging.info("Checking Company {}".format(snipe_company['name']))

            present_nb_tenant = next((item for item in netbox_tenants if item["custom_fields"][KEY_CUSTOM_FIELD] == snipe_company['id']), None)
            if present_nb_tenant is None:
                # Tenant is unique by Name
                present_nb_tenant = next((item for item in netbox_tenants if item["name"] == snipe_company['name']), None)
                if present_nb_tenant is None:
                    logging.info("Adding Tenant {} to netbox.".format(snipe_company['name']))
                    self.netbox.tenancy.tenants.create(name=snipe_company['name'],
                                                       slug=Syncer.slugify(snipe_company['name']),
                                                       description=desc,
                                                       custom_fields={KEY_CUSTOM_FIELD: snipe_company['id']})
                else:
                    if self.allow_linking:
                        logging.info("Found Tenant {} by name. Updating custom field instead.".format(snipe_company['name']))
                        self.netbox.tenancy.tenants.update([{"id": present_nb_tenant["id"],
                                                             "description": desc.replace("Imported", "Updated"),
                                                             "custom_fields": {KEY_CUSTOM_FIELD: snipe_company['id']}}])
                    else:
                        logging.info("Found Tenant {} by name. Skipping, since linking is not enabled.".format(snipe_company['name']))

            elif present_nb_tenant['name'] != snipe_company['name']:
                if self.allow_updates:
                    logging.info("The Tenant {} is present, updating Item".format(snipe_company['name']))
                    self.netbox.tenancy.tenants.update([{"id": present_nb_tenant["id"], "name": snipe_company['name'],
                                                         "slug": Syncer.slugify(snipe_company['name']),
                                                         "description": desc.replace("Imported", "Updated")}])
                else:
                    logging.info("The Tenant {} is changed. Skipping since updating is not enabled.".format(snipe_company['name']))


    def sync_manufacturers(self, snipe_manufacturers):
        netbox_manufacturers = list(self.netbox.dcim.manufacturers.all())

        for snipe_manuf in snipe_manufacturers:
            logging.info("Checking Manufacturer {}".format(snipe_manuf['name']))

            # search in netbox manufs for the custom field ID, if not found, search for name, if not found ->create
            present_nb_manuf = next((item for item in netbox_manufacturers if item["custom_fields"][KEY_CUSTOM_FIELD] == snipe_manuf['id']), None)
            if present_nb_manuf is None:
                # Manufacturer is unique by Name
                present_nb_manuf = next((item for item in netbox_manufacturers if item["name"] == snipe_manuf['name']), None)

                if present_nb_manuf is None:
                    logging.info("Adding Manufacturer {} to netbox".format(snipe_manuf['name']))
                    self.netbox.dcim.manufacturers.create(name=snipe_manuf['name'], slug=Syncer.slugify(snipe_manuf['name']),
                                                          description=self.desc,
                                                          custom_fields={KEY_CUSTOM_FIELD: snipe_manuf['id']})
                else:
                    if self.allow_linking:
                        logging.info("Found Manufacturer {} by name. Updating custom field instead.".format(snipe_manuf['name']))
                        self.netbox.dcim.manufacturers.update([{"id": present_nb_manuf["id"],
                                                                "description": self.desc.replace("Imported", "Updated"),
                                                                "custom_fields": {KEY_CUSTOM_FIELD: snipe_manuf['id']}}])
                    else:
                        logging.info("Found Manufacturer {} by name. Skipping, since linking is not enabled.".format(snipe_manuf['name']))

            elif present_nb_manuf['name'] != snipe_manuf['name']:
                if self.allow_updates:
                    logging.info("The Manufacturer {} is present, updating Item".format(snipe_manuf['name']))
                    self.netbox.dcim.manufacturers.update([{"id": present_nb_manuf["id"], "name": snipe_manuf['name'],
                                                            "slug": Syncer.slugify(snipe_manuf['name']),
                                                            "description": self.desc.replace("Imported", "Updated")}])
                else:
                    logging.info("The Manufacturer {} is changed. Skipping since updating is not enabled.".format(snipe_manuf['name']))


    def sync_device_types(self, snipe_models):
        netbox_device_types = list(self.netbox.dcim.device_types.all())
        netbox_manufacturers = list(self.netbox.dcim.manufacturers.all())

        for model in snipe_models:
            update_obj = {}
            logging.info("Checking Device Type {}".format(model['name']))
            # get the manufacturer by Name of the Snipe Model-Manufacturer for later use
            manuf_by_model = next((item for item in netbox_manufacturers if item["name"] == model['manufacturer']['name']), None)

            # search the Device Type by Custom Field ID-Value
            present_nb_devtype = next((item for item in netbox_device_types if item['custom_fields'][KEY_CUSTOM_FIELD] == model['id']), None)

            if present_nb_devtype is None:  # No associated Device Type found

                # Search by Model+Manufacturer
                present_nb_devtype = next((item for item in netbox_device_types if item['model'] == model['name'] and
                                           item['manufacturer']['name'] == model['manufacturer']['name']), None)

                if present_nb_devtype is None:
                    logging.info("Adding Device Type {} to netbox".format(model['name']))

                    self.netbox.dcim.device_types.create(slug=Syncer.slugify(model['name']),
                                                         description=self.desc, model=model['name'],
                                                         part_number=model['model_number'],
                                                         manufacturer=manuf_by_model.id,
                                                         custom_fields={KEY_CUSTOM_FIELD: model['id']},
                                                         comments="Notes from SnipeIT when initially creating this Netbox Entry. "
                                                                  "(It will not be Updated on further syncs):\n\n " +
                                                                  str(model['notes']).replace('\r\n', '\r\n\r\n'),
                                                         is_full_depth=False, u_height=0.0)
                else:
                    # Found Device Type by Mode+Manufacturer, so update the Custom Field ID-Value for proper linking
                    if self.allow_linking:
                        update_obj = update_obj | {"id": present_nb_devtype["id"], "custom_fields": {KEY_CUSTOM_FIELD: model['id']}}
                        logging.info("Found Device Type {} by Model and Manufacturer Name. Updating custom field.".format(model['name']))
                    else:
                        logging.info("Found Device Type {} by name. Skipping, since linking is not enabled.".format(model['name']))

            else:
                # Found associated Device Type, check if things have changed

                if present_nb_devtype['model'] != model['name']:
                    update_obj = update_obj | {"id": present_nb_devtype["id"], "model": model['name'], "slug": Syncer.slugify(model['name'])}

                if present_nb_devtype['part_number'] != model['model_number']:
                    update_obj = update_obj | {"id": present_nb_devtype["id"], "part_number": model['model_number']}

                if present_nb_devtype['manufacturer']['id'] != manuf_by_model.id:
                    update_obj = update_obj | {"id": present_nb_devtype["id"], "manufacturer": manuf_by_model.id}

                if "id" in update_obj:
                    if self.allow_updates:
                        logging.info("The Device Type {} has changed, updating Item".format(model['name']))
                    else:
                        logging.info("The Device Type {} has changed. Skipping since updating is not enabled.".format(model['name']))


            # check if the Device Type needs an Update and write it to the API
            if "id" in update_obj and self.allow_updates:
                update_obj = update_obj | {"description": self.desc.replace("Imported", "Updated")}
                self.netbox.dcim.device_types.update([update_obj])

    def sync_sites(self, top_locations):
        netbox_sites = list(self.netbox.dcim.sites.all())

        for location in top_locations:
            logging.info("Checking Top Location {}".format(location['name']))

            present_nb_devtype = next((item for item in netbox_sites if item['custom_fields'][KEY_CUSTOM_FIELD] == location['id']), None)
            if present_nb_devtype is None:
                # Site is unique by Name
                present_nb_devtype = next((item for item in netbox_sites if item["name"] == location['name']), None)

                if present_nb_devtype is None:
                    logging.info("Adding Site {} to netbox".format(location['name']))
                    self.netbox.dcim.sites.create(name=location['name'], slug=Syncer.slugify(location['name']),
                                                  description=self.desc, status='active',
                                                  custom_fields={KEY_CUSTOM_FIELD: location['id']})
                else:
                    if self.allow_linking:
                        logging.info("Found Site {} by name. Updating custom field instead.".format(location['name']))
                        self.netbox.dcim.sites.update([{"id": present_nb_devtype["id"],
                                                        "comments": present_nb_devtype['comments'] + '\r\n\r\n' + self.desc.replace("Imported", "Updated") + " (Snipe ID)",
                                                        "custom_fields": {KEY_CUSTOM_FIELD: location['id']}}])
                    else:
                        logging.info("Found Site {} by name. Skipping, since linking is not enabled.".format(location['name']))

            elif present_nb_devtype['name'] != location['name']:
                if self.allow_updates:
                    logging.info("The Site {} is present, updating Item".format(location['name']))
                    self.netbox.dcim.sites.update([{"id": present_nb_devtype["id"], "name": location['name'],
                                                    "slug": Syncer.slugify(location['name']),
                                                    "comments": present_nb_devtype['comments'] + '\r\n\r\n' + self.desc.replace("Imported", "Updated") + " (Values)",
                                                    }])
                else:
                    logging.info("The Site {} is changed. Skipping since updating is not enabled.".format(location['name']))



