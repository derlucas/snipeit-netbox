# SnipeIT to NetBox Sync

This Software can sync Data from SnipeIt to NetBox.

## Requirements + Installation

- Python 3.10 (or newer)
- SnipeIt and NetBox API Key

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
SnipeIt Database ID.

    source venv/bin/activate  (just once you open a new Terminal)
    python main.py --allow-update --allow-linking

By default, without any command line args, the programm will just create new
Items in NetBox. When duplicate Items are found by Name, it will skip Updating.

To Enable Updating already present Items, use the Command line switch "--allow-update".

To allow adding the Database ID to already present Items, 
use the Command Line Switch "--allow-linking". This will match Items by Name and
other NetBox unique constraints to find possible Matches and set the SnipeIt
Database ID in the NetBox Item.
