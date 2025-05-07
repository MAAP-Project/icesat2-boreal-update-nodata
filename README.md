# Update ICESat-2 Boreal nodata values

This repository contains a script for upating the nodata values for the ICESat-2 Boreal v2.1 output COGs.

## Overview

The script performs the following operations:

- Loads an inventory of COG files from a CSV in S3
- For each COG, replaces NaN values with -9999.0
- Writes the processed COGs to the specified output S3 directory
- Creates a summary file listing all processed COG paths

## Requirements

- AWS credentials with read/write access to relevant S3 buckets
- [uv](https://github.com/astral-sh/uv)

## Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/MAAP-project/icesat2-boreal-update-nodata.git
cd icesat2-boreal-update-nodata
uv sync
```

## Usage

Run the script with:

```bash
export AWS_REGION=us-west-2
uv run main.py --output-dir S3_PATH
```

### Arguments

- `--output-dir`: S3 directory to store processed COGs (required)

### Example

```bash
uv run main.py --output-dir s3://my-bucket/processed-data/
```

## Implementation Details

The script uses [Coiled](https://www.coiled.io/) for distributed processing, enabling efficient handling of large datasets. Each COG file is processed independently, with NaN values replaced by the specified NODATA value. To use the coiled functionality you will need to have a coiled API key set up.
