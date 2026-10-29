"""Optional S3 archival for source snapshots, using the AWS SDK credential chain."""
import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def archive_json_snapshot(source_slug, payload):
    """Archive a source payload to S3 when S3_BUCKET_NAME is configured.

    Uses IAM role credentials on AWS where available. Local development can leave
    the bucket unset; archival is then a no-op. Errors are logged but do not break
    public monitoring pages.
    """
    bucket = os.getenv('S3_BUCKET_NAME', '').strip()
    if not bucket:
        return False
    try:
        import boto3
        region = os.getenv('AWS_REGION', 'ap-south-1')
        client = boto3.client('s3', region_name=region)
        now = datetime.now(timezone.utc)
        key = f"floodguard/source-snapshots/{source_slug}/{now:%Y/%m/%d/%H%M%S}.json"
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=json.dumps(payload, ensure_ascii=False, default=str).encode('utf-8'),
            ContentType='application/json',
            ServerSideEncryption='AES256',
        )
        logger.info('Archived %s source snapshot to s3://%s/%s', source_slug, bucket, key)
        return True
    except Exception as exc:
        logger.warning('S3 source snapshot archival failed for %s: %s', source_slug, exc)
        return False
