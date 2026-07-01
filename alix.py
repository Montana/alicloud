#!/usr/bin/env python3
"""
alix - a friendly CLI for Alibaba Cloud
=======================================

One tool for the everyday stuff: ECS servers, OSS storage, and DNS.

Setup:
    pip install oss2 alibabacloud_ecs20140526 alibabacloud_alidns20150109
    python alix.py config          # interactive one-time setup

Examples:
    python alix.py ecs list                    # show all your servers
    python alix.py ecs start i-abc123          # start a server
    python alix.py ecs stop i-abc123           # stop a server (saves money!)
    python alix.py oss buckets                 # list your buckets
    python alix.py oss ls my-bucket            # list files in a bucket
    python alix.py oss up my-bucket photo.jpg  # upload a file
    python alix.py oss down my-bucket photo.jpg  # download a file
    python alix.py dns list example.com        # show DNS records
    python alix.py dns add example.com www A 1.2.3.4   # add a record
"""

import argparse
import json
import os
import sys
from pathlib import Path

CONFIG_PATH = Path.home() / ".alix" / "config.json"

# ---------------------------------------------------------------------------
# Config & credentials
# ---------------------------------------------------------------------------

def load_config():
    """Load credentials from env vars first, then ~/.alix/config.json."""
    cfg = {}
    if CONFIG_PATH.exists():
        try:
            cfg = json.loads(CONFIG_PATH.read_text())
        except json.JSONDecodeError:
            print(f"Warning: {CONFIG_PATH} is corrupted, run `alix config` again.")
    # Environment variables always win
    cfg["access_key_id"] = os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID", cfg.get("access_key_id"))
    cfg["access_key_secret"] = os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET", cfg.get("access_key_secret"))
    cfg["region"] = os.environ.get("ALIBABA_CLOUD_REGION", cfg.get("region", "us-west-1"))
    return cfg


def require_credentials(cfg):
    if not cfg.get("access_key_id") or not cfg.get("access_key_secret"):
        sys.exit(
            "Error: No credentials found.\n"
            "   Run `python alix.py config` for one-time setup,\n"
            "   or set ALIBABA_CLOUD_ACCESS_KEY_ID / ALIBABA_CLOUD_ACCESS_KEY_SECRET env vars."
        )


def cmd_config(_args):
    """Interactive credential setup."""
    print("alix one-time setup - credentials are stored in", CONFIG_PATH)
    print("(Create an AccessKey at: RAM console -> Users -> your user -> AccessKeys)\n")
    key_id = input("AccessKey ID: ").strip()
    key_secret = input("AccessKey Secret: ").strip()
    region = input("Default region [us-west-1]: ").strip() or "us-west-1"

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(
        {"access_key_id": key_id, "access_key_secret": key_secret, "region": region},
        indent=2,
    ))
    CONFIG_PATH.chmod(0o600)  # keep secrets private
    print("\nSaved. Try: python alix.py ecs list")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _missing_dep(pkg, pip_name):
    sys.exit(f"Error: Missing dependency '{pkg}'. Install it with:\n   pip install {pip_name}")


def _table(rows, headers):
    """Print a simple aligned table without external deps."""
    if not rows:
        print("(nothing found)")
        return
    widths = [max(len(str(h)), *(len(str(r[i])) for r in rows)) for i, h in enumerate(headers)]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    print(fmt.format(*headers))
    print(fmt.format(*("-" * w for w in widths)))
    for r in rows:
        print(fmt.format(*(str(c) for c in r)))


# ---------------------------------------------------------------------------
# ECS (servers)
# ---------------------------------------------------------------------------

def _ecs_client(cfg):
    try:
        from alibabacloud_ecs20140526.client import Client
        from alibabacloud_tea_openapi import models as open_models
    except ImportError:
        _missing_dep("alibabacloud_ecs20140526", "alibabacloud_ecs20140526")
    conf = open_models.Config(
        access_key_id=cfg["access_key_id"],
        access_key_secret=cfg["access_key_secret"],
        region_id=cfg["region"],
        endpoint=f"ecs.{cfg['region']}.aliyuncs.com",
    )
    return Client(conf)


