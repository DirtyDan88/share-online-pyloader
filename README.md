# share-online-pyloader
Terminal downloader for [share-online.biz](http://www.share-online.biz/) premium members.

This python-script enables you to download content via terminal from [share-online.biz](http://www.share-online.biz/) with your premium-account, for example if you want to run some downloads but only have termial-access to a remote computer. It can be seen as a simple and light-weight alternative to jDownloader, pyLoad, aria2 etc.
See license for legal restrictions.

![Screenshot of UI](https://raw.githubusercontent.com/DirtyDan88/share-online-pyloader/master/screenshot.png)

## Setup
- well, a valid share-online premium-account (enter username and password inside the script)
- python3
  - python3-requests
  - python3-pip to install module rarfile (http://rarfile.readthedocs.io/en/latest/)
  - rarfile also needs unrar

Debian/Ubuntu:
```sh
# sudo apt-get install python3 python3-pip unrar-free
# sudo python3 -m pip install rarfile
# git clone https://github.com/DirtyDan88/share-online-pyloader.git
# cd share-online-pyloader
# python share-online.py -h
```
If you run into problems when installing pip, try this:
```sh
# wget https://bootstrap.pypa.io/get-pip.py
# sudo python get-pip.py
```

## Usage
- type ```python3 share-online.py -h``` for help message
- optional arguments:

        -s      the number of download-slots to use (e.g. parallel executed downloads)
        -e      extract files after download
        -p      password for archieves (only when -e is present)
- positional arguments:

        - linkListFileName      file-name with share-online links, see link-ids-TEMPLATE.txt
        - Example:              # python3 share-online.py links.txt

## Grabbing link-ids:
Copy content of DLC-file and decrypt it here: [dcrypt.it](http://dcrypt.it/) to get links via Click'n'Load you can use this script: [https://github.com/drwilly/clicknload2text](https://github.com/drwilly/clicknload2text).

Copy the links into a file as shown in link-ids-TEMPLATE.txt and run the downloader. Enjoy!
