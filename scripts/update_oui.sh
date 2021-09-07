# Script to update the Python netaddr module's Ethernet IAB/OUI library.
# See more at https://www.redelijkheid.com/blog/2019/5/10/update-python-netaddr-oui-database
#
# NOTE: you should run this *every* time you run upgrade.sh !!!
#

WORKDIR="/opt/openl2m"
PYTHONVERSION="python3.6"

# here we go:
cd $WORKDIR

# check if a netaddr directory inside the virtual env exists
if [ ! -d "venv/lib/$PYTHONVERSION/site-packages/netaddr/eui" ]
then
    echo " netaddr package directory 'venv/lib/$PYTHONVERSION/site-packages/netaddr/eui' not found!"
    echo " NOT updating the OUI database."
    exit 1
fi

# check for alternate python version
if [ -f "../altpython.sh" ]; then
  source "../altpython.sh"
  echo "Using Alternate Python version '${PYTHONVERSION}'"
fi

# make sure the virtual environment is activated!
source venv/bin/activate

# go to the netaddr install location inside the Virtual Environment:
cd venv/lib/$PYTHONVERSION/site-packages/netaddr/eui

# copy old files
cp iab.idx iab.idx.old
cp iab.txt iab.txt.old
cp oui.idx oui.idx.old
cp oui.txt oui.txt.old

# download new iab and oui files
curl http://standards-oui.ieee.org/iab/iab.txt --output iab.txt
curl http://standards-oui.ieee.org/oui/oui.txt --output oui.txt

# run the 'index creation script'
python3 ieee.py