def cmd_ecs_list(args):
    cfg = load_config()
    require_credentials(cfg)
    from alibabacloud_ecs20140526 import models as ecs_models
    client = _ecs_client(cfg)
    req = ecs_models.DescribeInstancesRequest(region_id=cfg["region"], page_size=100)
    resp = client.describe_instances(req)
    instances = resp.body.instances.instance or []
    rows = []
    for i in instances:
        ip = ""
        if i.public_ip_address and i.public_ip_address.ip_address:
            ip = i.public_ip_address.ip_address[0]
        elif i.eip_address and i.eip_address.ip_address:
            ip = i.eip_address.ip_address
        rows.append([i.instance_id, i.instance_name or "-", i.status, i.instance_type, ip or "-"])
    _table(rows, ["INSTANCE ID", "NAME", "STATUS", "TYPE", "PUBLIC IP"])


def _ecs_power(action, instance_id):
    cfg = load_config()
    require_credentials(cfg)
    from alibabacloud_ecs20140526 import models as ecs_models
    client = _ecs_client(cfg)
    if action == "start":
        client.start_instance(ecs_models.StartInstanceRequest(instance_id=instance_id))
        print(f"Starting {instance_id} ... (check status with `alix ecs list`)")
    elif action == "stop":
        client.stop_instance(ecs_models.StopInstanceRequest(instance_id=instance_id, stopped_mode="StopCharging"))
        print(f"Stopping {instance_id} (billing paused where supported)")
    elif action == "reboot":
        client.reboot_instance(ecs_models.RebootInstanceRequest(instance_id=instance_id))
        print(f"Rebooting {instance_id} ...")


def cmd_ecs_start(args): _ecs_power("start", args.instance_id)
def cmd_ecs_stop(args): _ecs_power("stop", args.instance_id)
def cmd_ecs_reboot(args): _ecs_power("reboot", args.instance_id)


# ---------------------------------------------------------------------------
# OSS (object storage)
# ---------------------------------------------------------------------------

def _oss_auth(cfg):
    try:
        import oss2
    except ImportError:
        _missing_dep("oss2", "oss2")
    return oss2, oss2.Auth(cfg["access_key_id"], cfg["access_key_secret"])


def _oss_bucket(cfg, bucket_name):
    oss2, auth = _oss_auth(cfg)
    endpoint = f"https://oss-{cfg['region']}.aliyuncs.com"
    return oss2, oss2.Bucket(auth, endpoint, bucket_name)


def cmd_oss_buckets(args):
    cfg = load_config()
    require_credentials(cfg)
    oss2, auth = _oss_auth(cfg)
    service = oss2.Service(auth, f"https://oss-{cfg['region']}.aliyuncs.com")
    rows = [[b.name, b.location, b.creation_date] for b in oss2.BucketIterator(service)]
    _table(rows, ["BUCKET", "LOCATION", "CREATED"])


def cmd_oss_ls(args):
    cfg = load_config()
    require_credentials(cfg)
    oss2, bucket = _oss_bucket(cfg, args.bucket)
    rows = []
    for obj in oss2.ObjectIterator(bucket, prefix=args.prefix or "", max_keys=200):
        size_mb = obj.size / (1024 * 1024)
        size = f"{size_mb:.1f} MB" if size_mb >= 0.1 else f"{obj.size} B"
        rows.append([obj.key, size])
    _table(rows, ["KEY", "SIZE"])


def cmd_oss_up(args):
    cfg = load_config()
    require_credentials(cfg)
    _, bucket = _oss_bucket(cfg, args.bucket)
    local = Path(args.file)
    if not local.exists():
        sys.exit(f"Error: File not found: {local}")
    key = args.key or local.name
    bucket.put_object_from_file(key, str(local))
    print(f"Uploaded {local} -> oss://{args.bucket}/{key}")


def cmd_oss_down(args):
    cfg = load_config()
    require_credentials(cfg)
    _, bucket = _oss_bucket(cfg, args.bucket)
    dest = args.dest or Path(args.key).name
    bucket.get_object_to_file(args.key, dest)
    print(f"Downloaded oss://{args.bucket}/{args.key} -> {dest}")


# ---------------------------------------------------------------------------
# DNS
# ---------------------------------------------------------------------------

def _dns_client(cfg):
    try:
        from alibabacloud_alidns20150109.client import Client
        from alibabacloud_tea_openapi import models as open_models
    except ImportError:
        _missing_dep("alibabacloud_alidns20150109", "alibabacloud_alidns20150109")
    conf = open_models.Config(
        access_key_id=cfg["access_key_id"],
        access_key_secret=cfg["access_key_secret"],
        endpoint="alidns.aliyuncs.com",
    )
    return Client(conf)


