import logging
import math
import requests


class Snipe:
    def __init__(self, url: str, token: str):
        self.url = "{}/api/v1/".format(url if url[-1] != "/" else url[:-1])
        self.token = token
        self.headers = {'Authorization': 'Bearer ' + token,
                        'accept': 'application/json',
                        'content-type': 'application/json'}


    def __get_paged_items(self, session: requests.Session, endpoint: str, pagesize: int = 100):
        response = session.get(self.url + endpoint, params={'limit': pagesize, 'offset': 0},
                               headers=self.headers).json()
        yield response
        num_pages = math.ceil(response['total'] / pagesize)

        for page in range(1, num_pages):
            next_page = session.get(self.url + endpoint, params={'limit': pagesize, 'offset': page * pagesize},
                                    headers=self.headers).json()
            yield next_page

    @staticmethod
    def __custom_fields_has_mac_type(custom_fields: dict):
        for field in custom_fields.values():
            if field['field_format'].lower() == "mac":
                return True
        return False


    def get_locations(self):
        session = requests.Session()

        locations = []
        for page in self.__get_paged_items(session, "locations", pagesize=200):
            for location in page['rows']:
                if location not in locations:
                    locations.append(location)

        locations = sorted(locations, key=lambda d: d['name'])
        return locations

    def get_assets_with_mac(self):
        session = requests.Session()
        fieldsets = self.__get_fieldsets_with_mac(session)

        # i don't know an easy way to fetch only assets with mac fieldsets, so we have to get everything and filter locally

        assets = []
        for page in self.__get_paged_items(session, "hardware", pagesize=200):
            print("Page {}".format(len(page['rows'])))
            for asset in page['rows']:
                if Snipe.__custom_fields_has_mac_type(asset['custom_fields']):
                    if asset not in assets:
                        assets.append(asset)

        assets = sorted(assets, key=lambda d: d['asset_tag'])
        return assets


    def get_models_and_manufacturers_with_mac(self):
        session = requests.Session()

        fieldsets = self.__get_fieldsets_with_mac(session)

        manufacturers = []
        models = []

        for page in self.__get_paged_items(session, "models"):
            for model in page['rows']:
                if model['fieldset'] is not None and model['fieldset']['id'] in fieldsets:

                    if model not in models:
                        models.append(model)

                    if model['manufacturer'] not in manufacturers:
                        manufacturers.append(model['manufacturer'])

        manufacturers = sorted(manufacturers, key=lambda d: d['id'])
        models = sorted(models, key=lambda d: d['id'])


        return manufacturers, models

    def __get_fieldsets_with_mac(self, session: requests.Session):
        response = session.get(self.url + "fieldsets", headers=self.headers).json()
        fieldsets_with_mac = []

        for fieldset in response['rows']:
            for fields in fieldset['fields']['rows']:
                if str(fields['format']).lower() == "mac":
                    fieldsets_with_mac.append(fieldset['id'])
                    break

        return fieldsets_with_mac

    def get_companies(self):
        session = requests.Session()
        return session.get(self.url + "companies", headers=self.headers).json()['rows']
