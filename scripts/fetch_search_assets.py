import os
import tarfile
from pathlib import Path
from tempfile import TemporaryDirectory

import boto3


def main():
    bucket = os.getenv("B2_BUCKET")
    if not bucket:
        return

    data_dir = Path(__file__).resolve().parent.parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    client = boto3.client(
        "s3",
        endpoint_url=os.environ["B2_ENDPOINT_URL"],
        region_name=os.environ["B2_REGION"],
        aws_access_key_id=os.environ["B2_KEY_ID"],
        aws_secret_access_key=os.environ["B2_APPLICATION_KEY"],
    )

    with TemporaryDirectory() as temp_dir:
        archive = Path(temp_dir) / "search-data.tar.gz"
        print("Downloading search assets from Backblaze B2...", flush=True)
        client.download_file(bucket, os.environ["B2_OBJECT_KEY"], str(archive))

        with tarfile.open(archive, "r:gz") as bundle:
            bundle.extractall(data_dir, filter="data")

    print("Search assets are ready.", flush=True)


if __name__ == "__main__":
    main()