def cmd_dns_list(args):
    cfg = load_config()
    require_credentials(cfg)
    from alibabacloud_alidns20150109 import models as dns_models
    client = _dns_client(cfg)
    req = dns_models.DescribeDomainRecordsRequest(domain_name=args.domain, page_size=100)
    resp = client.describe_domain_records(req)
    records = resp.body.domain_records.record or []
    rows = [[r.record_id, r.rr, r.type, r.value, r.ttl] for r in records]
    _table(rows, ["RECORD ID", "HOST", "TYPE", "VALUE", "TTL"])


def cmd_dns_add(args):
    cfg = load_config()
    require_credentials(cfg)
    from alibabacloud_alidns20150109 import models as dns_models
    client = _dns_client(cfg)
    req = dns_models.AddDomainRecordRequest(
        domain_name=args.domain, rr=args.host, type=args.type.upper(), value=args.value
    )
    resp = client.add_domain_record(req)
    print(f"Added {args.host}.{args.domain} {args.type.upper()} -> {args.value} (record ID: {resp.body.record_id})")


def cmd_dns_delete(args):
    cfg = load_config()
    require_credentials(cfg)
    from alibabacloud_alidns20150109 import models as dns_models
    client = _dns_client(cfg)
    client.delete_domain_record(dns_models.DeleteDomainRecordRequest(record_id=args.record_id))
    print(f"Deleted record {args.record_id}")


# ---------------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog="alix",
        description="A friendly CLI for Alibaba Cloud (ECS servers, OSS storage, DNS).",
        epilog="Run `alix <group> -h` for details, e.g. `alix ecs -h`.",
    )
    sub = parser.add_subparsers(dest="group")

    # config
    p = sub.add_parser("config", help="one-time credential setup")
    p.set_defaults(func=cmd_config)

    # ecs
    ecs = sub.add_parser("ecs", help="manage servers").add_subparsers(dest="action")
    p = ecs.add_parser("list", help="list all instances")
    p.set_defaults(func=cmd_ecs_list)
    for name, fn, help_text in [
        ("start", cmd_ecs_start, "start an instance"),
        ("stop", cmd_ecs_stop, "stop an instance (pauses billing where supported)"),
        ("reboot", cmd_ecs_reboot, "reboot an instance"),
    ]:
        p = ecs.add_parser(name, help=help_text)
        p.add_argument("instance_id", help="e.g. i-abc123")
        p.set_defaults(func=fn)

    # oss
    oss = sub.add_parser("oss", help="manage file storage").add_subparsers(dest="action")
    p = oss.add_parser("buckets", help="list buckets")
    p.set_defaults(func=cmd_oss_buckets)
    p = oss.add_parser("ls", help="list files in a bucket")
    p.add_argument("bucket")
    p.add_argument("prefix", nargs="?", help="optional path prefix")
    p.set_defaults(func=cmd_oss_ls)
    p = oss.add_parser("up", help="upload a file")
    p.add_argument("bucket")
    p.add_argument("file")
    p.add_argument("key", nargs="?", help="remote name (defaults to filename)")
    p.set_defaults(func=cmd_oss_up)
    p = oss.add_parser("down", help="download a file")
    p.add_argument("bucket")
    p.add_argument("key")
    p.add_argument("dest", nargs="?", help="local path (defaults to filename)")
    p.set_defaults(func=cmd_oss_down)

    # dns
    dns = sub.add_parser("dns", help="manage DNS records").add_subparsers(dest="action")
    p = dns.add_parser("list", help="list records for a domain")
    p.add_argument("domain")
    p.set_defaults(func=cmd_dns_list)
    p = dns.add_parser("add", help="add a record")
    p.add_argument("domain")
    p.add_argument("host", help="e.g. www or @")
    p.add_argument("type", help="A, CNAME, TXT, MX, ...")
    p.add_argument("value")
    p.set_defaults(func=cmd_dns_add)
    p = dns.add_parser("delete", help="delete a record by ID (get IDs from `dns list`)")
    p.add_argument("record_id")
    p.set_defaults(func=cmd_dns_delete)

    args = parser.parse_args()
    if not getattr(args, "func", None):
        parser.print_help()
        sys.exit(0)
    try:
        args.func(args)
    except Exception as e:  # surface API errors in a friendly way
        msg = str(e)
        if "InvalidAccessKeyId" in msg or "SignatureDoesNotMatch" in msg:
            sys.exit("Error: Credentials rejected. Re-run `python alix.py config` with a valid AccessKey.")
        sys.exit(f"Error: {msg}")


if __name__ == "__main__":
    main()
