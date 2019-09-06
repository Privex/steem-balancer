Steem RPC Load Balancer
=======================

A small Python load balancer for Steem RPC nodes.

```
    +===================================================+
    |                 © 2019 Privex Inc.                |
    |               https://www.privex.io               |
    +===================================================+
    |                                                   |
    |        Steem RPC Load Balancer                    |
    |                                                   |
    |        Core Developer(s):                         |
    |                                                   |
    |          (+)  Chris (@someguy123) [Privex]        |
    |                                                   |
    +===================================================+
```

License
=======

Released under the GNU AGPLv3 - see LICENSE.txt and AGPL-3.0.txt


Quickstart
==========

**Initial Setup**

```bash
# Install Python 3.7, pip, virtualenv, and redis
apt update
apt install -y python3.7 python3.7-dev python3-pip python3-venv redis-server
# Install pipenv
pip3 install pipenv
# Create and login to stmbal user to run the balancer
adduser --gecos "" --disabled-password stmbal
su - stmbal

# Clone the repo, install deps + create venv with pipenv
git clone https://github.com/Privex/steem-balancer.git
cd steem-balancer
pipenv install

# Copy example config and add nodes as needed
cp configs/nodes.json.example configs/nodes.json
nano configs/nodes.json

# Become root again
exit
```

**For production - install systemd service**

As root:

```bash

cp -v /home/stmbal/steem-balancer/steem-balancer.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable steem-balancer.service
systemctl start steem-balancer.service
```

**For development - use ./run.sh dev**

```bash
su - stmbal
cd steem-balancer
./run.sh dev

```

