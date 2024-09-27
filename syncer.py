import datetime
import logging
import unicodedata
import re
from datetime import datetime, timezone

import pynetbox

KEY_CUSTOM_FIELD = "snipe_object_id"
DEFAULT_SITE_NAME = "Default Site"


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


    def __gen_update_comment(self, old_comment: str, suffix: str = None):
        val = old_comment + '\r\n\r\n' + self.desc.replace("Imported", "Updated")
        if suffix is not None:
            val += " (" + suffix + ")"
        return val

    def __get_fallback_site(self, company_name=None):

        if company_name is not None:
            # try a hard mapping
            # ToDo: this is not very elegant and should be configurable
            company_name = company_name.lower()
            if "akademie" in company_name:
                fallback_site = self.netbox.dcim.sites.get(name="547 Akademie")
            elif "oper" in company_name or "medienabt" in company_name:
                fallback_site = self.netbox.dcim.sites.get(name="530 Verwaltung/Oper")
            elif "schauspi" in company_name:
                fallback_site = self.netbox.dcim.sites.get(name="529 Schauspielhaus")
            elif "ballett" in company_name:
                fallback_site = self.netbox.dcim.sites.get(name="551 Ballettzentrum")
            else:
                fallback_site = self.netbox.dcim.sites.get(name=DEFAULT_SITE_NAME)

        else:
            fallback_site = self.netbox.dcim.sites.get(name=DEFAULT_SITE_NAME)


        if fallback_site is None:
            fallback_site = self.netbox.dcim.sites.create(name=DEFAULT_SITE_NAME, slug=Syncer.slugify(DEFAULT_SITE_NAME),
                                                          description="Default Site for SnipeIT Import", status='active')

        return fallback_site

    def ensure_netbox_custom_field(self, lock: bool = False):
        content_types = ['dcim.device', 'dcim.devicetype', 'dcim.interface', 'dcim.manufacturer', 'dcim.site', 'dcim.devicerole',
                         'dcim.location', 'tenancy.tenant']
        cufi = {"name": KEY_CUSTOM_FIELD, "display": "Snipe object id", "object_types": content_types,
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
        # ToDo: remove local desc
        desc = "Imported from SnipeIT {}".format(datetime.now(timezone.utc).strftime("%y-%m-%d %H:%M:%S (UTC)"))

        for snipe_company in snipe_companies:
            logging.info("Checking Company {}".format(snipe_company['name']))

            present_nb_tenant = next((item for item in netbox_tenants if item["custom_fields"][KEY_CUSTOM_FIELD] == snipe_company['id']), None)
            if present_nb_tenant is None:
                # Tenant is unique by Name
                present_nb_tenant = next((item for item in netbox_tenants if item["name"].lower().strip() == snipe_company['name'].lower().strip()), None)
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
                present_nb_manuf = next((item for item in netbox_manufacturers if item["name"].lower().strip() == snipe_manuf['name'].lower().strip()), None)

                if present_nb_manuf is None:
                    logging.info("Adding Manufacturer {} to netbox".format(snipe_manuf['name']))
                    self.netbox.dcim.manufacturers.create(name=snipe_manuf['name'], slug=Syncer.slugify(snipe_manuf['name']),
                                                          description=self.desc,
                                                          custom_fields={KEY_CUSTOM_FIELD: snipe_manuf['id']})
                else:
                    if self.allow_linking:
                        logging.info("Found Manufacturer {} by name. Updating custom field instead.".format(snipe_manuf['name']))
                        self.netbox.dcim.manufacturers.update([{"id": present_nb_manuf["id"],
                                                                "custom_fields": {KEY_CUSTOM_FIELD: snipe_manuf['id']}}])
                    else:
                        logging.info("Found Manufacturer {} by name. Skipping, since linking is not enabled.".format(snipe_manuf['name']))

            elif present_nb_manuf['name'] != snipe_manuf['name']:
                if self.allow_updates:
                    logging.info("The Manufacturer {} is present, updating Item".format(snipe_manuf['name']))
                    self.netbox.dcim.manufacturers.update([{"id": present_nb_manuf["id"], "name": snipe_manuf['name'],
                                                            "slug": Syncer.slugify(snipe_manuf['name'])}])
                else:
                    logging.info("The Manufacturer {} is changed. Skipping since updating is not enabled.".format(snipe_manuf['name']))

    def sync_models_to_device_types(self, snipe_models):
        netbox_device_types = list(self.netbox.dcim.device_types.all())
        netbox_manufacturers = list(self.netbox.dcim.manufacturers.all())

        for model in snipe_models:
            update_obj = {}
            logging.info("Checking Device Type {}".format(model['name']))
            # get the manufacturer by Name of the Snipe Model-Manufacturer for later use
            manuf_by_model = next((item for item in netbox_manufacturers if item["name"] == model['manufacturer']['name']), None)

            # search the Device Type by Custom Field ID-Value
            present_nb_devtype = next((item for item in netbox_device_types if item['custom_fields'][KEY_CUSTOM_FIELD] == model['id']), None)   # ToDo: use function

            if present_nb_devtype is None:  # No associated Device Type found

                # Search by Model+Manufacturer
                present_nb_devtype = next((item for item in netbox_device_types if item['model'].lower().strip() == model['name'].lower().strip() and
                                           item['manufacturer']['name'].lower().strip() == model['manufacturer']['name'].lower().strip()), None)

                if present_nb_devtype is None:
                    logging.info("Adding Device Type {} to netbox".format(model['name']))

                    self.netbox.dcim.device_types.create(slug=Syncer.slugify(model['name']),
                                                         description=self.desc, model=model['name'],
                                                         part_number=model['model_number'],
                                                         manufacturer=manuf_by_model.id,
                                                         custom_fields={KEY_CUSTOM_FIELD: model['id']},
                                                         comments="Notes from SnipeIT when initially creating this Netbox Entry. "
                                                                  "\n " +
                                                                  str(model['notes']).replace('\r\n', '\r\n\r\n'),
                                                         is_full_depth=False, u_height=0.0)
                else:
                    # Found Device Type by Mode+Manufacturer, so update the Custom Field ID-Value for proper linking
                    if self.allow_linking:
                        update_obj = update_obj | {"id": present_nb_devtype["id"],
                                                   "custom_fields": {KEY_CUSTOM_FIELD: model['id']},
                                                   "comments": self.__gen_update_comment(present_nb_devtype['comments'], "Snipe ID")}
                        logging.info("Found Device Type {} by Model and Manufacturer Name. Updating custom field.".format(model['name']))
                        self.netbox.dcim.device_types.update([update_obj])
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
                        update_obj = update_obj | {"comments": self.__gen_update_comment(present_nb_devtype['comments'], "Values")}
                        self.netbox.dcim.device_types.update([update_obj])
                    else:
                        logging.info("The Device Type {} has changed. Skipping since updating is not enabled.".format(model['name']))

    def sync_top_locations_to_sites(self, locations):
        netbox_sites = list(self.netbox.dcim.sites.all())

        # the top locations without a parent will be the Sites in NetBox
        top_locations = list(filter(lambda s: s['parent'] is None, locations))

        for location in top_locations:
            logging.info("Checking Top Location as Site: {}".format(location['name']))

            present_nb_site = next((item for item in netbox_sites if item['custom_fields'][KEY_CUSTOM_FIELD] == location['id']), None)   # ToDo: use function
            if present_nb_site is None:
                # Site is unique by Name
                present_nb_site = next((item for item in netbox_sites if item["name"].lower().strip() == location['name'].lower().strip()), None)   # ToDo: use function

                if present_nb_site is None:
                    logging.info("Adding Site {} to netbox".format(location['name']))
                    self.netbox.dcim.sites.create(name=location['name'], slug=Syncer.slugify(location['name']),
                                                  description=self.desc, status='active',
                                                  custom_fields={KEY_CUSTOM_FIELD: location['id']})
                else:
                    if self.allow_linking:
                        logging.info("Found Site {} by name. Updating custom field instead.".format(location['name']))
                        self.netbox.dcim.sites.update([{"id": present_nb_site["id"],
                                                        "comments": self.__gen_update_comment(present_nb_site['comments'], "Snipe ID"),
                                                        "custom_fields": {KEY_CUSTOM_FIELD: location['id']}}])
                    else:
                        logging.info("Found Site {} by name. Skipping, since linking is not enabled.".format(location['name']))

            elif present_nb_site['name'] != location['name']:
                if self.allow_updates:
                    logging.info("The Site {} is present, updating Item".format(location['name']))
                    self.netbox.dcim.sites.update([{"id": present_nb_site["id"], "name": location['name'],
                                                    "slug": Syncer.slugify(location['name']),
                                                    "comments": self.__gen_update_comment(present_nb_site['comments'],"Values"),
                                                    }])
                else:
                    logging.info("The Site {} is changed. Skipping since updating is not enabled.".format(location['name']))



    def __sync_location(self, netbox_sites, netbox_locations, locations_with_parents, location):
        logging.info("Checking Location {}".format(location['name']))
        # try to find the site
        parent = location['parent']
        site = None

        # traverse up the tree to find the top location which is the Site
        while site is None:
            if parent is not None:
                logging.debug("parent: {}".format(parent['name']))
                site = next((item for item in netbox_sites if item['custom_fields'][KEY_CUSTOM_FIELD] == parent['id']), None)   # ToDo: use function
            else:
                logging.error("can not find the Site for Location {}".format(location['name']))
                return

            parent_item = next((item for item in locations_with_parents if item['id'] == parent['id']), None)   # ToDo: use function
            if parent_item is not None:
                parent = parent_item['parent']
            else:
                parent = None


        logging.debug("Site for Location {} will be {}".format(location['name'], site['name']))

        # check if we can find the location by Snipe ID
        present_nb_loc = next((item for item in netbox_locations if item['custom_fields'][KEY_CUSTOM_FIELD] == location['id']), None)   # ToDo: use function

        if present_nb_loc is None:
            # not found by ID, so Location is unique by Name within a Site, try find it
            present_nb_loc = next((item for item in netbox_locations if item["name"].lower().strip() == location['name'].lower().strip() and item['site']['id'] == site['id']), None)   # ToDo: use function

            if present_nb_loc is None:
                logging.info("Adding Location {} to netbox".format(location['name']))
                self.netbox.dcim.locations.create(name=location['name'], slug=Syncer.slugify(location['name']),
                                                  description=self.desc, status='active', site=site['id'],
                                                  custom_fields={KEY_CUSTOM_FIELD: location['id']})
            else:
                if self.allow_linking:
                    logging.info("Found Location {} by name. Updating custom field instead.".format(location['name']))
                    self.netbox.dcim.locations.update([{"id": present_nb_loc["id"],
                                                        "custom_fields": {KEY_CUSTOM_FIELD: location['id']}}])
                else:
                    logging.info("Found Location {} by name. Skipping, since linking is not enabled.".format(location['name']))
        else:
            # is present, so check if changed and we may update
            if present_nb_loc['name'] != location['name'] or present_nb_loc['site']['id'] != site['id']:
                if self.allow_updates:
                    logging.info("The Location {} has changed, updating Item".format(location['name']))
                    self.netbox.dcim.locations.update([{"id": present_nb_loc["id"], "name": location['name'],
                                                        "site": site['id'],
                                                        "slug": Syncer.slugify(location['name'])
                                                        }])
                else:
                    logging.info("The Location {} has changed. Skipping since updating is not enabled.".format(location['name']))

    def __sync_location_relationships(self, sub_locations):
        # get them fresh from the API
        netbox_locations = list(self.netbox.dcim.locations.all())
        updates = []

        for snipe_location in sub_locations:
            present_nb_loc = next((item for item in netbox_locations if item['custom_fields'][KEY_CUSTOM_FIELD] == snipe_location['id']), None)  # ToDo: use function
            assert present_nb_loc is not None
            present_nb_parent_loc = next((item for item in netbox_locations if item['custom_fields'][KEY_CUSTOM_FIELD] == snipe_location['parent']['id']), None)  # ToDo: use function
            assert present_nb_parent_loc is not None

            if present_nb_loc and present_nb_loc['parent'] and present_nb_parent_loc and present_nb_loc['parent']['id'] != present_nb_parent_loc['id']:
                if self.allow_updates:
                    logging.info("The Location {} has changed, updating Item".format(present_nb_loc['name']))
                    updates.append({"id": present_nb_loc["id"], "parent": present_nb_parent_loc['id']})
                else:
                    logging.info("The Location {} has changed. Skipping since updating is not enabled.".format(present_nb_loc['name']))

        # update all at once
        self.netbox.dcim.locations.update(updates)

    def sync_locations(self, locations):
        netbox_locations = list(self.netbox.dcim.locations.all())
        netbox_sites = list(self.netbox.dcim.sites.all())

        snipe_locations_with_parent = list(filter(lambda s: s['parent'] is not None, locations))

        snipe_sub_locations = []

        for snipe_location in snipe_locations_with_parent:
            # check if the locations's parent is a NetBox Site, then it is considered a top level Location
            if next((item for item in netbox_sites if item['custom_fields'][KEY_CUSTOM_FIELD] == snipe_location['parent']['id']), None) is None:    # ToDo: use function
                snipe_sub_locations.append(snipe_location)


        for snipe_location in snipe_locations_with_parent:
            self.__sync_location(netbox_sites, netbox_locations, snipe_locations_with_parent, snipe_location)

        self.__sync_location_relationships(snipe_sub_locations)

    @staticmethod
    def __get_customfield_from_dict_list(the_list: list, needle: int):
        return next((item for item in the_list if item["custom_fields"][KEY_CUSTOM_FIELD] == needle), None)


    def __get_role_from_category(self, netbox_roles, snipe_asset):
        category_name = snipe_asset['category']['name']
        # ToDo: take the category name, if contains a hyphen, only take first part upto the
        #  hypen (trim). Then search for that name, if not found -> create a new role

        hypos = category_name.find("-")
        if hypos > 1:
            category_name = category_name[0:hypos].strip()

        # first search by snipe id in the custom field
        role = Syncer.__get_customfield_from_dict_list(netbox_roles, snipe_asset['category']['id'])
        if role is None:
            # then search by the name
            role = next((item for item in netbox_roles if item['name'] == category_name), None)

            if role is not None:
                # then update the custom field id
                self.netbox.dcim.device_roles.update([{"id": role['id'],
                                                       "custom_fields": {KEY_CUSTOM_FIELD: snipe_asset['category']['id']}}])

        if role is None:
            role = self.netbox.dcim.device_roles.create(name=category_name,
                                                        slug=Syncer.slugify(category_name))
            netbox_roles.append(role)

        return netbox_roles, role


    def sync_assets_to_devices(self, snipe_assets, update_unique_existing, no_append_assettag):
        netbox_devices = list(self.netbox.dcim.devices.all())
        netbox_tenants = list(self.netbox.tenancy.tenants.all())
        netbox_sites = list(self.netbox.dcim.sites.all())
        netbox_locations = list(self.netbox.dcim.locations.all())
        netbox_roles = list(self.netbox.dcim.device_roles.all())
        netbox_device_types = list(self.netbox.dcim.device_types.all())


        fallback_site = None

        for snipe_asset in snipe_assets:
            logging.info("Checking Asset: {} Tag: {}".format(snipe_asset['name'], snipe_asset['asset_tag']))
            if snipe_asset['name'] == "xxxxxxxxxxxxxx":
                logging.info("debug me - set breakpoint here")

            if update_unique_existing or no_append_assettag:
                # check if the name is unique in snipeit
                otherAsset = next((item for item in snipe_assets if (item["name"] and item["name"].lower().strip() == snipe_asset['name'].lower().strip() and item['id'] != snipe_asset['id'])), None)
                unique = (not otherAsset)
            else:
                unique = False

            nb_device_type = Syncer.__get_customfield_from_dict_list(netbox_device_types, snipe_asset['model']['id'])

            if not nb_device_type:
                logging.warn("No device type! skipping")
                continue

            location = None
            # Location:
            # if checked out to a Location:
            #       the property "location" contains e.g. "{'id': 76, 'name': '530 Verwaltung/Oper'}"
            #       the property "assigned_to" contains e.g. "{'id': 76, 'name': '530 Verwaltung/Oper', 'type': 'location'}"
            # if the found location is a site, set site, but not location (this ensures that already existing devices with location can be updated)

            if snipe_asset['location']:
                locationId = snipe_asset['location']['id']
            elif snipe_asset['rtd_location']:
                locationId = snipe_asset['rtd_location']['id']
            else:
                locationId = None

            if locationId:
                location = Syncer.__get_customfield_from_dict_list(netbox_locations, locationId)

            if location is not None:
                site = location['site']
            elif locationId:
                site = Syncer.__get_customfield_from_dict_list(netbox_sites, locationId)
            elif snipe_asset['company'] is not None:
                site = self.__get_fallback_site(snipe_asset['company']['name'])
            else:
                site = None

            nb_tenant = None
            if snipe_asset['company'] is not None:
                nb_tenant = Syncer.__get_customfield_from_dict_list(netbox_tenants, snipe_asset['company']['id'])

            netbox_roles, role = self.__get_role_from_category(netbox_roles, snipe_asset)

            try:
                self.__sync_device(nb_device_type, nb_tenant, netbox_devices, role, site, snipe_asset, update_unique_existing, unique, no_append_assettag)
            except Exception as e:
                logging.error("---------------------------------------------------------")
                logging.error("Error importing/updating Asset: {} Tag: {}".format(snipe_asset['name'], snipe_asset['asset_tag']))
                logging.error(e)


    def __update_device(self, nb_device, snipe_device, nb_role, nb_site, nb_tenant, nb_device_type, nb_status, update_custom_field_id: bool = False):
        """
        This function updates a netbox device. It will check for changed properties and only write to netbox if something has changed
        :param update_custom_field_id: This sets when the linking ID should be updated
        """
        update_dict = {'id': nb_device['id']}

        if update_custom_field_id:
            update_dict = update_dict | {"custom_fields": {KEY_CUSTOM_FIELD: snipe_device['id']}}

        if nb_device['asset_tag'] != snipe_device['asset_tag']:
            update_dict = update_dict | {'asset_tag': snipe_device['asset_tag']}

        if nb_device['serial'] != snipe_device['serial']:
            update_dict = update_dict | {'serial': snipe_device['serial']}

        if nb_site and nb_device['site']['id'] != nb_site['id']:
            update_dict = update_dict | {'site': nb_site['id']}

        if nb_device['device_role']['id'] != nb_role['id']:
            update_dict = update_dict | {'device_role': nb_role['id']}

        if nb_tenant and nb_device['tenant'] and nb_device['tenant']['id'] != nb_tenant['id']:
            update_dict = update_dict | {'tenant': nb_tenant['id']}

        if nb_device['device_type']['id'] != nb_device_type['id']:
            update_dict = update_dict | {'device_type': nb_device_type['id']}

        if nb_device['status']['value'] != nb_status:
            update_dict = update_dict | {'status': nb_status}

        # check if we altered the netbox name to avoid conflict
        oldname = nb_device['name']

        if oldname is not None and oldname.rfind(snipe_device['asset_tag']) > 1:
            # strip the tag
            oldname = oldname[0:oldname.rfind(snipe_device['asset_tag'])-1]


        # snipe's empty name can be an empty string rather then None
        check_name = snipe_device['name'] if len(snipe_device['name']) > 0 else None

        if oldname != check_name:
            if check_name is None:
                # no check needed, Netbox allows multiple Devices without Name
                name = None
            else:
                # check for possible name conflict
                if self.netbox.dcim.devices.get(name=check_name, site_id=nb_site['id'], tenant_id=nb_tenant['id']):
                    name = "{} {}".format(check_name, snipe_device['asset_tag'])
                else:
                    name = snipe_device['name']

            update_dict = update_dict | {'name': name}


        if len(update_dict.values()) > 1:
            update_dict = update_dict | {"comments": self.__gen_update_comment(nb_device['comments'], "Snipe ID" if "custom_fields" in update_dict.keys() else "Values")}
            logging.info("Updating Device {}".format(update_dict))
            self.netbox.dcim.devices.update([update_dict])



    def __sync_device(self, nb_device_type, nb_tenant, netbox_devices, nb_role, nb_site, snipe_asset, update_unique_existing, unique, no_append_assettag):

        # try finding by SnipeID, this will be a hard unique association:
        device = next((item for item in netbox_devices if item["custom_fields"][KEY_CUSTOM_FIELD] == snipe_asset['id']), None)

        nb_status = 'active'
        if snipe_asset['status_label']['status_meta'] in ['undeployable', 'pending']: # deployed, deployable
            nb_status = 'offline'
            if snipe_asset['assigned_to'] == None:
                if not device:
                    # no not create undeployable and not deployed device
                    return
                #else
                    # fixme: change location to none?
        elif snipe_asset['status_label']['status_meta'] in ['deployable']:
            nb_status = 'inventory'

        if device is not None:
            # check if updating is allowed, then check changed fields and update
            self.__update_device(device, snipe_asset, nb_role, nb_site, nb_tenant, nb_device_type,  nb_status, False)
            return

        # try finding by Asset Tag, the Tag is a required field in Snipe and Optional in Netbox
        device = next((item for item in netbox_devices if item["asset_tag"] and item["asset_tag"] == snipe_asset['asset_tag']), None)
        if device is not None:
            # check if updating is allowed, then check changed fields and update
            self.__update_device(device, snipe_asset, nb_role, nb_site, nb_tenant, nb_device_type, nb_status, True)
            return


        if unique and update_unique_existing:
            # Try finding device by Name and Tenant, Netbox has a unique constraint to that two fields
            device = next((item for item in netbox_devices if (item["name"] and item["name"].lower().strip() == snipe_asset['name'].lower().strip() and item['tenant'] is not None and item['tenant']['id'] == nb_tenant['id'])), None)
            # If a device with the same Name and Tenant is found update it
            if device is not None:
                # check if updating is allowed, then check changed fields and update
                self.__update_device(device, snipe_asset, nb_role, nb_site, nb_tenant, nb_device_type, nb_status, True)
                return
                
        # if no device is found with same uniqe name and same tenant we add the Asset Tag to the Name and create a new Device
        if snipe_asset['name']:
            if unique and (update_unique_existing or no_append_assettag):
                name = snipe_asset['name']
            else:
                name = "{} {}".format(snipe_asset['name'], snipe_asset['asset_tag'])
        else:
            name = snipe_asset['asset_tag']

        logging.info("Adding Device to netbox, name {}".format(name))
        device = self.netbox.dcim.devices.create(name=name,
                                                 comments="Notes from SnipeIT when initially creating this Netbox Entry. "
                                                          "\n " +
                                                          str(snipe_asset['notes']).replace('\r\n', '\r\n\r\n'),
                                                 description=self.desc,
                                                 status=nb_status,
                                                 site=nb_site['id'] if nb_site else 1,
                                                 asset_tag=snipe_asset['asset_tag'],
                                                 role=nb_role['id'],
                                                 serial=snipe_asset['serial'],
                                                 device_type=nb_device_type['id'],
                                                 tenant=nb_tenant['id'] if nb_tenant is not None else None,
                                                 custom_fields={KEY_CUSTOM_FIELD: snipe_asset['id']})

        netbox_devices.append(device)











