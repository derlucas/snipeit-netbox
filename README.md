# Snipe-IT to NetBox Sync

This Software can sync Data from [Snipe-IT](https://github.com/snipe/snipe-it) to [NetBox](https://github.com/netbox-community/netbox).

## Requirements + Installation

- Python 3.10 (or newer)
- Snipe-IT and NetBox API Key

Install dependencies by creating a Python Virtual Environment:

    python -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt

Configure the API endpoints and Access Tokens in the "config.ini" file.
Use the example "config.ini.default" file, rename it to "config.ini" and 
change the values in the File.

## Usage

The Program will introduce a new Custom Field in Netbox to allow linking the 
Snipe-IT Database ID.

    source venv/bin/activate  (just once you open a new Terminal)
    python main.py [--allow-update] [--allow-linking] [--update-unique-existing|--no-append-assettag]

* `--allow-update`: Update existing assets
* `--allow-linking`: add custom field 'Snipe object id' to imported/updated netbox items and link to id of snipe-it item and use as unique-key for further syncs.
* `--update-unique-existing`: if the name of a snipe-it asset is unique and can be found in netbox, update it in netbox. Includes no-append-assettag.
* `--no-append-assettag`: if the name of a snipe-it asset is unique add it without appending the assettag

By default, without any command line args, the programm will just create new
Items in NetBox. When duplicate Items are found by Name, it will skip Updating.

To Enable Updating already present Items, use the Command line switch "--allow-update".

To allow adding the Database ID to already present Items, 
use the Command Line Switch "--allow-linking". This will match Items by Name and
other NetBox unique constraints to find possible Matches and set the Snipe-IT
Database ID in the NetBox Item.

If you have already items in netbox and want to update them by just the asset-name enable "--update-unique-existing". Only assets 
with a unique name in snipe-it will be updated. If there are more assets in snipe-it with the same name they are all added.
In this mode also "--no-append-assettag" is enabled.

Usually the imported (created/updated) devices get the snipe-it-assettag appended to the name. Use "--no-append-assettag" to 
disable dis behavior. If there are more assets in snipe-it with the same name for this assets the tag is added to the name.


## Link, Sync, Information

Deleted Items in Snipe-IT will NOT be deleted from NetBox.

The software will only sync Device Types (and thus Devices) with a MAC field set assigned in Snipe-IT.

- Snipe Devices are synced to NetBox Devices
- Snipe Manufacturers are synced to NetBox Manufacturers
- Snipe Asset Models are synced to NetBox Device Types
- Snipe Companies are synced to NetBox Tenants
- Snipe Locations without a parent Location are synced to Netbox Sites