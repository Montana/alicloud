# alix

<img width="1254" height="1254" alt="alicloud" src="https://github.com/user-attachments/assets/dce15da9-545e-4b34-837d-f5dbaaf03441" />

<br>A simple command-line tool for Alibaba Cloud. Manage ECS servers, OSS storage, and DNS records with short commands.</br>

I made this generally for the purpose of shortening the structure for a plugin-based Alibaba Cloud CLI, and to run anything in AliCloud goes as follows:

```bash
aliyun <command> <sub-command> [parameters]
```
## Installation

```bash
pip install oss2 alibabacloud_ecs20140526 alibabacloud_alidns20150109
```

## Setup

Run the interactive setup once:

```bash
python alix.py config
```
Here's a GIF showing you: 

<img width="730" height="604" alt="alix-demo" src="https://github.com/user-attachments/assets/ba23811f-fa07-498b-8218-200f45253981" />

This stores your AccessKey in `~/.alix/config.json` with restricted file permissions. You can create an AccessKey in the Alibaba Cloud RAM console under Users > your user > AccessKeys.

Alternatively, set environment variables (these take priority over the config file):

```bash
export ALIBABA_CLOUD_ACCESS_KEY_ID=your-key-id
export ALIBABA_CLOUD_ACCESS_KEY_SECRET=your-key-secret
export ALIBABA_CLOUD_REGION=us-west-1
```

## Usage

### ECS (servers)

```bash
python alix.py ecs list                  # list all instances
python alix.py ecs start i-abc123        # start an instance
python alix.py ecs stop i-abc123         # stop an instance (pauses billing where supported)
python alix.py ecs reboot i-abc123       # reboot an instance
```

### OSS (object storage)

```bash
python alix.py oss buckets                       # list buckets
python alix.py oss ls my-bucket                  # list files in a bucket
python alix.py oss ls my-bucket photos/          # list files under a prefix
python alix.py oss up my-bucket photo.jpg        # upload a file
python alix.py oss up my-bucket photo.jpg remote-name.jpg
python alix.py oss down my-bucket photo.jpg      # download a file
python alix.py oss down my-bucket photo.jpg local-name.jpg
```

### DNS

```bash
python alix.py dns list example.com                  # list records for a domain
python alix.py dns add example.com www A 1.2.3.4     # add a record
python alix.py dns delete 123456789                  # delete a record by ID
```

Record IDs are shown in the output of `dns list`.

## Help

Every command group has built-in help:

```bash
python alix.py -h
python alix.py ecs -h
python alix.py oss up -h
```

## Requirements

- Python 3.8 or later
- Dependencies are loaded lazily: you only need the packages for the services you actually use (`oss2` for OSS, `alibabacloud_ecs20140526` for ECS, `alibabacloud_alidns20150109` for DNS)

