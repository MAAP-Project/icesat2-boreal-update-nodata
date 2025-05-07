"""
Icesat2 Boreal nodata update script

This script processes Cloud Optimized GeoTIFF (COG) files from the Icesat2 Boreal dataset,
updating NaN values to a specified NODATA value. It uses distributed processing via Coiled
to handle large datasets efficiently.

The script:
1. Loads an inventory of COG files from a CSV in S3
2. For each COG, replaces NaN values with the specified NODATA value
3. Writes the processed COGs to the specified output S3 directory
4. Creates a summary file listing all processed COG paths

Usage:
    uv run main.py [--output-dir S3_PATH]

Arguments:
    --output-dir    S3 directory to store processed COGs

Example:
    uv run main.py --output-dir s3://my-bucket/processed-data/

Notes:
    - Requires AWS credentials with read/write access to relevant S3 buckets
    - Uses Coiled for distributed processing
    - The NODATA value is set to -9999.0 by default
"""

import argparse
import io
import os

import boto3
import coiled
import numpy as np
import rasterio

INVENTORY_CSV = (
    "s3://maap-ops-workspace/shared/henrydevseed/icesat2-boreal-v2.1-inventory.csv"
)
NODATA = -9999.0


def _parse_s3_path(s3_path: str) -> tuple[str, str]:
    """Parse an S3 path into bucket and key components"""
    if not s3_path.startswith("s3://"):
        raise ValueError(f"{s3_path} is not a valid s3 key")

    _, _, bucket, key = s3_path.split("/", 3)
    return bucket, key


def load_inventory_data() -> list[str]:
    """read the inventory file and create a list of keys"""
    bucket, key = _parse_s3_path(INVENTORY_CSV)
    s3_client = boto3.client("s3")
    response = s3_client.get_object(Bucket=bucket, Key=key)
    return response["Body"].read().decode("utf-8").splitlines()


def update_nodata(input_cog_key: str, output_nodata: float = -9999.0) -> bytes:
    with rasterio.open(input_cog_key) as src:
        profile = src.profile
        data = src.read()

        data[np.isnan(data)] = output_nodata
        profile.update(nodata=output_nodata)

        with rasterio.MemoryFile() as memfile_out:
            with memfile_out.open(**profile) as dst:
                dst.write(data)
                dst.update_tags(**src.tags())

            memfile_out.seek(0)
            return memfile_out.read()


@coiled.function(region="us-west-2", threads_per_worker=-1)
def process_cog(
    input_cog_key: str, output_dir: str, output_nodata: float = NODATA
) -> str:
    s3_client = boto3.client("s3")
    filename = os.path.basename(input_cog_key)
    dest_bucket, dest_dir = _parse_s3_path(output_dir)
    dest_key = f"{dest_dir.strip('/')}/{filename}"

    new_bytes = update_nodata(input_cog_key, output_nodata)

    s3_client.put_object(
        Bucket=dest_bucket, Key=dest_key, Body=new_bytes, ContentType="image/tiff"
    )

    return f"{output_dir}/{dest_key}"


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Process and update NODATA values in COGs."
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="s3://maap-ops-workspace/shared/henrydevseed/icesat2-boreal-nodata-test/",
        help="S3 directory to store processed COGs",
    )
    parser.add_argument(
        "--limit", type=int, default=10, help="Limit the number of COGs to process"
    )
    return parser.parse_args()


def write_inventory(updated_cog_keys: list[str], output_dir: str) -> None:
    buffer = io.BytesIO()
    for cog_key in updated_cog_keys:
        buffer.write(f"{cog_key}\n".encode("utf-8"))

    buffer.seek(0)

    bucket, key_prefix = _parse_s3_path(output_dir)
    updated_inventory_key = f"{key_prefix.strip('/')}/inventory.txt"
    s3_client = boto3.client("s3")

    s3_client.put_object(
        Bucket=bucket, Key=updated_inventory_key, Body=buffer.getvalue()
    )
    print(f"Output list written to s3://{bucket}/{updated_inventory_key}")


def main():
    args = parse_args()

    print(f"Copying the COGs to {args.output_dir} with updated nodata values")
    inventory = load_inventory_data()

    updated_cog_keys = process_cog.map(
        inventory[:10],
        output_dir=args.output_dir,
        output_nodata=NODATA,
    )
    write_inventory(list(updated_cog_keys), args.output_dir)


if __name__ == "__main__":
    main()
